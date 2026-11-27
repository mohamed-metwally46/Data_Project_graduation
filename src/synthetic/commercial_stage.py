"""Inspect, solve, validate, and publish an isolated SM-04A planning proposal."""
import argparse
import json
from pathlib import Path
import platform
from tempfile import TemporaryDirectory
from time import perf_counter

from jsonschema.exceptions import SchemaError, ValidationError

from scripts.benchmark_market_opportunities import peak_memory
from src.analytics.release import atomic_json, digest, stamped
from src.analytics.release_validation import read_json, schema_validator
from src.pipeline import write_json
from src.synthetic.commercial_config import APPROVALS, CONFIG, FLAGS, CommercialError, load_config, require, resolve_profiles
from src.synthetic.commercial_planning import OUTPUTS, SEARCH_LIMIT, VERSION, solve
from src.synthetic.commercial_validation import EXPECTED, quality_report, validate_plan
from src.synthetic.company_identity import read_templates
from src.synthetic.company_publication import (
    BUNDLE as COMPANY_BUNDLE, POINTER as COMPANY_POINTER, commit_stage, verify_artifacts, verify_tests,
)
from src.synthetic.company_stage import EXPECTED_PLAN, SCHEMA_SHA256, inspect_contract, read_planning_input, reconcile_counts, verify_population_approval
from src.synthetic.company_validation import validate_population
from src.synthetic.foundation import load_policy, require_generation_ready
from src.synthetic.planning import SCENARIO, fingerprint, load_context, validate_published

BASE = Path("data/planning/commercial_feasibility")
POINTER = BASE / "commercial_plan_manifest.json"
REPORT = Path("reports/synthetic_commercial_readiness.json")
PROFILE = "resolved_product_profiles.json"
REVIEW = "product_commercial_review.md"
VALIDATION = "commercial_feasibility_report.json"
QUALITY = "commercial_quality_report.json"
FILES = {"profiles": PROFILE, **OUTPUTS}
COMPANY_ID = "sm03b-68a129e0877cc0b7405db11375d2ef72ee862b7545075bd36c06099fa8e42363"
COMPANY_CONTENT = {
 COMPANY_BUNDLE: ("5d41f334d6c5bac78046e21ca231df826a9c5d844dc89bc47c6c753c1a1abce4", 2219027),
 "company_validation_report.json": ("fa1b012c76171f61e7ca41a7cec4ec929e1d30883c6f66f42566f44b6c92d58e", 22022),
}
SCHEMAS = ("commercial_config.v1", "commercial_plan.v1", "listing_stage.proposed")
NEEDED = {key: "pending" for key in APPROVALS}
IMPLEMENTATION = ("commercial_stage", "commercial_config", "commercial_planning", "commercial_validation", "listing_stage")


def timings_step(timings, name, callback, *args):
    started = perf_counter()
    result = callback(*args)
    timings[name] = perf_counter() - started
    return result


