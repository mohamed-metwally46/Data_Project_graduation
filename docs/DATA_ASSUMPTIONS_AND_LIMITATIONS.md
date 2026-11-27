# Data assumptions and limitations

- The current source is the approved 2024 Excel-to-CSV export. Its 1,048,575 data rows plus header reach Excel's worksheet limit. The export contains 29 exporters and 226 importers, and provides partial geographic coverage. This limitation is included in processed dataset and analytics metadata.
- Source release, HS revision, trade value currency and scale, and quantity units remain unverified. The numeric amount fields are available for inspection. Current analytics use record counts and distinct counts. Monetary totals, quantity totals, trade balances and inferred prices are deferred.
- Product code normalization is approved for this export. It preserves the observed code and only pads five-digit numeric strings. The reference match establishes compatibility with the supplied reference, while the publisher classification revision remains unknown.
- Quantity imputation is a temporary modeling assumption. Imputed quantities must be identified as estimates and do not enter current analytics.
- Country codes can refer to historical or aggregate trade entities. Use numeric reference keys, and preserve unresolved ISO2 values as null.
- SQLite is the processing store. The clean, enriched, and invalid-record tables are also published as Parquet with source coverage metadata.

## Trade Intelligence methodology

Each analytics output embeds the year, source scope, measure limitations, ranking basis, and included and excluded counts. Aggregations use distinct year/exporter/importer/product keys from matched, valid rows. Country summaries show observed partners and product activity. Product summaries show observed exporter and importer breadth. Route summaries report observed product breadth. Top lists sort by record count descending and then by the respective ID ascending. For a route in a single year, each unique route-product key counts once, so the route product list uses the product code to break ties.

The market opportunities output ranks up to 100 existing product-route connections by the sum of the observed destination count for the exporter and observed source count for the importer for the same product. The two counts explain each result. The ranking favors connections within broader observed networks and is sensitive to which exporters appear in the file. Use it to review observed connections only. This single-year export cannot establish growth, unmet demand, or future demand.
