from copy import deepcopy
from decimal import localcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.analytics.release import stamped
from src.synthetic.commercial_remediation import ALLOWED, OFFLINE, RESTRICTED
from src.synthetic.listing_stage import readiness
from src.synthetic.marketplace_scope import build_projection, coverage, membership, proposed_configuration, read_decisions
from src.synthetic.marketplace_scope_validation import (
    PACKAGE_METHOD, planning_inputs, require_exact_approval, solve_for_approved_scope, validate_projection,
)
from src.synthetic.planning import fingerprint
from src.synthetic.sm04a_scope import ARTIFACTS, construct, load_inputs, package_for

ROOT=Path(__file__).resolve().parents[1]


def exact_fixture_receipt(package):
    return {"package_fingerprint":fingerprint(PACKAGE_METHOD,package),"scope_id":package["scope_id"],
            "eligible_codes_fingerprint":package["eligible_codes_fingerprint"],
            "specification_fingerprint":package["specification_fingerprint"],
            "configuration_fingerprint":package["configuration_fingerprint"],
            "coverage_fingerprint":package["coverage_fingerprint"],
            "authorize":"corrected_provisional_commercial_planning_only","authority":"isolated test evidence"}


class ScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs=load_inputs(ROOT)
        cls.base,cls.remediation,cls.allocation,cls.company,cls.historical,cls.bindings,cls.observed=cls.inputs
        with TemporaryDirectory() as temp:
            d=Path(temp)
            cls.config,cls.scope,cls.diagnostics,cls.review,_=construct(ROOT,d,cls.inputs)
            files={name:stamped(d,name) for name in sorted(ARTIFACTS)}
            cls.package=package_for(ROOT,files,cls.config,cls.scope,cls.diagnostics,cls.historical)

    def test_exact_review_coverage_and_closed_dispositions(self):
        self.assertEqual(len(self.review["profiles"]),47)
        included,offline,unresolved=membership(self.config)
        self.assertEqual(offline,RESTRICTED)
        self.assertEqual((len(included),len(unresolved)),(279,8))
        self.assertTrue(all(self.config["products"][k]["commercial_terms"] is None for k in offline|unresolved))
        self.assertEqual({p["source_product_code"] for p in self.review["profiles"]},
                         {k for k,p in self.remediation["products"].items() if p["disposition"]=="review_required"})
        self.assertTrue(all(p["recommendation"] and p["remaining_uncertainty"] and not p["approved"]
                            for p in self.review["profiles"]))

    def test_exact_scope_counts_and_safe_coverage(self):
        counts=self.diagnostics["scope_counts"]
        self.assertEqual((counts["historical"]["products"],counts["historical"]["offers"]),(300,900))
        self.assertEqual((counts["proposed"]["listings"],counts["proposed"]["rfqs"],counts["proposed"]["offers"]),
                         (932,558,835))
        self.assertEqual(self.diagnostics["exceptions"]["proposed"]["importers_without_rfq"],
                         [{"slot_id":"IMP-SLOT-0043","display_code":"CMP-000043"}])
        self.assertTrue(all(not v for v in self.diagnostics["additional_exceptions"].values()))
        self.assertEqual(self.diagnostics["competition_scenarios_below_ceiling"],8)

    def test_retain_status_targets_responses_and_reject_mutation(self):
        for key, field in (("listings","status"),("rfqs","response_count"),("offers","supplier_slot_id")):
            data=deepcopy(self.scope)
            data[key][0][field]="changed"
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,"SCOPE_RELATIONSHIP_MISMATCH"):
                validate_projection(ROOT,data,self.diagnostics,self.allocation,self.company,self.config,
                                    self.bindings,self.observed)
        data=deepcopy(self.scope)
        data["included_product_codes"][0]="999999"
        with self.assertRaisesRegex(ValueError,"SCOPE_MEMBERSHIP_MISMATCH"):
            validate_projection(ROOT,data,self.diagnostics,self.allocation,self.company,self.config,
                                self.bindings,self.observed)
        data=deepcopy(self.scope)
        data["offers"].append(data["offers"][0])
        with self.assertRaises(ValueError):
            validate_projection(ROOT,data,self.diagnostics,self.allocation,self.company,self.config,
                                self.bindings,self.observed)

    def test_ceiling_and_invalid_measurement_fail_closed(self):
        config=deepcopy(self.config)
        code=next(iter(RESTRICTED))
        config["products"][code]["disposition"]="new_proposal"
        with self.assertRaisesRegex(ValueError,"SCOPE_MEMBERSHIP_MISMATCH"):
            membership(config)
        proposal=deepcopy(self.remediation)
        proposal["products"]["220190"]["specification"]["allowed_uoms"].append("KG")
        decisions=read_decisions(ROOT,self.remediation)
        with self.assertRaisesRegex(ValueError,"INCOMPATIBLE_SCOPE_SPECIFICATION"):
            proposed_configuration(self.base,proposal,decisions,self.allocation["selected_products"])

    def test_order_and_caller_context_do_not_change_result(self):
        original=deepcopy(self.allocation)
        for key in ("selected_products","company_slots","listing_allocations","rfq_allocations","offer_allocations"):
            original[key].reverse()
        decisions=read_decisions(ROOT,self.remediation)
        with localcontext() as context:
            context.prec=3
            self.assertEqual(proposed_configuration(self.base,self.remediation,decisions,original["selected_products"]),
                             self.config)
        self.assertEqual(build_projection(original,self.company,self.config,self.bindings),self.scope)
        self.assertEqual(coverage(original,self.company,self.config),self.diagnostics)

    def test_strategy_receipt_and_changed_approval_bindings_are_rejected(self):
        p=self.package
        with self.assertRaisesRegex(ValueError,"EXACT_SCOPE_APPROVAL_REQUIRED"):
            planning_inputs(p,{"strategy":"adaptive_scope_option_d","ceiling":287},self.scope,self.config,self.diagnostics)
        approval=exact_fixture_receipt(p)
        self.assertEqual(require_exact_approval(p,approval),approval["package_fingerprint"])
        for field in ("eligible_codes_fingerprint","configuration_fingerprint","specification_fingerprint","coverage_fingerprint"):
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"EXACT_SCOPE_APPROVAL_REQUIRED"):
                require_exact_approval({**p,field:"changed"},approval)
        scope=deepcopy(self.scope)
        scope["listings"].pop()
        with self.assertRaisesRegex(ValueError,"EXACT_SCOPE_BINDING_CHANGED"):
            planning_inputs(p,approval,scope,self.config,self.diagnostics)
        self.assertEqual(readiness(ROOT)["status"],"blocked")
        self.assertEqual(readiness(ROOT)["sm05"],"blocked")
        self.assertEqual(readiness(ROOT)["backend_import"],"blocked")

    def test_independent_scope_builds_are_byte_identical(self):
        with TemporaryDirectory() as a,TemporaryDirectory() as b:
            for d in (Path(a),Path(b)):
                construct(ROOT,d,self.inputs)
            for name in ARTIFACTS:
                self.assertEqual((Path(a)/name).read_bytes(),(Path(b)/name).read_bytes())


