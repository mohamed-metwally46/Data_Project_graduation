"""Profile, construct and independently validate the SM-02 planning witness."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from time import perf_counter

from src.analytics.release import MANIFEST, atomic_json, engine_for, stamped
from src.analytics.release_validation import read_json
from src.pipeline import write_json
from src.synthetic.allocation import NoPlan, build_allocations, geography, profile, select_clusters, supplier_bound
from src.synthetic.determinism import canonical_json
from src.synthetic.foundation import POLICY_PATH, load_policy, verify_pinned_source
from src.synthetic.planning_validation import check, validate_plan

PLANNING = Path("data/planning/synthetic_marketplace")
POINTER = PLANNING / "allocation_plan_manifest.json"
REPORT = Path("reports/synthetic_joint_feasibility.json")
BENCHMARK = Path("reports/synthetic_planning_benchmark.json")
SCENARIO = Path("configs/synthetic/planning.v1.json")
GEOGRAPHY = Path("configs/synthetic/m49_reference.json")
ARTIFACTS = ("allocation_plan.json", "geographic_eligibility.json", "product_eligibility.json")


def fingerprint(*objects):
    return "sha256:" + hashlib.sha256(canonical_json(objects).encode("utf-8")).hexdigest()


def read_scenario(path):
    scenario = read_json(path)
    check(scenario["version"] == "1.0.0" and scenario["approval_status"] == "proposed"
          and isinstance(scenario["scenario_id"], str) and bool(scenario["scenario_id"]), "provisional scenario")
    for key in ("supplier_market_cap", "importer_market_cap", "product_prefix_cap"):
        check(type(scenario[key]) is int and scenario[key] > 0, f"scenario {key}")
    check(type(scenario["sensitivity"]["supplier_market_cap"]) is int
          and scenario["sensitivity"]["supplier_market_cap"] > 0, "sensitivity market cap")
    return scenario


def load_context(root, scenario_path):
    started = perf_counter()
    policy = load_policy(root)
    scenario = read_scenario(scenario_path)
    geodata = read_json(root / GEOGRAPHY)
    check(all(region in ("", "Africa", "Americas", "Asia", "Europe", "Oceania")
              for _, region, _ in geodata["rows"].values()), "canonical M49 region labels")
    verified = verify_pinned_source(root, policy)
    verification_time = perf_counter() - started
    manifest = read_json(root / MANIFEST)
    check(all(manifest[k] == v for k,v in policy["source"].items()), "source pin after validation")
    started = perf_counter()
    enrichment = read_json(root / manifest["inputs"]["enrichment_summary"]["path"])
    engine = engine_for(root, enrichment)
    check(engine.metadata["dataset_version"] == policy["source"]["dataset_fingerprint"], "source engine fingerprint")
    engine_time = perf_counter() - started
    started = perf_counter()
    geo = geography(engine.countries, scenario, geodata)
    profiles, stats = profile(engine, geo)
    counts = verified["statistics"]["market_universe"]["category_counts"]
    stats["category_relationships_excluded_by_geography"] = {
        c: counts[c] - stats[f"eligible_category_{c.lower()}_relationships"] for c in "ABC"
    }
    stats["external_relationships_excluded_by_geography"] = (
        verified["statistics"]["market_universe"]["external_relationships"] - stats["eligible_external_relationships"]
    )
    timings = {"pinned_source_verification_seconds": verification_time, "source_initialization_seconds": engine_time,
               "geographic_and_product_profiling_seconds": perf_counter() - started}
    return policy, scenario, geodata, engine, geo, profiles, stats, verified, timings


def make_plan(policy, scenario, engine, geo, profiles):
    started = perf_counter()
    clusters = select_clusters(engine, geo, profiles, scenario, policy["targets"], policy["proposed_defaults"])
    selection = perf_counter() - started
    started = perf_counter()
    plan = build_allocations(clusters, profiles, policy["proposed_defaults"], policy["targets"])
    plan["source"] = policy["source"]
    plan["scenario_id"] = scenario["scenario_id"]
    return plan, {"product_selection_seconds": selection, "joint_allocation_seconds": perf_counter() - started}


def profile_artifacts(geo, profiles, policy):
    return {
        "geographic_eligibility.json": {"planning_only": True, "importable": False, "source": policy["source"],
                                         "records": list(geo.values())},
        "product_eligibility.json": {"planning_only": True, "importable": False, "source": policy["source"],
                                     "records": list(profiles.values())},
    }


def sensitivity(scenario, stats, policy):
    started = perf_counter()
    cap = scenario["sensitivity"]["supplier_market_cap"]
    n = stats["eligible_observed_exporters"]
    demand = policy["targets"]["supplier_roles"]
    result = {"scenario_id": scenario["scenario_id"] + "-tight-supplier-cap",
              "approval_status": "proposed", "supplier_market_cap": cap, "eligible_observed_exporters": n,
              "supplier_slots_upper_bound": n * cap, "required_supplier_slots": demand,
              "coverage_metrics": None, "evidence_distribution": None}
    try:
        supplier_bound(n, cap, demand)
        result["status"] = "not_evaluated_beyond_bound"
    except NoPlan as error:
        result.update(status=error.status, constraint=str(error))
    return result, perf_counter() - started


def publish(root, context, started):
    policy, scenario, geodata, engine, geo, profiles, stats, verified, timings = context
    plan, stages = make_plan(policy, scenario, engine, geo, profiles)
    second, repeated = make_plan(policy, scenario, engine, geo, profiles)
    check(plan == second and fingerprint(plan) == fingerprint(second), "repeat allocation determinism")
    configuration = fingerprint(policy, scenario, geodata)
    plan_id = "sm02-" + fingerprint(configuration, plan).split(":")[1]
    relative = PLANNING / "plans" / plan_id
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    alternative, comparison = sensitivity(scenario, stats, policy)
    with tempfile.TemporaryDirectory(prefix="sm02-stage-", dir=destination.parent) as work:
        stage = Path(work) / "artifacts"
        stage.mkdir()
        files = {"allocation_plan.json": plan, **profile_artifacts(geo, profiles, policy)}
        for name, data in files.items():
            write_json(stage / name, data)
        # Compare actual serialized bytes for the independently rebuilt allocation.
        replay = Path(work) / "replay.json"
        write_json(replay, second)
        first_bytes, second_bytes = (stage / "allocation_plan.json").read_bytes(), replay.read_bytes()
        check(first_bytes == second_bytes, "byte-identical repeat allocation")
        mark = perf_counter()
        results = validate_plan(read_json(stage / "allocation_plan.json"), engine, geo, scenario, policy)
        validation_time = perf_counter() - mark
        stamps = {name: stamped(stage, name) for name in ARTIFACTS}
        manifest = {
            "planning_schema_version": "1.0.0", "planning_only": True, "importable": False,
            "planning_artifact_id": plan_id, "planning_content_fingerprint": fingerprint(plan),
            "configuration_fingerprint": configuration, "source": policy["source"], "scenario": scenario,
            "fixed_targets": policy["targets"], "proposed_defaults": policy["proposed_defaults"],
            "artifact_directory": relative.as_posix(), "artifacts": stamps,
            "structural_feasibility": results["structural_feasibility"],
            "commercial_feasibility": results["commercial_feasibility"],
            "validation": {"status": "passed", "counts": results["counts"],
                           "reproducibility": "byte_identical_repeat_allocation"},
            "outstanding_approvals": list(policy["unresolved"]),
            "full_generation": "blocked",
        }
        if destination.exists():
            check(all(stamped(destination, n) == stamp for n,stamp in stamps.items()), "existing plan integrity")
        else:
            stage.rename(destination)
        report = {
            "planning_only": True, "importable": False, "planning_artifact_id": plan_id,
            "source_verification": verified, "provisional_scenario": scenario["scenario_id"],
            "profiles": stats, "allocation": results,
            "scenario_comparison": [
                {"scenario_id": scenario["scenario_id"], "approval_status": "proposed",
                 "status": "structurally_feasible_commercially_conditional",
                 "supplier_market_cap": scenario["supplier_market_cap"],
                 "importer_market_cap": scenario["importer_market_cap"],
                 "observed_market_distribution": results["geographic_allocation"],
                 "evidence_distribution": results["bilateral_evidence"],
                 "execution_seconds_excluding_source": sum(stages.values())},
                alternative,
            ],
            "recommended_scenario": scenario["scenario_id"],
            "sm03_handoff": "provisional_pending_configuration_and_separate_authorization",
            "backend_compatibility": "pending_confirmation",
        }
        from scripts.benchmark_market_opportunities import peak_memory
        benchmark = {"planning_artifact_id": plan_id, **timings, **stages,
                     "repeat_allocation_seconds_with_loaded_indexes": sum(repeated.values()),
                     "independent_validation_seconds": validation_time,
                     "scenario_comparison_seconds": comparison,
                     "total_planning_seconds_before_reporting": perf_counter() - started,
                     "artifact_sizes_bytes": {name: stamp["size_bytes"] for name, stamp in stamps.items()},
                     "memory": peak_memory()}
        atomic_json(root / REPORT, report)
        atomic_json(root / BENCHMARK, benchmark)
        atomic_json(root / POINTER, manifest)
    return manifest


def validate_published(root, context):
    policy, scenario, geodata, engine, geo, profiles, _, _, _ = context
    manifest = read_json(root / POINTER)
    check(manifest["planning_only"] is True and manifest["importable"] is False
          and manifest["source"] == policy["source"] and manifest["scenario"] == scenario
          and manifest["configuration_fingerprint"] == fingerprint(policy, scenario, geodata)
          and manifest["fixed_targets"] == policy["targets"]
          and manifest["proposed_defaults"] == policy["proposed_defaults"], "manifest policy and source")
    plan_id = manifest["planning_artifact_id"]
    check(isinstance(plan_id, str) and plan_id.startswith("sm02-") and len(plan_id) == 69
          and all(ch in "0123456789abcdef" for ch in plan_id[5:]), "planning artifact ID")
    relative = PLANNING / "plans" / plan_id
    check(manifest["artifact_directory"] == relative.as_posix()
          and set(manifest["artifacts"]) == set(ARTIFACTS), "artifact directory and set")
    location = root / relative
    check(all(stamped(location, name) == manifest["artifacts"][name] for name in ARTIFACTS), "artifact hashes")
    plan = read_json(location / ARTIFACTS[0])
    check(fingerprint(plan) == manifest["planning_content_fingerprint"]
          and plan_id == "sm02-" + fingerprint(manifest["configuration_fingerprint"], plan).split(":")[1],
          "allocation content identity")
    for name, data in profile_artifacts(geo, profiles, policy).items():
        check(read_json(location / name) == data, f"independent profile {name}")
    results = validate_plan(plan, engine, geo, scenario, policy)
    check(results["counts"] == manifest["validation"]["counts"]
          and results["structural_feasibility"] == manifest["structural_feasibility"]
          and results["commercial_feasibility"] == manifest["commercial_feasibility"]
          and manifest["full_generation"] == "blocked", "manifest feasibility and counts")
    return {"planning_artifact_id": plan_id, "status": "validated", **results["counts"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("profile", "plan", "validate", "inspect", "compare-scenarios"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--scenario", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = read_json(args.root / POINTER)
        elif args.command == "compare-scenarios":
            result = read_json(args.root / REPORT)["scenario_comparison"]
        else:
            started = perf_counter()
            context = load_context(args.root, args.scenario or args.root / SCENARIO)
            if args.command == "profile":
                result = context[6]
            elif args.command == "validate":
                result = validate_published(args.root, context)
            else:
                result = publish(args.root, context, started)
        print(json.dumps(result, indent=2))
    except (NoPlan, ValueError, OSError) as error:
        parser.exit(1, json.dumps({"status": getattr(error, "status", "blocked"), "error": str(error)}) + "\n")


if __name__ == "__main__":
    main()
