"""Inspect SM-03 approval gates and generate the approved company-only stage."""
import argparse
from collections import Counter
import json
from pathlib import Path
from time import perf_counter

from jsonschema.exceptions import SchemaError, ValidationError

from src.analytics.release import MANIFEST, digest, snapshot, stamped
from src.analytics.release_validation import read_json, schema_validator, unique_index
from src.synthetic.company_identity import CONTRACT_VERSION, company_context, presentation_group, read_templates, template_fingerprint
from src.synthetic.foundation import load_policy, require_generation_ready
from src.synthetic.planning import ARTIFACTS, GEOGRAPHY, PLANNING, POINTER, SCENARIO, fingerprint


EXPECTED_PLAN = "sm02-90bf5c26373c3d2c45f3fe7f371fbbe8a45b880825f9aa0ee9315de2a96b9ef3"
SCHEMA = "schemas/company_stage.proposed.schema.json"
SCHEMA_SHA256 = "f37213461ede31e9ab233a2727716706173afdb5e2d61f679b08feaa79406417"
APPROVAL_REFERENCE = "User attachment d044fc1c-4991-452b-b6e4-e5d57192afd8"
READINESS = Path("reports/synthetic_company_readiness.json")
TECHNICAL_CHECKS = ("source_and_plan_integrity", "canonical_schema_validated", "identity_config_validated",
                    "fixture_engine_and_validator_tested", "fixture_isolation_tested")
STAGES = {"SM-03A": "authorized", "SM-03B": "conditional", "SM-04": "unauthorized",
          "SM-05": "unauthorized", "SM-06": "unauthorized", "backend_import": "unauthorized"}


def require(condition, detail):
    if not condition:
        raise ValueError(f"Company-stage input check failed: {detail}")


def approval_state(policy, identity, verified=None):
    verified = verified or {}
    permanent = identity["permanent_identity"]
    stages = identity["authorization"]
    root_reference = permanent["root_namespace_approval_reference"]
    root_approved = (permanent["approved_root_namespace"] == permanent["proposed_root_namespace"]
                     and isinstance(root_reference, str) and bool(root_reference.strip()))
    missing = []
    if (not identity.get("approved_plan") or not set(identity.get("approved_strategy", ()))
            == {f"SM-03.R{i}" for i in range(1, 6)}):
        missing.append("approved_plan_and_strategies")
    if not root_approved:
        missing.append("exact_root_namespace")
    key_review = permanent["identity_key_review_reference"]
    if not isinstance(key_review, str) or not key_review.strip():
        missing.append("canonical_identity_key_review")
    if stages != STAGES:
        missing.append("conditional_company_only_authorization")
    company_specific = [name for name in TECHNICAL_CHECKS if verified.get(name) is not True]
    try:
        require_generation_ready(policy)
        full_guard = True
    except ValueError:
        full_guard = False
    return {
        "pending_company_approvals": missing,
        "pending_company_technical_checks": company_specific,
        "stage_authorization": stages,
        "company_population_status": "blocked" if missing or company_specific else "gate_ready",
        "full_generation_guard_passed": full_guard,
        "policy_generation_status": policy["generation_status"],
        "backend_contract_status": policy["contract_status"],
        "namespace_status": "approved" if root_approved else "proposed_marketplace_namespace_unapproved",
    }


def require_population_authorized(policy, identity, verified=None):
    state = approval_state(policy, identity, verified)
    blockers = state["pending_company_approvals"] + state["pending_company_technical_checks"]
    if blockers:
        raise ValueError("Company population blocked: " + ", ".join(blockers))
    return state


def inspect_contract(root, identity):
    permanent = identity["permanent_identity"]
    require(identity["authorization"] == STAGES, "recorded stage authorization")
    require(permanent["proposed_root_namespace"] == "9e5fdfc5-2675-57fe-8e94-81dc91ed9639"
            and permanent["approved_root_namespace"] in (None, permanent["proposed_root_namespace"])
            and permanent["population_key"] == "globiq-marketplace-baseline-001"
            and permanent["algorithm"] == "hierarchical_uuid5_v1", "namespace policy")
    schema_validator(root, "company_stage.proposed")
    require(digest(root / SCHEMA) == SCHEMA_SHA256, "canonical schema SHA-256")
    return {"version": CONTRACT_VERSION, "path": SCHEMA, "sha256": SCHEMA_SHA256,
            "scope": "canonical_intermediate_not_backend_importable"}


