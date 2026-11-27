from copy import deepcopy
from decimal import Decimal, localcontext, ROUND_UP
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from src.analytics.release_validation import read_json
from src.pipeline import write_json
from src.synthetic.commercial_config import canonical_decimal, convert, load_config, resolve_profiles
from src.synthetic.commercial_planning import solve
from src.synthetic.commercial_remediation import (
    ALLOWED, CONFIG, CORRECTIONS, IMPLEMENTATION, RESTRICTED, REVIEW, OFFLINE, SCHEMA_PATHS, impact, implementation_binding,
    load_remediation, marketplace_availability, marketplace_eligibility, offline_rejection_case,
    proposal_binding, public_candidate_index, require_planning_scope,
)
from src.synthetic.commercial_stage import publication, read_bundle, read_inputs
from src.synthetic.company_publication import POINTER as COMPANY_POINTER
from src.synthetic.determinism import CLASSIFICATION_CONTEXT, external_id, hierarchical_external_id
from src.synthetic.listing_population_validation import (
    canonical_listing_terms, validate_for_publication, validate_population_bundle, validate_serialized,
)
from src.synthetic.listing_stage import (
    FIXTURE_NAMESPACE, FIXTURE_POPULATION, IDENTIFIERS, build_fixture, fixture_example, identifier_details,
    readiness, validate_fixture,
)
from src.synthetic.planning import fingerprint
from src.synthetic.sm04a_remediation import proposed_profiles, reconcile_identities

ROOT = Path(__file__).resolve().parents[1]


class RemediationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old,cls.allocation,_,_,_=read_inputs(ROOT,False,{})
        cls.proposal=load_remediation(ROOT,cls.allocation["selected_products"],cls.old["units"])
        cls.policies=cls.proposal["products"]
        _,directory=publication(ROOT)
        cls.bundle=read_bundle(directory)
        manifest=read_json(ROOT/COMPANY_POINTER)
        cls.company=read_json(ROOT/manifest["artifact_directory"]/"company_stage.json")

    def test_restriction_overrides_positive_stock_active_and_category_a(self):
        policy=self.policies["930400"]
        listing={"status":"active","stock":"99","product_code":"930400"}
        result=marketplace_availability(listing,policy)
        self.assertEqual(result,{"visible":False,"matching":False,"reason":"PRODUCT_RESTRICTED"})
        self.assertEqual(marketplace_eligibility(listing,{},policy,self.old["units"],"A"),"PRODUCT_RESTRICTED")
        self.assertEqual(marketplace_eligibility(listing,{},None,self.old["units"],"A"),"PRODUCT_SUITABILITY_UNRESOLVED")
        self.assertEqual(public_candidate_index([listing],self.policies),[])
        self.assertTrue(offline_rejection_case("930400",offline_test_mode=True)["offline_only"])
        with self.assertRaisesRegex(ValueError,"OFFLINE_QA_ONLY"):
            offline_rejection_case("930400")

    def test_exact_scope_projection(self):
        report=impact(self.allocation,self.bundle,self.company)
        historical=report["historical"]
        public=report["restriction_only_projection"]
        self.assertEqual((historical["products"],historical["offer_allocations"]),(300,900))
        self.assertEqual(len(report["per_restricted_product"]),len(RESTRICTED))
        self.assertEqual((public["products"],public["listing_allocations"],public["rfq_allocations"],
                          public["offer_allocations"]),(287,958,574,858))
        self.assertEqual(public["response_histogram"],{"0":116,"1":171,"2":174,"3":113})
        with self.assertRaisesRegex(ValueError,"STRUCTURAL_SCOPE_APPROVAL_REQUIRED"):
            require_planning_scope()
        self.assertIsNone(readiness(ROOT)["approval_package_fingerprint"])

    def test_form_and_measurement_policy(self):
        for code,(form,unit) in CORRECTIONS.items():
            policy=self.policies[code]
            spec=policy["specification"]
            self.assertEqual((spec["physical_form"],spec["canonical_uom"]),(form,unit))
            listing={"product_code":code,"specification_key":spec["specification_key"],"physical_form":form,
                     "unit":unit,"status":"active","stock":"40","moq":"1","quantity_increment":"1",
                     "maximum_order_quantity":None}
            request={**listing,"requested_quantity":"2"}
            self.assertTrue(marketplace_availability(listing,policy)["visible"])
            self.assertEqual(marketplace_eligibility(listing,request,policy,self.old["units"],"A"),"ELIGIBLE")
            for wrong_form in ("solid","frozen"):
                self.assertEqual(marketplace_eligibility(listing,{**request,"physical_form":wrong_form},policy,self.old["units"],"A"),
                                 "PRODUCT_SPECIFICATION_MISMATCH")
            if unit in {"PCS","M"}:
                self.assertEqual(marketplace_eligibility(listing,{**request,"unit":"SET" if unit=="PCS" else "M2"},
                                                        policy,self.old["units"],"A"),"INCOMPATIBLE_UNIT")
        self.assertEqual(self.policies["640399"]["specification"]["physical_form"],"saleable_pair")
        self.assertEqual(self.policies["481820"]["specification"]["physical_form"],"retail_pack")
        self.assertEqual(self.policies["851830"]["commercial_group"],"specialized_equipment")
        self.assertEqual(set(proposed_profiles(self.proposal,self.old,self.allocation)),set(CORRECTIONS))

    def test_shared_identifier_validation_and_preserved_ids(self):
        valid=identifier_details()
        supplier,product,_=valid["fixture_listing"]["logical_key"]
        for kind,key in (("product",(CLASSIFICATION_CONTEXT,10600)),
                         ("product",(CLASSIFICATION_CONTEXT,"10600")),
                         ("product",("wrong","010600")),
                         ("listing",(supplier,"default")),
                         ("listing",(supplier.upper(),product,"default")),
                         ("listing",(supplier,"bad","default")),
                         ("listing",(supplier,product,"other"))):
            with self.subTest(kind=kind,key=key),self.assertRaisesRegex(ValueError,"logical key"):
                hierarchical_external_id(FIXTURE_NAMESPACE,FIXTURE_POPULATION,kind,*key)
        with self.assertRaisesRegex(ValueError,"unauthorized"):
            hierarchical_external_id(IDENTIFIERS["root"],IDENTIFIERS["population"],"product",CLASSIFICATION_CONTEXT,"010600")
        with self.assertRaisesRegex(ValueError,"scoped"):
            external_id(FIXTURE_NAMESPACE,"listing",supplier,product,"default")
        actual=reconcile_identities(self.company)
        self.assertEqual((actual["company_uuids"],actual["company_roles"],actual["company_products"]),(500,500,1800))
        self.assertEqual(valid["fixture_product"]["external_id"],"cbfaeac3-71c0-52aa-b85c-d4c394cd026c")
        self.assertEqual(valid["fixture_listing"]["external_id"],"fb51050e-3b24-59e2-adae-e5a094b16411")

    def test_decimal_context_and_canonical_serialization(self):
        found=proposed_profiles(self.proposal,self.old,self.allocation)
        sample=deepcopy(self.old)
        code="220190"
        sample["products"]={code:sample["products"][code]}
        selected=[r for r in self.allocation["selected_products"] if r["product_code"]==code]
        sample_plan={
            "listing_allocations":[{"listing_id":f"fixture-listing-{i}","product_code":code,"status":"active"}
                                   for i in range(2)],
            "rfq_allocations":[{"request_id":"fixture-request","product_code":code,"response_count":2}],
            "offer_allocations":[{"offer_id":f"fixture-offer-{i}","request_id":"fixture-request",
                                   "listing_id":f"fixture-listing-{i}","product_code":code} for i in range(2)],
        }
        before=solve(sample,resolve_profiles(sample,selected),sample_plan,{})
        with localcontext() as caller:
            caller.prec=3
            caller.rounding=ROUND_UP
            self.assertEqual(found,proposed_profiles(self.proposal,self.old,self.allocation))
            for rows in sample_plan.values():
                rows.reverse()
            self.assertEqual(before,solve(sample,resolve_profiles(sample,selected),sample_plan,{}))
            self.assertEqual(convert("0.001","TONNE","KG",self.old["units"],["TONNE","KG"]),Decimal("1"))
            self.assertEqual(canonical_decimal("12345.00",2),Decimal("12345"))
        for value in ("NaN","Infinity","1e2","+1.00","01.00","1.0","1.000","-0","0.00","1.001"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                canonical_decimal(value,2,allow_zero_stock=True)
        self.assertEqual(canonical_decimal("0",2,allow_zero_stock=True),Decimal(0))

    def test_implementation_bound_dependencies_invalidate(self):
        with TemporaryDirectory() as tmp:
            temp=Path(tmp)
            for name in IMPLEMENTATION:
                (temp/name).parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/name,temp/name)
            baseline=implementation_binding(temp)
            for name in ("src/synthetic/determinism.py","src/synthetic/listing_population_validation.py"):
                path=temp/name
                original=path.read_bytes()
                path.write_bytes(original+b"\n# changed\n")
                self.assertNotEqual(implementation_binding(temp)["fingerprint"],baseline["fingerprint"])
                path.write_bytes(original)

    def test_configuration_schema_policy_and_specification_invalidate(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in (CONFIG,*SCHEMA_PATHS):
                (root/name).parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/name,root/name)
            exact=proposal_binding(root,self.old,self.proposal)
            for name in (CONFIG,*SCHEMA_PATHS):
                path=root/name
                old=path.read_bytes()
                path.write_bytes(old+b"\n")
                self.assertNotEqual(proposal_binding(root,self.old,self.proposal),exact)
                path.write_bytes(old)
            changed=deepcopy(self.proposal)
            changed["products"]["220190"]["disposition"]=REVIEW
            self.assertNotEqual(proposal_binding(root,self.old,changed)["product_suitability_fingerprint"],
                                exact["product_suitability_fingerprint"])
            changed["products"]["220190"]["specification"]["physical_form"]="standalone_item"
            self.assertNotEqual(proposal_binding(root,self.old,changed)["commercial_specifications_fingerprint"],
                                exact["commercial_specifications_fingerprint"])

    def test_registry_retired_reservations_and_retained_codes(self):
        fixture=fixture_example()
        start=build_fixture(fixture)
        retired={**start["identity_registry"][0],"identity_status":"retired"}
        revised=deepcopy(fixture)
        revised["listings"][0].update(listing_id="fixture-appended",product_code="010601")
        revised["profiles"][0]["product_code"]="010601"
        revised["suppliers"][0]["associations"]["010601"]=revised["suppliers"][0]["associations"]["010600"]
        new=build_fixture(revised,[retired])
        self.assertEqual(new["listings"][0]["display_code"],"LST-000002")
        self.assertIn(retired,new["identity_registry"])
        validate_fixture(ROOT,new,revised)
        with self.assertRaisesRegex(ValueError,"retired"):
            build_fixture(fixture,[retired])
        revised["metadata"]["plan_id"]="fixture-different"
        with self.assertRaisesRegex(ValueError,"identity scope"):
            build_fixture(revised,[retired])


