"""Benchmark Phase 04.2 locally without materializing the candidate universe."""
import ctypes
import json
import os
from pathlib import Path
import platform
from statistics import median
from time import perf_counter

from src.analytics.market_opportunity_intelligence import MarketRelationshipEngine
from src.pipeline import write_json

REPETITIONS = 5
DATABASE = Path("data/processed/trade.sqlite")
ENRICHMENT = Path("reports/enrichment_summary.json")
SUMMARY = Path("data/processed/analytics/market_opportunity_summary.json")


def peak_memory():
    if os.name == "nt":
        from ctypes import wintypes

        class MemoryCounters(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "peak", "working", "quota_peak_paged", "quota_paged",
                    "quota_peak_nonpaged", "quota_nonpaged", "pagefile", "peak_pagefile"
                )
            ]

        counters = MemoryCounters()
        counters.size = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        read = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
        read.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
        read.restype = wintypes.BOOL
        if not read(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.size):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"peak_bytes": counters.peak, "method": "Windows PeakWorkingSetSize for the benchmark process"}
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {"peak_bytes": peak if platform.system() == "Darwin" else peak * 1024,
            "method": "getrusage(RUSAGE_SELF).ru_maxrss"}


def timed_call(operation):
    started = perf_counter()
    result = operation()
    query_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    output = json.dumps(result).encode("utf-8")
    serialization_ms = (perf_counter() - started) * 1000
    return result, {"query_ms": query_ms, "serialization_ms": serialization_ms,
                    "query_and_serialization_ms": query_ms + serialization_ms,
                    "response_bytes": len(output)}


def instrumented_query(engine, filters):
    timings = {"filter_and_count_ms": 0, "pagination_ms": 0, "reference_enrichment_ms": 0}
    names = {"matching_blocks": "filter_and_count_ms", "page_keys": "pagination_ms",
             "relationship": "reference_enrichment_ms"}

    def measure(original, field):
        def wrapper(*args):
            started = perf_counter()
            value = original(*args)
            timings[field] += (perf_counter() - started) * 1000
            return value
        return wrapper

    for name, field in names.items():
        setattr(engine, name, measure(getattr(engine, name), field))
    try:
        engine.query_relationships(**filters)
    finally:
        for name in names:
            delattr(engine, name)
    return timings


def main():
    started = perf_counter()
    engine = MarketRelationshipEngine.from_files(DATABASE, ENRICHMENT)
    initialized = perf_counter() - started
    cold_filters = {"product_code": "392690"}
    _, cold = timed_call(lambda: engine.query_relationships(**cold_filters))
    started = perf_counter()
    summary = engine.summary()
    summary_seconds = perf_counter() - started
    started = perf_counter()
    write_json(SUMMARY, summary)
    summary_write_seconds = perf_counter() - started
    few = min((r for r in summary["products"] if r["external_relationships"]),
              key=lambda r: r["external_relationships"])
    many = max(summary["products"], key=lambda r: r["external_relationships"])
    large_exporter = max(summary["markets"]["exporter"], key=lambda r: r["external_relationships"])
    no_product = min(set(engine.descriptions) - engine.products.keys())
    cases = {
        "small_product": {"product_code": few["product_code"]},
        "large_product_first_page": {"product_code": many["product_code"]},
        "large_product_later_page": {"product_code": many["product_code"], "page": 100},
        "large_exporter": {"exporter_code": large_exporter["market"]["code"]},
        "importer": {"importer_code": 490},
        "directional_pair": {"exporter_code": 24, "importer_code": 32},
        "category_filtered": {"product_code": many["product_code"], "category": "B"},
        "no_results": {"product_code": no_product},
    }
    measured = {}
    for label, filters in cases.items():
        samples, phases = [], []
        for _ in range(REPETITIONS):
            result, timing = timed_call(lambda: engine.query_relationships(**filters))
            samples.append(timing)
            phases.append(instrumented_query(engine, filters))
        measured[label] = {
            "filters": filters, "total_matches": result["pagination"]["total_matches"],
            "returned": result["pagination"]["returned_count"],
            **{k: round(median(s[k] for s in samples), 6) for k in samples[0]},
            **{k: round(median(s[k] for s in phases), 6) for k in phases[0]},
        }
    lookup = "2024:24:010111:124"
    samples = [timed_call(lambda: engine.lookup_id(lookup))[1] for _ in range(REPETITIONS)]
    measured["individual_lookup"] = {
        "relationship_id": lookup,
        **{k: round(median(s[k] for s in samples), 6) for k in samples[0]},
    }
    result = {
        "dataset_version": engine.metadata["dataset_version"],
        "environment": {"platform": platform.platform(), "python": platform.python_version(),
                        "processor": platform.processor(), "logical_cpus": os.cpu_count()},
        "method": ("One fresh Python process, one engine load. Cold is its first query, with the OS disk "
                   "cache uncontrolled. Warm cases use median timings over repeated queries. "
                   "Phase timings are medians of separate instrumented passes. Serialization measures "
                   "JSON encoding; query timings exclude console transport."),
        "repetitions_per_warm_case": REPETITIONS,
        "dataset_load_seconds": engine.load_seconds,
        "engine_initialization_total_seconds": initialized,
        "summary_generation_seconds": summary_seconds,
        "summary_serialization_and_write_seconds": summary_write_seconds,
        "summary_bytes": SUMMARY.stat().st_size,
        "cold_first_query": {"filters": cold_filters, **cold},
        "warm_queries": measured,
        "memory": peak_memory(),
    }
    write_json(Path("reports/market_opportunity_benchmark.json"), result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