def verify_population_approval(identity):
    permanent = identity["permanent_identity"]
    require(permanent["approved_root_namespace"] == permanent["proposed_root_namespace"]
            == "9e5fdfc5-2675-57fe-8e94-81dc91ed9639"
            and permanent["root_namespace_approval_reference"] == f"{APPROVAL_REFERENCE}, SM-03B section 2",
            "exact permanent namespace approval")
    require(permanent["population_key"] == "globiq-marketplace-baseline-001"
            and permanent["algorithm"] == "hierarchical_uuid5_v1"
            and permanent["identity_key_review_reference"] ==
            f"{APPROVAL_REFERENCE}, sections 2 and 7. Existing hierarchical_uuid5_v1 and identity-NNNNNN approved.",
            "canonical key approval")
    expected_config = "sha256:852bd021302a857f1da4cd685bc0ca9052f2710055498e6fc868a4be72b591f8"
    require(identity.get("company_population_approval") == {
        "reference": f"{APPROVAL_REFERENCE}, sections 2, 7 and 20",
        "scope": "isolated_canonical_company_stage_only",
        "planning_artifact_id": EXPECTED_PLAN,
        "planning_configuration_fingerprint": expected_config,
        "canonical_schema_sha256": SCHEMA_SHA256,
        "company_key_format": "identity-NNNNNN",
    } and identity["approved_plan"]["configuration_fingerprint"] == expected_config
        and identity["approved_plan"]["planning_artifact_id"] == EXPECTED_PLAN
        and identity["authorization"] == STAGES, "company-only approval binding to the exact plan and schema")
    reconciled_baseline = {key: value for key, value in identity.items() if key != "company_population_approval"}
    reconciled_baseline["permanent_identity"] = {
        **permanent, "approved_root_namespace": None, "root_namespace_approval_reference": None,
        "identity_key_review_reference": None,
    }
    require(template_fingerprint(reconciled_baseline) ==
            "sha256:568258b7b68a7daf35cec8573436f0b655b216cdf1ed955f785d121d287480ea",
            "approved identity configuration")


def reusable_evidence(root, identity, contract, planning_id):
    path = root / READINESS
    if not path.is_file():
        return {}
    previous = read_json(path)
    if (previous.get("identity_configuration_fingerprint") != template_fingerprint(identity)
            or previous.get("canonical_contract") != contract
            or previous.get("planning", {}).get("artifact_id") != planning_id):
        return {}
    return previous.get("technical_checks", {})


def read_planning_input(root, policy):
    started = perf_counter()
    manifest = read_json(root / POINTER)
    scenario, geopolicy = read_json(root / SCENARIO), read_json(root / GEOGRAPHY)
    relative = PLANNING / "plans" / EXPECTED_PLAN
    require(manifest["planning_artifact_id"] == EXPECTED_PLAN
            and manifest["artifact_directory"] == relative.as_posix(), "unexpected planning artifact")
    require(manifest["source"] == policy["source"] and manifest["scenario"] == scenario
            and manifest["planning_schema_version"] == "1.0.0" and manifest["planning_only"] is True
            and manifest["importable"] is False and manifest["validation"]["status"] == "passed"
            and manifest["structural_feasibility"] == "validated_provisional"
            and manifest["configuration_fingerprint"] == fingerprint(policy, scenario, geopolicy)
            and manifest["fixed_targets"] == policy["targets"]
            and manifest["proposed_defaults"] == policy["proposed_defaults"], "plan status, source, or policy")
    location = root / relative
    require(set(manifest["artifacts"]) == set(ARTIFACTS) and all(
        stamped(location, name) == manifest["artifacts"][name] for name in ARTIFACTS
    ), "planning artifact hash or size mismatch")
    plan = read_json(location / "allocation_plan.json")
    geo = read_json(location / "geographic_eligibility.json")
    require(fingerprint(plan) == manifest["planning_content_fingerprint"]
            and EXPECTED_PLAN == "sm02-" + fingerprint(manifest["configuration_fingerprint"], plan).split(":")[1]
            and plan["source"] == geo["source"] == policy["source"], "plan content or artifact source")
    require(all(row["region"] in (None, "Africa", "Americas", "Asia", "Europe", "Oceania")
                for row in geo["records"]), "unexpected geographic region label")
    return manifest, plan, geo, perf_counter() - started


