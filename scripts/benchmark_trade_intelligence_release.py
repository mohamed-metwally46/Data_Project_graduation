"""Measure an integrated regeneration and read-only release validation."""
import json
from pathlib import Path
import platform
from statistics import median
from time import perf_counter

from scripts.benchmark_market_opportunities import peak_memory, timed_call
from src.analytics.release import MANIFEST, engine_for, generate, validate
from src.analytics.release_validation import read_json, require
from src.pipeline import write_json


def main():
    root = Path.cwd()
    previous = read_json(root / MANIFEST)
    started = perf_counter()
    current, report = generate(root)
    generation_seconds = perf_counter() - started
    require(previous == current and report["reproducibility"] == "byte_identical_to_existing_release",
            "benchmark requires a stable published release")
    verification = validate(root)
    started = perf_counter()
    engine = engine_for(root, read_json(root / "reports/enrichment_summary.json"))
    engine_seconds = perf_counter() - started
    product = current["statistics"]["market_universe"]["category_counts"]
    require(product["A"] > 0, "benchmark needs observed relationships")
    product_code = next(iter(engine.product_codes))
    cases = {"product": {"product_code": product_code},
             "exporter": {"exporter_code": min(engine.export_products)},
             "importer": {"importer_code": max(engine.import_products)}}
    samples = {}
    for name, filters in cases.items():
        measured = [timed_call(lambda: engine.query_relationships(**filters))[1] for _ in range(5)]
        samples[name] = {"filters": filters, **{key: median(r[key] for r in measured) for key in measured[0]}}
    benchmark = {
        "release_id": current["release_id"], "dataset_fingerprint": current["dataset_fingerprint"],
        "environment": {"platform": platform.platform(), "python": platform.python_version(),
                        "processor": platform.processor()},
        "method": ("One local Python process, sequential regeneration and independent validation against "
                   "an existing release, followed by a separate engine load and five warm calls per case. "
                   "OS disk cache uncontrolled. Query timings include JSON encoding, excluding console transport."),
        "repetitions_per_warm_query": 5,
        "regeneration_seconds": generation_seconds,
        "validation_seconds": verification["validation_seconds"],
        "regeneration_stages": report["measurements"],
        "standalone_engine_initialization_seconds": engine_seconds,
        "summary_artifacts_total_bytes": sum(r["size_bytes"] for r in current["artifacts"].values()),
        "manifest_bytes": (root / MANIFEST).stat().st_size,
        "reproducibility": report["reproducibility"],
        "memory": peak_memory(), "warm_queries": samples,
    }
    write_json(root / "reports/trade_intelligence_release_benchmark.json", benchmark)
    print(json.dumps(benchmark, indent=2))


if __name__ == "__main__":
    main()
