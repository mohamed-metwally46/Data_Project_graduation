# Trade Route Intelligence

A route is a directional relationship observed between two numeric country or trade-area identifiers. The stable ID is YEAR:EXPORTER:IMPORTER. Country reference keys can designate historical entities or trade areas. Names and ISO labels are displayed when available. Profiles require both endpoints to match the reference, and missing labels do not change identity.

## Run and query

From the repository root:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m src.analytics.route_intelligence
python -m src.analytics.route_intelligence --route-id 2024:4:490
```

The build reads the enriched SQLite table, its country and product references, and reports/enrichment_summary.json. It writes [route_intelligence.json](../data/processed/analytics/route_intelligence.json), which follows the [route schema](../schemas/route_intelligence.schema.json). Alternate inputs and destination can be passed via --database, --summary, and --output.

The JSON keeps a composition query ID in each profile. Look up that ID with the command above or call product_composition(db, year, exporter, importer) using a connection from open_database. The query returns each product code as text, its description or null, its reference mapping status, and its eligible record count. Retain the processed SQLite database from the same release to serve the details. This design avoids repeating descriptions and storing more than a million route-product objects in the summary.

## Eligibility, grain, and ties

The shared eligibility rule requires valid fields and matches to the numeric country keys and normalized product reference. Route Intelligence checks the source grain before applying the shared observed-record aggregation. The 2024 source has 1,048,575 eligible rows, 1,048,575 unique year/exporter/importer/product keys, zero duplicated keys, and zero records on duplicated keys. If duplicate keys appear, the command reports counts and sample keys and stops publication. It reads the source database in read-only mode.

Each route's eligible record count equals its distinct eligible product count. Each product's eligible record count equals its distinct directional route count. A trade data record can summarize activity across shipments or transactions. Every eligible product in a route has one record. Composition is ordered by ascending product code and flagged as tied when multiple eligible products appear. The existing route output still exposes a deterministic code-only preview under its legacy field name.

The detail query also shows normalized unmapped product codes with zero eligible records when otherwise-valid rows link that code to a profiled pair. Coverage counts mapped and unmapped normalized codes. Pairs observed only in otherwise-valid unmapped data are counted in metadata and have no eligible route profile. Invalid records and unmatched country rows remain available in the enrichment reports. No unmatched codes occurred in the current release.

## Relative coverage

| Metric | Numerator | Denominator |
| --- | --- | --- |
| Dataset record percentage | Eligible route records | All eligible records |
| Exporter record percentage | Eligible route records | All eligible outgoing records for the exporter |
| Importer record percentage | Eligible route records | All eligible incoming records for the importer |
| Exporter product percentage | Distinct eligible products on route | Union of distinct eligible products across the exporter's routes |
| Importer product percentage | Distinct eligible products on route | Union of distinct eligible products across the importer's routes |
| Reference mapped percentage | Mapped normalized product codes on route | All distinct normalized product codes on otherwise-valid route rows |

Percentages are rounded to six decimals. A zero denominator yields null. Reverse flags check whether the opposite direction appears in the same year. A reciprocal pair counts once in metadata and both of its directional profiles carry a reverse flag. Eligible self-trade would have its own profile and count on both sides. It does not count as reciprocal.

## Validation and coverage

Release validation groups eligible observations independently from enriched Parquet and compares full product composition, route counts, reference labels, reverse flags, and percentages. For each country/area it compares outgoing and incoming totals, partner sets, and product unions with Country Intelligence. For each product it compares composition totals, exporters, importers, and route counts with Product Intelligence. Checks use every eligible record. The test suite validates the summary schema and tests directional relationships, null labels, ties, self-trade, and duplicate rejection.

The verified release contains 3,734 directional profiles, including 396 directions with an observed reverse. Those directions form 198 reciprocal pairs. No self-trade routes were observed. The JSON is 5,781,134 bytes. On the development machine, a measured build took about 7.1 seconds, and three sampled composition lookups took 0.48 to 0.53 seconds each, including a route with 4,298 products.

The 2024 extract reached Excel's worksheet row limit. It covers 29 observed exporters, 226 observed importers, and 4,577 observed eligible products. The country reference has 238 entries. Currency, trade-value scale, quantity units, and HS revision remain unverified. The output uses no trade values, quantities, or imputed quantities. Percentages describe this extract and cannot establish trade volume, transaction frequency, economic dependence, international market share, market growth, unmet demand, or future demand. A missing reverse direction means only that it was unobserved here. These relationships describe markets and carry no information about physical transport itineraries.

Later synthetic marketplace work may use observed pair and product combinations as selection inputs. Fictional suppliers, buyers, listings, prices, and transactions require separately documented generation assumptions.
