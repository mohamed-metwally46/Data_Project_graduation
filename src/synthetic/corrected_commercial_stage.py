"""Execute and publish the exact approved SM-04A corrected planning scope."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from types import SimpleNamespace

from scripts.benchmark_market_opportunities import peak_memory
from src.analytics.release import MANIFEST, atomic_json, stamped
from src.analytics.release_validation import read_json, schema_validator
from src.pipeline import write_json
from src.synthetic.commercial_config import FLAGS, canonical_decimal, require
from src.synthetic.commercial_stage import POINTER as HISTORICAL_POINTER
from src.synthetic.commercial_validation import quality_report
from src.synthetic.company_publication import POINTER as COMPANY_POINTER, commit_stage, verify_artifacts, verify_tests
from src.synthetic.listing_stage import identifier_details
from src.synthetic.marketplace_scope import APPROVAL_EVIDENCE, RELATIONS
from src.synthetic.marketplace_scope_validation import (
    planning_inputs, require_exact_approval, solve_for_approved_scope, validate_projection, validate_scoped_commercial,
)
from src.synthetic.planning import POINTER as STRUCTURAL_POINTER, fingerprint
from src.synthetic.sm04a_remediation import REPORT as REMEDIATION_REPORT
from src.synthetic.sm04a_scope import POINTER as SCOPE_POINTER, load_inputs, read_published

BASE = Path("data/planning/commercial_feasibility")
POINTER = BASE/"corrected_plan_manifest.json"
REPORT = Path("reports/sm04a_corrected_commercial_readiness.json")
SCHEMA = "commercial_plan.corrected.v1"
METHOD = "corrected-commercial-plan-v1"
APPROVAL_METHOD = "sm04b-exact-listing-review-v1"
SCOPE_APPROVAL = "sha256:c2ba6877a9b8816c2ebf80ab509eae5de81f59c3dd53f54affc38d1670df1d75"
CONFIG_APPROVAL = "sha256:2c2b6438662b33e1aa65a7f705020d68043a96b5cb9d961d8ee7a28ba8a8c714"
FILES = {"profiles":"resolved_product_profiles.json", "listings":"listing_commercial_plan.json",
         "rfqs":"rfq_commercial_plan.json", "offers":"offer_commercial_plan.json"}
VALIDATION = "commercial_feasibility_report.json"
QUALITY = "commercial_quality_report.json"
EXPECTED = {
    "products":279,"companies":500,"supplier_associations":1116,"importer_associations":556,
    "listings":932,"active":792,"out_of_stock":96,"inactive":44,"visible_catalog":888,
    "rfqs":558,"offers":835,"competitive_rfqs":279,"category_records":{"A":1001,"B":0,"C":0},
    "unique_directional_relationships":279,"responding_suppliers":295,"active_supplier_coverage":300,
    "rfq_importer_coverage":199,"supplier_markets":25,"importer_markets":75,
    "active_product_coverage":279,"rfq_product_coverage":279,
}
TRACKED = (MANIFEST,STRUCTURAL_POINTER,COMPANY_POINTER,HISTORICAL_POINTER,SCOPE_POINTER,
           REMEDIATION_REPORT,APPROVAL_EVIDENCE)


def approved_inputs(root):
    original=load_inputs(root)
    manifest,projection,config,diagnostics=read_published(root,original)
    package=manifest["package"]
    require(manifest["review_package_fingerprint"]==SCOPE_APPROVAL
            and package["configuration_fingerprint"]==CONFIG_APPROVAL,
            "CORRECTED_APPROVAL_FINGERPRINT_MISMATCH","published scope or exact commercial configuration")
    require((root/APPROVAL_EVIDENCE).is_file(),"EXACT_SCOPE_APPROVAL_REQUIRED","product owner approval record")
    approval=read_json(root/APPROVAL_EVIDENCE)
    require_exact_approval(package,approval)
    require(all(projection["counts"][k]==v for k,v in EXPECTED.items())
            and diagnostics["exceptions"]["proposed"]["importers_without_rfq"]==
              [{"slot_id":"IMP-SLOT-0043","display_code":"CMP-000043"}]
            and all(not value for value in diagnostics["additional_exceptions"].values()),
            "CORRECTED_SCOPE_MISMATCH","approved counts or RFQ coverage exception")
    solver,profiles,_=planning_inputs(package,approval,projection,config,diagnostics)
    profiles=[{**p,"suitability":"marketplace_allowed",
               "commercial_specification":config["products"][p["product_code"]]["specification"]}
              for p in profiles]
    older=read_json(root/REMEDIATION_REPORT)["implementation"]
    paths={v["path"] for v in older["files"]+package["implementation"]["files"]}
    paths.add("src/synthetic/corrected_commercial_stage.py")
    implementation=[stamped(root,p) for p in sorted(paths)]
    schemas={s["path"]:s for s in package["schemas"]}
    schema_path=f"schemas/{SCHEMA}.schema.json"
    schemas[schema_path]=stamped(root,schema_path)
    identifiers=identifier_details()
    bindings={"approved_scope_package":SCOPE_APPROVAL,"scope_id":projection["scope_id"],
              "approval_evidence":stamped(root,APPROVAL_EVIDENCE),
              "configuration_fingerprint":CONFIG_APPROVAL,"eligible_codes_fingerprint":package["eligible_codes_fingerprint"],
              "specification_fingerprint":package["specification_fingerprint"],
              "suitability_fingerprint":fingerprint({c:r["suitability"] for c,r in config["products"].items()}),
              "offline_codes_fingerprint":package["offline_codes_fingerprint"],
              "unresolved_codes_fingerprint":package["unresolved_codes_fingerprint"],
              "identifier_policy_fingerprint":identifiers["fingerprint"],"upstream":projection["bindings"],
              "implementation":{"version":"corrected-implementation-v1","files":implementation,
                                "fingerprint":fingerprint("corrected-implementation-v1",implementation)},
              "schemas":schemas,"master_seed":solver["master_seed"],"method":METHOD}
    return original,manifest,projection,config,diagnostics,approval,solver,profiles,bindings


def read_bundle(directory):
    data={}
    for key,name in FILES.items():
        artifact=read_json(directory/name)
        require(set(artifact)=={"metadata","records"},"INVALID_CORRECTED_ARTIFACT",name)
        data.setdefault("metadata",artifact["metadata"])
        require(data["metadata"]==artifact["metadata"],"INVALID_CORRECTED_ARTIFACT",name)
        data[key]=artifact["records"]
    return data


def validate_serialized(root, directory, context):
    original,_,projection,config,diagnostics,_,solver,profiles,bindings=context
    _,_,allocation,company,_,scope_bindings,observed=original
    validate_projection(root,projection,diagnostics,allocation,company,config,scope_bindings,observed)
    candidate=read_bundle(directory)
    schema_validator(root,SCHEMA).validate(candidate)
    require(candidate["metadata"]=={**FLAGS,"schema_version":"1.0.0","stage":"SM-04A-corrected","bindings":bindings}
            and candidate["profiles"]==profiles, "CORRECTED_PLAN_PROFILE_MISMATCH","profile data or provenance")
    validate_scoped_commercial(candidate,projection,profiles,solver)
    profile_by_code={p["product_code"]:p for p in profiles}
    for key in FILES:
        if key=="profiles":
            continue
        for row in candidate[key]:
            p=profile_by_code[row["product_code"]]
            quote=row["target_price"] if key=="rfqs" else row["price"]
            canonical_decimal(quote["basis_quantity"],p["quantity_precision"])
            require(p["measurement_unit"] in p["permitted_units"]
                    and all(solver["units"][u]["dimension"]==solver["units"][p["measurement_unit"]]["dimension"]
                            for u in p["permitted_units"]),
                    "CORRECTED_PLAN_UNIT_MISMATCH",row[RELATIONS[key][1]])
    statuses=Counter(r["status"] for r in candidate["listings"])
    inactive=Counter("zero_stock" if r["stock"]=="0" else "positive_stock"
                     for r in candidate["listings"] if r["status"]=="inactive")
    requests=Counter(r["request_id"] for r in candidate["offers"])
    responses=Counter(str(requests[r["request_id"]]) for r in candidate["rfqs"])
    counts=projection["counts"]
    require(dict(responses)==counts["responses"] and statuses=={k:counts[k] for k in
            ("active","out_of_stock","inactive")} and inactive["zero_stock"]==solver["inactive_zero"],
            "CORRECTED_SCENARIO_MISMATCH","serialized response histogram or stock states")
    return {**FLAGS,"status":"passed","scope_counts":counts,"inactive_stock":dict(sorted(inactive.items())),
            "verified_profiles":len(profiles),"verified_listings":len(candidate["listings"]),
            "verified_rfqs":len(candidate["rfqs"]),"feasible_allocated_responses":len(candidate["offers"]),
            "infeasible_allocated_responses":0,"unresolved_scenarios":0,
            "preserved_competitive_rfqs":counts["competitive_rfqs"],
            "coverage_exceptions":diagnostics["exceptions"]["proposed"],
            "independent_source":"pinned SQLite eligible triples and serialized original associations",
            "fulfillment":"full_independent_no_reservation"}


def corrected_quality(candidate, projection, allocation, solver, observed, search):
    def observed_lookup(code,exporter,importer):
        return {"category":"A"} if (code,exporter,importer) in observed else None

    data=quality_report(candidate,allocation,solver,SimpleNamespace(lookup_relationship=observed_lookup))
    active_stock=defaultdict(set)
    for listing in candidate["listings"]:
        if listing["status"]=="active":
            active_stock[listing["product_code"]].add(listing["stock"])
    by_product=data["by_product"]
    for row in by_product:
        row["unique_active_stocks"]=len(active_stock[row["product_code"]])
    scope=projection["counts"]
    return {**FLAGS,**data,"scope_denominators":{k:scope[k] for k in ("products","listings","active","rfqs","offers")},
            "products_with_diversity":{
                **{field:sum(row[field]["unique"]>1 for row in by_product)
                   for field in ("listing_prices","moqs","rfq_quantities","offer_prices")},
                "active_stock":sum(row["unique_active_stocks"]>1 for row in by_product),
            },
            "boundaries":{key:sum(row[key] for row in by_product) for key in
                          ("price_boundary_count","positive_stock_boundary_count","moq_boundary_count")},
            "coverage":{"competitive_rfqs":scope["competitive_rfqs"],"active_supplier":scope["active_supplier_coverage"],
                        "rfq_importer":scope["rfq_importer_coverage"],"responding_suppliers":scope["responding_suppliers"]},
            "fallback_search_nodes":search,
            "candidate_interpretation":"Synthetic same-product candidates with observed Category A evidence. Allocation is not ranking ground truth."}


def build(root, directory, context):
    original,scope,projection,config,diagnostics,approval,solver,profiles,bindings=context
    mark=perf_counter()
    plans,solver_metrics=solve_for_approved_scope(scope["package"],approval,projection,config,diagnostics)
    solver_seconds=perf_counter()-mark
    data={**plans,"profiles":profiles,"metadata":{**FLAGS,"schema_version":"1.0.0",
                                                   "stage":"SM-04A-corrected","bindings":bindings}}
    mark=perf_counter()
    for k,n in FILES.items():
        write_json(directory/n,{"metadata":data["metadata"],"records":data[k]})
    serialization=perf_counter()-mark
    mark=perf_counter()
    validation=validate_serialized(root,directory,context)
    validation_seconds=perf_counter()-mark
    quality=corrected_quality(read_bundle(directory),projection,original[2],solver,original[6],solver_metrics["search_nodes"])
    mark=perf_counter()
    write_json(directory/VALIDATION,validation)
    write_json(directory/QUALITY,quality)
    serialization+=perf_counter()-mark
    return validation, quality, solver_metrics["search_nodes"], {
        "solver":solver_seconds,"independent_serialized_validation":validation_seconds,"serialization":serialization,
        **{k:v for k,v in solver_metrics.items() if k!="search_nodes"},
    }


def listing_package(plan_id, content_fingerprint, artifacts, context, validation, quality, reproducibility):
    _,_,projection,_,diagnostics,_,_,_,bindings=context
    identifiers=identifier_details()
    return {
        "version":APPROVAL_METHOD,"status":"pending_explicit_approval","authorization_scope":"SM-04B isolated canonical product and listing population only",
        "commercial_plan_id":plan_id,"deterministic_content_fingerprint":content_fingerprint,
        "bindings":bindings,"artifacts":artifacts,"identifier_specifications":identifiers,
        "validation":validation,"reproducibility":reproducibility,
        "quality":{"artifact":artifacts[QUALITY],"rfq_diagnostics":quality["rfq_diagnostics"],
            "products_with_diversity":quality["products_with_diversity"],"boundaries":quality["boundaries"]},
        "accepted_coverage_exceptions":{"companies":diagnostics["exceptions"]["proposed"],
            "unresolved_product_exclusions":projection["unresolved_product_codes"],
            "offline_only_product_exclusions":projection["offline_only_product_codes"],
            "competition_scenarios_below_ceiling":diagnostics["competition_scenarios_below_ceiling"],
            "responding_suppliers_below_ceiling":diagnostics["scope_counts"]["restriction_only"]["responding_suppliers"]
                                                  -projection["counts"]["responding_suppliers"]},
        "population_targets":{"products":279,"permanent_product_uuids":279,"listings":932,"permanent_listing_uuids":932,
                              "registry_entries":932,"planning_mappings":932,"active":792,"out_of_stock":96,"inactive":44},
        "required_before_publication":["explicit listing-only execution approval","validate all production-shaped serialized records",
            "verify registry and mappings","independent full listing-stage reproducibility","isolated publication"],
        "backend_importable":False,"full_marketplace_release":False,"rfq_and_offer_generation_authorized":False,
    }


def verify_publication(root, context):
    manifest=read_json(root/POINTER)
    stamps=manifest["artifacts"]
    content=fingerprint(METHOD,stamps)
    plan_id="sm04ac-"+content.split(":")[1]
    rel=BASE/"corrected_plans"/plan_id
    require(manifest["status"]=="validated_corrected_provisional" and manifest["commercial_plan_id"]==plan_id
            and manifest["deterministic_content_fingerprint"]==content and manifest["artifact_directory"]==rel.as_posix()
            and all(manifest[k]==value for k,value in FLAGS.items()) and manifest["listing_generation_authorized"] is False
            and set(stamps)=={*FILES.values(),VALIDATION,QUALITY} and (root/rel).resolve()==root/rel
            and manifest["bindings"]==context[-1],
            "CORRECTED_PUBLICATION_MISMATCH","manifest, flags, or implementation binding")
    verify_artifacts(root/rel,stamps)
    repeat={"byte_identical":True,"builds":[stamps,stamps]}
    validation=validate_serialized(root,root/rel,context)
    quality=read_json(root/rel/QUALITY)
    package=listing_package(plan_id,content,stamps,context,validation,quality,repeat)
    require(validation==manifest["validation"]==read_json(root/rel/VALIDATION)
            and manifest["reproducibility"]==repeat and manifest["sm04b_approval_package"]==package
            and manifest["sm04b_approval_package_fingerprint"]==fingerprint(APPROVAL_METHOD,package),
            "CORRECTED_PUBLICATION_MISMATCH","validation, deterministic builds or listing package")
    return manifest


def publish(root):
    start=perf_counter()
    require((root/APPROVAL_EVIDENCE).is_file(),"EXACT_SCOPE_APPROVAL_REQUIRED","product owner approval record")
    before=[stamped(root,p) for p in TRACKED]
    context=approved_inputs(root)
    verified=perf_counter()
    tests=verify_tests(root)
    require(tests["tests_passed"]>=74,"REGRESSION_BASELINE_CHANGED","74-test baseline")
    tested=perf_counter()
    require(all((root/p).resolve()==root/p for p in (BASE,BASE/"corrected_plans",POINTER)),
            "OUTPUT_ISOLATION_FAILURE","corrected planning publication location")
    with TemporaryDirectory(dir=root/BASE) as work:
        first,second=Path(work)/"candidate",Path(work)/"rebuild"
        first.mkdir()
        second.mkdir()
        validation,quality,search,measurements=build(root,first,context)
        measured=perf_counter()
        replay_validation,replay_quality,replay_search,_=build(root,second,context)
        names=sorted({*FILES.values(),VALIDATION,QUALITY})
        builds=[{n:stamped(d,n) for n in names} for d in (first,second)]
        require(builds[0]==builds[1] and all((first/n).read_bytes()==(second/n).read_bytes() for n in names)
                and replay_validation==validation and replay_quality==quality and replay_search==search,
                "CORRECTED_REPRODUCIBILITY_FAILURE","two independently serialized full builds")
        content=fingerprint(METHOD,builds[0])
        plan_id="sm04ac-"+content.split(":")[1]
        rel=BASE/"corrected_plans"/plan_id
        repeat={"byte_identical":True,"builds":builds}
        package=listing_package(plan_id,content,builds[0],context,validation,quality,repeat)
        manifest={**FLAGS,"status":"validated_corrected_provisional","commercial_plan_id":plan_id,
                  "artifact_directory":rel.as_posix(),"bindings":context[-1],
                  "deterministic_content_fingerprint":content,"artifacts":builds[0],
                  "validation":validation,"reproducibility":repeat,"fallback_search_nodes":search,
                  "listing_generation_authorized":False,"sm04b_approval_package":package,
                  "sm04b_approval_package_fingerprint":fingerprint(APPROVAL_METHOD,package)}
        built=perf_counter()
        require(before==[stamped(root,p) for p in TRACKED],"HISTORICAL_BINDING_CHANGED","upstream pointers")
        commit_stage(root/rel,first,root/POINTER,manifest)
    verify_publication(root,context)
    report={**manifest,"regression_suite":tests,"unchanged_upstream":before,
            "corrected_full_builds":2,"actual_generation":{"permanent_product_ids":0,"permanent_listing_ids":0,
                 "listings":0,"rfqs":0,"offers":0},
            "authorization":{"sm04b":"pending","sm05":"blocked","sm06":"blocked","backend_import":"blocked",
                             "full_marketplace":"blocked"},
            "operational":{"seconds":{"upstream_verification":verified-start,"regression_suite":tested-verified,
                "first_build":measurements,"second_build_and_comparison":built-measured,
                "publication_and_reverification":perf_counter()-built,"total_excluding_report_write":perf_counter()-start},
                "peak_memory":peak_memory()}}
    atomic_json(root/REPORT,report)
    require(read_json(root/REPORT)==report,"CORRECTED_REPORT_INTEGRITY_FAILURE","serialized report")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("plan","validate"))
    args=parser.parse_args()
    root=Path.cwd().resolve()
    try:
        result=publish(root) if args.command=="plan" else verify_publication(root,approved_inputs(root))
        print(json.dumps({k:result[k] for k in ("status","commercial_plan_id","sm04b_approval_package_fingerprint",
                         "fallback_search_nodes","validation","regression_suite","operational") if k in result},indent=2))
    except (OSError,ValueError,KeyError) as error:
        parser.exit(1,json.dumps(getattr(error,"finding",{"code":"CORRECTED_PLANNING_ERROR","detail":str(error)}))+"\n")


if __name__=="__main__":
    main()
