from contextlib import closing
from importlib.util import find_spec
import json
from pathlib import Path
import sqlite3
import unittest

from src.analytics.market_opportunity_intelligence import MarketRelationshipEngine, QueryError


ROWS = (
    (4, 8, "010111"), (8, 12, "010111"), (12, 4, "010111"), (4, 20, "010111"),
    (4, 12, "9999AA"), (8, 4, "9999AA"), (24, 20, "9999AA"),
)


def fixture(rows=ROWS):
    with closing(sqlite3.connect(":memory:")) as db:
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE country(code INTEGER PRIMARY KEY,name,iso2,iso3);
            CREATE TABLE product(code TEXT PRIMARY KEY,description);
            CREATE TABLE enriched_trade_data(year,exporter_code,importer_code,product_code,
                invalid_fields,exporter_matched,importer_matched,product_matched);
        """)
        db.executemany("INSERT INTO country VALUES (?,?,NULL,NULL)",
                       [(x, f"Area {x}") for x in (4, 8, 12, 16, 20, 24)])
        db.executemany("INSERT INTO product VALUES (?,?)",
                       [("010111", "Horses"), ("9999AA", "Legacy"), ("970600", "Unobserved")])
        db.executemany("INSERT INTO enriched_trade_data VALUES (2024,?,?,?,NULL,1,1,1)", rows)
        return MarketRelationshipEngine(db, {
            "rows": {"enriched": len(rows)},
            "join_validation": {k: {"before": len(rows), "after": len(rows), "reference_keys_unique": True}
                                for k in ("exporter", "importer", "product")},
            "metadata": {"complete_global_coverage": False, "source": "Fixture", "limitation": "Partial",
                         "trade_value_unit": None, "quantity_unit": None, "hs_revision": None},
        })


class MarketRelationshipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = fixture()

    def test_categories_evidence_and_id(self):
        a = self.engine.lookup_id("2024:4:010111:8")
        b = self.engine.lookup_relationship("10111", 4, 12)
        c = self.engine.lookup_relationship("010111", 12, 8)
        self.assertEqual([a["category"], b["category"], c["category"]], ["A", "B", "C"])
        self.assertEqual(a["relationship_id"], "2024:4:010111:8")
        self.assertTrue(a["reverse_pair_observed"])
        self.assertFalse(a["reverse_product_link_observed"])
        self.assertTrue(b["reverse_product_link_observed"])
        self.assertEqual(a["evidence"]["other_pair_product_count"], 0)
        self.assertEqual(b["evidence"]["other_pair_product_count"], 1)
        self.assertEqual(b["evidence"]["exporter_product_destinations"], 2)
        self.assertIsNone(c["importer"]["iso2"])
        self.assertIsNone(self.engine.lookup_relationship("010111", 24, 8))

    def test_pagination_against_independent_candidate_enumeration(self):
        pairs = {(e, i) for e, i, _ in ROWS}
        candidates = []
        for product in {p for _, _, p in ROWS}:
            links = {(e, i) for e, i, p in ROWS if p == product}
            for e in {e for e, _ in links}:
                for i in {i for _, i in links}:
                    if e != i:
                        category = "A" if (e, i) in links else "B" if (e, i) in pairs else "C"
                        candidates.append((product, e, i, category))
        candidates.sort()
        for filters in ({"product_code": "010111"}, {"exporter_code": 4}, {"importer_code": 8},
                        {"exporter_code": 4, "importer_code": 12, "category": "B"},
                        {"product_code": "010111", "category": "C"}):
            fields = ("product_code", "exporter_code", "importer_code", "category")
            expected = [row for row in candidates
                        if all(row[fields.index(k)] == v for k, v in filters.items())]
            seen = []
            for page in range(1, (len(expected) + 1) // 2 + 1):
                result = self.engine.query_relationships(**filters, page=page, page_size=2)
                self.assertEqual(result["pagination"]["total_matches"], len(expected))
                seen.extend((r["product_code"], r["exporter"]["code"], r["importer"]["code"], r["category"])
                            for r in result["records"])
            self.assertEqual(seen, expected)
        released = self.engine.summary()["universe"]
        self.assertEqual(released["external_relationships"], len(candidates))
        self.assertEqual(released["same_market_exclusions"], 4)
        for category in "ABC":
            self.assertEqual(released["category_counts"][category], sum(r[-1] == category for r in candidates))

    def test_no_results_and_input_errors(self):
        for filters, reason in (
            ({"product_code": "970600"}, "product_unobserved"),
            ({"exporter_code": 20}, "exporter_role_unobserved"),
            ({"importer_code": 24}, "importer_role_unobserved"),
            ({"product_code": "010111", "exporter_code": 24}, "no_matches"),
            ({"product_code": "010111", "page": 100}, "page_out_of_range"),
        ):
            self.assertEqual(self.engine.query_relationships(**filters)["empty_reason"], reason)
        for filters, reason in (
            ({}, "unbounded_query"), ({"product_code": "000000"}, "unknown_product"),
            ({"exporter_code": 999}, "unknown_market"), ({"exporter_code": 4, "importer_code": 4}, "same_market"),
            ({"exporter_code": 4, "category": "D"}, "invalid_category"),
            ({"exporter_code": 4, "page": 0}, "invalid_page"),
            ({"exporter_code": 4, "page_size": 501}, "invalid_page_size"),
        ):
            with self.assertRaises(QueryError) as caught:
                self.engine.query_relationships(**filters)
            self.assertEqual(caught.exception.code, reason)

    def test_fingerprint_and_duplicate_rejection(self):
        self.assertEqual(fixture(tuple(reversed(ROWS))).metadata, self.engine.metadata)
        self.assertNotEqual(fixture(ROWS[:-1]).metadata["dataset_version"], self.engine.metadata["dataset_version"])
        with self.assertRaisesRegex(ValueError, "Duplicate eligible relationship"):
            fixture(ROWS + (ROWS[0],))

    @unittest.skipUnless(find_spec("jsonschema"), "Install requirements-dev.txt")
    def test_schemas(self):
        from jsonschema import Draft202012Validator

        root = Path(__file__).resolve().parents[1] / "schemas"
        for name, value in (
            ("market_opportunity_summary", self.engine.summary()),
            ("market_relationship_query", self.engine.query_relationships(product_code="010111")),
            ("market_relationship_query", self.engine.query_relationships(product_code="970600")),
        ):
            schema = json.loads((root / f"{name}.schema.json").read_text())
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(value)


if __name__ == "__main__":
    unittest.main()
