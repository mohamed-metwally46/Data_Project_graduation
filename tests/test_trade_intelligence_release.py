import csv
from importlib.util import find_spec
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from src.preprocessing.trade import TRADE_FIELDS


@unittest.skipUnless(find_spec("pyarrow") and find_spec("jsonschema"), "Install requirements-dev.txt")
class ReleaseTests(unittest.TestCase):
    def setUp(self):
        from src.analytics.release import CONTRACTS
        from src.export.parquet import run as export
        from src.pipeline import run as pipeline

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = Path(__file__).resolve().parents[1]
        for file in CONTRACTS:
            destination = self.root / file
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.repo / file, destination)
        config = self.root / "configs/country_iso2.json"
        config.parent.mkdir()
        config.write_text("{}", encoding="utf-8")
        self.write_csv("country_codes.csv", ("country_code", "country_name", "country_iso2", "country_iso3"),
                       [(4, "Afghanistan", "AF", "AFG"), (8, "Area", "", ""),
                        (12, "Algeria", "DZ", "DZA"), (16, "Idle", "", "")])
        self.write_csv("product_codes.csv", ("code", "description"),
                       [("010111", "Horses"), ("9999AA", "Legacy"), ("970600", "Idle product")])
        self.write_csv("trade_data.csv", TRADE_FIELDS,
                       [(2024, e, i, p, "1", "1") for e, i, p in (
                           (4, 8, "10111"), (8, 12, "010111"), (12, 4, "010111"),
                           (4, 12, "9999AA"), (8, 4, "9999AA"),
                       )])
        processed = self.root / "data/processed"
        pipeline(self.root, processed, self.root / "reports")
        export(processed / "trade.sqlite", processed)

    def write_csv(self, filename, header, rows):
        with (self.root / filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)

    def test_generate_validate_inspect_and_determinism(self):
        from src.analytics.release import MANIFEST, generate, validate

        first, initial = generate(self.root)
        self.assertEqual(initial["reproducibility"], "first_generation")
        second, verification = generate(self.root)
        self.assertEqual(second, first)
        self.assertEqual(verification["reproducibility"], "byte_identical_to_existing_release")
        self.assertEqual(validate(self.root)["release_id"], first["release_id"])
        self.assertEqual(first["statistics"]["zero_observation_country_profiles"], 1)
        self.assertEqual({r["dataset_fingerprint"] for r in first["artifacts"].values()},
                         {first["dataset_fingerprint"]})
        self.assertEqual(first["statistics"]["market_universe"]["category_counts"]["A"], 5)
        for mode in ("inspect", "validate", "generate"):
            cli = subprocess.run([sys.executable, "-m", "src.analytics.release", mode,
                                  "--root", str(self.root)], cwd=self.repo, check=True,
                                 capture_output=True, text=True)
            self.assertEqual(json.loads(cli.stdout)["release_id"], first["release_id"])
        self.assertTrue((self.root / MANIFEST).is_file())

    def test_failure_protection_and_stale_detection(self):
        from jsonschema import SchemaError
        from src.analytics.release import MANIFEST, generate, validate

        manifest, _ = generate(self.root)
        pointer = self.root / MANIFEST
        original = pointer.read_bytes()
        location = self.root / manifest["artifact_directory"]
        country = location / "country_intelligence.json"
        content = country.read_bytes()
        country.write_bytes(content + b" ")
        with self.assertRaisesRegex(ValueError, "file integrity"):
            validate(self.root)
        country.unlink()
        with self.assertRaises(FileNotFoundError):
            validate(self.root)
        country.write_bytes(content)
        schema = self.root / "schemas/country_intelligence.schema.json"
        valid_schema = schema.read_bytes()
        schema.write_text('{"type": 5}', encoding="utf-8")
        with self.assertRaises(SchemaError):
            generate(self.root)
        self.assertEqual(pointer.read_bytes(), original)

        schema.write_bytes(valid_schema)
        reference = self.root / "product_codes.csv"
        valid_reference = reference.read_bytes()
        reference.write_bytes(valid_reference.replace(b"Horses", b"Altered"))
        with self.assertRaisesRegex(ValueError, "stale release inputs"):
            validate(self.root)
        with self.assertRaisesRegex(ValueError, "logical dataset fingerprint"):
            generate(self.root)
        self.assertEqual(pointer.read_bytes(), original)
        reference.write_bytes(valid_reference)
        (self.root / "data/processed/enriched_trade_data.parquet").unlink()
        with self.assertRaises(FileNotFoundError):
            generate(self.root)
        self.assertEqual(pointer.read_bytes(), original)


    def test_reencoded_parquet_changes_artifact_identity_only(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from src.analytics.release import generate, validate

        before, _ = generate(self.root)
        file = self.root / "data/processed/enriched_trade_data.parquet"
        data = pq.read_table(file)
        pq.write_table(data.take(pa.array(list(reversed(range(data.num_rows))))), file,
                       compression="gzip")
        with self.assertRaisesRegex(ValueError, "stale release inputs"):
            validate(self.root)
        after, _ = generate(self.root)
        self.assertEqual(before["dataset_fingerprint"], after["dataset_fingerprint"])
        self.assertNotEqual(before["release_id"], after["release_id"])
        self.assertNotEqual(before["inputs"]["enriched_parquet"]["sha256"],
                            after["inputs"]["enriched_parquet"]["sha256"])

if __name__ == "__main__":
    unittest.main()
