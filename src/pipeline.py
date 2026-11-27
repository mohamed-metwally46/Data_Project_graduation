"""Build the clean and enriched trade datasets and validation reports."""
import argparse
import json
import logging
from pathlib import Path
import sqlite3
import tempfile

from src.enrichment.references import country_records, product_records, require_unique
from src.preprocessing.trade import TRADE_FIELDS, parse_trade, read_records

LOG = logging.getLogger(__name__)
COVERAGE = {
    "complete_global_coverage": False,
    "source": "Available Excel-to-CSV export",
    "limitation": "The supplied export reaches Excel's worksheet limit including the header.",
    "trade_value_unit": None,
    "quantity_unit": None,
    "hs_revision": None,
}

SCHEMA = """
CREATE TABLE product (code TEXT PRIMARY KEY, description TEXT NOT NULL);
CREATE TABLE country (
    code INTEGER PRIMARY KEY, name TEXT NOT NULL, iso2_original TEXT,
    iso2 TEXT, iso3 TEXT, iso2_source TEXT
);
CREATE TABLE trade (
    row_id INTEGER PRIMARY KEY, year INTEGER, exporter_code INTEGER,
    importer_code INTEGER, product_code_original TEXT NOT NULL,
    product_code TEXT, trade_value_original TEXT NOT NULL, trade_value REAL,
    quantity_original TEXT, quantity_observed REAL, invalid_fields TEXT
);
"""

JOINS = (
    ("exporter", "country", "e", "t.exporter_code"),
    ("importer", "country", "i", "t.importer_code"),
    ("product", "product", "p", "t.product_code"),
)


def write_json(path, value):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def count(db, query, parameters=()):
    return db.execute(query, parameters).fetchone()[0]


def as_dicts(db, query):
    return [dict(row) for row in db.execute(query)]


def build_clean(db):
    # Index the temporary observations by product for the grouped imputation.
    db.executescript("""
        CREATE INDEX trade_product ON trade(product_code);
        CREATE TABLE invalid_trade_records AS
            SELECT * FROM trade WHERE invalid_fields IS NOT NULL;
        CREATE TEMP TABLE product_quantity_mean (
            code TEXT PRIMARY KEY, mean_quantity REAL
        );
        INSERT INTO product_quantity_mean
            SELECT t.product_code, AVG(t.quantity_observed)
            FROM trade AS t JOIN product AS p ON p.code = t.product_code
            WHERE t.invalid_fields IS NULL AND t.quantity_observed IS NOT NULL
            GROUP BY t.product_code;
        CREATE TABLE trade_data_clean AS
            SELECT t.*,
                CASE WHEN t.quantity_original IS NULL
                     THEN m.mean_quantity ELSE t.quantity_observed END AS quantity_processed,
                (t.quantity_original IS NULL AND m.mean_quantity IS NOT NULL)
                    AS quantity_was_imputed
            FROM trade AS t
            LEFT JOIN product_quantity_mean AS m
                ON m.code = t.product_code AND t.invalid_fields IS NULL;
    """)


def build_enriched(db, expected, reports):
    base = "FROM trade_data_clean AS t"
    joins = ""
    unmatched = {}
    validation = {}
    for label, table, alias, key in JOINS:
        unique = count(db, f"SELECT COUNT(*) - COUNT(DISTINCT code) FROM {table}") == 0
        if not unique:
            raise ValueError(f"{table} keys must be non-null and unique")
        joins += f" LEFT JOIN {table} AS {alias} ON {key} = {alias}.code"
        after = count(db, f"SELECT COUNT(*) {base} {joins}")
        if after != expected:
            raise ValueError(f"{label} join changed row count from {expected} to {after}")
        validation[label] = {"reference_keys_unique": unique, "before": expected, "after": after}
        original = "t.product_code_original" if label == "product" else key
        unmatched[label] = as_dicts(db, f"""
            SELECT {original} AS original_code, {key} AS lookup_code, COUNT(*) AS rows
            {base} {joins} WHERE {alias}.code IS NULL
            GROUP BY {original}, {key} ORDER BY rows DESC, original_code
        """)
    db.execute(f"""
        CREATE TABLE enriched_trade_data AS
        SELECT t.*,
            e.name AS exporter_name, e.iso2_original AS exporter_iso2_original,
            e.iso2 AS exporter_iso2, e.iso3 AS exporter_iso3,
            e.iso2_source AS exporter_iso2_source,
            i.name AS importer_name, i.iso2_original AS importer_iso2_original,
            i.iso2 AS importer_iso2, i.iso3 AS importer_iso3,
            i.iso2_source AS importer_iso2_source,
            p.description AS product_description,
            e.code IS NOT NULL AS exporter_matched,
            i.code IS NOT NULL AS importer_matched,
            p.code IS NOT NULL AS product_matched
        {base} {joins}
    """)
    db.execute("""
        CREATE VIEW unmatched_trade_records AS SELECT * FROM enriched_trade_data
        WHERE NOT (exporter_matched AND importer_matched AND product_matched)
    """)
    write_json(reports / "unmatched_records.json", unmatched)
    return validation, unmatched


