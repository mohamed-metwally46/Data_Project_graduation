"""SM-04A-S review package and exact-scope approval checkpoint."""
import argparse
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from scripts.benchmark_market_opportunities import peak_memory
from src.analytics.release import MANIFEST, atomic_json, stamped, verify_entry
from src.analytics.release_validation import read_json, unique_index
from src.pipeline import write_json
from src.synthetic.commercial_config import require
from src.synthetic.commercial_remediation import CONFIG as REMEDIATION_CONFIG, verify_historical, load_remediation
from src.synthetic.commercial_stage import POINTER as HISTORICAL_POINTER, publication, read_inputs
from src.synthetic.company_publication import POINTER as COMPANY_POINTER, commit_stage, verify_artifacts, verify_tests
from src.synthetic.marketplace_scope import (
    APPROVAL_EVIDENCE, CEILING, DOMAINS, FLAGS, RELATIONS, REVIEW_CONFIG, build_projection, coverage,
    membership, proposed_configuration, read_decisions,
)
from src.synthetic.marketplace_scope_validation import (
    PACKAGE_METHOD, observed_evidence, planning_inputs, validate_projection,
)
from src.synthetic.planning import POINTER as STRUCTURAL_POINTER, fingerprint
from src.synthetic.sm04a_remediation import REPORT as REMEDIATION_REPORT, reconcile_identities

BASE = Path("data/planning/marketplace_scope")
POINTER = BASE / "scope_manifest.json"
REPORT = Path("reports/sm04a_scope_resolution_report.json")
CONFIG_FILE = "commercial.scope.proposed.v1.json"
PROJECTION = "scope_projection.json"
COVERAGE = "scope_coverage.json"
REVIEW = "product_specification_review.json"
ARTIFACTS = (CONFIG_FILE, PROJECTION, COVERAGE, REVIEW)
SCHEMAS = ("schemas/commercial.scope.proposed.v1.schema.json","schemas/marketplace_scope.v1.schema.json",
           "schemas/commercial_remediation.v1.schema.json","schemas/listing_stage.remediation.v1.schema.json",
           "schemas/commercial_plan.v1.schema.json","schemas/commercial_config.v1.schema.json")
REM = "sha256:eaf60b25a07960d86db0d64481b1e3abf42f2eda284b32d93ee4ef77a7268631"
IMPLEMENTATION = ("src/synthetic/marketplace_scope.py","src/synthetic/marketplace_scope_validation.py",
                  "src/synthetic/sm04a_scope.py")
AUTHORITY = "User attachment eb48ea63-cba4-472c-bca8-27d7bba01b92, sections 1 and 2"
GROUP_DECISIONS = {
    "liquids":("Select one explicitly liquid form with L/ML.", "Review a separately described mass-priced form.",
               "Volume implies neither density nor a pack conversion."),
    "bulk":("Quote the named bulk material by net mass.", "Defer counted packs or surface-priced forms to a separate review.",
            "Grade, density, trade units and pack contents stay unspecified."),
    "pieces":("Quote one named complete item or the single explicitly described roll.", "Defer mixed packs or variable-width formats.",
              "The named item covers one synthetic presentation within a broader class."),
    "area":("Quote directly measured surface in M2.", "Review a fixed piece or length product separately.",
            "No width or area-to-length conversion is assumed."),
    "length":("Quote supplied linear length in M.", "Review a fixed finished item as its own proposed form.",
              "No count, diameter, width, certification, or mass conversion is claimed."),
    "equipment":("Quote one named replacement component.", "Defer any assembly requiring fitment specifications.",
                 "Compatibility and certification are outside the synthetic scope."),
    "specialist":("Use one fictional non-graded object and explicit synthetic budget bands.",
                  "Exclude if the fictional presentation is unsuitable.",
                  "No valuation, grade, identity of maker, or authenticity is asserted."),
    "unresolved_excluded":("Hold outside scope pending specific form and suitability decisions.",
                           "Revisit later with an exact named item and independent proposed values.",
                           "Inclusion changes exact scope and coverage and requires a new review binding."),
}


