# Trade Intelligence release architecture

The cleaning and enrichment pipeline writes the SQLite and Parquet datasets. The individual intelligence generators use shared eligibility rules and retain their existing JSON shapes. The release orchestrator invokes those generators in one workflow and writes separate versioned snapshots. The root-level analytics JSONs remain usable through the original commands. The manifest identifies which versioned directory is authoritative for a validated release.

## Three levels of identity

| Identity | Definition | Change behavior |
| --- | --- | --- |
| Source artifact | SHA-256 of file bytes plus exact byte length. Includes SQLite, enriched Parquet, references, ISO2 overrides, and enrichment summary. | Changes on byte edits, re-encoding, or SQLite layout changes. |
| Logical dataset | SHA-256 over canonical UTF-8 JSON lines. The first line contains loaded country label fields, product descriptions and coverage provenance. Subsequent lines contain year, normalized text product code, numeric exporter and numeric importer, ordered by product, exporter, importer and year. | Stable under row reorder or equivalent Parquet re-encoding. Changes when eligible keys, included labels, or provenance change. |
| Release | SHA-256 over canonical JSON containing the logical fingerprint, source integrity entries, methodology and validation versions, relevant source code and schema digests, and generation configuration. Prefixed with ti-. | Changes with relevant file bytes or contracts. Timestamps and benchmark measurements do not enter the hash. |

Canonical JSON uses sorted object keys and compact separators. The fingerprint inherits the Market Relationship engine's established normalization. Eligible rows have valid fields and match both market references and the product reference. The normalized product code remains text. Duplicate eligible composite keys prevent release publication. The independent path derives the same logical digest from Parquet keys and the reference CSVs plus verified overrides, rather than reading the SQLite indexes.

## Generation, validation, and consumers

The engine loads observed links and references once for summary and representative queries. Other generators keep their established country, product and route aggregations. The release validator independently constructs product link sets and directed pair product sets from Parquet. It reconciles country totals, distinct partners and product unions, and reconciles product route counts with route composition. Category partitions are checked from explicit role intersections in both market perspectives. Query evidence and pagination are tested against independent enumeration on bounded slices.

All four analytical artifacts have their own integrity entries and share one dataset and release ID through the manifest. Each schema is recorded with its path, digest and release-assigned contract version. Numeric country keys, string product codes, directional identifiers and nullable ISO labels are preserved. The manifest references immutable assets and an integrity-checked validation report. Those files do not refer to the manifest hash, so the hash graph has no circular dependency. A repeat build checks exact bytes before reusing the published directory.

A future local or Backend consumer should load one validated manifest and initialize one engine per dataset version. Pin the manifest ID and input hashes, verify that the engine's logical fingerprint matches, and keep query ordering and schema versions fixed for that consumer session. If the published pointer changes, choose explicitly when to move consumers to the new release. There is no HTTP service in this phase.
