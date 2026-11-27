"""Publish observed trade activity and explainable market-pair signals."""
import argparse
from itertools import groupby
import json
import logging
from pathlib import Path
import sqlite3

from src.analytics.country_intelligence import country_profiles
from src.analytics.observed import TOP_N, prepare_observed, route_counts, validate_enrichment
from src.analytics.product_intelligence import product_activity
from src.pipeline import as_dicts, write_json

LOG = logging.getLogger(__name__)


def aggregate(db, summary):
    metadata = prepare_observed(db, summary)
    included = metadata["included_unique_rows"]
    routes = route_counts(db)
    country_results = [
        {key: ([
            {k: value for k, value in entry.items() if k not in ("name", "description")}
            for entry in item
        ] if key.startswith("top_") else item)
         for key, item in row.items() if not key.startswith("distinct_")}
        for row in country_profiles(db, routes) if row["export_record_count"] or row["import_record_count"]
    ]
    product_results = [
        {key: value for key, value in row.items() if key != "distinct_routes"}
        for row in product_activity(db)
    ]
    # Each observed route-product combination has equal activity in a single-year snapshot.
    route_products = db.execute("""
        SELECT exporter_code, importer_code, product_code FROM observed
        ORDER BY exporter_code, importer_code, product_code
    """)
    by_pair = groupby(route_products, lambda row: (row[0], row[1]))
    for route, (pair, products) in zip(routes, by_pair, strict=True):
        if (route["exporter_code"], route["importer_code"]) != pair:
            raise ValueError("Route-to-product keys do not reconcile")
        route["top_products"] = [row[2] for _, row in zip(range(TOP_N), products)]
    for results, key in ((routes, "record_count"), (product_results, "record_count"),
                         (country_results, "export_record_count"),
                         (country_results, "import_record_count")):
        if sum(row[key] for row in results) != included:
            raise ValueError(f"Analytics counts do not reconcile for {key}")
    return metadata, country_results, product_results, routes


def opportunities(db):
    # Rank observed exporter/importer product connections by the breadth
    # of each side's observed partner network. This does not infer absent routes.
    return as_dicts(db, """
        SELECT o.exporter_code, o.importer_code, o.product_code,
               e.records AS exporter_destinations, i.records AS importer_sources,
               e.records + i.records AS score
        FROM observed AS o JOIN export_products AS e USING (exporter_code, product_code)
        JOIN import_products AS i USING (importer_code, product_code)
        ORDER BY score DESC, o.product_code, o.exporter_code, o.importer_code
        LIMIT 100
    """)


def run(database, output, summary_path):
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    db = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        validate_enrichment(db, summary)
        metadata, countries, products, routes = aggregate(db, summary)
        signals = opportunities(db)
    finally:
        db.close()
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("country_analytics", countries), ("product_analytics", products),
                       ("trade_routes", routes), ("market_opportunities", signals)):
        details = metadata
        if name == "market_opportunities":
            details = {**metadata, "score_definition": "Observed exporter destinations plus observed importer sources for the product",
                       "interpretation": "Observed market connections for review. No evidence of unmet demand, growth or future demand.",
                       "limit": 100}
        write_json(output / f"{name}.json", {"metadata": details, "records": rows})
    LOG.info("Published analytics for %s included rows", metadata["included_unique_rows"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/processed/trade.sqlite"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/analytics"))
    parser.add_argument("--summary", type=Path, default=Path("reports/enrichment_summary.json"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(args.database, args.output, args.summary)


if __name__ == "__main__":
    main()