def read_inputs(root, full, timings):
    policy = load_policy(root)
    config = load_config(root)
    require(all((root / rel).resolve() == root / rel for rel in (BASE, BASE / "plans", POINTER)),
            "OUTPUT_ISOLATION_FAILURE", "commercial planning path redirects outside its canonical location")
    identity = read_templates(root)
    verify_population_approval(identity)
    contract = inspect_contract(root, identity)
    # SM-02's independent validator already includes the complete read-only source workflow.
    context = load_context(root, root / SCENARIO) if full else None
    structural = timings_step(timings, "sm02_hash_and_load", read_planning_input, root, policy)
    manifest, allocation, geography, _ = structural
    require(identity["approved_plan"] == {key: manifest[key] for key in identity["approved_plan"]},
            "ALLOCATION_MISMATCH", "SM-02 artifacts diverged from the approved baseline")
    counts = reconcile_counts(allocation, policy)
    require(counts["product_prefix_groups"] == 94 and sum(r["supplier_eligible"] for r in geography["records"]) == 187
            and counts["bilateral_categories"] == {"A":1080,"B":0,"C":0}
            and counts["unique_directional_relationships"] == 300,
            "ALLOCATION_MISMATCH", "approved groups, geography or bilateral totals")
    if full:
        timings.update(context[-1])
        result = timings_step(timings, "sm02_independent_validation", validate_published, root, context)
        require(result["status"] == "validated" and result["planning_artifact_id"] == EXPECTED_PLAN,
                "ALLOCATION_MISMATCH", "independent SM-02 validation")
    else:
        from src.analytics.release import MANIFEST, snapshot
        published = read_json(root / MANIFEST)
        sources, contracts = snapshot(root)
        require(published["status"] == "validated" and all(published[k] == v for k,v in policy["source"].items())
                and published["inputs"] == sources and published["contracts"] == contracts,
                "SOURCE_INTEGRITY_FAILURE", "pinned input or contract hashes changed")
        location = root / published["artifact_directory"]
        for name, metadata in published["artifacts"].items():
            require(all(metadata[k] == v for k,v in stamped(location, name + ".json").items()),
                    "SOURCE_INTEGRITY_FAILURE", name)

    started = perf_counter()
    cm = read_json(root / COMPANY_POINTER)
    expected_dir = COMPANY_POINTER.parent / "populations" / COMPANY_ID
    require((root / expected_dir).resolve() == root / expected_dir and
            cm["status"] == "validated" and cm["stage"] == "SM-03B" and cm["stage_id"] == COMPANY_ID
            and cm["artifact_directory"] == expected_dir.as_posix()
            and cm["source"] == policy["source"] and cm["approved_sm02_plan_id"] == EXPECTED_PLAN
            and cm["planning_artifacts"] == manifest["artifacts"]
            and cm["population_id"] == identity["permanent_identity"]["population_key"]
            and cm["schema"] == contract and contract["sha256"] == SCHEMA_SHA256
            and cm["is_synthetic"] is True and cm["is_intermediate"] is True
            and cm["backend_importable"] is False and cm["full_marketplace_release"] is False,
            "COMPANY_STAGE_INTEGRITY_FAILURE", "pinned SM-03B manifest")
    artifacts = {name: {"path": name, "sha256": sha, "size_bytes": size}
                 for name, (sha, size) in COMPANY_CONTENT.items()}
    require(cm["artifacts"] == artifacts, "COMPANY_STAGE_INTEGRITY_FAILURE", "pinned company artifact metadata")
    verify_artifacts(root / expected_dir, artifacts)
    engine = context[3] if context else None
    if engine:
        def observed(code, market, role):
            links = engine.products.get(code)
            return links is not None and market in (links.exports if role == "exporter" else links.imports)

        bundle = read_json(root / expected_dir / COMPANY_BUNDLE)
        markets = {m["market_code"]: m for m in geography["records"]}
        result = validate_population(root, bundle, {**allocation, "plan_id": EXPECTED_PLAN}, markets, identity, observed)
        require(result == cm["validation"], "COMPANY_STAGE_INTEGRITY_FAILURE", "serialized company validation")
    timings["sm03b_verification"] = perf_counter() - started

    started = perf_counter()
    selected = allocation["selected_products"]
    require(len(selected) == 300 and all(r["reference_description"] for r in selected),
            "UNRESOLVED_PRODUCT_PROFILE", "selected catalog")
    timings["product_catalog_inspection"] = perf_counter() - started
    schemas = {}
    for name in SCHEMAS:
        schema_validator(root, name)
        path = f"schemas/{name}.schema.json"
        schemas[name] = {"version":"1.0.0", **stamped(root, path)}
    from src.synthetic.listing_stage import IDENTIFIERS

    bindings = {"source": policy["source"], "structural_plan_id": EXPECTED_PLAN,
                "structural_artifacts": manifest["artifacts"], "company_stage_id": COMPANY_ID,
                "company_artifacts": artifacts, "population_id": cm["population_id"],
                "configuration": {"version":config["version"], **stamped(root, CONFIG)},
                "configuration_fingerprint":fingerprint(config),
                "schemas":schemas, "solver_version":VERSION, "master_seed":config["master_seed"],
                "implementation_fingerprint":fingerprint({
                    module: digest(root / "src" / "synthetic" / (module + ".py")) for module in IMPLEMENTATION}),
                "identifier_policy_fingerprint":fingerprint(IDENTIFIERS)}
    return config, allocation, engine, bindings, counts


