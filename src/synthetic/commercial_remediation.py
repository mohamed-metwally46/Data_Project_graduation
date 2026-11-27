"""SM-04A-R policy, immutable upstream checks, and read-only scope reconciliation."""
from collections import Counter, defaultdict
from pathlib import Path

from src.analytics.release import stamped
from src.analytics.release_validation import read_json, schema_validator, unique_index
from src.synthetic.commercial_config import DECIMAL_POLICY, dec, require
from src.synthetic.commercial_planning import basic_availability, eligibility
from src.synthetic.planning import fingerprint

CONFIG = Path("configs/synthetic/commercial.remediation.v1.json")
SCHEMA_PATHS = ("schemas/commercial_remediation.v1.schema.json", "schemas/listing_stage.remediation.v1.schema.json")
HISTORICAL_PLAN = "sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d"
HISTORICAL_PACKAGE = "sha256:1ae2075cc7b6203557003416f49bef2f5f815fb05ed55dd0cdb9cab6b854bb91"
STRUCTURAL_BLOCK = "STRUCTURAL_SCOPE_APPROVAL_REQUIRED"
ALLOWED, OFFLINE, REVIEW = "marketplace_allowed", "restricted_offline_qa", "review_required"
RESTRICTED = frozenset("010600 220429 220890 240220 281410 300220 300239 300490 300660 360690 382100 681310 930400".split())
CORRECTIONS = {
    "220190": ("liquid", "L"), "321590": ("liquid", "L"), "851830": ("standalone_device", "PCS"),
    "401099": ("length_material", "M"), "590610": ("length_material", "M"), "580632": ("length_material", "M"),
}
IMPLEMENTATION = (
    "src/synthetic/commercial_config.py", "src/synthetic/commercial_planning.py",
    "src/synthetic/commercial_validation.py", "src/synthetic/commercial_stage.py",
    "src/synthetic/commercial_remediation.py", "src/synthetic/sm04a_remediation.py",
    "src/synthetic/listing_stage.py", "src/synthetic/listing_population_validation.py",
    "src/synthetic/determinism.py", "src/synthetic/planning.py", "src/synthetic/planning_validation.py",
    "src/synthetic/allocation.py", "src/synthetic/company_stage.py", "src/synthetic/company_identity.py",
    "src/synthetic/company_validation.py", "src/synthetic/company_publication.py",
    "src/synthetic/foundation.py", "src/analytics/release.py", "src/analytics/release_validation.py",
    "src/analytics/market_opportunity_intelligence.py", "src/analytics/observed.py",
    "src/pipeline.py", "src/enrichment/references.py", "src/preprocessing/trade.py",
    "requirements.txt", "requirements-dev.txt",
)


def require_planning_scope():
    require(False, STRUCTURAL_BLOCK, "13 offline-only products intersect the protected allocation; a revised marketplace scope requires explicit approval")


def implementation_binding(root):
    files = [stamped(root, name) for name in sorted(IMPLEMENTATION)]
    return {"version":"commercial_implementation_files_v1", "files":files,
            "fingerprint":fingerprint("commercial_implementation_files_v1", files)}


def proposal_binding(root, baseline, proposal):
    products = proposal["products"]
    return {
        "configuration":stamped(root,CONFIG), "configuration_fingerprint":fingerprint(proposal),
        "unit_registry_fingerprint":fingerprint(baseline["units"]),
        "product_suitability_fingerprint":fingerprint({
            code:{"disposition":p["disposition"],"offline_qa_only":p["offline_qa_only"]}
            for code,p in products.items()}),
        "commercial_specifications_fingerprint":fingerprint({c:p["specification"] for c,p in products.items()}),
        "price_and_quantity_proposal_fingerprint":fingerprint({c:p["commercial_override"] for c,p in products.items()}),
        "decimal_policy":DECIMAL_POLICY, "schemas":[stamped(root,name) for name in SCHEMA_PATHS],
    }


def verify_historical(root, manifest, directory, current):
    from src.synthetic.commercial_stage import QUALITY, REPORT, read_bundle

    stored = read_json(root / REPORT)
    historical = manifest["bindings"]
    require(manifest["commercial_plan_id"] == HISTORICAL_PLAN and
            all(historical[k] == v for k, v in current.items() if k != "implementation_fingerprint")
            and all(stored[k] == v for k, v in manifest.items())
            and manifest["reproducibility"]["builds"] == [manifest["artifacts"], manifest["artifacts"]],
            "HISTORICAL_BINDING_CHANGED", "historical plan, evidence or pinned inputs")
    bundle = read_bundle(directory)
    require(fingerprint(bundle) == manifest["deterministic_content_fingerprint"]
            and fingerprint(bundle["profiles"]) == manifest["resolved_profile_fingerprint"],
            "HISTORICAL_BINDING_CHANGED", "historical commercial contents")
    package = {
        "commercial_plan_id":manifest["commercial_plan_id"], "artifacts":manifest["artifacts"],
        "commercial_configuration":historical["configuration"],
        "commercial_configuration_fingerprint":historical["configuration_fingerprint"],
        "resolved_profile_fingerprint":manifest["resolved_profile_fingerprint"],
        "identifier_policy_fingerprint":historical["identifier_policy_fingerprint"],
        "canonical_schemas":historical["schemas"],
        "deterministic_content_fingerprint":manifest["deterministic_content_fingerprint"],
        "quality_artifact":QUALITY, "population_id":historical["population_id"],
        "authorization_scope":"SM-04B canonical product references and listings only",
    }
    require(fingerprint(package) == HISTORICAL_PACKAGE,
            "HISTORICAL_BINDING_CHANGED", "legacy approval fingerprint")
    return bundle


