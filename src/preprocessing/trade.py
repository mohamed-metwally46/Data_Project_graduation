"""Validation and normalization for source trade records."""
import csv
import math
import re


TRADE_FIELDS = (
    "Year", "Exporter Country Code", "Importer Country Code",
    "HS Product Code", "Trade Value", "Quantity",
)
LEGACY_PRODUCT_CODES = {"9999AA"}


def read_records(path, fields):
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f"{path}: expected CSV header {fields}")
        for row in reader:
            if None in row or None in row.values():
                raise ValueError(f"{path}: incorrect field count at line {reader.line_num}")
            yield row


def normalize_product_code(code):
    if not isinstance(code, str):
        raise TypeError("Product codes must be strings")
    if re.fullmatch(r"[0-9]{5}", code):
        return "0" + code
    if re.fullmatch(r"[0-9]{6}", code) or code in LEGACY_PRODUCT_CODES:
        return code
    return None


def positive_integer(value):
    if re.fullmatch(r"[0-9]+", value) and int(value) > 0:
        return int(value)
    return None


def positive_measure(value):
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        number = float(value)
        if math.isfinite(number) and number > 0:
            return number
    return None


def parse_trade(row_number, row):
    year, exporter, importer, raw_code, raw_value, raw_quantity = (
        row[field] for field in TRADE_FIELDS
    )
    fields = (positive_integer(year), positive_integer(exporter),
              positive_integer(importer), normalize_product_code(raw_code),
              positive_measure(raw_value), positive_measure(raw_quantity))
    invalid = [name for name, value in zip(TRADE_FIELDS, fields)
               if value is None and (name != "Quantity" or raw_quantity != "")]
    return (row_number, *fields[:3], raw_code, fields[3], raw_value, fields[4],
            raw_quantity or None, fields[5], ", ".join(invalid) or None)
