"""Build directional route profiles and query their complete product composition."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3

from src.analytics.observed import ELIGIBLE_ROWS, VALID_COUNTRY_ROWS, prepare_observed, route_counts, validate_enrichment
from src.pipeline import as_dicts, write_json


def inspect_grain(db):
    row = db.execute(f"""
        WITH keys AS (
            SELECT COUNT(*) AS n FROM enriched_trade_data WHERE {ELIGIBLE_ROWS}
            GROUP BY year, exporter_code, importer_code, product_code
        )
        SELECT COALESCE(SUM(n), 0), COUNT(*), COUNT(*) FILTER (WHERE n > 1),
               COALESCE(SUM(n) FILTER (WHERE n > 1), 0) FROM keys
    """).fetchone()
    return dict(zip(("eligible_records", "unique_composite_keys", "duplicated_composite_keys",
                     "records_on_duplicated_keys"), row, strict=True))


def require_unique_grain(db, grain):
    if grain["duplicated_composite_keys"]:
        samples = as_dicts(db, f"""
            SELECT year, exporter_code, importer_code, product_code, COUNT(*) AS records
            FROM enriched_trade_data WHERE {ELIGIBLE_ROWS}
            GROUP BY year, exporter_code, importer_code, product_code
            HAVING COUNT(*) > 1 ORDER BY year, exporter_code, importer_code, product_code LIMIT 5
        """)
        raise ValueError(f"Duplicate eligible composite keys: {grain}. Sample keys: {samples}")


def route_id(year, exporter, importer):
    return f"{year}:{exporter}:{importer}"


def percentage(numerator, denominator):
    return round(100 * numerator / denominator, 6) if denominator else None


def product_composition(db, year, exporter, importer):
    """Return full code-ordered detail for a published directional route."""
    rows = [dict(row) for row in db.execute(f"""
        SELECT t.product_code, p.description, p.code IS NOT NULL AS reference_mapped,
               COUNT(*) FILTER (WHERE t.product_matched) AS record_count
        FROM enriched_trade_data AS t LEFT JOIN product AS p ON p.code = t.product_code
        WHERE {VALID_COUNTRY_ROWS} AND t.product_code IS NOT NULL
          AND t.year = ? AND t.exporter_code = ? AND t.importer_code = ?
        GROUP BY t.product_code ORDER BY t.product_code
    """, (year, exporter, importer))]
    if not any(row["record_count"] for row in rows):
        raise ValueError(f"No eligible observed route {route_id(year, exporter, importer)}")
    for row in rows:
        row["reference_mapped"] = bool(row["reference_mapped"])
        row["description"] = row["description"] if (row["description"] or "").strip() else None
        if row["record_count"] != int(row["reference_mapped"]):
            raise ValueError(f"Product reference or eligible grain mismatch for {row['product_code']}")
    return rows


def build(db, summary):
    validate_enrichment(db, summary)
    grain = inspect_grain(db)
    require_unique_grain(db, grain)
    metadata = prepare_observed(db, summary)
    if len(metadata["years"]) != 1:
        raise ValueError("Route Intelligence requires exactly one eligible year")
    year = metadata["years"][0]["year"]
    routes = route_counts(db)
    pairs = {(row["exporter_code"], row["importer_code"]): row for row in routes}
    included = metadata["included_unique_rows"]
    if (len(pairs) != len(routes) or included != grain["eligible_records"]
            or sum(row["record_count"] for row in routes) != included):
        raise ValueError("Directional route counts do not reconcile with eligible rows")
    labels = {row["code"]: dict(row) for row in db.execute("SELECT code,name,iso2,iso3 FROM country")}
    for label in labels.values():
        if not (label["name"] or "").strip():
            label["name"] = None
    directions = {}
    for role, table in (("exporter", "export_products"), ("importer", "import_products")):
        directions[role] = {row[0]: (row[1], row[2]) for row in db.execute(f"""
            SELECT {role}_code, SUM(records), COUNT(*) FROM {table} GROUP BY {role}_code
        """)}
    unmapped = {(row[0], row[1]): row[2] for row in db.execute(f"""
        SELECT exporter_code, importer_code, COUNT(DISTINCT product_code)
        FROM enriched_trade_data WHERE {VALID_COUNTRY_ROWS} AND NOT product_matched AND year = ?
        GROUP BY exporter_code, importer_code
    """, (year,))}
    observed_products = db.execute("SELECT COUNT(DISTINCT product_code) FROM observed").fetchone()[0]
    coverage = {
        "complete_global_coverage": False,
        "source_limitation": metadata["limitation"],
        "observed_exporters": len(directions["exporter"]),
        "observed_importers": len(directions["importer"]),
        "imputed_quantity_used": False,
        "measure": "Observed eligible record keys, with no monetary or shipment interpretation.",
    }
    profiles = []
    for (exporter, importer), row in pairs.items():
        mapped = row["distinct_products"]
        records = row["record_count"]
        if mapped != records:
            raise ValueError("Single-year route product diversity must match the eligible record count")
        missing = unmapped.get((exporter, importer), 0)
        exports, export_diversity = directions["exporter"][exporter]
        imports, import_diversity = directions["importer"][importer]
        reverse = exporter != importer and (importer, exporter) in pairs
        profiles.append({
            "route_id": route_id(year, exporter, importer), "year": year,
            "exporter": {**labels[exporter], "reference_mapped": True},
            "importer": {**labels[importer], "reference_mapped": True},
            "record_count": records, "distinct_products": mapped,
            "product_reference_coverage": {
                "observed_normalized_products": mapped + missing,
                "mapped_products": mapped, "unmapped_products": missing,
                "mapped_percent": percentage(mapped, mapped + missing),
            },
            "product_composition": {
                "query_route_id": route_id(year, exporter, importer),
                "ordering": "product_code_ascending",
                "eligible_products_tied": mapped > 1,
            },
            "relative_coverage": {
                "percent_of_dataset_records": percentage(records, included),
                "percent_of_exporter_records": percentage(records, exports),
                "percent_of_importer_records": percentage(records, imports),
                "percent_of_exporter_products": percentage(mapped, export_diversity),
                "percent_of_importer_products": percentage(mapped, import_diversity),
            },
            "self_trade": exporter == importer, "reverse_observed": reverse,
            "reverse_route_id": route_id(year, importer, exporter) if reverse else None,
            "coverage": coverage,
        })
    # The route release describes composition, without a ranking limit.
    del metadata["top_n"], metadata["ranking_basis"]
    return {"metadata": {
        **metadata, "year": year, "route_count": len(profiles), "coverage": coverage,
        "observed_eligible_products": observed_products, "country_reference_entries": len(labels),
        "record_grain": grain, "record_grain_unique": True,
        "directed_routes_with_reverse": sum(row["reverse_observed"] for row in profiles),
        "reciprocal_pairs": sum(row["reverse_observed"] for row in profiles) // 2,
        "self_trade_routes": sum(row["self_trade"] for row in profiles),
        "pairs_with_only_unmapped_codes": len(unmapped.keys() - pairs.keys()),
        "composition_command": "python -m src.analytics.route_intelligence --route-id <route_id>",
    }, "records": profiles}


def open_database(database):
    db = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def run(database, output, summary_path):
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    with closing(open_database(database)) as db:
        result = build(db, summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/processed/trade.sqlite"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/analytics/route_intelligence.json"))
    parser.add_argument("--summary", type=Path, default=Path("reports/enrichment_summary.json"))
    parser.add_argument("--route-id", help="Print full product composition as JSON for YEAR:EXPORTER:IMPORTER")
    args = parser.parse_args()
    try:
        if args.route_id is None:
            result = run(args.database, args.output, args.summary)
            print(f"Published {result['metadata']['route_count']} directional route profiles")
        else:
            if not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*:[1-9][0-9]*", args.route_id):
                raise ValueError("Expected YEAR:EXPORTER:IMPORTER")
            with closing(open_database(args.database)) as db:
                rows = product_composition(db, *(int(part) for part in args.route_id.split(":")))
            print(json.dumps({"route_id": args.route_id, "records": rows}, ensure_ascii=True))
    except ValueError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
