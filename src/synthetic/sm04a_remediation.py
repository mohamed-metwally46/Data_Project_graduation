"""Produce verified SM-04A-R evidence without building a corrected marketplace plan."""
import argparse
from collections import Counter
from pathlib import Path
import json
from time import perf_counter

from scripts.benchmark_market_opportunities import peak_memory
from src.analytics.release import MANIFEST, atomic_json, stamped
from src.analytics.release_validation import read_json
from src.synthetic.commercial_config import commercial_context, dec, price_domain, quantity_ticks, require, resolve_profiles
from src.synthetic.commercial_planning import common_interval
from src.synthetic.commercial_remediation import (
    ALLOWED, CORRECTIONS, HISTORICAL_PACKAGE, OFFLINE, REVIEW, STRUCTURAL_BLOCK, impact,
    implementation_binding, load_remediation, proposal_binding, suitability_reason, verify_historical,
)
from src.synthetic.commercial_stage import POINTER, QUALITY, publication, read_inputs
from src.synthetic.company_publication import POINTER as COMPANY_POINTER, verify_tests
from src.synthetic.determinism import display_code, entity_namespace, hierarchical_external_id, population_namespace
from src.synthetic.listing_stage import IDENTIFIERS, identifier_details
from src.synthetic.planning import POINTER as STRUCTURAL_POINTER, fingerprint

REPORT = Path("reports/sm04a_remediation_report.json")


def reconcile_identities(bundle):
    root, population = IDENTIFIERS["root"], IDENTIFIERS["population"]
    namespace = population_namespace(root,population)
    registry = sorted(bundle["identity_registry"], key=lambda r:r["originating_planning_slot_id"])
    for n, row in enumerate(registry,1):
        logical = f"identity-{n:06d}"
        require(row["persistent_company_key"] == logical and row["display_code"] == display_code("CMP",n)
                and row["external_id"] == str(hierarchical_external_id(root,population,"company",logical)),
                "IDENTITY_REGRESSION",logical)
    require({r["external_id"] for r in registry} == {r["external_id"] for r in bundle["companies"]},
            "IDENTITY_REGRESSION","company set")
    for r in bundle["company_roles"]:
        require(r["external_id"] == str(hierarchical_external_id(root,population,"company_role",r["company_external_id"],r["role"])),
                "IDENTITY_REGRESSION",r["external_id"])
    for a in bundle["company_products"]:
        require(a["external_id"] == str(hierarchical_external_id(
            root,population,"company_product",a["role_external_id"],a["source_product_code"])),
                "IDENTITY_REGRESSION",a["external_id"])
    fixture = identifier_details()
    require(fixture["fixture_product"]["external_id"] == "cbfaeac3-71c0-52aa-b85c-d4c394cd026c"
            and fixture["fixture_listing"]["external_id"] == "fb51050e-3b24-59e2-adae-e5a094b16411",
            "IDENTITY_REGRESSION","listed fixture identities")
    return {"company_uuids":len(registry),"company_display_codes":len(registry),
            "company_roles":len(bundle["company_roles"]),"company_products":len(bundle["company_products"]),
            "population_namespace":str(namespace),"company_namespace":str(entity_namespace(namespace,"company")),
            "identifier_policy_fingerprint":fixture["fingerprint"],
            "fixture_product_uuid":fixture["fixture_product"]["external_id"],
            "fixture_listing_uuid":fixture["fixture_listing"]["external_id"]}


def proposed_profiles(config, baseline, allocation):
    selected = {r["product_code"]:r for r in allocation["selected_products"]}
    result = {}
    for code in sorted(CORRECTIONS):
        item = config["products"][code]
        source = baseline["products"][code]
        override = item["commercial_override"]
        entry = {**source, "group":item["commercial_group"]}
        if override:
            entry.update(reference_price=override["reference_price"],
                         parameters={k:v for k,v in override.items() if k != "reference_price"})
        proposal = {**baseline,"products":{code:entry}}
        p, = resolve_profiles(proposal, [selected[code]])
        check_domains(p, allocation)
        result[code] = p
    return result


@commercial_context
def check_domains(profile, allocation):
    code = profile["product_code"]
    scale = profile["quantity_precision"]
    def ticks(s):
        return quantity_ticks(s,scale)
    increment = ticks(profile["quantity_increment"])
    lo,hi = map(ticks,profile["moq_bounds"])
    smax = ticks(profile["stock_bounds"][1])
    rlo,rhi = map(ticks,profile["rfq_quantity_bounds"])
    lower,upper,_ = common_interval([(lo,min(hi,smax))],[increment])
    rfq_lower,rfq_upper,_ = common_interval([(rlo,min(rhi,smax)),(lo,smax)],[increment])
    quote = dec(profile["reference_price"])
    endpoints = [
        price_domain(profile["price_bounds"], quote, profile["price_variation"][kind],
                     profile["quoted_price_precision"]) for kind in ("listing","rfq","offer")
    ]
    requires_response = any(r["product_code"] == code for r in allocation["offer_allocations"])
    require(lower <= upper and (not requires_response or rfq_lower <= rfq_upper)
            and all(low <= high for low,high in endpoints),
            "PROPOSED_DOMAIN_CONFLICT", code)


