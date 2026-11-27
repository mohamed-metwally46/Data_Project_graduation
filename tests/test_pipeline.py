import csv
from contextlib import closing
from importlib.util import find_spec
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.analytics.country_intelligence import run as run_country_intelligence
from src.analytics.product_intelligence import run as run_product_intelligence
from src.analytics.route_intelligence import inspect_grain, open_database, percentage, product_composition
from src.analytics.route_intelligence import run as run_route_intelligence
from src.analytics.trade import aggregate, opportunities
from src.enrichment.references import country_records, require_unique
from src.pipeline import run
from src.preprocessing.trade import TRADE_FIELDS, normalize_product_code


def write_csv(root, name, header, rows):
    with (root / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


class NormalizationTests(unittest.TestCase):
    def test_formats(self):
        for original, normalized in {
            "80810": "080810", "330499": "330499", "010111": "010111",
            "9999AA": "9999AA", "": None, "1234": None, "1234567": None,
            "ABC123": None, " 80810": None,
        }.items():
            with self.subTest(original=original):
                self.assertEqual(normalize_product_code(original), normalized)
        with self.assertRaises(TypeError):
            normalize_product_code(80810)

    def test_conflicting_reference_keys(self):
        with self.assertRaisesRegex(ValueError, "Duplicate or conflicting"):
            list(require_unique([(1, "AA"), (1, "BB")], 0, "country key"))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "configs").mkdir()
        self.overrides = self.root / "configs/country_iso2.json"
        self.overrides.write_text(
            '{"516":{"iso3":"NAM","iso2":"NA","source":"https://example.test"}}',
            encoding="utf-8",
        )
        self.country_header = ("country_code", "country_name", "country_iso2", "country_iso3")
        write_csv(self.root, "country_codes.csv", self.country_header,
                  [(4, "Afghanistan", "AF", "AFG"), (516, "Namibia", "", "NAM"),
                   (490, "Other Asia", "", "S19")])
        write_csv(self.root, "product_codes.csv", ("code", "description"),
                  [("080810", "Apples"), ("330499", "Cosmetics"), ("010111", "Horses")])
        write_csv(self.root, "trade_data.csv", TRADE_FIELDS, [
            (2024, 4, 516, "80810", "3", "2"),
            (2024, 516, 4, "080810", "4", "6"),
            (2024, 4, 490, "080810", "5", ""),
            (2024, 4, 516, "330499", "6", "90"),
            (2024, 516, 4, "330499", "7", ""),
            (2024, 4, 516, "010111", "8", ""),
            (2024, 4, 999, "1234567", "9", "9"),
        ])

    def test_enrichment_and_analytics(self):
        output = self.root / "processed"
        summary = run(self.root, output, self.root / "reports")
        self.assertEqual(summary["rows"], {"original": 7, "clean": 7, "enriched": 7, "invalid": 1})
        for step in summary["join_validation"].values():
            self.assertEqual((step["before"], step["after"]), (7, 7))
        self.assertEqual(summary["product_matches"]["recovered_from_exact_misses"], 1)
        self.assertEqual(summary["unmatched_rows_by_join"], {"exporter": 0, "importer": 1, "product": 1})
        self.assertEqual(summary["quantity"]["imputed"], 2)
        self.assertEqual(summary["quantity"]["originally_missing_and_unfilled"], 1)
        db = sqlite3.connect(output / "trade.sqlite")
        self.addCleanup(db.close)
        db.row_factory = sqlite3.Row
        rows = db.execute("""
            SELECT quantity_original, quantity_processed, quantity_was_imputed
            FROM enriched_trade_data ORDER BY row_id
        """)
        self.assertEqual([tuple(row) for row in rows],
                         [("2", 2., 0), ("6", 6., 0), (None, 4., 1),
                          ("90", 90., 0), (None, 90., 1), (None, None, 0), ("9", 9., 0)])
        row = db.execute("""
            SELECT product_code_original, product_code, product_description,
                   importer_iso2_original, importer_iso2, importer_iso2_source
            FROM enriched_trade_data WHERE row_id = 1
        """).fetchone()
        self.assertEqual(tuple(row), ("80810", "080810", "Apples", None, "NA", "https://example.test"))
        self.assertEqual(db.execute("SELECT COUNT(*) FROM unmatched_trade_records").fetchone()[0], 1)
        metadata, countries, products, routes = aggregate(db, summary)
        self.assertEqual(metadata["included_unique_rows"], 6)
        self.assertEqual((len(countries), len(products), len(routes)), (3, 3, 3))
        self.assertEqual(opportunities(db)[0]["score"], 3)

    def test_duplicate_reference_aborts_before_join(self):
        write_csv(self.root, "product_codes.csv", ("code", "description"),
                  [("080810", "Apples"), ("080810", "Conflicting description")])
        with self.assertRaisesRegex(ValueError, "Duplicate or conflicting product key"):
            run(self.root, self.root / "processed", self.root / "reports")
        self.assertFalse((self.root / "processed/trade.sqlite").exists())

    def test_country_intelligence_directions_and_rankings(self):
        with (self.root / "country_codes.csv").open("a", encoding="utf-8") as stream:
            stream.write("8,Albania,AL,ALB\n")
        with (self.root / "trade_data.csv").open("a", encoding="utf-8") as stream:
            stream.write("2024,4,516,080810,3,2\n")
            stream.write("2024,490,516,010111,3,\n")
        output = self.root / "processed"
        reports = self.root / "reports"
        run(self.root, output, reports)
        result = run_country_intelligence(
            output / "trade.sqlite", output / "country_intelligence.json",
            reports / "enrichment_summary.json", top_n=2,
        )
        profiles = {profile["code"]: profile for profile in result["records"]}
        self.assertEqual(len(profiles), len(result["records"]))
        self.assertEqual(set(profiles), {4, 8, 490, 516})
        for direction in ("export", "import"):
            self.assertEqual(sum(row[f"{direction}_record_count"] for row in profiles.values()), 7)
            self.assertEqual(profiles[8][f"{direction}_record_count"], 0)
            self.assertEqual(profiles[8][f"top_{direction}_products"], [])
        self.assertEqual(result["metadata"]["excluded_rows"], 2)
        afghanistan = profiles[4]
        self.assertEqual((afghanistan["export_record_count"], afghanistan["import_record_count"]), (4, 2))
        self.assertEqual((afghanistan["export_destinations"], afghanistan["import_sources"]), (2, 1))
        self.assertEqual((afghanistan["distinct_exported_products"],
                          afghanistan["distinct_imported_products"]), (3, 2))
        self.assertEqual(
            [(item["product_code"], item["record_count"]) for item in afghanistan["top_export_products"]],
            [("080810", 2), ("010111", 1)],
        )
        self.assertEqual(afghanistan["top_export_destinations"][0]["name"], "Namibia")
        self.assertEqual(profiles[516]["import_record_count"], 4)
        self.assertEqual(profiles[490]["name"], "Other Asia")
        self.assertIsNone(profiles[490]["iso2"])
        self.assertEqual(profiles[490]["year"], 2024)
        self.assertFalse(profiles[490]["coverage"]["imputed_quantity_used"])

    def test_product_intelligence_coverage_and_rankings(self):
        with (self.root / "product_codes.csv").open("a", encoding="utf-8") as stream:
            stream.write("9999AA,Legacy special code\n970600,Unobserved product\n")
        with (self.root / "trade_data.csv").open("a", encoding="utf-8") as stream:
            stream.write("2024,4,516,080810,3,2\n")
            stream.write("2024,4,490,123456,3,\n")
            stream.write("2024,4,490,9999AA,3,\n")
        output = self.root / "processed"
        reports = self.root / "reports"
        run(self.root, output, reports)
        database = output / "trade.sqlite"
        with sqlite3.connect(database) as db:
            db.execute("UPDATE product SET description = ' ' WHERE code = '010111'")
        db.close()
        result = run_product_intelligence(
            database, output / "product_intelligence.json",
            reports / "enrichment_summary.json", top_n=2,
        )
        profiles = {row["product_code"]: row for row in result["records"]}
        self.assertEqual(len(profiles), len(result["records"]))
        self.assertEqual(sum(row["record_count"] for row in profiles.values()), 7)
        apples = profiles["080810"]
        self.assertEqual((apples["record_count"], apples["input_row_count"]), (3, 4))
        self.assertEqual((apples["exporters"], apples["importers"], apples["distinct_routes"]), (2, 3, 3))
        self.assertEqual([x["exporter_code"] for x in apples["top_exporters"]], [4, 516])
        self.assertEqual([x["importer_code"] for x in apples["top_importers"]], [4, 490])
        self.assertEqual(apples["top_importers"][1]["importer_name"], "Other Asia")
        self.assertEqual([(x["exporter_code"], x["importer_code"]) for x in apples["top_routes"]],
                         [(4, 490), (4, 516)])
        self.assertEqual(apples["top_exporters"][0]["percent_of_product_records"], 66.666667)
        self.assertEqual(profiles["9999AA"]["exporters"], 1)
        self.assertEqual(profiles["9999AA"]["importers"], 1)
        self.assertTrue(profiles["010111"]["reference_mapped"])
        self.assertIsNone(profiles["010111"]["description"])
        self.assertFalse(profiles["123456"]["reference_mapped"])
        self.assertEqual(profiles["123456"]["record_count"], 0)
        coverage = result["reference_coverage"]
        self.assertEqual(coverage["unmapped_product_rows"], 1)
        self.assertEqual(coverage["products_missing_description"], 2)
        self.assertEqual(coverage["unobserved_reference_codes"], ["970600"])
        self.assertEqual(coverage["unnormalizable_codes"],
                         [{"product_code_original": "1234567", "input_row_count": 1}])

    @unittest.skipUnless(find_spec("pyarrow"), "PyArrow is required for Parquet export")
    def test_parquet_export_preserves_types_and_values(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from src.export.parquet import run as export_parquet

        output = self.root / "processed"
        run(self.root, output, self.root / "reports")
        counts = export_parquet(output / "trade.sqlite", output)
        self.assertEqual(counts, {"trade_data_clean": 7, "enriched_trade_data": 7,
                                  "invalid_trade_records": 1})
        table = pq.read_table(output / "enriched_trade_data.parquet")
        self.assertEqual(table.schema.field("product_code").type, pa.string())
        self.assertEqual(table.schema.field("quantity_was_imputed").type, pa.bool_())
        self.assertEqual(table.column("product_code")[0].as_py(), "080810")
        self.assertTrue(table.column("quantity_was_imputed")[2].as_py())
        self.assertIn(b"globiq.dataset", table.schema.metadata)

    def test_conflicting_external_country_mapping_rejected(self):
        path = self.root / "country_codes.csv"
        write_csv(self.root, path.name, self.country_header, [(516, "Namibia", "", "ZZZ")])
        with self.assertRaisesRegex(ValueError, "Conflicting or invalid ISO2"):
            list(country_records(path, self.overrides))

    def test_route_intelligence_composition_and_directions(self):
        with (self.root / "trade_data.csv").open("a", encoding="utf-8") as stream:
            stream.write("2024,4,4,010111,3,2\n2024,4,516,123456,3,2\n")
        output = self.root / "processed"
        reports = self.root / "reports"
        run(self.root, output, reports)
        database = output / "trade.sqlite"
        with closing(sqlite3.connect(database)) as db, db:
            db.execute("UPDATE country SET name='', iso3=NULL WHERE code=490")
            db.execute("UPDATE product SET description='' WHERE code='010111'")
        summary = reports / "enrichment_summary.json"
        destination = output / "route_intelligence.json"
        country_before = run_country_intelligence(database, output / "country.json", summary)
        product_before = run_product_intelligence(database, output / "product.json", summary)
        result = run_route_intelligence(database, destination, summary)
        first_bytes = destination.read_bytes()
        run_route_intelligence(database, destination, summary)
        self.assertEqual(first_bytes, destination.read_bytes())
        self.assertEqual(country_before, run_country_intelligence(database, output / "country.json", summary))
        self.assertEqual(product_before, run_product_intelligence(database, output / "product.json", summary))
        routes = {row["route_id"]: row for row in result["records"]}
        self.assertEqual(len(routes), len(result["records"]))
        self.assertEqual(result["metadata"]["record_grain"]["eligible_records"], 7)
        self.assertEqual(result["metadata"]["reciprocal_pairs"], 1)
        forward = routes["2024:4:516"]
        self.assertEqual(forward["reverse_route_id"], "2024:516:4")
        self.assertEqual(routes["2024:516:4"]["reverse_route_id"], forward["route_id"])
        self.assertIsNone(routes["2024:4:490"]["importer"]["name"])
        self.assertIsNone(routes["2024:4:490"]["importer"]["iso2"])
        self.assertIsNone(routes["2024:4:490"]["importer"]["iso3"])
        self.assertTrue(routes["2024:4:4"]["self_trade"])
        self.assertFalse(routes["2024:4:4"]["reverse_observed"])
        self.assertFalse(routes["2024:4:4"]["product_composition"]["eligible_products_tied"])
        self.assertTrue(forward["product_composition"]["eligible_products_tied"])
        self.assertEqual(forward["relative_coverage"]["percent_of_dataset_records"], 42.857143)
        self.assertEqual(forward["relative_coverage"]["percent_of_exporter_records"], 60)
        self.assertEqual(forward["relative_coverage"]["percent_of_importer_records"], 100)
        self.assertEqual(forward["relative_coverage"]["percent_of_exporter_products"], 100)
        self.assertEqual(forward["relative_coverage"]["percent_of_importer_products"], 100)
        self.assertIsNone(percentage(0, 0))
        with closing(open_database(database)) as db:
            details = product_composition(db, 2024, 4, 516)
        self.assertEqual([row["product_code"] for row in details], ["010111", "080810", "123456", "330499"])
        self.assertIsNone(details[0]["description"])
        self.assertFalse(details[2]["reference_mapped"])
        self.assertEqual(forward["product_reference_coverage"]["mapped_percent"], 75)
        self.assertEqual(sum(row["record_count"] for row in details), forward["record_count"])
        self.assertEqual(sum(row["record_count"] for row in routes.values()), 7)
        self.assertEqual(json.loads(first_bytes), result)

    def test_route_intelligence_rejects_duplicate_eligible_grain(self):
        with (self.root / "trade_data.csv").open("a", encoding="utf-8") as stream:
            stream.write("2024,4,516,080810,3,2\n")
        output = self.root / "processed"
        reports = self.root / "reports"
        run(self.root, output, reports)
        database = output / "trade.sqlite"
        with closing(open_database(database)) as db:
            self.assertEqual(inspect_grain(db), {
                "eligible_records": 7, "unique_composite_keys": 6,
                "duplicated_composite_keys": 1, "records_on_duplicated_keys": 2,
            })
        destination = output / "routes.json"
        with self.assertRaisesRegex(ValueError, "Duplicate eligible composite keys.*080810"):
            run_route_intelligence(database, destination, reports / "enrichment_summary.json")
        self.assertFalse(destination.exists())

    @unittest.skipUnless(find_spec("jsonschema"), "Install requirements-dev.txt for schema validation")
    def test_route_intelligence_json_schema(self):
        from jsonschema import Draft202012Validator

        output = self.root / "processed"
        reports = self.root / "reports"
        run(self.root, output, reports)
        path = output / "routes.json"
        run_route_intelligence(output / "trade.sqlite", path, reports / "enrichment_summary.json")
        schema_path = Path(__file__).resolve().parents[1] / "schemas/route_intelligence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
