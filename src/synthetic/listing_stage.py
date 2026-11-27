"""Proposed listing contract and deterministic identities for isolated fixtures only."""
import argparse
import json
from pathlib import Path
import re
import tempfile

from jsonschema.exceptions import ValidationError

from src.analytics.release_validation import read_json, schema_validator, unique_index
from src.pipeline import write_json
from src.synthetic.commercial_config import APPROVALS, PRODUCT, CommercialError, dec, load_config, require
from src.synthetic.commercial_planning import basic_availability
from src.synthetic.determinism import (
    LISTING_FIXTURE_POPULATION, LISTING_FIXTURE_ROOT, display_code, external_id, hierarchical_external_id,
)
from src.synthetic.foundation import load_policy, require_generation_ready
from src.synthetic.planning import fingerprint

FIXTURE_NAMESPACE = LISTING_FIXTURE_ROOT
FIXTURE_POPULATION = LISTING_FIXTURE_POPULATION
UUID5 = re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-5[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}")
IDENTIFIERS = {
    "status":"proposed", "version":"1.0.0", "algorithm":"hierarchical_uuid5_v1",
    "root":"9e5fdfc5-2675-57fe-8e94-81dc91ed9639", "population":"globiq-marketplace-baseline-001",
    "product_entity":"product","listing_entity":"listing","classification_context":"globiq-trade-reference-2024-v1",
    "product_logical_key":["classification_context","normalized_source_product_code"],
    "listing_logical_key":["supplier_external_uuid","product_external_uuid","variant"],
    "initial_variant":"default", "variant_pattern":"[a-z][a-z0-9-]{0,39}", "display_prefix":"LST",
    "text_encoding":"NFC strings inside compact UTF-8 ordered JSON arrays",
    "code_encoding":"ASCII six digits or literal 9999AA, leading zeros preserved",
    "classification_revision":"unverified; version the source context if its code semantics change",
    "continuity":"Existing classification context persists across releases with identical code semantics. Explicit migration for changed semantics.",
    "display_allocation":"Allocate by sorted original planning reference, retain issued codes in registry and never recycle them.",
    "retirement":"Registry reservations survive retirement. Reactivation requires explicit review of the same logical listing.",
}


def fixture_id(entity, *key, root=FIXTURE_NAMESPACE, population=FIXTURE_POPULATION):
    require(root == FIXTURE_NAMESPACE and population == FIXTURE_POPULATION,
            "UNAPPROVED_IDENTIFIER_SPECIFICATION", "only isolated fixture identifiers are permitted")
    if entity == "product":
        valid = len(key) == 2 and key[0] == IDENTIFIERS["classification_context"] and isinstance(key[1], str) and PRODUCT.fullmatch(key[1])
    else:
        valid = entity == "listing" and len(key) == 3 and all(isinstance(x,str) and UUID5.fullmatch(x) for x in key[:2]) and (
            isinstance(key[2],str) and re.fullmatch(IDENTIFIERS["variant_pattern"], key[2]))
    require(valid, "INVALID_IDENTIFIER_KEY", entity)
    try:
        return str(hierarchical_external_id(root,population,entity,*key))
    except ValueError as error:
        raise CommercialError("INVALID_IDENTIFIER_KEY",str(error)) from error


def identifier_details():
    context = IDENTIFIERS["classification_context"]
    product = fixture_id("product",context,"010600")
    supplier = str(external_id(FIXTURE_NAMESPACE,"fixture_supplier","example"))
    listing = fixture_id("listing",supplier,product,"default")
    return {**IDENTIFIERS,"fingerprint":fingerprint(IDENTIFIERS),"fixture_namespace":FIXTURE_NAMESPACE,
            "fixture_product":{"logical_key":[context,"010600"],"external_id":product},
            "fixture_listing":{"logical_key":[supplier,product,"default"],"external_id":listing,"display_code":"LST-000001"}}


def fixture_scope(fixture):
    require(fixture["metadata"]["fixture_only"] is True
            and fixture["metadata"]["plan_id"].startswith("fixture-")
            and all(fixture["metadata"][k].startswith("fixture-") for k in ("source_release","structural_plan_id","company_stage_id"))
            and 0 < len(fixture["listings"]) <= 12
            and all(r["listing_id"].startswith("fixture-") for r in fixture["listings"]),
            "INVALID_FIXTURE_SCOPE", "only isolated fixture listings are accepted")


