from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from jsonschema import ValidationError

from src.analytics.release import stamped
from src.pipeline import write_json
from src.synthetic.commercial_config import (
    FLAGS, convert, extended, load_config, normalized_price, price_domain, quantity_ticks, resolve_profiles,
)
from src.synthetic.commercial_planning import (
    basic_availability, common_interval, eligibility, price_record, solve,
)
from src.synthetic.commercial_stage import BASE, FILES, NEEDED, POINTER, QUALITY, REVIEW, VALIDATION, publication, read_inputs
from src.synthetic.commercial_validation import validate_plan
from src.synthetic.company_publication import commit_stage
from src.synthetic.listing_stage import (
    IDENTIFIERS, build_fixture, fixture_example, fixture_id, readiness, validate_fixture, write_fixture,
)
from src.synthetic.planning import fingerprint

ROOT = Path(__file__).resolve().parents[1]


class CommercialFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT)

    def test_exact_conversion_and_price_basis(self):
        units = self.config["units"]
        allowed = ["G","KG","TONNE"]
        self.assertEqual(convert("0.001","TONNE","KG",units,allowed),Decimal("1"))
        a = {"amount":"4.00","currency":"USD","basis_quantity":"1","basis_unit":"KG"}
        b = {**a,"amount":"2.00","basis_quantity":"500","basis_unit":"G"}
        self.assertEqual(normalized_price(a,"KG",units,allowed),normalized_price(b,"KG",units,allowed))
        self.assertEqual(extended(a,"0.12625","KG",units,allowed,2),"0.51")
        with self.assertRaisesRegex(ValueError,"INCOMPATIBLE_UOM"):
            convert("1","L","KG",units,["KG","L"])
        with self.assertRaisesRegex(ValueError,"INVALID_QUANTITY_PRECISION"):
            convert("0.000001","KG","G",units,allowed)

    def test_ticks_and_common_lattice(self):
        self.assertEqual(quantity_ticks("0.125",3),125)
        with self.assertRaisesRegex(ValueError,"INVALID_QUANTITY_PRECISION"):
            quantity_ticks("1.5",0)
        self.assertEqual(common_interval([(7,16),(9,20)],[4,6]),(1,1,12))
        self.assertEqual(common_interval([(13,15),(6,18)],[4,6]),(2,1,12))
        self.assertEqual(price_domain(["0.03","0.09"],Decimal("0.035"),["0","0"],2),(4,3))

    def test_fixture_identifiers_preserve_codes_and_mutable_fields(self):
        fixture = fixture_example()
        first = build_fixture(fixture)
        self.assertEqual(validate_fixture(ROOT,first,fixture)["listings"],1)
        listing = fixture["listings"][0]
        listing.update(status="inactive",stock="0",price={**listing["price"],"amount":"15.00"})
        revised = build_fixture(fixture,first["identity_registry"])
        self.assertEqual(revised["identity_registry"],first["identity_registry"])
        self.assertEqual(revised["listings"][0]["source_product_code"],"010600")
        self.assertEqual(revised["listings"][0]["external_id"],first["listings"][0]["external_id"])
        validate_fixture(ROOT,revised,fixture)
        with self.assertRaisesRegex(ValueError,"UNAPPROVED_IDENTIFIER_SPECIFICATION"):
            fixture_id("product",IDENTIFIERS["classification_context"],"010600",root=IDENTIFIERS["root"])
        with self.assertRaisesRegex(ValueError,"INVALID_IDENTIFIER_KEY"):
            fixture_id("product",IDENTIFIERS["classification_context"],"10600")
        broken = deepcopy(revised)
        broken["identity_registry"][0]["identity_status"] = "retired"
        with self.assertRaisesRegex(ValueError,"registry"):
            validate_fixture(ROOT,broken,fixture)

    def test_fixture_serialization_and_duplicate_rejection(self):
        fixture = fixture_example()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"listing_fixture.json"
            write_fixture(path,ROOT,fixture)
            before = path.read_bytes()
            fixture["listings"].append({**fixture["listings"][0],"listing_id":"fixture-duplicate"})
            with self.assertRaisesRegex(ValueError,"DUPLICATE_IDENTIFIER"):
                write_fixture(path,ROOT,fixture)
            self.assertEqual(path.read_bytes(),before)

    def test_status_and_commercial_eligibility(self):
        profile = {"measurement_unit":"KG","permitted_units":["KG"]}
        listing = {"product_code":"010600","status":"active","stock":"10","moq":"2","quantity_increment":"2",
                   "maximum_order_quantity":"8"}
        request = {"product_code":"010600","unit":"KG","requested_quantity":"4"}
        self.assertEqual(eligibility(listing,request,profile,self.config["units"],"A"),"ELIGIBLE")
        for stock,status,expected in (("0","out_of_stock","OUT_OF_STOCK"),("4","inactive","LISTING_NOT_ACTIVE")):
            self.assertFalse(basic_availability(status,Decimal(stock))["matching"])
            self.assertEqual(eligibility({**listing,"stock":stock,"status":status},request,
                                         profile,self.config["units"],"A"),expected)
        self.assertEqual(eligibility(listing,{**request,"requested_quantity":"5"},profile,
                                     self.config["units"],"A"),"INVALID_QUANTITY_INCREMENT")
        with self.assertRaisesRegex(ValueError,"STATUS_CONFLICT"):
            basic_availability("out_of_stock",Decimal("1"))

    def test_authorization_and_full_generation_guard(self):
        status = readiness(ROOT)
        for key in ("status","sm05","sm06","backend_import","full_marketplace"):
            self.assertEqual(status[key],"blocked")
        command = subprocess.run([sys.executable,"-m","src.synthetic.listing_stage","generate"],
                                 cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(command.returncode,1)
        self.assertIn("SM04B_NOT_AUTHORIZED",command.stderr)

    def test_failed_publication_preserves_previous_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            pointer = directory/"commercial_plan_manifest.json"
            write_json(pointer,{"existing":True})
            before = pointer.read_bytes()
            candidate = directory/"candidate"
            target = directory/"target"
            candidate.mkdir()
            target.mkdir()
            write_json(candidate/"artifact.json",{"valid":True})
            write_json(target/"artifact.json",{"tampered":True})
            with self.assertRaisesRegex(ValueError,"artifact hashes"):
                commit_stage(target,candidate,pointer,{"artifacts":{"artifact.json":stamped(candidate,"artifact.json")}})
            self.assertEqual(pointer.read_bytes(),before)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            candidate = root/"candidate"
            candidate.mkdir()
            names = (*FILES.values(), REVIEW, QUALITY, VALIDATION)
            for name in names:
                write_json(candidate/name,{"fixture":True})
            artifacts = {name:stamped(candidate,name) for name in names}
            plan_id = "sm04a-"+fingerprint(artifacts).split(":")[1]
            relative = BASE/"plans"/plan_id
            (root/relative).parent.mkdir(parents=True)
            candidate.rename(root/relative)
            manifest = {**FLAGS,"artifacts":artifacts,"commercial_plan_id":plan_id,
                        "artifact_directory":relative.as_posix(),"status":"validated_provisional",
                        "exact_approvals":NEEDED}
            write_json(root/POINTER,manifest)
            self.assertEqual(publication(root)[0]["commercial_plan_id"],plan_id)
            write_json(root/POINTER,{**manifest,"backend_importable":True})
            with self.assertRaisesRegex(ValueError,"approval flags"):
                publication(root)

    def test_bounded_price_fallback(self):
        profile = {"product_code":"010600","quoted_price_precision":2,"price_bounds":["0.01","0.99"],
                   "price_variation":{"listing":["0","1"],"offer":["0.5","0.5"]},"currency":"USD",
                   "price_basis_quantity":"1","price_basis_unit":"PCS"}
        effort = {"search_nodes":0}
        for number in range(10):
            quote = price_record(self.config,profile,"listing",str(number),Decimal("0.10"),linked_offer=True,effort=effort)
            self.assertEqual(int(Decimal(quote["amount"])*100)%2,0)
        self.assertGreater(effort["search_nodes"],0)


class CommercialAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, cls.plan, _, cls.bindings, _ = read_inputs(ROOT,False,{})
        cls.profiles = resolve_profiles(cls.config,cls.plan["selected_products"])
        cls.result = {**solve(cls.config,cls.profiles,cls.plan,{}),"profiles":cls.profiles,
                      "metadata":{**FLAGS,"schema_version":"1.0.0","bindings":cls.bindings}}
        products = {p["product_code"]:SimpleNamespace(exports=set(),imports=set()) for p in cls.profiles}
        market = {}
        for slot in cls.plan["company_slots"]:
            sid, code = slot["slot_id"], slot["market_code"]
            market[sid] = code
            for product in slot["product_codes"]:
                evidence = products[product]
                (evidence.exports if slot["role"] == "supplier" else evidence.imports).add(code)
        requests = {r["request_id"]:r for r in cls.plan["rfq_allocations"]}
        bilateral = {(r["product_code"],market[r["target_supplier_slot_id"]],r["destination_market"])
                     for r in requests.values() if r["type"] == "targeted"}
        bilateral.update((r["product_code"],market[r["supplier_slot_id"]],requests[r["request_id"]]["destination_market"])
                         for r in cls.plan["offer_allocations"])
        cls.engine = SimpleNamespace(products=products,lookup_relationship=lambda p,e,i:
                                     {"category":"A" if (p,e,i) in bilateral else "B"})

    def validate(self,data):
        return validate_plan(ROOT,data,self.config,self.profiles,self.plan,self.bindings,self.engine)

    def test_complete_plan_invariants_and_independent_inventory(self):
        output = self.validate(self.result)
        self.assertEqual(output["full_fulfillment_responses"],900)
        self.assertEqual(output["response_histogram"]["0"],120)
        self.assertEqual(output["competitive_rfqs"],300)
        self.assertEqual(output["bilateral_records"],{"A":1080,"B":0,"C":0})
        changed = deepcopy(self.plan)
        for collection in ("listing_allocations","rfq_allocations","offer_allocations"):
            changed[collection].reverse()
        self.assertEqual(solve(self.config,self.profiles,changed,{}),
                         {k:self.result[k] for k in ("listings","rfqs","offers")})
        totals = {}
        for offer in self.result["offers"]:
            totals[offer["listing_id"]] = totals.get(offer["listing_id"],Decimal(0)) + Decimal(offer["offered_quantity"])
        self.assertTrue(any(Decimal(l["stock"]) < totals[l["listing_id"]] for l in self.result["listings"]
                            if l["listing_id"] in totals))

    def test_tampering_is_rejected(self):
        for section,field,value,error in (
            ("offers","extended_product_value","0.00","EXTENDED_VALUE_MISMATCH"),
            ("rfqs","buyer_slot_id","wrong","ALLOCATION_MISMATCH"),
            ("offers","category","B",ValidationError),
            ("listings","status","inactive","ALLOCATION_MISMATCH"),
        ):
            with self.subTest(section=section,field=field):
                changed = deepcopy(self.result)
                changed[section][0][field] = value
                if error is ValidationError:
                    with self.assertRaises(ValidationError):
                        self.validate(changed)
                else:
                    with self.assertRaisesRegex(ValueError,error):
                        self.validate(changed)
        changed = deepcopy(self.result)
        changed["listings"][0]["price"]["amount"] = "0.0001"
        with self.assertRaisesRegex(ValueError,"PRICE_DOMAIN_CONFLICT"):
            self.validate(changed)
        changed = deepcopy(self.result)
        changed["metadata"]["bindings"]["configuration_fingerprint"] = "tampered"
        with self.assertRaisesRegex(ValueError,"provenance"):
            self.validate(changed)

    def test_profile_precedence_and_missing_codes(self):
        config = deepcopy(self.config)
        selected = self.plan["selected_products"]
        config["products"]["010600"]["parameters"] = {"stock":["13","80"]}
        profiles = {p["product_code"]:p for p in resolve_profiles(config,selected)}
        self.assertEqual(profiles["010600"]["stock_bounds"],["13","80"])
        self.assertEqual(profiles["010600"]["reference_price"],"55")
        config["products"]["010600"]["reference_price"] = "0"
        with self.assertRaisesRegex(ValueError,"PRICE_DOMAIN_CONFLICT"):
            resolve_profiles(config,selected)
        del config["products"]["010600"]
        with self.assertRaisesRegex(ValueError,"UNRESOLVED_PRODUCT_PROFILE"):
            resolve_profiles(config,selected)
