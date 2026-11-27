# Market Relationship Intelligence

Phase 04.2 implements the categorical evidence model in the [feasibility methodology](MARKET_OPPORTUNITY_METHODOLOGY.md). It supports product and market exploration within the supplied extract. Category A is an observed product link. In B, the product link is unobserved and the directional pair has observations for other products. In C, both the product link and pair are unobserved. Every category requires observed exporter and importer roles for the product. The engine excludes equal numeric market keys. Reverse-direction evidence is reported separately.

## Run locally

From the project root:

```powershell
python -m src.analytics.market_opportunity_intelligence summary
python -m src.analytics.market_opportunity_intelligence query --product 010111 --category B --page 2 --page-size 10
python -m src.analytics.market_opportunity_intelligence query --exporter 24 --importer 32
python -m src.analytics.market_opportunity_intelligence lookup 2024:24:010111:124
python -m scripts.benchmark_market_opportunities
python -m unittest discover -s tests -v
```

Use requirements-dev.txt to enable schema tests. Put global --database and --enrichment-summary options before the subcommand to override sources. The summary command accepts --output. The benchmark uses the published local dataset paths and rewrites its summary and benchmark report.

### Python interfaces

Instantiate `MarketRelationshipEngine.from_files(database_path, enrichment_summary_path)` once per release and reuse the instance. It exposes `summary()`, `query_relationships(product_code=None, exporter_code=None, importer_code=None, category=None, page=1, page_size=50)`, `lookup_relationship(product_code, exporter_code, importer_code)`, and `lookup_id(relationship_id)`. Methods return JSON-compatible values. Lookup returns null for known keys without compatible observed roles.

Summary and query envelopes carry schema version 1.0 and a SHA-256 dataset version. The hash uses canonical JSON for the country and product reference fields and source metadata, followed by ordered eligible keys. It is stable across input row order and changes when an eligible key, a reference label or included provenance changes. The relationship ID is YEAR:EXPORTER:PRODUCT:IMPORTER, scoped to a dataset version. For example, 2024:24:010111:124 retains the leading zero.

## Architecture and contracts

The engine loads SQLite read-only, validates the enrichment summary, applies the shared eligible-row definition, and detects duplicate composite keys before serving queries. It creates per-product masks of observed partners, separate exporter and importer role indexes, and directional pair product counts. Market IDs are assigned bit positions in numeric order to keep membership tests and counts compact. Summaries aggregate intersections from both role perspectives. Detail queries count compact matching blocks and enrich only the requested page. The engine has no persistent candidate table or external cache. Legacy market opportunity analytics retain their original contract and output.

The [summary](../data/processed/analytics/market_opportunity_summary.json) has release metadata, the external universe and category counts, a profile for each observed product, and separate market summaries by role. Category percentages use all external relationships as their denominator and are rounded to six decimal places. Source metadata describes the coverage and how to interpret absence. See the [summary schema](../schemas/market_opportunity_summary.schema.json) and [query schema](../schemas/market_relationship_query.schema.json), whose relationship definition also describes individual lookups.

The verified 2024 release contains 7,312,207 gross combinations and 40,474 same-market exclusions. The 7,271,733 external relationships comprise 1,048,575 in A, 4,694,268 in B and 1,528,890 in C. These are counts of analytical relationships in the release.

Each relationship includes reference descriptions and nullable ISO labels, product and pair membership in both directions, observed partner counts, product diversity by market role, and product-network breadth. The other-products count subtracts one from the pair's distinct product count only when the specific link was observed. Explanations are selected from category templates using the release year and the validated link evidence.

## Filters and pagination

List queries require a product, exporter, or importer. All provided filters are conjunctive. Market codes are numeric reference IDs, including trade areas. Products are text, with the shared five-digit zero-padding rule and support for known special codes. Categories are uppercase A, B or C.

Apply filters, including category, before counting and paging. Order by product code, then numeric exporter code, then numeric importer code. Page numbering starts at 1. The default size is 50 and the maximum is 500. The response gives total matching rows, total pages, returned count, and previous/next flags. Previous means an earlier populated page exists. An out-of-range page returns no records with its requested page number and the true totals. The engine returns these pages consistently for a fixed release and filter set.

| Condition | Behavior |
| --- | --- |
| Unknown product or numeric market ID | QueryError with unknown_product or unknown_market |
| Known product without observations | Empty result with product_unobserved |
| Known market without the requested observed role | Empty result with exporter_role_unobserved or importer_role_unobserved |
| Valid filters with no matching combinations or category | Empty result with no_matches |
| Out-of-range page | Empty result with page_out_of_range |
| Same market on both sides | QueryError with same_market |
| Invalid category, page, or size | QueryError with invalid_category, invalid_page, or invalid_page_size |
| No narrowing filter | QueryError with unbounded_query |

For zero matches, a request past page 1 reports page_out_of_range. At page 1, inactive reasons are checked in product, exporter, importer order. The CLI reports query errors as JSON on stderr with exit code 2. An empty result describes observations in the supplied extract.

## Validation and local performance

The release check independently scans enriched Parquet and checks category membership, counts and supporting fields. It also reconciles every product and market summary against Phase 04.1, checks query pages against independent enumeration, validates both JSON schemas, and recomputes Country, Product, Route, and legacy opportunity outputs. The repository tests include fixture coverage of same-market exclusions, null ISO labels, leading zeros and special codes, input errors, version stability, lookup, and filter-before-pagination behavior.

The [benchmark report](../reports/market_opportunity_benchmark.json) records the development environment and five warm repetitions per case. One fresh process read the dataset and initialized the engine. The first query was timed after initialization with the OS cache uncontrolled. Separate instrumented passes measured filtering and counting, page selection, and enrichment. JSON encoding is included in the reported end-to-end query times. Console transport and remote request overhead are outside those timings.

| Measurement | Observed |
| --- | ---: |
| SQLite scan and reference loading within initialization | 2.67 s |
| Engine initialization, including fingerprint and indexing | 10.55 s |
| Summary generation | 1.11 s |
| Summary JSON serialization and write | 0.064 s |
| First query and encoding, after initialization | 0.82 ms |
| Warm product first page / page 100 | 0.62 ms / 0.63 ms |
| Warm large exporter / importer | 3.42 ms / 24.14 ms |
| Warm pair / category-filtered product | 3.01 ms / 0.76 ms |
| Warm no-result query / individual lookup | 0.026 ms / 0.022 ms |
| Peak process working set, Windows PeakWorkingSetSize | 104,583,168 bytes |
| Summary size | 2,204,606 bytes |

The largest exporter benchmark counted 415,155 matches and enriched 50 records. The sampled importer query took the longest, with block filtering and counting dominating its work. The benchmark report includes response bytes, with the sampled 50-record pages roughly 68–73 KB. These are local observations. Reuse one engine per release in a future backend process, monitor startup and importer-wide queries under realistic concurrency, and add indexes or different storage only if measurements justify them.

## Interpretation and future use

The 2024 export reached Excel's worksheet row limit and provides partial coverage, especially of exporters. Trade value currency, scale, quantity units, and HS revision remain unverified. Eligibility and classification use neither trade values nor quantities. Categories describe evidence in this release and cannot establish demand, market gaps, commercial viability, economic dependence, growth, or profitability.

Future backend integration can pin the engine to a release fingerprint and expose bounded, schema-validated responses. Later synthetic marketplace work can use observed product roles or reviewed compatibility scenarios to vary fictional market associations. Those choices require explicit synthetic provenance and independent assumptions for companies, capacity, prices and transactions.