def build_fixture(fixture, prior=()):
    fixture_scope(fixture)
    slots = unique_index(fixture["suppliers"],lambda r:r["supplier_slot_id"])
    products = unique_index(fixture["profiles"],lambda r:r["product_code"])
    meta = fixture["metadata"]
    records = unique_index(prior,lambda r:tuple(r["logical_key"]))
    require(all(r["population_id"] == FIXTURE_POPULATION and r["originating_plan_id"] == meta["plan_id"]
                and r["external_id"] == fixture_id("listing",*r["logical_key"])
                and re.fullmatch(r"LST-(?!000000)[0-9]{6}",r["display_code"])
                and r["identity_status"] in {"active","retired"} for r in records.values()),
            "INVALID_REGISTRY", "fixture registry identity scope")
    display_registry = unique_index(prior,lambda r:r["display_code"])
    ordinal = max((int(k.split("-")[-1]) for k in display_registry),default=0)
    items = {key:{"external_id":fixture_id("product",IDENTIFIERS["classification_context"],key),
                 "source_product_code":key,"classification_context":IDENTIFIERS["classification_context"],
                 "is_synthetic":True} for key in sorted(products)}
    payload = {"metadata":{"version":"1.0.0","fixture_only":True,"population_id":FIXTURE_POPULATION,
                "is_synthetic":True,"is_intermediate":True,"backend_importable":False,"full_marketplace_release":False,
                "plan_id":meta["plan_id"],"configuration_fingerprint":meta["configuration_fingerprint"]},
               "products":list(items.values()),"listings":[],"identity_registry":[],"planning_to_listing":[]}
    used = set()
    for row in sorted(fixture["listings"],key=lambda v:v["listing_id"]):
        slot, code, reference = row["supplier_slot_id"], row["product_code"], row["listing_id"]
        supplier = slots[slot]
        key = (supplier["company_external_id"],items[code]["external_id"],"default")
        require(key not in used, "DUPLICATE_IDENTIFIER", reference)
        used.add(key)
        prior_record = records.get(key)
        if prior_record:
            require(prior_record["identity_status"] == "active"
                    and prior_record["originating_planning_listing_id"] == reference,
                    "INVALID_REGISTRY", "retired record or changed original reference")
            code_display = prior_record["display_code"]
        else:
            ordinal += 1
            code_display = display_code("LST",ordinal)
        identity = {"external_id":fixture_id("listing",*key),"logical_key":list(key),"display_code":code_display,
                    "population_id":FIXTURE_POPULATION,"supplier_external_id":key[0],"product_external_id":key[1],
                    "variant":"default"}
        p = products[code]
        payload["listings"].append({**identity,"supplier_role_external_id":supplier["role_external_id"],
            "supplier_product_association_external_id":supplier["associations"][code],
            "source_product_code":code,"market_code":supplier["market_code"],
            "title":f"Fictional catalog item {code}","description":f"Synthetic demo listing for source product {code}.",
            "language":"en","image":None,"tags":[p["commercial_group"]],"pricing_provenance":"synthetic",
            "quantity_provenance":"synthetic","is_synthetic":True,"planning_listing_id":reference,
            "provenance":{"source_release":meta["source_release"],"structural_plan_id":meta["structural_plan_id"],
                          "company_stage_id":meta["company_stage_id"],"commercial_plan_id":meta["plan_id"],
                          "configuration_fingerprint":meta["configuration_fingerprint"],"configuration_version":"1.0.0"},
            **{k:row[k] for k in ("price","unit","stock","moq","quantity_increment","maximum_order_quantity","status")}})
        payload["identity_registry"].append({**identity,"originating_plan_id":meta["plan_id"],
             "originating_planning_listing_id":reference,"identity_status":"active"})
        payload["planning_to_listing"].append({"planning_listing_id":reference,"listing_external_id":identity["external_id"],
                                                "display_code":code_display})
    retired = [r for key,r in records.items() if key not in used]
    require(all(r["identity_status"] == "retired" for r in retired),
            "INVALID_REGISTRY","fixture revision needs explicit retirement reconciliation")
    payload["identity_registry"].extend(sorted(retired,key=lambda r:r["display_code"]))
    return payload


