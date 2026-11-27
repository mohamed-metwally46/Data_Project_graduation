"""Build product profiles using the same eligible trade keys as Country Intelligence."""
import argparse
from itertools import groupby
import json
from pathlib import Path
import sqlite3

from src.analytics.observed import TOP_N, prepare_observed, rankings, validate_enrichment
from src.pipeline import as_dicts, write_json


def product_activity(db, top_n=TOP_N):
    """Return eligible per-product counts and ranked keys for both exports."""
    products = as_dicts(db, """
        SELECT o.product_code, p.description, COUNT(*) AS record_count,
               COUNT(DISTINCT o.exporter_code) AS exporters,
               COUNT(DISTINCT o.importer_code) AS importers
        FROM observed AS o JOIN product AS p ON o.product_code = p.code
        GROUP BY o.product_code ORDER BY o.product_code
    """)
    for direction, dimension in (("export", "exporter"), ("import", "importer")):
        table = f"{direction}_products"
        totals = {row[0]: (row[1], row[2]) for row in db.execute(f"""
            SELECT product_code, SUM(records), COUNT(*) FROM {table} GROUP BY product_code
        """)}
        ranked = rankings(db, table, "product_code", f"{dimension}_code", top_n)
        if totals.keys() != {row["product_code"] for row in products}:
            raise ValueError(f"{dimension} product keys do not reconcile")
        for row in products:
            code = row["product_code"]
            if totals[code] != (row["record_count"], row[f"{dimension}s"]):
                raise ValueError(f"{dimension} counts do not reconcile for {code}")
            row[f"top_{dimension}s"] = ranked[code]
    routes = db.execute("""
        SELECT product_code, exporter_code, importer_code, COUNT(*) AS record_count
        FROM observed GROUP BY product_code, exporter_code, importer_code
        ORDER BY product_code, record_count DESC, exporter_code, importer_code
    """)
    for product, (code, pairs) in zip(
        products, groupby(routes, lambda row: row["product_code"]), strict=True
    ):
        total, distinct, top = 0, 0, []
        for pair in pairs:
            total += pair["record_count"]
            distinct += 1
            if distinct <= top_n:
                top.append({key: pair[key] for key in ("exporter_code", "importer_code", "record_count")})
        if product["product_code"] != code or total != product["record_count"]:
            raise ValueError(f"Route counts do not reconcile for {code}")
        product["distinct_routes"] = distinct
        product["top_routes"] = top
    return products


def reference_observations(db):
    return as_dicts(db, """
        WITH observed_codes AS (
            SELECT product_code, COUNT(*) AS input_row_count
            FROM enriched_trade_data WHERE product_code IS NOT NULL GROUP BY product_code
        )
        SELECT o.product_code, o.input_row_count, p.code IS NOT NULL AS reference_mapped,
               NULLIF(TRIM(p.description), '') IS NOT NULL AS has_description,
               p.description
        FROM observed_codes AS o LEFT JOIN product AS p ON p.code = o.product_code
        ORDER BY o.product_code
    """)


def labeled_rankings(activity, names):
    result = {}
    for field, dimensions in (
        ("top_exporters", ("exporter",)), ("top_importers", ("importer",)),
        ("top_routes", ("exporter", "importer")),
    ):
        result[field] = [
            {
                **item,
                **{f"{role}_name": names.get(item[f"{role}_code"]) for role in dimensions},
                "percent_of_product_records": round(
                    100 * item["record_count"] / activity["record_count"], 6
                ),
            }
            for item in activity[field]
        ]
    return result


def build(db, summary, top_n=TOP_N):
    if top_n < 1:
        raise ValueError("top_n must be positive")
    validate_enrichment(db, summary)
    metadata = prepare_observed(db, summary, top_n)
    years = db.execute("SELECT DISTINCT year FROM enriched_trade_data WHERE year IS NOT NULL").fetchall()
    if len(years) != 1:
        raise ValueError("Product Intelligence requires exactly one processed trade year")
    year = years[0][0]
    activity = {row["product_code"]: row for row in product_activity(db, top_n)}
    reference = reference_observations(db)
    invalid_codes = as_dicts(db, """
        SELECT product_code_original, COUNT(*) AS input_row_count
        FROM enriched_trade_data WHERE product_code IS NULL
        GROUP BY product_code_original ORDER BY product_code_original
    """)
    if (sum(row["input_row_count"] for row in reference + invalid_codes) != metadata["input_rows"]
            or not activity.keys() <= {row["product_code"] for row in reference}):
        raise ValueError("Product observations do not reconcile with processed input")
    exporters, importers = db.execute("""
        SELECT COUNT(DISTINCT exporter_code), COUNT(DISTINCT importer_code) FROM observed
    """).fetchone()
    coverage = {
        "complete_global_coverage": False,
        "source_limitation": metadata["limitation"],
        "observed_exporters": exporters,
        "observed_importers": importers,
        "record_count_meaning": "Unique eligible trade keys in the supplied export.",
        "zero_count_meaning": "No eligible observations in the supplied export.",
        "percent_denominator": "All eligible records for this product before Top-N truncation.",
        "imputed_quantity_used": False,
    }
    names = dict(db.execute("SELECT code, name FROM country"))
    empty = {"record_count": 0, "exporters": 0, "importers": 0, "distinct_routes": 0,
             "top_exporters": [], "top_importers": [], "top_routes": []}
    profiles = []
    for row in reference:
        code = row["product_code"]
        item = activity.get(code, empty)
        profiles.append({
            "product_code": code,
            "description": row["description"] if row["has_description"] else None,
            "reference_mapped": bool(row["reference_mapped"]),
            "year": year,
            "input_row_count": row["input_row_count"],
            **{field: item[field] for field in ("record_count", "exporters", "importers", "distinct_routes")},
            **labeled_rankings(item, names),
            "coverage": coverage,
        })
    if (len({row["product_code"] for row in profiles}) != len(profiles)
            or sum(row["record_count"] for row in profiles) != metadata["included_unique_rows"]):
        raise ValueError("Product profiles do not reconcile with eligible observations")
    mapped = sum(row["reference_mapped"] for row in profiles)
    unobserved = [row[0] for row in db.execute("""
        SELECT code FROM product EXCEPT
        SELECT product_code FROM enriched_trade_data WHERE product_code IS NOT NULL
        ORDER BY code
    """)]
    return {
        "metadata": {**metadata, "year": year, "profile_count": len(profiles), "coverage": coverage},
        "reference_coverage": {
            "observed_products": len(profiles), "mapped_products": mapped,
            "unmapped_products": len(profiles) - mapped,
            "products_missing_description": sum(row["description"] is None for row in profiles),
            "unobserved_reference_products": len(unobserved),
            "unobserved_reference_codes": unobserved,
            "unmapped_product_rows": sum(row["input_row_count"] for row in profiles if not row["reference_mapped"]),
            "unnormalizable_codes": invalid_codes,
        },
        "records": profiles,
    }


def run(database, output, summary_path, top_n=TOP_N):
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    db = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        result = build(db, summary, top_n)
    finally:
        db.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/processed/trade.sqlite"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/analytics/product_intelligence.json"))
    parser.add_argument("--summary", type=Path, default=Path("reports/enrichment_summary.json"))
    parser.add_argument("--top-n", type=int, default=TOP_N)
    args = parser.parse_args()
    result = run(args.database, args.output, args.summary, args.top_n)
    print(f"Published {result['metadata']['profile_count']} product profiles")


if __name__ == "__main__":
    main()