def quality_projections(quality, config):
    # These projections filter published diagnostics. No prices or requests are recomputed under changed units.
    result = {}
    modes = {
        "historical":lambda _:True,
        "restriction_only_historical_projection":lambda p:p["disposition"] != OFFLINE,
        "resolved_unchanged_measurement_historical_projection":lambda p:suitability_reason(p) is None
            and p["commercial_override"] is None,
    }
    for name, allow in modes.items():
        products = {c for c,v in config["products"].items() if allow(v)}
        rfqs = [r for r in quality["by_rfq"] if r["product_code"] in products]
        summaries = [r for r in quality["by_product"] if r["product_code"] in products]
        result[name] = {"product_denominator":len(products),
            "listing_denominator":sum(r["listings"] for r in summaries),"rfq_denominator":len(rfqs),
            "recorded_responses":sum(r["recorded_responses"] for r in rfqs),
            "structurally_eligible_category_a":sum(r["structurally_eligible_candidates"] for r in rfqs),
            "commercially_compatible":sum(r["commercially_compatible"] for r in rfqs),
            "eligible_nonresponding":sum(r["eligible_nonresponding"] for r in rfqs),
            "valid_but_incompatible":sum(r["valid_but_incompatible"] for r in rfqs),
            "unanswered_with_compatible":sum(r["recorded_responses"] == 0 and r["commercially_compatible"] > 0 for r in rfqs),
            "unanswered_without_compatible":sum(r["recorded_responses"] == 0 and r["commercially_compatible"] == 0 for r in rfqs),
            "boundary_counts":{key:sum(r[key] for r in summaries)
                 for key in ("price_boundary_count","positive_stock_boundary_count","moq_boundary_count")}}
    return result


def run(root, *, publish=False):
    started = perf_counter()
    tracks = (MANIFEST,STRUCTURAL_POINTER,COMPANY_POINTER,POINTER)
    before = [stamped(root,name) for name in tracks]
    config, allocation, _, upstream, _ = read_inputs(root,False,{})
    manifest,directory = publication(root)
    historical = verify_historical(root,manifest,directory,upstream)
    company_manifest = read_json(root/COMPANY_POINTER)
    company = read_json(root/company_manifest["artifact_directory"]/"company_stage.json")
    identities = reconcile_identities(company)
    require((len(company["companies"]),identities["company_roles"],identities["company_products"]) == (500,500,1800),
            "COMPANY_STAGE_INTEGRITY_FAILURE","company/role/portfolio totals")
    upstream_seconds = perf_counter() - started

    step = perf_counter()
    alternative = load_remediation(root,allocation["selected_products"],config["units"])
    corrected = proposed_profiles(alternative,config,allocation)
    projections = impact(allocation,historical,company,alternative["products"])
    quality = quality_projections(read_json(directory/QUALITY),alternative)
    statuses = Counter(p["disposition"] for p in alternative["products"].values())
    specs = {code:p["specification"] for code,p in alternative["products"].items()}
    unit_count = dict(Counter(p["canonical_uom"] for p in specs.values() if p is not None))
    groups = dict(Counter(p["commercial_group"] for p in alternative["products"].values() if p["specification"]))
    assess_seconds = perf_counter() - step

    step = perf_counter()
    regression = verify_tests(root) if publish else {"status":"not_run_in_inspect_mode"}
    tests_seconds = perf_counter() - step
    binding = implementation_binding(root)
    require(before == [stamped(root,name) for name in tracks], "HISTORICAL_BINDING_CHANGED","historical pointers")
    core = {
        "stage":"SM-04A-R","status":"blocked_pending_structural_scope","blocking_code":STRUCTURAL_BLOCK,
        "historical_package":{"fingerprint":HISTORICAL_PACKAGE,"status":"superseded_for_future_approval",
                              "plan_id":manifest["commercial_plan_id"],"artifacts":manifest["artifacts"]},
        "upstream":{"pointer_stamps":before,"source":upstream["source"],"structural_plan_id":upstream["structural_plan_id"],
                    "structural_artifacts":upstream["structural_artifacts"],"company_stage_id":upstream["company_stage_id"],
                    "company_artifacts":upstream["company_artifacts"]},
        "identity_reconciliation":identities,"implementation":binding,
        **proposal_binding(root,config,alternative),
        "impact":projections,"historical_quality_projections":quality,
        "proposed_profiles":{"reviewed":len(specs),"resolved":statuses[ALLOWED],"restricted":statuses[OFFLINE],
                             "review_required":statuses[REVIEW],"resolved_units":unit_count,"resolved_groups":groups,
                             "mandatory_corrections":corrected,"retained_nominal_variations":config["variation"]},
        "corrected_full_plan":{"status":"not_executed","builds":0,"new_plan_id":None},
        "exact_listing_approval_package":None,"permanent_product_ids_generated":0,"permanent_listing_ids_generated":0,
        "actual_listings_generated":0,"actual_rfqs_generated":0,"actual_offers_generated":0,
        "authorization":{"sm04b":"blocked","sm05":"blocked","sm06":"blocked","backend_import":"blocked",
                         "full_marketplace":"blocked"},
    }
    memory = peak_memory()
    result = {**core,"evidence_fingerprint":fingerprint("sm04a-remediation-evidence-v1",core),
              "regression_suite":regression,"operational":{"peak_working_set":memory,"seconds":{
                 "upstream_hash_verification_and_identity_reconciliation":upstream_seconds,
                 "scope_projection_and_proposal_checks":assess_seconds,"regression_suite":tests_seconds,
                 "total_excluding_report_write":perf_counter()-started}}}
    if publish:
        atomic_json(root/REPORT,result)
        saved = read_json(root/REPORT)
        require(saved == result and fingerprint("sm04a-remediation-evidence-v1",
                    {k:saved[k] for k in core}) == saved["evidence_fingerprint"],
                "REMEDIATION_REPORT_INTEGRITY_FAILURE","serialized evidence")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("inspect","report"))
    args = parser.parse_args()
    result = run(Path.cwd().resolve(),publish=args.action=="report")
    print(json.dumps({k:result[k] for k in ("status","blocking_code","evidence_fingerprint",
                                            "regression_suite","operational")},indent=2))


if __name__ == "__main__":
    main()