def validate_fixture(root, payload, fixture):
    fixture_scope(fixture)
    schema_validator(root,"listing_stage.proposed").validate(payload)
    original = unique_index(fixture["listings"],lambda r:r["listing_id"])
    products = unique_index(payload["products"],lambda r:r["source_product_code"])
    by_id = unique_index(payload["listings"],lambda r:r["external_id"])
    listings = unique_index(payload["listings"],lambda r:r["planning_listing_id"])
    unique_index(payload["listings"],lambda r:r["display_code"])
    registry = unique_index(payload["identity_registry"],lambda r:r["external_id"])
    unique_index(payload["identity_registry"],lambda r:r["display_code"])
    mappings = unique_index(payload["planning_to_listing"],lambda r:r["planning_listing_id"])
    slots = {r["supplier_slot_id"]:r for r in fixture["suppliers"]}
    config = fixture["metadata"]
    require(original.keys() == listings.keys() == mappings.keys() and by_id.keys() <= registry.keys()
            and products.keys() == {r["product_code"] for r in fixture["profiles"]}
            and payload["metadata"]["population_id"] == FIXTURE_POPULATION
            and payload["metadata"]["plan_id"] == config["plan_id"]
            and payload["metadata"]["configuration_fingerprint"] == config["configuration_fingerprint"],
            "ALLOCATION_MISMATCH", "fixture relationship sets or provenance")
    for uid in registry.keys() - by_id.keys():
        row = registry[uid]
        require(row["identity_status"] == "retired" and row["population_id"] == FIXTURE_POPULATION
                and row["originating_plan_id"] == config["plan_id"] and uid == fixture_id("listing",*row["logical_key"])
                and row["logical_key"] == [row["supplier_external_id"],row["product_external_id"],row["variant"]],
                "INVALID_REGISTRY","retired reservation")
    for code, product in products.items():
        context = IDENTIFIERS["classification_context"]
        require(product["classification_context"] == context and product["external_id"] == fixture_id("product",context,code),
                "INVALID_IDENTIFIER_KEY", code)
    for ref, row in listings.items():
        allocation = original[ref]
        code = allocation["product_code"]
        supplier = slots[allocation["supplier_slot_id"]]
        key = [supplier["company_external_id"],products[code]["external_id"],"default"]
        uuid = fixture_id("listing",*key)
        require(row["source_product_code"] == code and [row[part] for part in ("supplier_external_id","product_external_id","variant")] == key
                and row["logical_key"] == key and row["external_id"] == uuid and mappings[ref]["listing_external_id"] == uuid
                and row["market_code"] == supplier["market_code"] and row["supplier_role_external_id"] == supplier["role_external_id"]
                and row["supplier_product_association_external_id"] == supplier["associations"][code]
                and row["population_id"] == FIXTURE_POPULATION
                and mappings[ref]["display_code"] == row["display_code"]
                and registry[uuid] == {**{k: row[k] for k in ("external_id","logical_key","display_code","population_id",
                    "supplier_external_id","product_external_id","variant")},
                    "originating_plan_id":config["plan_id"],"originating_planning_listing_id":ref,"identity_status":"active"}
                and row["provenance"] == {"source_release":config["source_release"],"structural_plan_id":config["structural_plan_id"],
                    "company_stage_id":config["company_stage_id"],"commercial_plan_id":config["plan_id"],
                    "configuration_fingerprint":config["configuration_fingerprint"],"configuration_version":"1.0.0"}
                and all(row[k] == allocation[k] for k in ("price","unit","stock","moq","quantity_increment","maximum_order_quantity","status")),
                "ALLOCATION_MISMATCH", "fixture listing identity, registry, provenance or approved values", listing_id=ref)
        require(row["title"] == f"Fictional catalog item {code}" and
                row["description"] == f"Synthetic demo listing for source product {code}.",
                "UNSUPPORTED_PRESENTATION", ref)
        active = basic_availability(row["status"],dec(row["stock"]))["matching"]
        moq, increment = dec(row["moq"]), dec(row["quantity_increment"])
        require(moq > 0 and increment > 0 and moq % increment == 0 and dec(row["price"]["amount"]) > 0
                and dec(row["price"]["basis_quantity"]) > 0 and (not active or moq <= dec(row["stock"])),
                "INVALID_LISTING", "fixture commercial fields", listing_id=ref)
    return {"status":"validated_fixture","products":len(products),"listings":len(listings)}