def load_remediation(root, selected, units):
    config = read_json(root / CONFIG)
    schema_validator(root, "commercial_remediation.v1").validate(config)
    products = config["products"]
    reference = unique_index(selected, lambda r: r["product_code"])
    require(products.keys() == reference.keys() and config["decimal_policy"] == DECIMAL_POLICY
            and {code for code,p in products.items() if p["disposition"] == OFFLINE} == RESTRICTED,
            "REMEDIATION_CONFIGURATION_MISMATCH", "protected catalog, offline scope or decimal policy")
    for code, profile in products.items():
        spec = profile["specification"]
        require(profile["reference_description"] == reference[code]["reference_description"],
                "PRODUCT_REFERENCE_MISMATCH", code)
        if profile["disposition"] == OFFLINE:
            require(spec is None and profile["commercial_override"] is None and profile["offline_qa_only"] is True,
                    "OFFLINE_QA_ONLY", code)
            continue
        require(not profile["offline_qa_only"] and (profile["disposition"] == REVIEW or spec is not None),
                "PRODUCT_SPECIFICATION_UNRESOLVED", code)
        if spec is None:
            continue
        u = spec["canonical_uom"]
        require(spec["specification_key"] == f"globiq-{code}-demo-v1" and u in spec["allowed_uoms"]
                and u in units and len(set(spec["allowed_uoms"])) == len(spec["allowed_uoms"])
                and all(other in units and units[other]["dimension"] == units[u]["dimension"]
                        for other in spec["allowed_uoms"]), "INCOMPATIBLE_UOM", code)
        if code in CORRECTIONS:
            require((spec["physical_form"], u) == CORRECTIONS[code] and
                    spec["allowed_uoms"] == (["L","ML"] if u == "L" else [u]),
                    "PRODUCT_SPECIFICATION_MISMATCH", code)
    return config


def suitability_reason(profile):
    if profile is None:
        return "PRODUCT_SUITABILITY_UNRESOLVED"
    if profile.get("disposition") == OFFLINE or profile.get("offline_qa_only"):
        return "PRODUCT_RESTRICTED"
    if profile.get("disposition") != ALLOWED or not profile.get("specification"):
        return "PRODUCT_SUITABILITY_UNRESOLVED"
    return None


def validate_specification(record, policy):
    reason = suitability_reason(policy)
    require(reason is None, reason, "product is outside normal marketplace scope")
    spec = policy["specification"]
    require(record.get("specification_key") == spec["specification_key"]
            and record.get("physical_form") == spec["physical_form"]
            and record.get("unit") == spec["canonical_uom"],
            "PRODUCT_SPECIFICATION_MISMATCH", spec["specification_key"])
    return spec


def marketplace_availability(listing, policy):
    """Public visibility is derived only for a validated marketplace specification."""
    reason = suitability_reason(policy)
    if reason:
        return {"visible":False, "matching":False, "reason":reason}
    validate_specification(listing, policy)
    availability = basic_availability(listing["status"], dec(listing["stock"]))
    return {**availability, "reason":None}


def marketplace_eligibility(listing, request, policy, units, category):
    reason = suitability_reason(policy)
    if reason:
        return reason
    from src.synthetic.commercial_config import CommercialError
    if listing.get("product_code") != request.get("product_code"):
        return "PRODUCT_MISMATCH"
    try:
        spec = validate_specification(listing, policy)
    except CommercialError as error:
        return error.finding["code"]
    if (request.get("specification_key") != spec["specification_key"]
            or request.get("physical_form") != spec["physical_form"]):
        return "PRODUCT_SPECIFICATION_MISMATCH"
    return eligibility(listing, request, {"measurement_unit":spec["canonical_uom"],
                                         "permitted_units":spec["allowed_uoms"]}, units, category)


def public_candidate_index(listings, policies):
    return [row for row in listings if marketplace_availability(row, policies.get(row["product_code"]))["matching"]]


def offline_rejection_case(code, *, offline_test_mode=False):
    require(offline_test_mode is True and code in RESTRICTED, "OFFLINE_QA_ONLY", "explicit offline test scope required")
    return {"abstract_case":"product_suitability_rejection", "expected_reason":"PRODUCT_RESTRICTED",
            "offline_only":True,"backend_importable":False}


