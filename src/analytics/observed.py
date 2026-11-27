"""Shared observed-record definitions and ranking queries."""
from itertools import groupby

from src.pipeline import as_dicts, count


TOP_N = 10
VALID_COUNTRY_ROWS = "invalid_fields IS NULL AND exporter_matched AND importer_matched"
ELIGIBLE_ROWS = f"{VALID_COUNTRY_ROWS} AND product_matched"


def rankings(db, table, parent, child, top_n=TOP_N):
    query = f"""
        SELECT * FROM (
            SELECT {parent}, {child}, records,
                   ROW_NUMBER() OVER (PARTITION BY {parent}
                                     ORDER BY records DESC, {child}) AS rank
            FROM {table}
        ) WHERE rank <= ? ORDER BY {parent}, rank
    """
    rows = db.execute(query, (top_n,))
    return {key: [{child: row[child], "record_count": row["records"]}
                  for row in group] for key, group in groupby(rows, lambda row: row[parent])}


def prepare_observed(db, summary, top_n=TOP_N):
    db.executescript(f"""
        CREATE TEMP TABLE observed AS
        SELECT year, exporter_code, importer_code, product_code
        FROM enriched_trade_data
        WHERE {ELIGIBLE_ROWS}
        GROUP BY year, exporter_code, importer_code, product_code;
        CREATE TEMP TABLE export_products AS
        SELECT exporter_code, product_code, COUNT(*) AS records
        FROM observed GROUP BY exporter_code, product_code;
        CREATE TEMP TABLE import_products AS
        SELECT importer_code, product_code, COUNT(*) AS records
        FROM observed GROUP BY importer_code, product_code;
    """)
    years = as_dicts(db, "SELECT year, COUNT(*) AS record_count FROM observed GROUP BY year ORDER BY year")
    included = sum(year["record_count"] for year in years)
    if len(years) > 1:
        raise ValueError("Trade analytics require a single-year input; filter by year before running")
    metadata = {
        **summary["metadata"],
        "years": years,
        "input_rows": summary["rows"]["enriched"],
        "included_unique_rows": included,
        "excluded_rows": summary["rows"]["enriched"] - included,
        "ranking_basis": "Count of unique observed year/exporter/importer/product records",
        "top_n": top_n,
        "quantity_basis": "No quantity aggregations while measurement units are unverified",
        "value_basis": "No monetary aggregations while currency and scale are unverified",
    }
    return metadata


def route_counts(db):
    return as_dicts(db, """
        SELECT exporter_code, importer_code, COUNT(*) AS record_count,
               COUNT(DISTINCT product_code) AS distinct_products
        FROM observed GROUP BY exporter_code, importer_code
        ORDER BY exporter_code, importer_code
    """)


def validate_enrichment(db, summary):
    actual = count(db, "SELECT COUNT(*) FROM enriched_trade_data")
    if actual != summary["rows"]["enriched"] or any(
        check["before"] != actual or check["after"] != actual or not check["reference_keys_unique"]
        for check in summary["join_validation"].values()
    ):
        raise ValueError("Enrichment validation failed")
