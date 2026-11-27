# Country Intelligence

Run `python -m src.analytics.country_intelligence` from the project root. It reads the processed SQLite database and its enrichment summary and writes [country_intelligence.json](../data/processed/analytics/country_intelligence.json). Use `--top-n` to change the default of 10. The [JSON Schema](../schemas/country_intelligence.schema.json) describes the output contract.

## Existing analytics reviewed

| Existing output | Calculation and reuse |
| --- | --- |
| country_analytics.json | 226 observed profiles. Counts unique trade records and partners per direction. Ranks product and partner IDs by record count. The aggregation now shares the Country Intelligence implementation, while the legacy export keeps its original fields and observed-only scope. |
| product_analytics.json | 4,577 products. Counts observed records and distinct exporters and importers. Ranks participants by record count. A product has one record per observed pair in a single year, so its top routes tie and are ordered by partner codes. |
| trade_routes.json | 3,734 directed pairs. Counts records and distinct products. Each product has one record per route in the snapshot, so its top list is ordered by product code. |
| market_opportunities.json | 100 observed route-product connections. The score adds the exporter's observed destinations to the importer's observed sources for that product. The score reflects breadth in the export, which can be influenced by uneven coverage. |

The clean and enriched Parquet files each contain 1,048,575 rows. The invalid-record Parquet file contains zero rows. The enriched schema provides normalized product keys, match flags, and reference labels alongside value and quantity fields. Country Intelligence uses only the identifiers, labels, and validation flags. The existing tests covered enrichment, basic analytics and Parquet types. The country-specific test adds coverage for independent directions, product diversity, top-N truncation and tie-breaking, zero activity, null ISO2, and unique profiles.

## Profile scope and calculations

Every numeric key in the country reference gets one profile, including historical entities, trade areas, and entries with zero observations. Labels come from the processed references. ISO labels may be null, historical, or source-specific. Use the numeric code as the identifier.

An eligible record has valid fields and matches both country references and the product reference. It is counted once per unique year, exporter, importer, and normalized product code. Export and import perspectives are grouped separately. Both record-count totals must equal the included record count. Unique partners count the distinct opposite-side identifiers and product diversity counts the distinct normalized products for each direction.

Ranking entries include their reference name or description. Lists sort by observed record count descending, then by numeric partner code or product code ascending. Missing activity is represented by zero counts and empty rankings.

## Coverage and interpretation

The 2024 export reached Excel's worksheet row limit. It contains only 29 observed exporters and 226 observed importers. The current release has 238 profiles, including 12 without eligible records in either direction. Each profile carries coverage metadata. A zero means no eligible record was observed for that direction in the supplied export.

The counts measure observed records. Trade value currency and scale and quantity units remain unverified. Trade value and quantities, including imputed quantities, are excluded from the calculations. The coverage and single-year scope do not support claims about global totals, monetary rankings, growth, unmet demand, or future demand.