def impact(allocation, bundle, company, policies=None):
    slots = unique_index(allocation["company_slots"], lambda row: row["slot_id"])
    mappings = unique_index(company["slot_company_mapping"], lambda row: row["planning_slot_id"])
    require(slots.keys() == mappings.keys() and all(mappings[k]["product_codes"] == row["product_codes"]
            and mappings[k]["market_code"] == row["market_code"] and mappings[k]["initial_role"] == row["role"]
            for k,row in slots.items()), "COMPANY_STAGE_INTEGRITY_FAILURE", "portfolio cross-check")
    requests = unique_index(bundle["rfqs"], lambda r:r["request_id"])
    profiles = unique_index(bundle["profiles"], lambda r:r["product_code"])
    def measure(codes, attributed_companies):
        roles = {"supplier":Counter(), "importer":Counter()}
        markets = {"supplier":set(), "importer":set()}
        for slot,row in slots.items():
            count = len(codes.intersection(row["product_codes"]))
            if count:
                roles[row["role"]][mappings[slot]["company_external_id"]] = count
                markets[row["role"]].add(row["market_code"])
        listings = [r for r in bundle["listings"] if r["product_code"] in codes]
        rfqs = [r for r in bundle["rfqs"] if r["product_code"] in codes]
        offers = [r for r in bundle["offers"] if r["product_code"] in codes]
        links = [(r["product_code"],slots[r["target_supplier_slot_id"]]["market_code"],r["destination_market"])
                 for r in rfqs if r["type"] == "targeted" and r["category"] == "A"]
        links.extend((r["product_code"],slots[r["supplier_slot_id"]]["market_code"],
                      requests[r["request_id"]]["destination_market"]) for r in offers if r["category"] == "A")
        st = Counter(r["status"] for r in listings)
        kinds = Counter(r["type"] for r in rfqs)
        histogram = Counter(r["response_count"] for r in rfqs)
        active = [r for r in listings if r["status"] == "active"]
        return {
            "products":len(codes), "supplier_companies":len(roles["supplier"]), "importer_companies":len(roles["importer"]),
            "distinct_companies":sum(len(r) for r in roles.values()),
            "supplier_associations":sum(roles["supplier"].values()),"importer_associations":sum(roles["importer"].values()),
            "listing_allocations":len(listings),"active_listings":st["active"],"out_of_stock_listings":st["out_of_stock"],
            "inactive_listings":st["inactive"],"visible_catalog_listings":st["active"]+st["out_of_stock"],
            "generally_available_listings":st["active"],"open_rfqs":kinds["open"],"targeted_rfqs":kinds["targeted"],
            "rfq_allocations":len(rfqs),"offer_allocations":len(offers),
            "response_histogram":{str(k):histogram[k] for k in range(4)},
            "competitive_rfqs":histogram[2]+histogram[3],"category_a_records":len(links),
            "unique_directional_product_relationships":len(set(links)),
            "active_product_coverage":len({r["product_code"] for r in active}),
            "listed_supplier_coverage":len({r["supplier_slot_id"] for r in listings}),
            "active_supplier_coverage":len({r["supplier_slot_id"] for r in active}),
            "rfq_importer_coverage":len({r["buyer_slot_id"] for r in rfqs}),
            "market_coverage":{role:len(v) for role,v in markets.items()},
            "combined_market_coverage":len(set.union(*markets.values())),
            "commercial_group_coverage":dict(sorted(Counter(profiles[c]["commercial_group"] for c in codes).items())),
            **({"unique_affected_companies_by_role":{r:len(v) for r,v in roles.items()}} if attributed_companies else {}),
        }
    catalog = set(profiles)
    public = catalog - RESTRICTED
    historical = measure(catalog, False)
    offline = measure(RESTRICTED, True)
    remaining = measure(public, False)
    findings = [
        {"source_product_code":code,"reference_description":profiles[code]["reference_description"],
         "commercial_group":profiles[code]["commercial_group"],"original_review_notes":profiles[code]["review_notes"],
         "historical_suitability":"no_explicit_product_disposition",
         "disposition":OFFLINE,**measure({code}, True)} for code in sorted(RESTRICTED)
    ]
    overlap = {}
    for role in ("supplier","importer"):
        subset = [set(s["product_codes"]) for s in slots.values() if s["role"] == role]
        overlap[role] = {"lost_all":sum(v <= RESTRICTED for v in subset),
                         "partially_affected":sum(bool(v & RESTRICTED) and bool(v - RESTRICTED) for v in subset),
                         "multiple_restricted_associations":sum(len(v & RESTRICTED)>1 for v in subset)}
    result = {"historical":historical,"offline_excluded":offline,"restriction_only_projection":remaining,
              "overlap":overlap,"per_restricted_product":findings}
    if policies is not None:
        eligible = {code for code in public if suitability_reason(policies.get(code)) is None}
        result["resolved_specification_structural_projection"] = measure(eligible,False)
        result["pending_specification_structural_scope"] = measure(public-eligible,True)
    return result
