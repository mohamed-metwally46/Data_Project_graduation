"""Source reference validation and provenance-aware country enrichment."""
import json
import re

from src.preprocessing.trade import normalize_product_code, positive_integer, read_records


def require_unique(records, key_index, label):
    seen = set()
    for record in records:
        key = record[key_index]
        if key in seen:
            raise ValueError(f"Duplicate or conflicting {label}: {key}")
        seen.add(key)
        yield record


def product_records(path):
    for row in read_records(path, ("code", "description")):
        code = row["code"]
        if normalize_product_code(code) != code or not row["description"].strip():
            raise ValueError(f"Invalid product reference: {row}")
        yield code, row["description"]


def country_records(path, override_path):
    overrides = json.loads(override_path.read_text(encoding="utf-8-sig"))
    seen = set()
    fields = ("country_code", "country_name", "country_iso2", "country_iso3")
    for row in read_records(path, fields):
        code, name, iso2, iso3 = (row[field] for field in fields)
        key = positive_integer(code)
        if key is None:
            raise ValueError(f"Invalid country reference key: {code}")
        original = iso2 or None
        source = None
        if code in overrides:
            verified = overrides[code]
            seen.add(code)
            if (iso3 != verified["iso3"] or
                    (iso2 and iso2 != verified["iso2"]) or
                    not re.fullmatch(r"[A-Z]{2}", verified["iso2"]) or
                    not verified["source"].startswith("https://")):
                raise ValueError(f"Conflicting or invalid ISO2 mapping for {code}")
            if not iso2:
                iso2 = verified["iso2"]
                source = verified["source"]
        yield key, name, original, iso2 or None, iso3 or None, source
    if missing := overrides.keys() - seen:
        raise ValueError(f"Configured countries missing from reference: {sorted(missing)}")