def reconcile_counts(plan, policy):
    slots = unique_index(plan["company_slots"], lambda r: r["slot_id"])
    responses = unique_index(plan["rfq_allocations"], lambda r: r["request_id"])
    offers = plan["offer_allocations"]
    portfolios = Counter()
    roles = Counter()
    for slot in slots.values():
        role = slot["role"]
        roles[role] += 1
        portfolios[role] += len(slot["product_codes"])
    figures = {
        "products": len(unique_index(plan["selected_products"], lambda r: r["product_code"])),
        "companies": len(slots), "supplier_roles": roles["supplier"], "importer_roles": roles["importer"],
        "listings": len(plan["listing_allocations"]), "rfqs": len(responses), "offers": len(offers),
    }
    require(figures == policy["targets"], "fixed allocation counts")
    require(all(portfolios[role] == roles[role] * policy["proposed_defaults"][f"products_per_{role}"]
                for role in roles), "portfolio counts")
    respondents = {rid: set() for rid in responses}
    categories = Counter()
    relationships = set()
    def classify_record(code, supplier, buyer, category):
        categories[category] += 1
        relationships.add((slots[supplier]["market_code"], code, slots[buyer]["market_code"], category))
    for row in responses.values():
        if row["type"] == "targeted":
            classify_record(row["product_code"], row["target_supplier_slot_id"], row["buyer_slot_id"], row["category"])
    for offer in offers:
        rid, supplier = offer["request_id"], offer["supplier_slot_id"]
        require(supplier not in respondents[rid], "duplicate respondent")
        respondents[rid].add(supplier)
        classify_record(offer["product_code"], supplier, responses[rid]["buyer_slot_id"], offer["category"])
    require(all(len(respondents[rid]) == r["response_count"] for rid,r in responses.items()), "actual response count")
    mix = Counter(str(len(company_ids)) for company_ids in respondents.values())
    require(mix == Counter(policy["proposed_defaults"]["offers_per_rfq"]), "response distribution")
    request_types = Counter(row["type"] for row in responses.values())
    return {**figures, "portfolio_associations": dict(portfolios), "response_distribution": dict(mix),
            "listing_statuses": dict(Counter(r["status"] for r in plan["listing_allocations"])),
            "supplier_markets": len({s["market_code"] for s in slots.values() if s["role"] == "supplier"}),
            "importer_markets": len({s["market_code"] for s in slots.values() if s["role"] == "importer"}),
            "product_prefix_groups": len({r["provisional_group"] for r in plan["selected_products"]}),
            "active_listing_product_coverage": len({r["product_code"] for r in plan["listing_allocations"]
                                                    if r["status"] == "active"}),
            "rfq_product_coverage": len({r["product_code"] for r in responses.values()}),
            "rfq_importer_coverage": len({r["buyer_slot_id"] for r in responses.values()}),
            "rfq_types": dict(request_types),
            "distinct_supplier_competition_requests": sum(len(v)>1 for v in respondents.values()),
            "bilateral_categories": {c: categories[c] for c in "ABC"},
            "bilateral_records": sum(categories.values()),
            "unique_directional_relationships": len(relationships)}