def write_fixture(path, root, fixture):
    require(not path.resolve().is_relative_to((root/"data").resolve()),"INVALID_FIXTURE_SCOPE","fixture output under data")
    with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
        candidate = Path(tmp)/path.name
        write_json(candidate,build_fixture(fixture))
        result = validate_fixture(root, read_json(candidate), fixture)
        candidate.replace(path)
    return result


def fixture_example():
    def ref(entity):
        return str(external_id(FIXTURE_NAMESPACE,entity,"fixture"))
    return {"metadata":{"fixture_only":True,"plan_id":"fixture-plan","source_release":"fixture-release",
                        "structural_plan_id":"fixture-structural","company_stage_id":"fixture-company",
                        "configuration_fingerprint":fingerprint("example")},
            "suppliers":[{"supplier_slot_id":"fixture-supplier","company_external_id":ref("supplier"),
                          "role_external_id":ref("role"),"market_code":840,"associations":{"010600":ref("association")}}],
            "profiles":[{"product_code":"010600","commercial_group":"fixture_group"}],
            "listings":[{"listing_id":"fixture-listing","supplier_slot_id":"fixture-supplier","product_code":"010600",
                         "price":{"amount":"10.00","currency":"USD","basis_quantity":"1","basis_unit":"PCS"},
                         "unit":"PCS","stock":"10","moq":"1","quantity_increment":"1","maximum_order_quantity":None,
                         "status":"active"}]}


def readiness(root):
    load_config(root)
    try:
        require_generation_ready(load_policy(root))
        full = True
    except ValueError:
        full = False
    require(not full,"AUTHORIZATION_SCOPE","full marketplace guard must remain blocked")
    from src.synthetic.commercial_remediation import HISTORICAL_PACKAGE, STRUCTURAL_BLOCK

    return {"stage":"SM-04B","status":"blocked","approved_execution":"SM-04A_only",
            "missing_exact_approvals":["marketplace_scope", *APPROVALS], "approval_package":None,
            "approval_package_fingerprint":None, "blocker":STRUCTURAL_BLOCK,
            "historical_package":{"fingerprint":HISTORICAL_PACKAGE,"status":"superseded_for_future_approval"},
            "permanent_generation_entry_point":"requires the separately authorized SM-04B execution",
            "technical_requirements":["verified_source_sm02_and_sm03b","resolved_profiles_for_approved_scope",
                "approved_product_and_listing_keys","final_canonical_schemas","validated_responses_for_approved_scope",
                "reproducibility_and_quality_review","identifier_registry_and_validator","regression_and_isolation",
                "approved_scope_with_exact_cardinalities","resolved_suitability_and_commercial_specifications",
                "complete_implementation_binding","explicit_listing_only_execution"],
            "sm05":"blocked","sm06":"blocked","backend_import":"blocked","full_marketplace":"blocked"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("readiness","inspect-identifiers","fixture","generate"))
    parser.add_argument("--root",type=Path,default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.command == "generate":
            state = readiness(args.root)
            raise CommercialError("SM04B_NOT_AUTHORIZED","exact approvals and explicit execution required",
                                  missing_exact_approvals=state["missing_exact_approvals"])
        if args.command == "readiness":
            result = readiness(args.root)
        elif args.command == "fixture":
            fixture = fixture_example()
            with tempfile.TemporaryDirectory() as directory:
                result = write_fixture(Path(directory)/"listing_bundle.json",args.root,fixture)
        else:
            result = identifier_details()
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,KeyError,ValidationError) as error:
        finding = getattr(error,"finding",{"severity":"BLOCKER","code":"VALIDATION_FAILURE","detail":str(error)})
        parser.exit(1,json.dumps(finding)+"\n")


if __name__ == "__main__":
    main()