def load_inputs(root):
    base, allocation, _, upstream, _ = read_inputs(root,False,{})
    prior, directory = publication(root)
    historical = verify_historical(root,prior,directory,upstream)
    evidence = read_json(root/REMEDIATION_REPORT)
    remainder = {k:v for k,v in evidence.items() if k not in ("evidence_fingerprint","regression_suite","operational")}
    require(evidence["evidence_fingerprint"] == REM == fingerprint("sm04a-remediation-evidence-v1",remainder),
            "REMEDIATION_EVIDENCE_CHANGED","historical evidence identity")
    record = evidence["implementation"]
    for stamp in record["files"]:
        require(stamped(root,stamp["path"]) == stamp,"REMEDIATION_EVIDENCE_CHANGED",stamp["path"])
    require(stamped(root,REMEDIATION_CONFIG)==evidence["configuration"],
            "REMEDIATION_EVIDENCE_CHANGED","remediation configuration")
    company_manifest = read_json(root/COMPANY_POINTER)
    company=read_json(root/company_manifest["artifact_directory"]/"company_stage.json")
    reconcile_identities(company)
    require((len(company["companies"]),len(company["company_roles"]),len(company["company_products"]))==(500,500,1800),
            "COMPANY_STAGE_INTEGRITY_FAILURE","pinned populations")
    tx=read_json(root/MANIFEST)
    verify_entry(root/tx["artifact_directory"],tx["validation"],"validation.json")
    observed = observed_evidence(root,tx,{r["product_code"] for r in allocation["selected_products"]})
    bindings = {
        "trade_intelligence":upstream["source"],"structural_plan_id":upstream["structural_plan_id"],
        "structural_artifacts":upstream["structural_artifacts"],
        "company_stage_id":upstream["company_stage_id"],"company_artifacts":upstream["company_artifacts"],
        "population_id":upstream["population_id"],"historical_plan_id":prior["commercial_plan_id"],
        "historical_artifacts":prior["artifacts"],"remediation_evidence":REM,
    }
    remediation = load_remediation(root,allocation["selected_products"],base["units"])
    return base,remediation,allocation,company,historical,bindings,observed


def review_table(configuration, decisions, remediation, historical, allocation):
    products=unique_index(historical["profiles"],lambda r:r["product_code"])
    review=[]
    for code in sorted(decisions["decisions"]):
        prior=products[code]
        row=configuration["products"][code]
        old=remediation["products"][code]
        review.append({
            "source_product_code":code,"source_description":prior["reference_description"],
            "review_category":old["historical_review"]["category"],"review_notes":old["historical_review_notes"],
            "previous_specification":old["specification"],
            "previous_candidate_measurement_basis":{"uom":prior["measurement_unit"],
                "saleable_basis":f'{prior["price_basis_quantity"]} {prior["price_basis_unit"]}',
                "physical_form":None,"prior_review_reason":old["historical_review"]["reason"]},
            "previous_commercial_terms":prior,"proposed_specification":row["specification"],
            "proposed_commercial_terms":row["commercial_terms"],"decision_group":row["decision_group"],
            "recommendation":row["resolution"],"disposition":row["disposition"],"approved":False,
            "remaining_uncertainty":row["resolution"] if row["specification"] is None
                else GROUP_DECISIONS[row["decision_group"]][2],
            "allocation_impact":{**{name:sum(r["product_code"]==code for r in allocation[section])
                                    for name,(section,_) in RELATIONS.items()},
                **{role+"_associations":sum(s["role"]==role and code in s["product_codes"]
                                           for s in allocation["company_slots"])
                   for role in ("supplier","importer")}},
        })
    groups={}
    for group in sorted({r["decision_group"] for r in review}):
        codes=[r["source_product_code"] for r in review if r["decision_group"]==group]
        excluded=group=="unresolved_excluded"
        policy,alternative,risk=GROUP_DECISIONS[group]
        groups[group]={"codes":codes,"count":len(codes),"policy":policy,
                       "alternative":alternative,"risk":risk,"separate_decision_needed_for_this_package":False,
                       "individual_decision_needed_before_future_inclusion":excluded,
                       "eligible_scope_delta":0 if excluded else len(codes)}
        if not excluded:
            d=DOMAINS[group]
            groups[group]["proposed_domain"]={"commercial_group":d[0],"unit":d[2],"permitted_units":d[3],
                   "stock":d[5],"moq":d[6],"increment":d[7],"rfq":d[8]}
    return {**FLAGS,"version":"1.0.0","approval_status":"proposed","original_review_count":len(review),
            "groups":groups,"profiles":review}