def population_fixture(products=2, supplier_count=2, listing_count=4):
    scope={"fixture_only":True,"root_namespace":FIXTURE_NAMESPACE,"population_id":FIXTURE_POPULATION,
           "plan_id":"fixture-commercial","configuration_fingerprint":fingerprint("test fixture"),
           "configuration_version":"1.1.0","structural_plan_id":"fixture-structural",
           "company_stage_id":"fixture-company","source_release":"fixture-source",
           "product_count":products,"listing_count":listing_count}
    meta={k:scope[k] for k in ("fixture_only","population_id","plan_id","configuration_fingerprint")}
    result={"metadata":{**meta,"version":"1.1.0","is_synthetic":True,"is_intermediate":True,
                         "backend_importable":False,"full_marketplace_release":False},"products":[],"listings":[],
             "planning_to_listing":[],"identity_registry":[]}
    catalog,policies,allocation,commercial=[],{},[],[]
    company={k:[] for k in ("companies","company_roles","company_products","slot_company_mapping")}
    def simple(entity,value):
        return str(external_id(FIXTURE_NAMESPACE,entity,value))
    def hierarchy(entity,*key):
        return str(hierarchical_external_id(FIXTURE_NAMESPACE,FIXTURE_POPULATION,entity,*key))
    for i in range(products):
        code=f"{10000+i:06d}"
        desc=f"Fictional reference {code}"
        catalog.append({"product_code":code,"reference_description":desc})
        spec=f"fixture-{code}"
        policies[code]={"disposition":ALLOWED,"offline_qa_only":False,"specification":{
            "specification_key":spec,"physical_form":"standalone_item","canonical_uom":"PCS","allowed_uoms":["PCS"]}}
        result["products"].append({"external_id":hierarchy("product",CLASSIFICATION_CONTEXT,code),
            "source_product_code":code,"reference_description":desc,"classification_context":CLASSIFICATION_CONTEXT,
            "specification_key":spec,"physical_form":"standalone_item","unit":"PCS","suitability":ALLOWED,"is_synthetic":True})
    for i in range(supplier_count):
        supplier=simple("fixture-supplier",str(i))
        role=simple("fixture-role",str(i))
        company["companies"].append({"external_id":supplier,"market_code":840})
        company["company_roles"].append({"external_id":role,"company_external_id":supplier,"role":"supplier"})
        company["slot_company_mapping"].append({"planning_slot_id":f"fixture-slot-{i}","initial_role":"supplier",
            "role_external_id":role,"company_external_id":supplier,"market_code":840,"product_codes":[]})
    units={"PCS":{"precision":0}}
    for n in range(listing_count):
        product=result["products"][n%products]
        slot=company["slot_company_mapping"][(n//products)%supplier_count]
        code=product["source_product_code"]
        sid=slot["company_external_id"]
        slot["product_codes"].append(code)
        assoc=simple("fixture-assoc",str(n))
        company["company_products"].append({"external_id":assoc,"company_external_id":sid,
            "role_external_id":slot["role_external_id"],"source_product_code":code,"source_market_code":840,
            "observed_role":"exporter"})
        ref=f"fixture-{n:06d}"
        struct={"listing_id":ref,"supplier_slot_id":slot["planning_slot_id"],"product_code":code,"status":"active"}
        allocation.append(struct)
        terms=canonical_listing_terms({"price":{"amount":"10","currency":"USD","basis_quantity":"1","basis_unit":"PCS"},
                "unit":"PCS","stock":"20","moq":"2","quantity_increment":"1","maximum_order_quantity":None,
                "status":"active"},units)
        spec={"specification_key":product["specification_key"],"physical_form":"standalone_item"}
        commercial.append({**struct,**terms,**spec})
        key=[sid,product["external_id"],"default"]
        uid=hierarchy("listing",*key)
        identity={"external_id":uid,"logical_key":key,"display_code":f"LST-{n+1:06d}",
                  "population_id":FIXTURE_POPULATION,"supplier_external_id":sid,"product_external_id":key[1],"variant":"default"}
        result["listings"].append({**identity,**terms,**spec,"suitability":ALLOWED,"source_product_code":code,
            "supplier_role_external_id":slot["role_external_id"],"supplier_product_association_external_id":assoc,
            "market_code":840,"title":"Fixture only","description":"Synthetic demo fixture.","language":"en","image":None,
            "tags":[],"pricing_provenance":"synthetic","quantity_provenance":"synthetic","is_synthetic":True,
            "planning_listing_id":ref,"provenance":{
                "source_release":scope["source_release"],"structural_plan_id":scope["structural_plan_id"],
                "company_stage_id":scope["company_stage_id"],"commercial_plan_id":scope["plan_id"],
                "configuration_fingerprint":scope["configuration_fingerprint"],"configuration_version":"1.1.0"}})
        result["planning_to_listing"].append({"planning_listing_id":ref,"listing_external_id":uid,
                                              "display_code":identity["display_code"]})
        result["identity_registry"].append({**identity,"originating_plan_id":scope["plan_id"],
                                           "originating_planning_listing_id":ref,"identity_status":"active"})
    commercial_profiles=[{"product_code":r["product_code"],"stock_bounds":["5","30"],"moq_bounds":["1","10"],
        "price_bounds":["5","20"],"reference_price":"10","price_variation":{"listing":["-0.20","0.20"]},
        "measurement_unit":"PCS","quantity_increment":"1","maximum_order_quantity":None} for r in catalog]
    return result,dict(scope=scope,catalog=catalog,policies=policies,company=company,allocation=allocation,
                       commercial=commercial,commercial_profiles=commercial_profiles,units=units)


class PopulationValidatorTests(unittest.TestCase):
    def test_production_shaped_fixture_at_representative_scale(self):
        data,context=population_fixture(300,4,1000)
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fixture.json"
            replay=Path(tmp)/"replay.json"
            write_json(path,data)
            write_json(replay,population_fixture(300,4,1000)[0])
            self.assertEqual(path.read_bytes(),replay.read_bytes())
            self.assertEqual(validate_serialized(ROOT,path,**context)["listings"],1000)
            with self.assertRaisesRegex(ValueError,"STRUCTURAL_SCOPE_APPROVAL_REQUIRED"):
                validate_for_publication(ROOT,path,**context)

    def test_production_shaped_adversarial_tampering(self):
        original,expected=population_fixture()
        cases=(
            ("listings","product_external_id",original["products"][1]["external_id"]),
            ("listings","supplier_external_id",original["listings"][2]["supplier_external_id"]),
            ("listings","supplier_role_external_id",original["listings"][2]["supplier_role_external_id"]),
            ("listings","supplier_product_association_external_id",original["listings"][1]["supplier_product_association_external_id"]),
            ("listings","external_id",original["listings"][1]["external_id"]),
            ("listings","display_code",original["listings"][1]["display_code"]),
            ("listings","logical_key",original["listings"][1]["logical_key"]),
            ("listings","stock","19"),
            ("listings","specification_key","tampered"),
            ("listings","planning_listing_id","incorrect"),
            ("planning_to_listing","planning_listing_id",original["planning_to_listing"][1]["planning_listing_id"]),
            ("identity_registry","display_code","LST-000777"),
        )
        for group,field,value in cases:
            with self.subTest(group=group,field=field):
                changed=deepcopy(original)
                changed[group][0][field]=value
                with self.assertRaises(ValueError):
                    validate_population_bundle(ROOT,changed,**expected)
        for group in ("listings","planning_to_listing"):
            changed=deepcopy(original)
            changed[group].pop()
            with self.assertRaisesRegex(ValueError,"CARDINALITY"):
                validate_population_bundle(ROOT,changed,**expected)
        restricted=deepcopy(expected)
        restricted["policies"]["010000"]["disposition"]=OFFLINE
        with self.assertRaisesRegex(ValueError,"PRODUCT_RESTRICTED"):
            validate_population_bundle(ROOT,original,**restricted)

    def test_production_shape_accepts_reordered_input(self):
        original,expected=population_fixture()
        reordered=deepcopy(original)
        for key in ("products","listings","planning_to_listing","identity_registry"):
            reordered[key].reverse()
        self.assertEqual(validate_population_bundle(ROOT,reordered,**expected),
                         validate_population_bundle(ROOT,original,**expected))
