"""Generate and independently verify versioned Trade Intelligence releases."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import tempfile
from time import perf_counter

from jsonschema.exceptions import SchemaError, ValidationError

from src.analytics.country_intelligence import build as build_country
from src.analytics.market_opportunity_intelligence import MarketRelationshipEngine
from src.analytics.observed import ELIGIBLE_ROWS
from src.analytics.product_intelligence import build as build_product
from src.analytics.release_validation import (
    ParquetEvidence, read_json, reconcile, require, schema_validator, validate_queries,
)
from src.analytics.route_intelligence import build as build_route, open_database
from src.pipeline import write_json

BASE = Path("data/processed/analytics")
MANIFEST = BASE / "trade_intelligence_release.json"
REPORT = Path("reports/trade_intelligence_validation.json")
METHOD = "globiq-observed-trade-v1"
VALIDATION_METHOD = "parquet-cross-layer-v1"
SCHEMA_VERSION = "1.0"
COMPONENTS = {
    "country_intelligence": ("country_intelligence", build_country),
    "product_intelligence": ("product_intelligence", build_product),
    "route_intelligence": ("route_intelligence", build_route),
    "market_opportunity_summary": ("market_opportunity_summary", None),
}
SOURCES = {
    "enriched_parquet": ("data/processed/enriched_trade_data.parquet", "Parquet enriched trade v1"),
    "processed_sqlite": ("data/processed/trade.sqlite", "SQLite enriched trade and references v1"),
    "enrichment_summary": ("reports/enrichment_summary.json", "Enrichment report JSON"),
    "country_reference": ("country_codes.csv", "UTF-8 CSV"),
    "product_reference": ("product_codes.csv", "UTF-8 CSV"),
    "country_iso2_overrides": ("configs/country_iso2.json", "Verified ISO2 overrides JSON"),
}
CONTRACTS = [
    "schemas/trade_intelligence_release.schema.json", "schemas/market_relationship_query.schema.json",
    *(f"schemas/{schema}.schema.json" for schema, _ in COMPONENTS.values()),
    *(f"src/analytics/{name}.py" for name in ("country_intelligence", "product_intelligence",
       "route_intelligence", "market_opportunity_intelligence", "observed", "release", "release_validation")),
    "src/pipeline.py", "src/preprocessing/trade.py", "src/enrichment/references.py",
    "requirements.txt", "requirements-dev.txt",
]
CONFIG = {"country_top_n": 10, "product_top_n": 10, "market_categories": ["A", "B", "C"]}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stamped(root, path):
    file = root / path
    return {"path": Path(path).as_posix(), "sha256": digest(file), "size_bytes": file.stat().st_size}


def snapshot(root):
    sources = {key: {**stamped(root, path), "format": format_label}
               for key, (path, format_label) in SOURCES.items()}
    return sources, [stamped(root, path) for path in CONTRACTS]


def identity(fingerprint, sources, contracts):
    payload = [METHOD, VALIDATION_METHOD, SCHEMA_VERSION, fingerprint, sources, contracts, CONFIG]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "ti-" + hashlib.sha256(raw).hexdigest()


def engine_for(root, summary):
    with closing(open_database(root / SOURCES["processed_sqlite"][0])) as db:
        return MarketRelationshipEngine(db, summary)


def generate_outputs(root, stage, summary, engine):
    artifacts = {}
    for name, (schema, builder) in COMPONENTS.items():
        if builder is None:
            data = engine.summary()
        else:
            with closing(open_database(root / SOURCES["processed_sqlite"][0])) as db:
                if name == "route_intelligence":
                    data = builder(db, summary)
                else:
                    top_n = CONFIG["country_top_n" if name == "country_intelligence" else "product_top_n"]
                    data = builder(db, summary, top_n)
        filename = f"{name}.json"
        write_json(stage / filename, data)
        key = "products" if builder is None else "records"
        artifacts[name] = {**stamped(stage, filename), "record_count": len(data[key]),
                           "schema": f"schemas/{schema}.schema.json", "schema_version": SCHEMA_VERSION,
                           "dataset_fingerprint": engine.metadata["dataset_version"],
                           "configuration": {"top_n": data["metadata"]["top_n"]}
                           if "top_n" in data["metadata"] else {}}
    return artifacts


def verify_entry(root, entry, expected_path):
    require(entry["path"] == Path(expected_path).as_posix(), f"unexpected artifact path {entry['path']}")
    require(all(entry[key] == value for key, value in stamped(root, expected_path).items()),
            f"file integrity {expected_path}")


def validate_artifacts(root, location, artifacts, engine):
    require(artifacts.keys() == COMPONENTS.keys(), "required artifact set")
    outputs = {}
    fingerprint = engine.metadata["dataset_version"]
    for name, (schema, builder) in COMPONENTS.items():
        entry = artifacts[name]
        verify_entry(location, entry, f"{name}.json")
        require(entry["schema"] == f"schemas/{schema}.schema.json"
                and entry["schema_version"] == SCHEMA_VERSION and entry["dataset_fingerprint"] == fingerprint,
                f"artifact association {name}")
        obj = read_json(location / f"{name}.json")
        schema_validator(root, schema).validate(obj)
        require(entry["record_count"] == len(obj["products" if builder is None else "records"]),
                f"artifact record count {name}")
        require(entry["configuration"] == ({"top_n": obj["metadata"]["top_n"]}
                if "top_n" in obj["metadata"] else {}), f"artifact configuration {name}")
        if name in ("country_intelligence", "product_intelligence"):
            require(obj["metadata"]["top_n"] == CONFIG[name.split("_")[0] + "_top_n"], f"ranking limit {name}")
        outputs[name] = obj
    started = perf_counter()
    evidence = ParquetEvidence(root)
    scanned = perf_counter()
    independent_fingerprint = evidence.fingerprint()
    timing = {"parquet_scan_seconds": scanned-started,
              "independent_fingerprint_seconds": perf_counter()-scanned}
    require(independent_fingerprint == fingerprint
            == outputs["market_opportunity_summary"]["metadata"]["dataset_version"],
            "Parquet and SQLite logical dataset fingerprint")
    statistics = reconcile(evidence, outputs)
    with closing(open_database(root / SOURCES["processed_sqlite"][0])) as db:
        queries = validate_queries(root, evidence, db, engine)
    return statistics, queries, timing


def atomic_json(destination, obj):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as work:
        staged = Path(work) / destination.name
        write_json(staged, obj)
        staged.replace(destination)


def generate(root):
    started = perf_counter()
    sources, contracts = snapshot(root)
    schema = schema_validator(root, "trade_intelligence_release")
    enrichment = read_json(root / SOURCES["enrichment_summary"][0])
    engine = engine_for(root, enrichment)
    fingerprint = engine.metadata["dataset_version"]
    release_id = identity(fingerprint, sources, contracts)
    releases = root / BASE / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    published = releases / release_id
    with tempfile.TemporaryDirectory(prefix="ti-stage-", dir=releases) as work:
        stage = Path(work) / "artifacts"
        stage.mkdir()
        artifacts = generate_outputs(root, stage, enrichment, engine)
        statistics, queries, timing = validate_artifacts(root, stage, artifacts, engine)
        require(snapshot(root) == (sources, contracts), "release inputs changed during generation")
        reproducibility = "first_generation"
        if published.exists():
            for name, entry in artifacts.items():
                verify_entry(published, entry, f"{name}.json")
            reproducibility = "byte_identical_to_existing_release"
        report = {
            "release_id": release_id, "dataset_fingerprint": fingerprint,
            "status": "validated", "method": VALIDATION_METHOD,
            "checks": ["input_integrity", "artifact_integrity", "schemas",
                       "independent_parquet_fingerprint", "full_cross_layer_aggregations", "public_queries"],
            "statistics": statistics, "queries": queries,
            "reproducibility": reproducibility,
            "measurements": {
                "sqlite_engine_initialization_seconds": engine.initialization_seconds,
                "sqlite_load_seconds_inside_initialization": engine.load_seconds,
                **timing,
                "generation_and_validation_seconds_before_publish": perf_counter() - started,
            },
        }
        manifest = {
            "manifest_schema_version": SCHEMA_VERSION, "release_id": release_id, "status": "validated",
            "dataset_fingerprint": fingerprint, "year": statistics["year"], "methodology": METHOD,
            "generation": {"command": "python -m src.analytics.release generate",
                           "deterministic": True, "configuration": CONFIG},
            "dataset": engine.metadata, "inputs": sources, "contracts": contracts,
            "artifact_directory": (BASE / "releases" / release_id).as_posix(),
            "artifacts": artifacts, "statistics": statistics,
            "limitations": [
                "Single-year extract at the Excel worksheet row limit. Coverage may be truncated.",
                "Observed exporter coverage is limited.",
                "Trade-value currency, monetary scale, quantity units and HS revision are unverified.",
                "Observed records are not shipments or transactions. Counts cannot establish demand, "
                "commercial viability or the real-world absence of a relationship.",
            ],
        }
        if published.exists():
            # Reuse the immutable report and artifact directory; publish repeat-run evidence separately.
            recorded = read_json(published / "validation.json")
            require(recorded["statistics"] == statistics and recorded["release_id"] == release_id
                    and recorded["dataset_fingerprint"] == fingerprint and recorded["status"] == "validated",
                    "existing validation evidence")
            manifest["validation"] = stamped(published, "validation.json")
        else:
            write_json(stage / "validation.json", report)
            manifest["validation"] = stamped(stage, "validation.json")
        schema.validate(manifest)
        if not published.exists():
            stage.rename(published)
        atomic_json(root / REPORT, report)
        atomic_json(root / MANIFEST, manifest)
    return manifest, report


def validate(root):
    started = perf_counter()
    manifest = read_json(root / MANIFEST)
    schema_validator(root, "trade_intelligence_release").validate(manifest)
    require(manifest["status"] == "validated", "manifest is not a validated release")
    sources, contracts = snapshot(root)
    require((manifest["inputs"], manifest["contracts"]) == (sources, contracts), "stale release inputs or contracts")
    require(manifest["methodology"] == METHOD and manifest["generation"]["configuration"] == CONFIG,
            "release methodology or configuration")
    summary = read_json(root / SOURCES["enrichment_summary"][0])
    engine = engine_for(root, summary)
    fingerprint = engine.metadata["dataset_version"]
    release_id = identity(fingerprint, sources, contracts)
    relative = BASE / "releases" / release_id
    require((manifest["release_id"], manifest["dataset_fingerprint"], manifest["artifact_directory"])
            == (release_id, fingerprint, relative.as_posix()) and manifest["dataset"] == engine.metadata,
            "manifest dataset identity")
    location = root / relative
    verify_entry(location, manifest["validation"], "validation.json")
    report = read_json(location / "validation.json")
    statistics, queries, timing = validate_artifacts(root, location, manifest["artifacts"], engine)
    require(statistics == manifest["statistics"] == report["statistics"]
            and manifest["year"] == statistics["year"] and report["status"] == "validated"
            and report["method"] == VALIDATION_METHOD
            and report["release_id"] == release_id and report["dataset_fingerprint"] == fingerprint,
            "published validation report identity or statistics")
    require(snapshot(root) == (sources, contracts), "release inputs changed during validation")
    return {"status": "validated", "release_id": release_id, "dataset_fingerprint": fingerprint,
            **timing, "queries": queries,
            "validation_seconds": perf_counter() - started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("generate", "validate", "inspect"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.mode == "generate":
            manifest, report = generate(args.root)
            result = {**report["measurements"], "release_id": manifest["release_id"], "status": "validated",
                      "reproducibility": report["reproducibility"]}
        elif args.mode == "validate":
            result = validate(args.root)
        else:
            result = read_json(args.root / MANIFEST)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, SchemaError, ValidationError) as error:
        parser.exit(1, json.dumps({"status": "invalid", "error": str(error)}) + "\n")


if __name__ == "__main__":
    main()