def construct(root, out, inputs):
    base,remediation,allocation,company,historical,bindings,observed=inputs
    decisions=read_decisions(root,remediation)
    config=proposed_configuration(base,remediation,decisions,allocation["selected_products"])
    reconciled=read_json(root/REMEDIATION_REPORT)["proposed_profiles"]["mandatory_corrections"]
    terms_by_code={r["product_code"]:r for r in historical["profiles"]} | reconciled
    preserved=("commercial_group","measurement_unit","permitted_units","quantity_precision",
               "price_basis_quantity","price_basis_unit","quoted_price_precision","reference_price",
               "price_bounds","price_variation","stock_bounds","moq_bounds","quantity_increment",
               "rfq_quantity_bounds","maximum_order_quantity")
    require(all(all(row["commercial_terms"][k]==terms_by_code[c][k] for k in preserved)
                and row["specification"]==remediation["products"][c]["specification"]
                for c,row in config["products"].items() if row["disposition"]=="existing_proposal"),
            "EXISTING_SCOPE_PROPOSAL_CHANGED","240 previous proposals")
    projection=build_projection(allocation,company,config,bindings)
    diagnostics=coverage(allocation,company,config)
    review=review_table(config,decisions,remediation,historical,allocation)
    for file,value in ((CONFIG_FILE,config),(PROJECTION,projection),(COVERAGE,diagnostics),(REVIEW,review)):
        write_json(out/file,value)
    result=validate_projection(root,read_json(out/PROJECTION),read_json(out/COVERAGE),allocation,company,
                               read_json(out/CONFIG_FILE),bindings,observed)
    require(read_json(out/REVIEW)==review and review["original_review_count"]==47,
            "SCOPE_REVIEW_CATALOG_MISMATCH","serialized review entries")
    limits=diagnostics["scope_counts"]
    require((limits["historical"]["products"],limits["historical"]["listings"],limits["historical"]["rfqs"],limits["historical"]["offers"])
            ==(300,1000,600,900)
            and (limits["restriction_only"]["products"],limits["restriction_only"]["listings"],limits["restriction_only"]["rfqs"],limits["restriction_only"]["offers"])
            ==(287,958,574,858)
            and (limits["previously_resolved"]["products"],limits["previously_resolved"]["listings"],
                 limits["previously_resolved"]["rfqs"],limits["previously_resolved"]["offers"])==(240,802,480,712),
            "SCOPE_COVERAGE_MISMATCH","pinned historical denominators")
    return config,projection,diagnostics,review,result


def package_for(root, files, config, projection, diagnostics, historical):
    codes,offline,unresolved=membership(config)
    files_to_bind=[stamped(root,path) for path in sorted(IMPLEMENTATION)]
    r=read_json(root/REMEDIATION_REPORT)
    implementation={"version":"scope-implementation-v1","remediation_binding":r["implementation"]["fingerprint"],
                    "files":files_to_bind}
    implementation["fingerprint"]=fingerprint("scope-implementation-v1",implementation)
    return {
        "version":PACKAGE_METHOD,"decision_authority":AUTHORITY,"strategy":"adaptive_scope_option_d","ceiling":CEILING,
        "scope_id":projection["scope_id"],"upstream":projection["bindings"],
        "decision_input":stamped(root,REVIEW_CONFIG),"artifacts":files,
        "source_codes_fingerprint":fingerprint(sorted(config["products"])),
        "eligible_codes_fingerprint":fingerprint(sorted(codes)),
        "offline_codes_fingerprint":fingerprint(sorted(offline)),
        "unresolved_codes_fingerprint":fingerprint(sorted(unresolved)),
        "specification_fingerprint":fingerprint({c:config["products"][c]["specification"] for c in sorted(codes)}),
        "configuration_fingerprint":fingerprint(config),"coverage_fingerprint":fingerprint(diagnostics),
        "implementation":implementation,"schemas":[stamped(root,s) for s in sorted(SCHEMAS)],
        "proposed_counts":projection["counts"],"additional_coverage_exceptions":diagnostics["additional_exceptions"],
        "competition_scenarios_below_ceiling":diagnostics["competition_scenarios_below_ceiling"],
        "proposed_inactive_zero":sum(r["status"]=="inactive" and r["stock"]=="0" for r in historical["listings"]
                                     if r["product_code"] in codes),
        "authorization_scope":"corrected_provisional_commercial_planning_only",
    }


