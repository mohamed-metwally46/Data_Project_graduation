# Trade Intelligence release

Use Python 3.12 or later from the project root. The release commands need the dependencies in requirements-dev.txt and the processed SQLite database, enriched Parquet, enrichment report, references, and ISO2 configuration.

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m src.analytics.release generate
python -m src.analytics.release validate
python -m src.analytics.release inspect
python -m scripts.benchmark_trade_intelligence_release
```

The pipeline and Parquet exporter can recreate the required processed inputs. A Trade Intelligence release starts at those inputs. The command does not run preprocessing, refresh legacy exports, or modify processed source data.

- **Generate** checks inputs, builds the four analytics artifacts in staging, validates their schemas, and reconciles them independently against enriched Parquet. The command moves the validated directory into its release-ID path and atomically replaces the manifest pointer last.
- **Validate** verifies fingerprints, paths, record counts, the manifest, and the recorded acceptance evidence. It independently rechecks the released artifacts and representative public queries without regenerating or writing outputs.
- **Inspect** reads the published [manifest](../data/processed/analytics/trade_intelligence_release.json). Inspection displays stored metadata. Use validate to check current integrity and compatibility.

The manifest links versioned artifacts and the immutable generation validation report. The [working report](../reports/trade_intelligence_validation.json) records the latest successful generation or same-release regeneration. Later timings and byte-comparison evidence can differ from the original embedded report. Use the [manifest schema](../schemas/trade_intelligence_release.schema.json) as the entry contract.

## Publication and failure behavior

A staging directory is private to a run. A failed run exits nonzero, cannot publish a validated pointer, and normally cleans its staging directory. Forced termination can leave a ti-stage directory or an unreferenced completed directory. Consumers follow the manifest and do not discover releases by listing that directory. A later attempt can reuse an existing same-ID directory only after validating a fresh build and checking that all four analytical artifacts match. Existing version directories are retained. Local automation should avoid concurrent writers to the same release root.

The schema distinguishes generated, validated, invalid, and incomplete. The pointer publishes only validated releases. A rejected command reports an invalid attempt, and a missing pointer or required file prevents validation. A prior pointer may remain readable after an input changes, but validation rejects it as stale. A hash establishes byte identity, and cannot establish source authenticity or global completeness.

## Verification scope

The release validator checks four artifact schemas and the query response schema, checks both SQLite and Parquet logical identity, and independently reconciles full country, product, route, and candidate counts. It checks representative route-composition calls and two pages each across product, market, pair, combined and category queries. Lookup, errors, no-result behavior, labels, and explanatory evidence are included. Fixture tests cover modified and missing files, stale inputs, invalid schemas, preservation of a validated pointer after failure, and Parquet re-encoding.

The benchmark script measures a sequential regeneration and independent validation, peak working set for the development process, and representative in-memory calls after a separate engine load. See the [benchmark report](../reports/trade_intelligence_release_benchmark.json). Timings include local file access and validation for release operations. Query timings include JSON encoding and exclude transport. These measurements carry no service-level guarantee.

The verified release contains 39,011,861 bytes of analytical JSON and a 9,678-byte manifest. On the development machine, repeat generation took 72.34 seconds and independent validation took 47.20 seconds. The repeat run spent 6.29 seconds scanning Parquet and 3.85 seconds calculating the independent logical fingerprint. A separate engine initialization took 9.49 seconds. Peak process working set for the integrated benchmark was 832,299,008 bytes, including Parquet reconciliation and in-memory JSON validation. Five-run median query and encoding times were 0.65 ms for the sampled product, 1.58 ms for the sampled exporter, and 12.25 ms for the sampled importer. The OS disk cache was uncontrolled.
