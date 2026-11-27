"""Generate, validate and publish only the approved SM-03B canonical company stage."""
from collections import Counter
from itertools import combinations
from pathlib import Path
import re
from statistics import mean
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

from scripts.benchmark_market_opportunities import peak_memory
from src.analytics.release import atomic_json, stamped
from src.analytics.release_validation import read_json
from src.pipeline import write_json
from src.synthetic.company_identity import _build_companies, near_duplicate, normalized_brand, read_templates
from src.synthetic.company_stage import (
    EXPECTED_PLAN, READINESS, inspect_contract, inspect_inputs, read_planning_input,
    require, require_population_authorized, verify_population_approval,
)
from src.synthetic.company_validation import validate_population
from src.synthetic.determinism import population_namespace
from src.synthetic.foundation import load_policy
from src.synthetic.planning import SCENARIO, fingerprint, load_context, validate_published


STAGE = Path("data/synthetic/stages/companies")
POINTER = STAGE / "company_stage_manifest.json"
BUNDLE = "company_stage.json"
QUALITY = "company_validation_report.json"
COLLECTIONS = ("metadata", "companies", "company_roles", "company_products",
               "slot_company_mapping", "identity_registry")
DEPENDENCIES = (
    "product_specific_measurement_units", "product_level_price_ranges", "price_basis",
    "decimal_precision", "stock_bounds", "minimum_order_quantities", "quantity_increments",
    "rfq_requested_quantity_rules", "offer_fulfillment_compatibility", "commercial_feasibility",
    "actual_backend_field_mappings", "separate_sm04_authorization",
)


def verify_tests(root):
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=root, capture_output=True, text=True,
    )
    output = completed.stdout + completed.stderr
    match = re.search(r"^Ran (\d+) tests? in ", output, flags=re.MULTILINE)
    require(completed.returncode == 0 and match is not None and int(match[1]) >= 42
            and output.rstrip().endswith("\nOK"), "required regression suite failed\n" + output)
    return {"status": "passed", "tests_passed": int(match[1]),
            "command": "python -m unittest discover -s tests -v"}


def quality_report(data, geo, identity, validation):
    companies = data["companies"]
    mappings = {m["company_external_id"]: m for m in data["slot_company_mapping"]}
    names = {row["display_code"]: normalized_brand(row["name"]) for row in companies}
    near = [
        [a, b] for a, b in combinations(names, 2) if near_duplicate(names[a], names[b])
    ]
    lengths = [len(c["description"]) for c in companies]
    stems = sorted(identity["brand_starts"], key=lambda stem: (-len(stem), stem))
    by_stem = Counter(next(stem for stem in stems if row["brand"].startswith(stem)) for row in companies)
    markets = {"supplier": Counter(), "importer": Counter()}
    regions = {"supplier": Counter(), "importer": Counter()}
    portfolios = {"supplier": Counter(), "importer": Counter()}
    distinct_products = {"supplier": set(), "importer": set()}
    samples = {}
    sample_markets = set()
    for c in companies:
        mapping = mappings[c["external_id"]]
        role, market = mapping["initial_role"], c["market_code"]
        group = c["industry_group"]
        region = geo[market]["region"]
        markets[role][market] += 1
        regions[role][region] += 1
        portfolios[role][len(mapping["product_codes"])] += 1
        distinct_products[role].update(mapping["product_codes"])
        sample_key = (role, group, c["business_type"])
        if sample_key not in samples and (role, group, market) not in sample_markets:
            samples[sample_key] = {
                "is_synthetic": True, "display_code": c["display_code"], "name": c["name"],
                "market": geo[market]["name"], "market_code": market, "role": role,
                "industry_group": group, "business_type": c["business_type"],
                "description": c["description"], "product_codes": mapping["product_codes"],
            }
            sample_markets.add((role, group, market))
    return {
        "validation": validation,
        "name_quality": {"unique_normalized_company_names": len(set(names.values())),
                         "near_duplicate_warning_count": len(near), "warning_pairs_by_display_code": near,
                         "near_duplicate_rule": "Normalized whole names within one edit",
                         "legal_or_trademark_review_performed": False},
        "brand_quality": {"unique_brands": len({c["brand"] for c in companies}),
                          "distinct_configured_stems_used": len(by_stem), "counts_by_stem": dict(sorted(by_stem.items())),
                          "near_duplicate_brand_pairs": 0,
                          "stem_attribution": "Longest matching configured brand prefix"},
        "business_types": dict(Counter(c["business_type"] for c in companies)),
        "industry_groups": dict(Counter(c["industry_group"] for c in companies)),
        "descriptions": {"length_min": min(lengths), "length_max": max(lengths), "length_mean": mean(lengths),
                         "unique": len({c["description"] for c in companies})},
        "geography": {"markets_by_role": {
            role: [{"market_code": code, "name": geo[code]["name"], "region": geo[code]["region"],
                    "company_count": count} for code, count in sorted(counts.items())]
            for role, counts in markets.items()}, "regions_by_role": {role: dict(v) for role, v in regions.items()}},
        "portfolios": {role: {"companies_by_portfolio_size": dict(sorted(counts.items())),
                              "associations": sum(size * count for size, count in counts.items()),
                              "distinct_products": len(distinct_products[role])}
                       for role, counts in portfolios.items()},
        "safety_and_identity": {
            "validated_reserved_example_contacts": sum(c["email"].endswith(".example") for c in companies),
            "null_websites": sum(c["website"] is None for c in companies),
            "null_phone_address_tax_and_registration": sum(all(c[k] is None for k in (
                "phone", "street_address", "tax_identifier", "registration_number"
            )) for c in companies),
            "not_verified": sum(c["verification_status"] == "not_verified" for c in companies),
            "monograms": sum(c["visual_identity"]["type"] == "monogram" for c in companies),
            "synthetic_labels": sum(c["is_synthetic"] for c in companies),
            "unique_external_ids": len(mappings), "unique_display_codes": len(names),
            "unique_persistent_keys": len({r["persistent_company_key"] for r in data["identity_registry"]}),
            "resolved_slots": len(mappings),
        },
        "samples": list(samples.values()),
    }


