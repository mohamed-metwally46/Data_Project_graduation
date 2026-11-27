"""Build country and trade-area profiles from observed trade records."""
import argparse
import json
from pathlib import Path
import sqlite3

from src.analytics.observed import TOP_N, prepare_observed, rankings, route_counts, validate_enrichment
from src.pipeline import as_dicts, count, write_json


def country_profiles(db, routes, top_n=TOP_N):
    """Return one profile per reference key using the shared observed tables."""
    profiles = as_dicts(db, """
        WITH exports AS (
            SELECT exporter_code AS code, COUNT(*) AS records,
                   COUNT(DISTINCT importer_code) AS partners,
                   COUNT(DISTINCT product_code) AS products
            FROM observed GROUP BY exporter_code
        ), imports AS (
            SELECT importer_code AS code, COUNT(*) AS records,
                   COUNT(DISTINCT exporter_code) AS partners,
                   COUNT(DISTINCT product_code) AS products
            FROM observed GROUP BY importer_code
        )
        SELECT c.code, c.name, c.iso2, c.iso3,
               COALESCE(e.records, 0) AS export_record_count,
               COALESCE(i.records, 0) AS import_record_count,
               COALESCE(e.partners, 0) AS export_destinations,
               COALESCE(i.partners, 0) AS import_sources,
               COALESCE(e.products, 0) AS distinct_exported_products,
               COALESCE(i.products, 0) AS distinct_imported_products
        FROM country AS c LEFT JOIN exports AS e ON c.code = e.code
        LEFT JOIN imports AS i ON c.code = i.code
        ORDER BY c.code
    """)
    names = {row["code"]: row["name"] for row in profiles}
    descriptions = dict(db.execute("SELECT code, description FROM product"))
    for direction, role, partner, partner_field in (
        ("export", "exporter_code", "importer_code", "top_export_destinations"),
        ("import", "importer_code", "exporter_code", "top_import_sources"),
    ):
        top_products = rankings(db, f"{direction}_products", role, "product_code", top_n)
        partners = {}
        for route in routes:
            partners.setdefault(route[role], []).append(route)
        for row in profiles:
            code = row["code"]
            row[f"top_{direction}_products"] = [
                {**item, "description": descriptions[item["product_code"]]}
                for item in top_products.get(code, [])
            ]
            ranked = sorted(partners.get(code, []),
                            key=lambda route: (-route["record_count"], route[partner]))
            row[partner_field] = [
                {"country_code": route[partner], "name": names[route[partner]],
                 "record_count": route["record_count"]}
                for route in ranked[:top_n]
            ]
    return profiles


def build(db, summary, top_n=TOP_N):
    if top_n < 1:
        raise ValueError("top_n must be positive")
    validate_enrichment(db, summary)
    metadata = prepare_observed(db, summary, top_n)
    if not metadata["years"]:
        raise ValueError("Country Intelligence requires at least one eligible record to identify the year")
    year = metadata["years"][0]["year"]
    profiles = country_profiles(db, route_counts(db), top_n)
    included = metadata["included_unique_rows"]
    if (len({row["code"] for row in profiles}) != len(profiles)
            or len(profiles) != count(db, "SELECT COUNT(*) FROM country")
            or any(sum(row[field] for row in profiles) != included
                   for field in ("export_record_count", "import_record_count"))):
        raise ValueError("Country profiles do not reconcile with the reference and observed records")
    coverage = {
        "complete_global_coverage": False,
        "source_limitation": metadata["limitation"],
        "observed_exporters": sum(row["export_record_count"] > 0 for row in profiles),
        "observed_importers": sum(row["import_record_count"] > 0 for row in profiles),
        "zero_count_meaning": "No eligible records observed for this direction in the supplied export.",
        "record_count_meaning": "Unique observed trade keys, not monetary value or physical volume.",
        "imputed_quantity_used": False,
        "interpretation": "Single-year observations cannot establish market growth, unmet demand, or future demand.",
    }
    return {
        "metadata": {**metadata, "year": year, "profile_count": len(profiles), "coverage": coverage},
        "records": [{**row, "year": year, "coverage": coverage} for row in profiles],
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
    parser.add_argument("--output", type=Path, default=Path("data/processed/analytics/country_intelligence.json"))
    parser.add_argument("--summary", type=Path, default=Path("reports/enrichment_summary.json"))
    parser.add_argument("--top-n", type=int, default=TOP_N)
    args = parser.parse_args()
    result = run(args.database, args.output, args.summary, args.top_n)
    print(f"Published {result['metadata']['profile_count']} country and trade-area profiles")


if __name__ == "__main__":
    main()