def summarize(db, validation, unmatched):
    raw_rows = count(db, "SELECT COUNT(*) FROM trade")
    clean_rows = count(db, "SELECT COUNT(*) FROM trade_data_clean")
    enriched_rows = count(db, "SELECT COUNT(*) FROM enriched_trade_data")
    exact = count(db, """
        SELECT COUNT(*) FROM trade JOIN product ON product.code = trade.product_code_original
    """)
    normalized = count(db, "SELECT COUNT(*) FROM enriched_trade_data WHERE product_matched")
    recovered = count(db, """
        SELECT COUNT(*) FROM enriched_trade_data AS t
        LEFT JOIN product AS p ON p.code = t.product_code_original
        WHERE t.product_matched AND p.code IS NULL
    """)
    quantities = dict(db.execute("""
        SELECT COUNT(*) FILTER (WHERE quantity_original IS NULL) AS missing_before,
               COUNT(*) FILTER (WHERE quantity_processed IS NULL) AS missing_after,
               COUNT(*) FILTER (WHERE quantity_was_imputed) AS imputed,
               COUNT(*) FILTER (WHERE quantity_original IS NULL AND quantity_processed IS NULL)
                    AS originally_missing_and_unfilled,
               COUNT(*) FILTER (WHERE quantity_original IS NOT NULL AND quantity_observed IS NULL)
                    AS invalid_nonblank
        FROM trade_data_clean
    """).fetchone())
    no_quantity = as_dicts(db, """
        SELECT product_code, COUNT(*) AS rows FROM trade_data_clean
        WHERE quantity_original IS NULL AND quantity_processed IS NULL
        GROUP BY product_code ORDER BY product_code
    """)
    country_iso2 = {
        "recovered": as_dicts(db, """
            SELECT code, name, iso2, iso3, iso2_source AS source FROM country
            WHERE iso2_source IS NOT NULL ORDER BY code
        """),
        "unresolved": as_dicts(db, """
            SELECT code, name, iso3 FROM country WHERE iso2 IS NULL ORDER BY code
        """),
        "trade_rows_before": count(db, """
            SELECT COUNT(*) FROM enriched_trade_data
            WHERE (exporter_matched AND exporter_iso2_original IS NULL)
               OR (importer_matched AND importer_iso2_original IS NULL)
        """),
        "trade_rows_after": count(db, """
            SELECT COUNT(*) FROM enriched_trade_data
            WHERE (exporter_matched AND exporter_iso2 IS NULL)
               OR (importer_matched AND importer_iso2 IS NULL)
        """),
    }
    invalid = count(db, "SELECT COUNT(*) FROM invalid_trade_records")
    duplicate = count(db, """
        SELECT COALESCE(SUM(n - 1), 0) FROM
            (SELECT COUNT(*) AS n FROM trade WHERE invalid_fields IS NULL
             GROUP BY year, exporter_code, importer_code, product_code HAVING COUNT(*) > 1)
    """)
    if raw_rows != clean_rows or raw_rows != enriched_rows:
        raise ValueError("Raw, clean and enriched row counts do not reconcile")
    if quantities["missing_before"] != quantities["imputed"] + quantities["originally_missing_and_unfilled"]:
        raise ValueError("Missing quantity counts do not reconcile")
    return {
        "metadata": COVERAGE,
        "rows": {"original": raw_rows, "clean": clean_rows, "enriched": enriched_rows,
                 "invalid": invalid},
        "product_matches": {
            "exact": exact, "normalized": normalized, "recovered_from_exact_misses": recovered,
            "exact_percent": (100 * exact / raw_rows) if raw_rows else None,
            "normalized_percent": (100 * normalized / raw_rows) if raw_rows else None,
        },
        "quantity": quantities,
        "unfilled_quantity_by_product": no_quantity,
        "country_iso2": country_iso2,
        "join_validation": validation,
        "unmatched_rows_by_join": {key: sum(item["rows"] for item in rows)
                                    for key, rows in unmatched.items()},
        "duplicate_normalized_trade_keys_beyond_first": duplicate,
    }


def run(root, output, reports):
    output.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as working:
        path = Path(working) / "trade.sqlite"
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                db.executescript(SCHEMA)
                countries = country_records(root / "country_codes.csv", root / "configs/country_iso2.json")
                products = product_records(root / "product_codes.csv")
                db.executemany("INSERT INTO country VALUES (?,?,?,?,?,?)",
                               require_unique(countries, 0, "country key"))
                db.executemany("INSERT INTO product VALUES (?,?)",
                               require_unique(products, 0, "product key"))
                trade = read_records(root / "trade_data.csv", TRADE_FIELDS)
                db.executemany("INSERT INTO trade VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (parse_trade(index, row) for index, row in enumerate(trade, 1)))
                LOG.info("Loaded source rows. Building clean dataset.")
                build_clean(db)
                LOG.info("Validating country and product joins.")
                expected = count(db, "SELECT COUNT(*) FROM trade")
                validation, unmatched = build_enriched(db, expected, Path(working))
                summary = summarize(db, validation, unmatched)
                db.execute("CREATE TABLE dataset_metadata (metadata_json TEXT NOT NULL)")
                db.execute("INSERT INTO dataset_metadata VALUES (?)", (json.dumps(COVERAGE),))
                db.execute("DROP TABLE trade")
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Processed database failed its integrity check")
        finally:
            db.close()
        path.replace(output / path.name)
        (Path(working) / "unmatched_records.json").replace(reports / "unmatched_records.json")
    write_json(reports / "data_quality_after_cleaning.json", summary)
    write_json(reports / "enrichment_summary.json", summary)
    LOG.info("Published %s enriched rows", summary["rows"]["enriched"])
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("data/processed"))
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(args.root, args.output, args.reports)


if __name__ == "__main__":
    main()
