# Product Intelligence

From the project root, run `python -m src.analytics.product_intelligence`. The command reads the processed SQLite database and enrichment summary and writes [product_intelligence.json](../data/processed/analytics/product_intelligence.json). Use `--database`, `--summary`, and `--output` for alternate paths, and `--top-n` for a positive ranking size. The default is 10.

## Inputs and observed metrics

The enriched trade table contributes year, numeric exporter and importer keys, normalized text product code, original product code, and eligibility flags. The product reference provides descriptions. The country reference provides names for countries, historical entities, and trade areas. ISO2 is optional and does not determine identity.

Product and Country Intelligence share the same eligibility rules. A valid row must match both country references and the product reference. Deduplicate by year, exporter, importer, and normalized product code. Each resulting key contributes once to its product. The Product Intelligence command requires a single processed year.

| Field | Definition |
| --- | --- |
| product_code, description, reference_mapped | Normalized string key, reference description or null, and reference key membership. Leading zeros and supported special strings are preserved. The HS revision is unverified. |
| input_row_count | Processed rows carrying this normalized code, before eligibility filters and deduplication. |
| record_count | Number of unique eligible keys for the product. |
| exporters, importers | Distinct observed numeric IDs on each side, calculated independently. |
| distinct_routes | Distinct directed exporter-importer pairs among eligible records for this product. In a single year this equals the product's eligible record count. |
| top_exporters, top_importers, top_routes | Ranked dimensions with reference labels, counts, and percentage of all eligible records for the product before truncation. Percentages are rounded to six decimal places. |
| coverage | Source limitation, observed exporter/importer coverage, and count and percentage interpretation, included for every profile. |

The [JSON Schema](../schemas/product_intelligence.schema.json) defines the output contract. The top-level reference coverage counts observed, mapped, unmapped, missing-description, and unobserved reference products, and lists unobserved reference codes. An observed normalized code without a reference gets a profile with its input count, null description, and zero eligible activity. It also contributes to the unmapped-row total. Raw strings without normalized keys appear in the unnormalizable-code report with frequency. A mapped product can still have a missing description. Unobserved reference codes have no matching normalized key anywhere in the processed input.

## Ranking and reconciliation

Rank by eligible record count descending, then by ascending numeric entity code. Route ties use exporter code, then importer code. Return at most Top-N entries, excluding any ties that fall after that boundary. For the current one-year grain every route within a product has one record, so route ordering only breaks equal counts. Missing labels remain null and have no effect on rank. Percentages describe record shares in this extract.

Run `python -m unittest discover -s tests -v` for fixture tests covering normalization, independent rankings, ties, zero eligible observations, missing descriptions, deduplication, and null ISO2. The builder reconciles the full exporter, importer, and route count totals for each eligible product before publishing any rankings. It also checks unique profile IDs and reconciles totals to the processed and eligible datasets. For release validation, validate the output with a Draft 2020-12 validator and independently group the enriched Parquet by eligible trade keys. Compare per-product counts, distinct dimensions, rankings, and reference coverage to the JSON.

The previous product JSON already published record counts, exporter and importer breadth, and code-only rankings. The legacy export now calls the same aggregation core and keeps its existing JSON contract. The Country Intelligence contract and eligibility rules are unchanged.

## Coverage and limitations

The current run covers 1,048,575 eligible records from 2024, 29 observed exporters, and 226 observed importers. It includes 4,577 mapped product profiles, with zero missing descriptions, zero unmapped codes, and 445 unobserved reference products. The source export reached Excel's worksheet limit and provides partial global coverage. Zero means no eligible observation in this extract. Currency, value scale, quantity units, and HS revision remain unverified. Rankings use record counts and exclude trade value, reported quantity, and imputed quantity. This snapshot cannot establish international market share, market growth, unmet demand, or future demand.

A later Synthetic Marketplace phase can use observed products and geography as selection inputs. Simulated supply, prices, demand, and marketplace entities will need independent assumptions and explicit synthetic provenance.
