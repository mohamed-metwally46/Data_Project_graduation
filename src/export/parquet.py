"""Export validated SQLite trade tables to typed Parquet files."""
import argparse
from pathlib import Path
import sqlite3
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

TABLES = ("trade_data_clean", "enriched_trade_data", "invalid_trade_records")
INTEGERS = {"row_id", "year", "exporter_code", "importer_code"}
NUMBERS = {"trade_value", "quantity_observed", "quantity_processed"}
FLAGS = {"quantity_was_imputed", "exporter_matched", "importer_matched", "product_matched"}
BATCH_SIZE = 50_000


def column_type(name):
    if name in INTEGERS:
        return pa.int64()
    if name in NUMBERS:
        return pa.float64()
    if name in FLAGS:
        return pa.bool_()
    return pa.string()


def export_table(db, table, output, metadata):
    cursor = db.execute(f"SELECT * FROM {table} ORDER BY row_id")
    names = [column[0] for column in cursor.description]
    schema = pa.schema([(name, column_type(name)) for name in names], metadata=metadata)
    count = 0
    with pq.ParquetWriter(output, schema) as writer:
        while rows := cursor.fetchmany(BATCH_SIZE):
            columns = []
            for name, values in zip(names, zip(*rows), strict=True):
                if name in FLAGS:
                    values = [bool(value) if value is not None else None for value in values]
                columns.append(pa.array(values, type=column_type(name)))
            writer.write_batch(pa.RecordBatch.from_arrays(columns, schema=schema))
            count += len(rows)
    parquet = pq.ParquetFile(output)
    if parquet.metadata.num_rows != count or not parquet.schema_arrow.equals(
        schema, check_metadata=True
    ):
        raise ValueError(f"Parquet verification failed for {table}")
    return count


def run(database, output):
    output.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("BEGIN")
        metadata, = db.execute("SELECT metadata_json FROM dataset_metadata").fetchone()
        with tempfile.TemporaryDirectory(dir=output) as working:
            staging = Path(working)
            counts = {
                table: export_table(db, table, staging / f"{table}.parquet",
                                    {"globiq.dataset": metadata})
                for table in TABLES
            }
            if counts["trade_data_clean"] != counts["enriched_trade_data"]:
                raise ValueError("Clean and enriched Parquet counts differ")
            for path in staging.iterdir():
                path.replace(output / path.name)
    finally:
        db.close()
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/processed/trade.sqlite"))
    parser.add_argument("--output", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    for table, count in run(args.database, args.output).items():
        print(f"{table}: {count:,} rows")


if __name__ == "__main__":
    main()