def publish(root):
    started=perf_counter()
    tracks=(MANIFEST,STRUCTURAL_POINTER,COMPANY_POINTER,HISTORICAL_POINTER,REMEDIATION_REPORT)
    before=[stamped(root,p) for p in tracks]
    inputs=load_inputs(root)
    verified=perf_counter()
    tests=verify_tests(root)
    require(tests["tests_passed"]>=66,"REGRESSION_BASELINE_CHANGED","66 test baseline")
    checked=perf_counter()
    require(all((root/p).resolve()==root/p for p in (BASE,BASE/"proposals",POINTER)),
            "OUTPUT_ISOLATION_FAILURE","marketplace scope publication path")
    (root/BASE).mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(dir=root/BASE) as temp:
        a=Path(temp)/"candidate"
        b=Path(temp)/"rebuild"
        a.mkdir()
        b.mkdir()
        config,projection,diagnostics,review,validation=construct(root,a,inputs)
        construct(root,b,inputs)
        stamps=[{file:stamped(d,file) for file in sorted(ARTIFACTS)} for d in (a,b)]
        require(stamps[0]==stamps[1] and all((a/p).read_bytes()==(b/p).read_bytes() for p in ARTIFACTS),
                "SCOPE_REPRODUCIBILITY_FAILURE","two independent proposed scope builds")
        package=package_for(root,stamps[0],config,projection,diagnostics,inputs[4])
        review_hash=fingerprint(PACKAGE_METHOD,package)
        rel=BASE/"proposals"/review_hash.split(":")[1]
        manifest={**FLAGS,"status":"validated_proposal_awaiting_exact_approval","artifact_directory":rel.as_posix(),
                  "scope_id":projection["scope_id"],"review_package_fingerprint":review_hash,
                  "package":package,"artifacts":stamps[0],
                  "reproducibility":{"builds":stamps,"byte_identical":True},
                  "exact_scope_approved":False,"exact_specifications_approved":False,
                  "corrected_commercial_plan_validated":False}
        built=perf_counter()
        require(before==[stamped(root,p) for p in tracks],"HISTORICAL_BINDING_CHANGED","upstream pointers")
        commit_stage(root/rel,a,root/POINTER,manifest)
    read_published(root,inputs)
    result={**manifest,"validation":validation,"regression_suite":tests,"verified_pointers":before,
            "review_counts":dict(Counter(p["disposition"] for p in config["products"].values())),
            "corrected_full_plan_builds":0,"actual_generation":{"permanent_product_ids":0,"permanent_listing_ids":0,
                         "listings":0,"rfqs":0,"offers":0},
            "operational":{"seconds":{"upstream_verification":verified-started,"regression_suite":checked-verified,
                        "independent_scope_builds":built-checked,"publication_and_recheck":perf_counter()-built,
                        "total_excluding_report_write":perf_counter()-started},"peak_memory":peak_memory()}}
    atomic_json(root/REPORT,result)
    require(read_json(root/REPORT)==result,"SCOPE_REPORT_INTEGRITY_FAILURE","serialized checkpoint report")
    return result


def read_published(root,inputs=None):
    if inputs is None:
        inputs=load_inputs(root)
    manifest=read_json(root/POINTER)
    base,remediation,allocation,company,historical,bindings,observed=inputs
    package=manifest["package"]
    hash_id=fingerprint(PACKAGE_METHOD,package)
    rel=BASE/"proposals"/hash_id.split(":")[1]
    require(manifest["status"]=="validated_proposal_awaiting_exact_approval"
            and manifest["review_package_fingerprint"]==hash_id and manifest["artifact_directory"]==rel.as_posix()
            and set(manifest["artifacts"])==set(ARTIFACTS) and manifest["artifacts"]==package["artifacts"]
            and manifest["scope_id"]==package["scope_id"] and manifest["exact_scope_approved"] is False
            and manifest["exact_specifications_approved"] is False
            and manifest["corrected_commercial_plan_validated"] is False
            and manifest["reproducibility"]=={"builds":[manifest["artifacts"],manifest["artifacts"]],"byte_identical":True}
            and all(manifest[k] == v for k,v in FLAGS.items())
            and (root/rel).resolve()==root/rel,
            "SCOPE_PACKAGE_INTEGRITY_FAILURE","manifest")
    location=root/rel
    verify_artifacts(location,manifest["artifacts"])
    projection,config,diagnostics,review=(read_json(location/file) for file in (PROJECTION,CONFIG_FILE,COVERAGE,REVIEW))
    decisions=read_decisions(root,remediation)
    require(config==proposed_configuration(base,remediation,decisions,allocation["selected_products"])
            and review==review_table(config,decisions,remediation,historical,allocation)
            and package==package_for(root,manifest["artifacts"],config,projection,diagnostics,historical),
            "SCOPE_PACKAGE_INTEGRITY_FAILURE","rules, configuration or bound artifact changes")
    validate_projection(root,projection,diagnostics,allocation,company,config,bindings,observed)
    return manifest,projection,config,diagnostics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("publish-proposal","verify-proposal","prepare-planning"))
    args=parser.parse_args()
    root=Path.cwd().resolve()
    try:
        if args.command=="publish-proposal":
            result=publish(root)
            print(json.dumps({k:result[k] for k in ("status","scope_id","review_package_fingerprint","regression_suite","operational")},indent=2))
        else:
            manifest,projection,config,diagnostics=read_published(root)
            if args.command=="prepare-planning":
                path=root/APPROVAL_EVIDENCE
                approval=read_json(path) if path.is_file() else None
                planning_inputs(manifest["package"],approval,projection,config,diagnostics)
            print(json.dumps({"status":manifest["status"],"scope_id":manifest["scope_id"],
                  "review_package_fingerprint":manifest["review_package_fingerprint"]},indent=2))
    except (OSError,ValueError,KeyError) as error:
        parser.exit(1,json.dumps(getattr(error,"finding",{"code":"SCOPE_ERROR","detail":str(error)}))+"\n")


if __name__=="__main__":
    main()