def verify_artifacts(directory, expected):
    require(directory.is_dir() and not directory.is_symlink()
            and set(expected) == {file.name for file in directory.iterdir()}
            and all(not (directory / filename).is_symlink()
                    and stamped(directory, filename) == expected[filename] for filename in expected),
            "published company directory and artifact hashes")


def inspect_publication(root, recorded):
    require(approval_paths(root.resolve()), "isolated company publication location")
    manifest = read_json(root / POINTER)
    artifacts = manifest["artifacts"]
    stage_id = "sm03b-" + fingerprint(artifacts).split(":")[1]
    relative = STAGE / "populations" / stage_id
    require(manifest["status"] == "validated" and manifest["stage"] == "SM-03B"
            and manifest["stage_id"] == recorded["stage_id"] == stage_id
            and manifest["artifact_directory"] == relative.as_posix()
            and manifest["validation"] == recorded["validation"] and artifacts == recorded["artifacts"]
            and manifest["backend_importable"] is False and manifest["full_marketplace_release"] is False,
            "company manifest and recorded publication")
    verify_artifacts(root / relative, artifacts)


def commit_stage(directory, prepared, pointer, manifest):
    """Commit an immutable directory and switch the company pointer only after hash checks."""
    directory.parent.mkdir(parents=True, exist_ok=True)
    if not directory.exists():
        try:
            prepared.rename(directory)
        except OSError:
            if not directory.is_dir():
                raise
    verify_artifacts(directory, manifest["artifacts"])
    atomic_json(pointer, manifest)