def inspect_inputs(root):
    started = perf_counter()
    policy = load_policy(root)
    identity = read_templates(root)
    ti = read_json(root / MANIFEST)
    require(ti["status"] == "validated" and all(ti[k] == v for k,v in policy["source"].items()),
            "pinned Trade Intelligence manifest")
    sources, contracts = snapshot(root)
    require(ti["inputs"] == sources and ti["contracts"] == contracts, "Trade Intelligence input integrity")
    ti_directory = Path(ti["artifact_directory"])
    require(ti_directory == MANIFEST.parent / "releases" / policy["source"]["release_id"]
            and set(ti["artifacts"]) == {"country_intelligence","product_intelligence",
                                         "route_intelligence","market_opportunity_summary"},
            "Trade Intelligence artifact location")
    require(all(all(entry[k] == value for k, value in stamped(root/ti_directory, f"{name}.json").items())
                for name,entry in ti["artifacts"].items()), "Trade Intelligence artifact integrity")
    source_seconds = perf_counter() - started
    planning, plan, geo, plan_load = read_planning_input(root, policy)
    require(identity["approved_plan"] == {key: planning[key] for key in (
        "planning_artifact_id", "configuration_fingerprint", "planning_content_fingerprint", "source", "artifacts"
    )}, "exact SM-02 approval binding")
    contract = inspect_contract(root, identity)
    started = perf_counter()
    counts = reconcile_counts(plan, policy)
    products = unique_index(plan["selected_products"], lambda row: row["product_code"])
    markets = unique_index(geo["records"], lambda row: row["market_code"])
    presentation = Counter()
    for slot in plan["company_slots"]:
        context = company_context(slot, products, markets, {"allocation_plan_id": EXPECTED_PLAN, **policy["source"]})
        require(all(context["reference_descriptions"]), f"missing reference description in {context['slot_id']}")
        presentation[presentation_group(identity, context)] += 1
    reconciliation = perf_counter() - started
    technical = {**reusable_evidence(root, identity, contract, EXPECTED_PLAN),
                 "source_and_plan_integrity": True, "canonical_schema_validated": True,
                 "identity_config_validated": True}
    return {
        "source": {**policy["source"], "integrity_status": "passed", "statistics": ti["statistics"]},
        "planning": {"artifact_id": EXPECTED_PLAN, "configuration_fingerprint": planning["configuration_fingerprint"],
                     "content_fingerprint": planning["planning_content_fingerprint"],
                     "artifact_hashes": planning["artifacts"], "provisional": True, "counts": counts},
        "geography": {"canonical_region_labels": True, "reference_markets": len(geo["records"]),
                      "provisional_business_location_candidates": sum(r["supplier_eligible"] for r in geo["records"])},
        "approved_decisions": identity["approved_strategy"],
        "identity_configuration_fingerprint": template_fingerprint(identity),
        "context_preview": {"slots_checked_without_instantiation": sum(presentation.values()),
                            "presentation_groups": dict(sorted(presentation.items()))},
        "canonical_contract": contract, "technical_checks": technical,
        "approvals": approval_state(policy, identity, technical),
        "measurements_seconds": {"pinned_source_hash_checks": source_seconds, "plan_artifact_loading": plan_load,
                                 "serialized_plan_count_reconciliation": reconciliation},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect-inputs", "readiness", "inspect-identifiers", "validate-config", "generate"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.command in ("inspect-identifiers", "validate-config"):
            config = read_templates(args.root)
            result = {"identity": config["permanent_identity"], "approved_identity": config["approved_identity"],
                      "canonical_contract": inspect_contract(args.root, config)}
        elif args.command == "generate":
            from src.synthetic.company_publication import generate

            result = generate(args.root)
        else:
            result = inspect_inputs(args.root)
            if args.command == "readiness" and (args.root / READINESS).is_file():
                previous = read_json(args.root / READINESS)
                if previous.get("status") == "published" and result["approvals"]["company_population_status"] == "gate_ready":
                    from src.synthetic.company_publication import inspect_publication

                    inspect_publication(args.root, previous["company_stage"])
                    result.update(status=previous["status"], company_stage=previous["company_stage"])
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, SchemaError, ValidationError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