class ScopeFixturePlannerTests(unittest.TestCase):
    def test_shared_solver_uses_approved_fixture_counts_only(self):
        code="000012"
        spec={"specification_key":"fixture-demo-length","physical_form":"length_material"}
        terms={"product_code":code,"measurement_unit":"M","permitted_units":["M"],"reference_price":"10",
               "price_bounds":["5","15"],"price_variation":{"listing":["-0.20","0.20"],"rfq":["-0.15","0.10"],
               "offer":["-0.10","0.05"]},"quoted_price_precision":2,"currency":"USD","price_basis_quantity":"1",
               "price_basis_unit":"M","stock_bounds":["10","50"],"moq_bounds":["1","3"],"rfq_quantity_bounds":["3","6"],
               "maximum_order_quantity":None,"quantity_precision":3,"quantity_increment":"0.5"}
        config={"master_seed":42,"unit_registry":{"M":{"precision":3,"factor":"1","dimension":"length"}},
                "products":{**{p:{"disposition":"offline_only","suitability":OFFLINE,"exact_approval":False}
                               for p in RESTRICTED},
                            code:{"disposition":"new_proposal","suitability":ALLOWED,"exact_approval":False,
                                  "specification":spec,"commercial_terms":terms}}}
        scope={"included_product_codes":[code],"counts":{"listings":1,"rfqs":1,"offers":1},
               "listings":[{"listing_id":"fixture-L","status":"active","product_code":code}],
               "rfqs":[{"request_id":"fixture-R","response_count":1,"product_code":code}],
               "offers":[{"offer_id":"fixture-O","request_id":"fixture-R","listing_id":"fixture-L",
                          "product_code":code,"category":"A"}]}
        scope={"scope_id":"sm04as-"+fingerprint("scope-projection-v1",scope).split(":")[1],**scope}
        diagnostics={"fixture":True}
        package={"scope_id":scope["scope_id"],"eligible_codes_fingerprint":fingerprint([code]),
                 "specification_fingerprint":fingerprint({code:spec}),"configuration_fingerprint":fingerprint(config),
                 "coverage_fingerprint":fingerprint(diagnostics),"proposed_inactive_zero":0}
        result,_=solve_for_approved_scope(package,exact_fixture_receipt(package),scope,config,diagnostics)
        self.assertEqual(len(result["offers"]),1)
        self.assertEqual(result["offers"][0]["offered_quantity"],result["rfqs"][0]["requested_quantity"])
        self.assertEqual(result["offers"][0]["specification_key"],"fixture-demo-length")
        self.assertEqual(result["listings"][0]["price"]["basis_quantity"],"1.000")