def generate(root):
    started = perf_counter()
    root = root.resolve()
    timings = {}
    identity = read_templates(root)
    verify_population_approval(identity)
    policy = load_policy(root)
    inspect_contract(root, identity)
    require(approval_paths(root), "isolated company publication location")
    step = perf_counter()
    baseline = inspect_inputs(root)
    timings["readiness_input_checks"] = perf_counter() - step
    step = perf_counter()
    tests = verify_tests(root)
    timings["regression_tests"] = perf_counter() - step
    context = load_context(root, root / SCENARIO)
    timings.update(context[-1])
    step = perf_counter()
    verification = validate_published(root, context)
    planning, plan, geo, _ = read_planning_input(root, policy)
    figures = baseline["planning"]["counts"]
    require(verification["planning_artifact_id"] == EXPECTED_PLAN and verification["status"] == "validated"
            and baseline["planning"]["artifact_hashes"] == planning["artifacts"]
            and figures["bilateral_categories"] == {"A": 1080, "B": 0, "C": 0}
            and figures["unique_directional_relationships"] == 300
            and figures["rfq_types"].get("targeted") == 180
            and figures["response_distribution"] == {"0": 120, "1": 180, "2": 180, "3": 120}
            and figures["portfolio_associations"] == {"supplier": 1200, "importer": 600}
            and figures["supplier_markets"] == 25 and figures["importer_markets"] == 75,
            "independent approved allocation verification and exact population totals")
    require(identity == read_templates(root), "identity configuration changed during preflight")
    timings["allocation_verification"] = perf_counter() - step
    technical = {**baseline["technical_checks"], "fixture_engine_and_validator_tested": True,
                 "fixture_isolation_tested": True, "independent_source_verification": True,
                 "independent_plan_validation": True, "stage_output_isolation": True}
    approvals = require_population_authorized(policy, identity, technical)
    require(not approvals["full_generation_guard_passed"], "full generation guard must remain blocked")

    markets = {r["market_code"]: r for r in geo["records"]}
    plan = {**plan, "plan_id": EXPECTED_PLAN}
    permanent = identity["permanent_identity"]
    cohort, namespace = permanent["population_key"], permanent["approved_root_namespace"]
    seed = identity["approved_identity"]["master_seed"]
    engine = context[3]

    def observed_role(code, market, role):
        links = engine.products.get(code)
        return links is not None and market in (links.exports if role == "exporter" else links.imports)

    (root / STAGE).mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=root / STAGE) as work:
        candidate = Path(work) / "candidate"
        candidate.mkdir()
        builds = []
        replay_started = None
        serial_seconds = 0
        for index in range(1, 3):
            step = perf_counter()
            if index == 2:
                replay_started = step
            build_metrics = {}
            data = _build_companies(plan, markets, identity, (), cohort=cohort, namespace=namespace, seed=seed,
                                    fixture_only=False, timings=build_metrics)
            timings[f"build_{index}_generation"] = perf_counter() - step
            timings[f"build_{index}_registry_generation"] = build_metrics["registry_generation"]
            path = candidate / BUNDLE if index == 1 else Path(work) / BUNDLE
            step = perf_counter()
            write_json(path, data)
            serial_seconds += perf_counter() - step
            builds.append({"bundle": stamped(path.parent, path.name),
                           "collection_fingerprints": {name: fingerprint(data[name]) for name in COLLECTIONS}})
        require(builds[0] == builds[1] and (candidate / BUNDLE).read_bytes() == path.read_bytes(),
                "full-population reproducibility")
        timings["reproducibility_verification"] = perf_counter() - replay_started
        timings["serialization"] = serial_seconds

        step = perf_counter()
        serialized = read_json(candidate / BUNDLE)
        validation = validate_population(root, serialized, plan, markets, identity, observed_role)
        timings["independent_serialized_population_validation"] = perf_counter() - step
        step = perf_counter()
        quality = quality_report(serialized, markets, identity, validation)
        write_json(candidate / QUALITY, quality)
        timings["quality_report"] = perf_counter() - step
        artifacts = {name: stamped(candidate, name) for name in (BUNDLE, QUALITY)}
        require(artifacts[BUNDLE] == builds[0]["bundle"], "candidate bundle changed during validation")
        stage_id = "sm03b-" + fingerprint(artifacts).split(":")[1]
        relative = STAGE / "populations" / stage_id
        manifest = {
            "status": "validated", "stage": "SM-03B", "stage_id": stage_id,
            "artifact_directory": relative.as_posix(), "population_id": cohort,
            "is_synthetic": True, "is_intermediate": True, "backend_importable": False,
            "full_marketplace_release": False, "source": policy["source"],
            "approved_sm02_plan_id": EXPECTED_PLAN,
            "planning_configuration_fingerprint": planning["configuration_fingerprint"],
            "planning_artifacts": planning["artifacts"], "schema": baseline["canonical_contract"],
            "identity_configuration_fingerprint": baseline["identity_configuration_fingerprint"],
            "master_seed": seed, "root_namespace": namespace,
            "derived_population_namespace": str(population_namespace(namespace, cohort)),
            "identifier_algorithm": permanent["algorithm"], "company_key_format": "identity-NNNNNN",
            "validation": validation, "artifacts": artifacts,
            "reproducibility": {"byte_identical": True, "independent_builds": builds,
                                "collection_fingerprint_encoding": "Planning fingerprint of each parsed collection"},
            "approvals": {"strategy_decisions": identity["approved_strategy"],
                          "company_population": identity["company_population_approval"],
                          "root_namespace": permanent["root_namespace_approval_reference"],
                          "canonical_key_review": permanent["identity_key_review_reference"]},
            "remaining_dependencies": list(DEPENDENCIES),
        }
        step = perf_counter()
        commit_stage(root / relative, candidate, root / POINTER, manifest)
        timings["stage_publication"] = perf_counter() - step
    timings["total_execution"] = perf_counter() - started
    try:
        memory = peak_memory()
    except (OSError, ImportError) as error:
        memory = {"peak_bytes": None, "method": str(error)}
    readiness = {
        **baseline, "status": "published", "technical_checks": technical, "approvals": approvals,
        "source_verification": context[7]["verification"], "independent_plan_validation": verification,
        "company_stage": {"stage_id": stage_id, "manifest": POINTER.as_posix(),
                          "artifact_directory": relative.as_posix(), "validation": validation,
                          "artifacts": artifacts},
        "reproducibility": manifest["reproducibility"], "regression_suite": tests,
        "measurements_seconds": {**baseline["measurements_seconds"], **timings},
        "peak_process_memory": memory, "remaining_dependencies": list(DEPENDENCIES),
    }
    atomic_json(root / READINESS, readiness)
    return readiness


def approval_paths(root):
    """Reject redirected stage directories or a redirected manifest."""
    for relative in (STAGE, STAGE / "populations", POINTER):
        if (root / relative).resolve() != root / relative:
            return False
    return True
