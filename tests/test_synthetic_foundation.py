from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import NAMESPACE_URL

from jsonschema import ValidationError

from src.analytics.release import MANIFEST
from src.analytics.release_validation import schema_validator
from src.synthetic.determinism import display_code, external_id, named_random_stream
from src.synthetic.foundation import SOURCE, TARGETS, load_policy, require_generation_ready, verify_pinned_source


ROOT = Path(__file__).resolve().parents[1]


class SyntheticFoundationTests(unittest.TestCase):
    def test_approved_pin_targets_and_blocked_configuration(self):
        policy = load_policy(ROOT)
        self.assertEqual(policy["source"], SOURCE)
        self.assertEqual(policy["targets"], TARGETS)
        self.assertEqual(policy["proposed_defaults"]["status"], "proposed")
        self.assertTrue(all(value is None for value in policy["unresolved"].values()))
        with self.assertRaisesRegex(ValueError, "blocked"):
            require_generation_ready(policy)

    def test_policy_rejects_unapproved_or_inconsistent_values(self):
        original = load_policy(ROOT)
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "policy.json"
            for section, key, value, error in (
                ("targets", "companies", 510, ValueError),
                ("targets", "supplier_roles", True, ValidationError),
                ("source", "release_id", "ti-" + "a" * 64, ValueError),
                ("source", "dataset_fingerprint", "sha256:broken", ValidationError),
                ("proposed_defaults", "status", "approved", ValidationError),
                ("proposed_defaults", "offers_per_rfq", {"0": 119, "1": 181, "2": 180, "3": 120}, ValueError),
                ("proposed_defaults", "bilateral_percent", {"a_min": 101, "b_max": 20, "c": 0}, ValidationError),
                ("proposed_defaults", "rfq_types", {"open": 299, "targeted": 301}, ValueError),
                ("unresolved", "master_seed", 42, ValidationError),
            ):
                with self.subTest(section=section, key=key, value=value):
                    policy = deepcopy(original)
                    policy[section][key] = value
                    path.write_text(json.dumps(policy), encoding="utf-8")
                    with self.assertRaises(error):
                        load_policy(ROOT, path)

    def test_source_mismatch_fails_before_release_validation(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            path = root / MANIFEST
            path.parent.mkdir(parents=True)
            for change in ({"release_id": "ti-" + "f"*64}, {"year": 2023}, {"status": "incomplete"}):
                path.write_text(json.dumps({**SOURCE, "status": "validated", **change}), encoding="utf-8")
                with patch("src.synthetic.foundation.validate") as validate:
                    with self.assertRaisesRegex(ValueError, "approved validated source pin"):
                        verify_pinned_source(root, load_policy(ROOT))
                    validate.assert_not_called()

    def test_source_uses_readonly_validator_and_rechecks_afterward(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            path = root / MANIFEST
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({**SOURCE, "status": "validated", "statistics": {"eligible_records": 3}}))
            with patch("src.synthetic.foundation.validate", return_value={**SOURCE, "status": "validated"}) as validate:
                result = verify_pinned_source(root, load_policy(ROOT))
            validate.assert_called_once_with(root)
            self.assertEqual(result["statistics"]["eligible_records"], 3)
            with patch("src.synthetic.foundation.validate", return_value={**SOURCE, "status": "invalid"}):
                with self.assertRaisesRegex(ValueError, "changed during verification"):
                    verify_pinned_source(root, load_policy(ROOT))

    def test_id_and_display_code(self):
        fixture = external_id(NAMESPACE_URL, "product", "010111")
        self.assertEqual(fixture.version, 5)
        self.assertEqual(fixture, external_id(str(NAMESPACE_URL), "product", "010111"))
        self.assertNotEqual(fixture, external_id(NAMESPACE_URL, "product", 10111))
        self.assertNotEqual(fixture, external_id(NAMESPACE_URL, "company", "010111"))
        self.assertNotEqual(external_id(NAMESPACE_URL, "fixture", "a:b", "c"),
                            external_id(NAMESPACE_URL, "fixture", "a", "b:c"))
        self.assertEqual(display_code("PRD", 42), "PRD-000042")
        for prefix, ordinal in [("bad", 42), ("PRD", 0), ("PRD", True), ("PRD", 1_000_000)]:
            with self.assertRaises(ValueError):
                display_code(prefix, ordinal)

    def test_random_stream_isolation_and_repeatability(self):
        first = named_random_stream(42, "fixture", "allocation")
        another = named_random_stream(42, "fixture", "attributes")
        expected_attributes = [another.getrandbits(64) for _ in range(4)]
        values = [first.getrandbits(64) for _ in range(4)]
        repeated = named_random_stream(42, "fixture", "allocation")
        self.assertEqual(values, [repeated.getrandbits(64) for _ in range(4)])
        self.assertNotEqual(values, expected_attributes)
        for _ in range(100):
            first.random()
        unchanged = named_random_stream(42, "fixture", "attributes")
        self.assertEqual(expected_attributes, [unchanged.getrandbits(64) for _ in range(4)])
        with self.assertRaises(ValueError):
            named_random_stream(True, "fixture")

    def test_proposed_contract_with_isolated_fixture(self):
        validate = schema_validator(ROOT, "marketplace_bundle.proposed")
        fixture_id = str(external_id(NAMESPACE_URL, "fixture", 1))
        data = dict.fromkeys(("market_references", "products", "companies", "company_roles",
                             "company_product_associations", "listings", "rfqs", "offers"), [])
        data["manifest"] = {
            "contract_version": "0.1.0-draft", "contract_status": "proposed_backend_confirmation_pending",
            "marketplace_release_id": "isolated-fixture", "dataset_type": "synthetic_marketplace",
            "is_synthetic": True, "source_release_id": SOURCE["release_id"],
            "dataset_fingerprint": SOURCE["dataset_fingerprint"], "policy_version": "1.0.0",
            "configuration_sha256": "0"*64, "namespace": fixture_id, "artifacts": [],
        }
        data["rfqs"] = [{"external_id": fixture_id, "display_code": "RFQ-000001", "is_synthetic": True,
                         "importer_association_id": fixture_id, "destination_market_id": fixture_id,
                         "type": "open", "status": "open", "quantity": "10.00", "unit": "fixture-unit",
                         "currency": "USD", "target_supplier_role_id": None, "evidence": None}]
        validate.validate(data)
        data["rfqs"][0]["quantity"] = 10
        with self.assertRaises(ValidationError):
            validate.validate(data)
        data["rfqs"][0].update(quantity="10", type="targeted")
        with self.assertRaises(ValidationError):
            validate.validate(data)


if __name__ == "__main__":
    unittest.main()
