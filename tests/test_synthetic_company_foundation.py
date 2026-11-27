from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import NAMESPACE_URL

from jsonschema import ValidationError

from src.analytics.release import MANIFEST, stamped
from src.pipeline import write_json
from src.synthetic.company_identity import FIXTURE_NAMESPACE, build_fixture_companies, company_context, fixture_company_id, near_duplicate, read_templates
from src.synthetic.company_publication import commit_stage
from src.synthetic.company_stage import EXPECTED_PLAN, TECHNICAL_CHECKS, approval_state, inspect_inputs, read_planning_input, require_population_authorized, verify_population_approval
from src.synthetic.company_validation import validate_company_stage, write_validated_fixture
from src.synthetic.determinism import entity_namespace, external_id, hierarchical_external_id, population_namespace
from src.synthetic.foundation import load_policy
from src.synthetic.planning import ARTIFACTS, GEOGRAPHY, PLANNING, POINTER, SCENARIO, fingerprint
from src.analytics.release_validation import read_json


ROOT = Path(__file__).resolve().parents[1]


class CompanyPopulationGateTests(unittest.TestCase):
    def test_exact_company_population_binding(self):
        settings = read_templates(ROOT)
        verify_population_approval(settings)
        for section, field, replacement, error in (
            ("permanent_identity", "approved_root_namespace", FIXTURE_NAMESPACE, "namespace approval"),
            ("permanent_identity", "identity_key_review_reference", "", "canonical key approval"),
            ("company_population_approval", "planning_artifact_id", "sm02-wrong", "approval binding"),
            ("company_population_approval", "canonical_schema_sha256", "0" * 64, "approval binding"),
            ("authorization", "backend_import", "authorized", "approval binding"),
        ):
            with self.subTest(field=field):
                changed = deepcopy(settings)
                changed[section][field] = replacement
                with self.assertRaisesRegex(ValueError, error):
                    verify_population_approval(changed)
        settings["brand_starts"].reverse()
        with self.assertRaisesRegex(ValueError, "approved identity configuration"):
            verify_population_approval(settings)

    def test_failed_candidate_preserves_previous_pointer(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            prepared = root / "candidate"
            prepared.mkdir()
            write_json(prepared / "company_stage.json", {"validated": True})
            manifest = {"stage_id": "new", "artifacts": {
                "company_stage.json": stamped(prepared, "company_stage.json"),
            }}
            pointer = root / "company_stage_manifest.json"
            write_json(pointer, {"stage_id": "previous"})
            before = pointer.read_bytes()
            directory = root / "populations" / "new"
            directory.mkdir(parents=True)
            write_json(directory / "company_stage.json", {"tampered": True})
            with self.assertRaisesRegex(ValueError, "artifact hashes"):
                commit_stage(directory, prepared, pointer, manifest)
            self.assertEqual(pointer.read_bytes(), before)


def fixture_input():
    p, q = "010111", "080810"
    slots = [
        {"slot_id": "SUP-SLOT-0001", "market_code": 4, "role": "supplier", "product_codes": [p,q]},
        {"slot_id": "SUP-SLOT-0002", "market_code": 4, "role": "supplier", "product_codes": [p]},
        {"slot_id": "IMP-SLOT-0001", "market_code": 8, "role": "importer", "product_codes": [p,q]},
    ]
    listings = [{"listing_id": f"L{n}", "supplier_slot_id": supplier, "product_code": code}
                for n,(supplier,code) in enumerate(((slots[0]["slot_id"],p),(slots[1]["slot_id"],p),
                                                   (slots[0]["slot_id"],q)),1)]
    rfqs = [{"request_id": "R1", "type": "open", "buyer_slot_id": slots[2]["slot_id"],
             "destination_market": 8, "product_code": p},
            {"request_id": "R2", "type": "targeted", "buyer_slot_id": slots[2]["slot_id"],
             "destination_market": 8, "target_supplier_slot_id": slots[0]["slot_id"], "product_code": q}]
    offers = [{"offer_id": f"O{n}", "request_id": "R1" if n<3 else "R2", **listing}
              for n,listing in enumerate(listings,1)]
    plan = {"fixture_only": True, "plan_id": "fixture-company-03a",
            "source": {"release_id": "fixture-trade", "dataset_fingerprint": "sha256:" + "0"*64, "year": 2024},
            "company_slots": slots, "selected_products": [{"product_code": key} for key in (p,q)],
            "listing_allocations": listings, "rfq_allocations": rfqs, "offer_allocations": offers}
    geo = {4: {"name": "Fixture North", "supplier_eligible": True, "importer_eligible": False},
           8: {"name": "Fixture South", "supplier_eligible": False, "importer_eligible": True}}
    def observed(code, market, role):
        return code in (p,q) and (market,role) in ((4,"exporter"),(8,"importer"))
    return plan, geo, read_templates(ROOT), observed


class CompanyFixtureTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.geo, self.settings, self.observed = fixture_input()
        self.data = build_fixture_companies(self.plan,self.geo,self.settings)

    def validate(self, data=None, plan=None, observed=None):
        return validate_company_stage(ROOT, data or self.data, plan or self.plan, self.geo,
                                      self.settings, observed or self.observed)

    def test_fictional_context_roles_and_portfolios(self):
        r = self.validate()
        self.assertEqual(r["roles"], {"supplier":2,"importer":1})
        self.assertEqual((r["companies"],r["portfolio_associations"],r["slot_mappings"]), (3,5,3))
        self.assertEqual((r["listing_refs"],r["rfq_refs"],r["offer_refs"]), (3,2,3))
        self.assertTrue(all(c["is_synthetic"] and c["email"].endswith(".example")
                            for c in self.data["companies"]))
        values = [c["portfolio_focus"] for c in self.data["companies"]]
        self.assertEqual(values.count(self.settings["mixed_focus"]), 2)
        self.assertIn("live animal products", values)

    def test_determinism_and_identity_stability(self):
        plan = deepcopy(self.plan)
        plan["company_slots"].reverse()
        self.assertEqual(self.data, build_fixture_companies(plan,self.geo,self.settings))
        updated = deepcopy(self.settings)
        updated["role_templates"]["supplier"]["descriptors"] = ["Fictional Trade Supply"]
        rebuilt = build_fixture_companies(plan, self.geo, updated)
        self.assertEqual(self.data["slot_company_mapping"], rebuilt["slot_company_mapping"])
        self.assertNotEqual(self.data["companies"], rebuilt["companies"])
        first = self.data["slot_company_mapping"][0]
        uid = fixture_company_id(FIXTURE_NAMESPACE, plan["plan_id"], first["identity_slot_key"])
        self.assertEqual(uid, first["company_external_id"])
        added = [external_id(FIXTURE_NAMESPACE, "company_role", uid, role) for role in ("supplier","importer")]
        self.assertNotEqual(added[0], added[1])
        self.assertEqual(uid, fixture_company_id(FIXTURE_NAMESPACE, plan["plan_id"], first["identity_slot_key"]))

    def test_deterministic_collision_resolution_and_exhaustion(self):
        self.assertTrue(near_duplicate("norvexa","nervexa"))
        self.assertTrue(near_duplicate("norvexa","norvex"))
        self.settings["brand_starts"] = ["Nor","Ner","Vel","Ziv"]
        self.settings["brand_ends"] = ["vexa"]
        data = build_fixture_companies(self.plan,self.geo,self.settings)
        self.validate(data=data)
        chosen = {c["brand"] for c in data["companies"]}
        self.assertFalse({"Norvexa","Nervexa"} <= chosen)
        self.settings["brand_starts"] = ["Nor"]
        with self.assertRaisesRegex(ValueError, "collision budget"):
            build_fixture_companies(self.plan,self.geo,self.settings)

    def test_rejects_unapproved_namespace_real_plan_and_invalid_configuration(self):
        real = {**self.plan,"fixture_only":False,"plan_id":EXPECTED_PLAN}
        with self.assertRaisesRegex(ValueError, "fixture plans"):
            build_fixture_companies(real,self.geo,self.settings)
        for patch_fields in ({"fixture_namespace":str(NAMESPACE_URL)},{"status":"approved"},
                             {"approvals":{**self.settings["approvals"],"sm02_baseline":"unverified"}}):
            with self.assertRaisesRegex(ValueError, "fixture-only settings"):
                build_fixture_companies(self.plan,self.geo,{**self.settings,**patch_fields})
        with self.assertRaisesRegex(ValueError, "isolated fixture namespace"):
            fixture_company_id(str(NAMESPACE_URL),"fixture-cohort","identity-000001")
        policy = load_policy(ROOT)
        self.assertFalse(approval_state(policy,self.settings)["full_generation_guard_passed"])
        with self.assertRaisesRegex(ValueError, "blocked"):
            require_population_authorized(policy,self.settings)

    def test_validator_rejects_contacts_labels_and_allocation_changes(self):
        def rejects(edit, error):
            data = deepcopy(self.data)
            edit(data)
            with self.assertRaises(error):
                self.validate(data=data)
        rejects(lambda d: d["companies"][0].update(email="sales@somewhere.com"), ValidationError)
        rejects(lambda d: d["companies"][0].update(website="https://cmp-000001.invalid"), ValidationError)
        rejects(lambda d: d["companies"][0].update(phone="123"), ValidationError)
        rejects(lambda d: d["companies"][0].update(is_synthetic=False), ValidationError)
        rejects(lambda d: d["companies"][0].update(description="Verified manufacturer"), ValueError)
        rejects(lambda d: d["companies"][0].update(market_code=4), ValueError)
        rejects(lambda d: d["companies"][0].update(name=d["companies"][1]["name"]), ValueError)
        rejects(lambda d: d["company_roles"][0].update(role="supplier"), ValueError)
        rejects(lambda d: d["company_products"].pop(), ValueError)
        rejects(lambda d: d["company_products"].append(d["company_products"][0].copy()), ValueError)
        rejects(lambda d: d["slot_company_mapping"].pop(), ValueError)
        with self.assertRaisesRegex(ValueError, "observed role evidence"):
            self.validate(observed=lambda *_:False)
        plan = deepcopy(self.plan)
        plan["rfq_allocations"][0]["buyer_slot_id"] = "IMP-SLOT-9999"
        with self.assertRaisesRegex(ValueError, "unresolved downstream"):
            self.validate(plan=plan)

    def test_atomic_fixture_write_and_byte_identical_serialization(self):
        with tempfile.TemporaryDirectory() as work:
            file = Path(work)/"fixture.json"
            args = (self.plan,self.geo,self.settings,self.observed)
            write_validated_fixture(file,ROOT,self.data,*args)
            first = file.read_bytes()
            write_validated_fixture(file,ROOT,build_fixture_companies(*args[:-1]),*args)
            self.assertEqual(first,file.read_bytes())
            invalid = deepcopy(self.data)
            invalid["companies"][0]["email"]="sales@wrong.com"
            with self.assertRaises(ValidationError):
                write_validated_fixture(file,ROOT,invalid,*args)
            self.assertEqual(first,file.read_bytes())

    def test_source_mismatch_and_plan_artifact_hash_failure(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            def put(name,value):
                file=root/name
                file.parent.mkdir(parents=True,exist_ok=True)
                write_json(file,value)
            with patch("src.synthetic.company_stage.load_policy",return_value=load_policy(ROOT)), \
                 patch("src.synthetic.company_stage.read_templates",return_value=self.settings):
                put(MANIFEST,{"status":"validated","release_id":"wrong","dataset_fingerprint":"wrong","year":2024})
                with self.assertRaisesRegex(ValueError, "pinned Trade Intelligence manifest"):
                    inspect_inputs(root)
            policy = load_policy(ROOT)
            scenario, geo = read_json(ROOT/SCENARIO), read_json(ROOT/GEOGRAPHY)
            put(SCENARIO,scenario)
            put(GEOGRAPHY,geo)
            directory = PLANNING/"plans"/EXPECTED_PLAN
            for name in ARTIFACTS:
                put(directory/name,{})
            put(POINTER,{"planning_artifact_id": EXPECTED_PLAN,"artifact_directory":directory.as_posix(),
                         "source":policy["source"],"scenario":scenario,"planning_schema_version":"1.0.0",
                         "planning_only":True,"importable":False,"validation":{"status":"passed"},
                         "structural_feasibility":"validated_provisional",
                         "configuration_fingerprint":fingerprint(policy,scenario,geo),
                         "fixed_targets":policy["targets"],"proposed_defaults":policy["proposed_defaults"],
                         "artifacts":{name:stamped(root/directory,name) for name in ARTIFACTS}})
            put(directory/"allocation_plan.json",{"modified":True})
            with self.assertRaisesRegex(ValueError, "artifact hash or size mismatch"):
                read_planning_input(root,policy)

    def test_hierarchy_separates_populations_and_entity_types(self):
        root = FIXTURE_NAMESPACE
        a = population_namespace(root, "fixture-alpha")
        b = population_namespace(root, "fixture-beta")
        self.assertNotEqual(a, b)
        self.assertEqual(a, population_namespace(root, "fixture-alpha"))
        self.assertNotEqual(entity_namespace(a, "company"), entity_namespace(a, "company_role"))
        uid = str(hierarchical_external_id(root, "fixture-alpha", "company", "identity-000001"))
        self.assertEqual(uid, fixture_company_id(root, "fixture-alpha", "identity-000001"))
        self.assertNotEqual(uid, fixture_company_id(root, "fixture-beta", "identity-000001"))
        self.assertNotEqual(
            hierarchical_external_id(root, "fixture-alpha", "company_role", uid, "supplier"),
            hierarchical_external_id(root, "fixture-alpha", "company_role", uid, "importer"),
        )
        for key in ("SUP-SLOT-0001", "identity-000000", "identity-1"):
            with self.assertRaisesRegex(ValueError, "neutral"):
                hierarchical_external_id(root, "fixture-alpha", "company", key)
        with self.assertRaisesRegex(ValueError, "logical key"):
            hierarchical_external_id(root, "fixture-alpha", "company_product", uid, "10111")

    def test_registry_continuity_and_cross_plan_collision(self):
        registry = self.data["identity_registry"]
        plan = deepcopy(self.plan)
        plan["company_slots"].append({**plan["company_slots"][-1], "slot_id": "IMP-SLOT-0002"})
        expanded = build_fixture_companies(plan, self.geo, self.settings, registry)
        self.validate(data=expanded, plan=plan)
        by_slot = {r["originating_planning_slot_id"]: r for r in expanded["identity_registry"]}
        for record in registry:
            self.assertEqual(record, by_slot[record["originating_planning_slot_id"]])
        old = {r["external_id"] for r in registry}
        self.assertEqual(len({r["external_id"] for r in expanded["identity_registry"]} - old), 1)
        revised = {**plan, "plan_id": "fixture-revised"}
        with self.assertRaisesRegex(ValueError, "explicit identity reconciliation"):
            build_fixture_companies(revised, self.geo, self.settings, registry)
        with self.assertRaisesRegex(ValueError, "Registry belongs"):
            build_fixture_companies(plan, self.geo, self.settings, registry + [registry[0]])

    def test_stage_dependency_is_separate_from_full_generation(self):
        settings = deepcopy(self.settings)
        verification = dict.fromkeys(TECHNICAL_CHECKS, True)
        policy = load_policy(ROOT)
        settings["permanent_identity"].update(approved_root_namespace=None,
                                              root_namespace_approval_reference=None,
                                              identity_key_review_reference=None)
        with self.assertRaisesRegex(ValueError, "exact_root_namespace"):
            require_population_authorized(policy, settings, verification)
        # Test-only gate simulation. Never authorizes or generates a marketplace population.
        settings["permanent_identity"].update(
            approved_root_namespace=settings["permanent_identity"]["proposed_root_namespace"],
            root_namespace_approval_reference="test-only namespace record",
            identity_key_review_reference="test-only key review",
        )
        state = require_population_authorized(policy, settings, verification)
        self.assertEqual(state["company_population_status"], "gate_ready")
        self.assertFalse(state["full_generation_guard_passed"])
        for stage in ("SM-04", "SM-05", "SM-06", "backend_import"):
            self.assertEqual(state["stage_authorization"][stage], "unauthorized")
        with self.assertRaisesRegex(ValueError, "canonical_schema_validated"):
            require_population_authorized(policy, settings, {**verification,"canonical_schema_validated":False})
        with self.assertRaisesRegex(ValueError, "identity_config_validated"):
            require_population_authorized(policy, settings, {**verification,"identity_config_validated":False})

    def test_canonical_contacts_and_monograms(self):
        for company in self.data["companies"]:
            self.assertIsNone(company["website"])
            self.assertEqual(company["verification_status"], "not_verified")
            self.assertEqual(company["visual_identity"]["type"], "monogram")
        for address in ("sales@cmp-000001.example.com", "sales@cmp-000001.example.",
                        "sales@@cmp-000001.example"):
            broken = deepcopy(self.data)
            broken["companies"][0]["email"] = address
            with self.assertRaises(ValidationError):
                self.validate(data=broken)
        broken = deepcopy(self.data)
        broken["companies"][0]["name"] = "A" * 101
        with self.assertRaises(ValidationError):
            self.validate(data=broken)
        with self.assertRaisesRegex(ValueError, "fixture output isolation"):
            write_validated_fixture(ROOT/"data"/"fixture.json", ROOT, self.data,
                                    self.plan,self.geo,self.settings,self.observed)

    def test_context_checks_original_geography_and_product_references(self):
        catalog = {r["product_code"]: {**r, "reference_description": "Fixture product"}
                   for r in self.plan["selected_products"]}
        slot = self.plan["company_slots"][0]
        ctx = company_context(slot, catalog, self.geo, self.plan["source"])
        self.assertEqual(ctx["reference_descriptions"], ["Fixture product", "Fixture product"])
        self.assertEqual(ctx["product_codes"], slot["product_codes"])
        with self.assertRaisesRegex(ValueError, "incompatible market"):
            company_context({**slot,"market_code":8}, catalog, self.geo, self.plan["source"])
        catalog[slot["product_codes"][0]]["provisional_group"] = "prefix-99"
        with self.assertRaisesRegex(ValueError, "disagrees"):
            company_context(slot, catalog, self.geo, self.plan["source"])


if __name__ == "__main__":
    unittest.main()