def write_review(path, profiles):
    header = ("# Product commercial configuration review\n\n"
              "USD per stated basis. Every value below is a proposed synthetic planning parameter. "
              "The source descriptions and prefix groups come from the pinned reference.\n\n"
              "| Code | Reference description | Source group | Commercial group | Unit / alternatives | "
              "USD basis / reference / bounds | Precision (qty / price) | Stock | MOQ | Step | RFQ bounds | Max order | "
              "Variation (listing / RFQ / offer) | Overrides / review |\n"
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for p in profiles:
        values = [f'`{p["product_code"]}`', p["reference_description"], p["provisional_group"], p["commercial_group"],
                  "/".join(p["permitted_units"]),
                  f'{p["price_basis_quantity"]} {p["price_basis_unit"]} / {p["reference_price"]} / '+"–".join(p["price_bounds"]),
                  f'{p["quantity_precision"]} / {p["quoted_price_precision"]}', "–".join(p["stock_bounds"]),
                  "–".join(p["moq_bounds"]), p["quantity_increment"], "–".join(p["rfq_quantity_bounds"]),
                  p["maximum_order_quantity"] or "Open", " / ".join(" to ".join(p["price_variation"][kind])
                      for kind in ("listing","rfq","offer")), ", ".join([p["group_assignment"],
                      p["reference_price_source"], *p["override_fields"], *p["review_notes"]])]
        lines.append("| " + " | ".join(x.replace("|","\\|").replace("\n"," ") for x in values) + " |\n")
    path.write_text(header + "".join(lines), encoding="utf-8", newline="\n")


def read_bundle(directory):
    data = {}
    for collection, name in FILES.items():
        artifact = read_json(directory / name)
        require(set(artifact) == {"metadata", "records"}, "INVALID_ARTIFACT", name)
        data.setdefault("metadata", artifact["metadata"])
        require(data["metadata"] == artifact["metadata"], "INVALID_ARTIFACT", f"metadata mismatch {name}")
        data[collection] = artifact["records"]
    return data


def build(root, workspace, config, allocation, bindings, metrics, engine):
    profiles = timings_step(metrics, "profile_resolution", resolve_profiles, config, allocation["selected_products"])
    dataset = solve(config, profiles, allocation, metrics)
    dataset["profiles"] = profiles
    dataset["metadata"] = {**FLAGS, "schema_version":"1.0.0", "bindings":bindings}
    started = perf_counter()
    for collection, name in FILES.items():
        write_json(workspace / name, {"metadata":dataset["metadata"], "records":dataset[collection]})
    write_review(workspace / REVIEW, profiles)
    metrics["serialization"] = perf_counter() - started
    independent = read_bundle(workspace)
    validation = timings_step(metrics, "independent_serialized_validation", validate_plan, root, independent,
                              config, profiles, allocation, bindings, engine)
    quality = timings_step(metrics, "quality_diagnostics", quality_report, independent, allocation, config, engine)
    elapsed = perf_counter()
    write_json(workspace / VALIDATION, {**FLAGS, **validation})
    write_json(workspace / QUALITY, {**FLAGS, **quality})
    metrics["serialization"] += perf_counter() - elapsed
    return validation


def publication(root):
    manifest = read_json(root / POINTER)
    artifacts = manifest["artifacts"]
    stage_id = "sm04a-" + fingerprint(artifacts).split(":")[1]
    directory = BASE / "plans" / stage_id
    require(manifest["commercial_plan_id"] == stage_id and manifest["artifact_directory"] == directory.as_posix()
            and manifest["status"] == "validated_provisional" and manifest["exact_approvals"] == NEEDED
            and all(manifest[k] == v for k,v in FLAGS.items())
            and set(artifacts) == {*FILES.values(), REVIEW, QUALITY, VALIDATION}
            and (root / directory).resolve() == root / directory,
            "INVALID_ARTIFACT", "commercial pointer identity or approval flags")
    verify_artifacts(root / directory, artifacts)
    return manifest, root / directory


def generate(root, config, allocation, engine, bindings, timings, started, regression):
    from src.synthetic.commercial_remediation import require_planning_scope

    require_planning_scope()
    storage = root / BASE
    storage.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=storage) as tmp:
        work = Path(tmp)
        first, second = work / "candidate", work / "rebuild"
        first.mkdir()
        second.mkdir()
        metrics = {}
        validation = build(root, first, config, allocation, bindings, metrics, engine)
        search_nodes = metrics.pop("search_nodes")
        timings.update(metrics)
        repeat_started = perf_counter()
        replay_metrics = {}
        replay = build(root, second, config, allocation, bindings, replay_metrics, engine)
        built = {p.name: stamped(first,p.name) for p in sorted(first.iterdir())}
        rebuilt = {p.name: stamped(second,p.name) for p in sorted(second.iterdir())}
        require(replay == validation and built == rebuilt and search_nodes == replay_metrics["search_nodes"]
                and all((first / name).read_bytes() == (second / name).read_bytes() for name in built),
                "REPRODUCIBILITY_FAILURE", "independent complete builds differ")
        timings["rebuild_and_byte_comparison"] = perf_counter() - repeat_started
        stage_id = "sm04a-" + fingerprint(built).split(":")[1]
        relative = BASE / "plans" / stage_id
        manifest = {**FLAGS, "status":"validated_provisional", "commercial_plan_id":stage_id,
                    "artifact_directory":relative.as_posix(), "bindings":bindings,
                    "target_counts":EXPECTED, "resolved_profile_fingerprint":fingerprint(read_bundle(first)["profiles"]),
                    "deterministic_content_fingerprint":fingerprint(read_bundle(first)),
                    "solver":{"status":"feasible", "fallback_search_nodes":search_nodes,
                              "method":"exact integer lattice and bounded deterministic quote fallback",
                              "search_limit_per_listing":SEARCH_LIMIT},
                    "artifacts":built,"validation":validation,
                    "reproducibility":{"byte_identical":True,"builds":[built,rebuilt]},
                    "quality_artifact":QUALITY, "exact_approvals":NEEDED, "execution":"SM-04A_only"}
        timings_step(timings,"planning_publication",commit_stage,root/relative,first,root/POINTER,manifest)
        publication(root)
    timings["total_execution"] = perf_counter() - started
    try:
        memory = peak_memory()
    except (OSError, ImportError):
        memory = {"peak_bytes":None,"method":"unavailable"}
    report = {**manifest, "regression_suite":regression, "operational":{"seconds":timings,"peak_memory":memory,
              "python":platform.python_version()}, "sm04b_status":"blocked", "backend_import":"blocked",
              "full_marketplace_generation":"blocked"}
    atomic_json(root / REPORT, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect-inputs","inspect-identifiers","validate-config","resolve-profiles",
                                             "plan","validate-plan","quality","readiness"))
    parser.add_argument("--root",type=Path,default=Path.cwd())
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        started = perf_counter()
        timings = {}
        if args.command == "plan":
            from src.synthetic.commercial_remediation import require_planning_scope

            require_planning_scope()
        if args.command == "inspect-identifiers":
            from src.synthetic.listing_stage import identifier_details
            result = identifier_details()
        else:
            full = args.command in {"plan","validate-plan"}
            regression = timings_step(timings,"regression_suite",verify_tests,root) if args.command == "plan" else None
            config, allocation, engine, bindings, counts = read_inputs(root,full,timings)
            if args.command == "plan":
                result = generate(root,config,allocation,engine,bindings,timings,started,regression)
            elif args.command in {"validate-plan","quality","readiness"} and (root/POINTER).is_file():
                manifest, directory = publication(root)
                from src.synthetic.commercial_remediation import STRUCTURAL_BLOCK, verify_historical

                verify_historical(root,manifest,directory,bindings)
                if args.command == "validate-plan":
                    result = validate_plan(root,read_bundle(directory),config,
                         resolve_profiles(config,allocation["selected_products"]),allocation,manifest["bindings"],engine)
                else:
                    evidence = read_json(directory/QUALITY) if args.command == "quality" else manifest
                    result = {"historical_evidence":evidence, "current_marketplace_scope":STRUCTURAL_BLOCK}
            else:
                require(args.command not in {"validate-plan","quality"}, "MISSING_ARTIFACT", "run SM-04A planning first")
                result = {"bindings":bindings, "counts":counts,"exact_approvals":NEEDED,
                          "independent_input_validation":full}
                if args.command in {"validate-config","resolve-profiles"}:
                    profiles = resolve_profiles(config, allocation["selected_products"])
                    result["resolved_profiles"] = len(profiles)
                    if args.command == "resolve-profiles":
                        result["profiles"] = profiles
        print(json.dumps(result, indent=2))
    except (ValueError,OSError,KeyError,ValidationError,SchemaError) as error:
        finding = getattr(error, "finding", {"severity":"BLOCKER","code":"VALIDATION_FAILURE","detail":str(error)})
        parser.exit(1,json.dumps(finding)+"\n")


if __name__ == "__main__":
    main()
