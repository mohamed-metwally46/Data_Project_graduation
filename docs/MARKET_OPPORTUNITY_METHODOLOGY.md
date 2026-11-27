# Market Opportunity Intelligence feasibility and methodology

## Objective and decision

Support exploration of observed product-market relationships, candidate review, and later demo-data selection. Use categorical evidence in Phase 04.2. The extract supports describing its own network and finding compatible role combinations. It has no validated outcome for estimating commercial viability.

The existing market_opportunities.json contains up to 100 directly observed links. Its score is the number of observed destinations for the exporter-product plus the number of observed origins for the importer-product. It sorts descending by this sum, then by product, exporter, and importer code. This is a descriptive network-breadth calculation on existing connections. It favors nodes with broader recorded coverage and cannot measure commercial priority. The existing code and output contract are retained.

## Candidate definition

For year y and normalized text product p, let E(p) be the set of eligible observed exporters, I(p) the corresponding importers, T(p) their observed directed product links, and R all eligible directed pairs across products. The external universe is E(p) × I(p), excluding equal numeric market IDs. Markets include countries, historical entities, and trade areas. Reverse direction is a separate lookup. ISO2 and ISO3 are nullable display attributes.

| Category | Exact rule | Interpretation |
| --- | --- | --- |
| A | (e,i) is in T(p) | Directly observed product-market relationship in this extract. |
| B | (e,i) is outside T(p) and in R | Both roles were observed for the product and the directional pair was observed for other products. Product compatibility candidate for review. |
| C | (e,i) is outside T(p) and outside R | Both roles were observed for the product. Indirect compatibility candidate with less relationship evidence in the extract. |

All three require the observed product roles. A is a subset of R, and checking T(p) before R makes the categories exclusive. B and C are absence-of-observation categories. Their existence says nothing about whether the link already trades in the real world, and a category is not a ranking.

For each product, the gross count is the product of the two role-set sizes. Same-market exclusions are the cardinality of their intersection. A is the count of directly observed non-self links. A plus B equals the sum, over observed exporters for the product, of their outgoing neighbors intersected with the product's importer set, excluding the exporter itself. Subtract that sum from the external total to get C. This identity allows validation or summary calculation without storing the candidate universe.

## Measured candidate universe

The independent enriched Parquet scan verified 1,048,575 eligible records for 2024 and the same number of unique composite keys, with no duplicates or self-trade routes. The country reference has 238 profiles. The extract has 29 observed exporters, 226 observed importers, 4,577 observed products, and 3,734 directed pairs. Of those, 396 directions have a reverse, forming 198 reciprocal pairs. All eligible product codes mapped to the supplied reference. One observed importer has null ISO2.

The observed product roles support **7,312,207 gross combinations**. Excluding 40,474 same-market combinations leaves **7,271,733 external relationships**.

| Category | Relationships | Example for 010111, pure-bred breeding horses |
| --- | ---: | --- |
| A | 1,048,575 | Angola to Canada. The product link was observed. |
| B | 4,694,268 | Angola to Argentina. The direction was observed for 78 other products. |
| C | 1,528,890 | Angola to Iran. Both product roles were observed, and the direction was unobserved. |

There are same-market candidates even though no eligible self-trade was observed. They arise when a market belongs to both role sets for the same product.

| Grouping | Groups | Minimum | Median | 95th percentile | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Product | 4,577 | 1 | 1,114 | 4,530 | 6,294 |
| Exporter | 29 | 48,779 | 238,132 | 414,051 | 415,155 |
| Importer | 226 | 27 | 31,469 | 60,513 | 63,972 |

Percentiles use nearest rank. The [feasibility report](../reports/market_opportunity_feasibility.json) provides role counts per product, exact counts by product and market, category distributions, and examples that retain a null ISO2.

## Storage and performance

On the development machine, the Parquet scan and observed-analytics validation took 4.19 seconds. The streamed classification and count checks took 9.54 seconds. Once the relevant observations were in memory, the largest product slice, 6,294 external relationships for code 392690, took 2.35 milliseconds to classify. The last timing excludes database access, label joins and serialization.

The feasibility JSON is about 1.31 MB. Extrapolating from 1,000 compact JSONL rows gives about 669 MB for every candidate with IDs and category alone, before adding labels or evidence. Five fixed-width 32-bit fields per record would occupy about 145 MB before indexes. A Python list of five-field tuples would occupy about 698 MB in shallow storage alone, excluding value objects and allocator overhead. No peak memory measurement was taken. Product filters keep detailed reads small. Exporter-wide queries can still return hundreds of thousands of candidates and need pagination.

## Signals for production

All signals use the eligible trade grain (year, exporter_code, importer_code, product_code) and match flags. Rows must have valid fields and match both country references and the normalized product reference. Counts refer to distinct keys or sets, never price or quantity. Optional reference data is kept with provenance.

| Signal | Exact inputs and calculation | Supported use | Unsupported use and bias | Phase 04.2 |
| --- | --- | --- | --- | --- |
| Export role | Membership of (exporter_code, product_code) in eligible year keys | Evidence of an observed exporter role | Cannot identify active suppliers, production, or export capacity. Sparse exporter coverage suppresses visibility. | Yes |
| Export partners for product | Distinct importer_code for the exporter_code and product_code | Breadth of destinations observed for that product | Cannot measure shipment frequency or supplier readiness. Missing destination rows reduce breadth. | Yes |
| Export product diversity | Distinct product_code grouped by exporter_code | Breadth of products observed outgoing | Cannot measure specialization, competitiveness, or production capacity. Sensitive to code granularity and row coverage. | Yes |
| Import role | Membership of (importer_code, product_code) in eligible year keys | Evidence of an observed importer role | Cannot identify a buyer or purchasing intent. Imports from missing exporters are invisible. | Yes |
| Import partners for product | Distinct exporter_code for the importer_code and product_code | Breadth of origins observed for the product | Cannot measure purchasing power, supplier diversification in the real market, or unmet demand. The 29-exporter coverage particularly limits this measure. | Yes |
| Import product diversity | Distinct product_code grouped by importer_code | Breadth of products observed incoming | Cannot measure overall demand or addressable market. Larger observed networks and narrower code definitions influence counts. | Yes |
| Directional pair observed | Membership of (exporter_code, importer_code) in R | Evidence of at least one product relationship in that direction | Cannot establish logistics access, trade agreements, or transport feasibility. A missing pair may reflect the export cap. | Yes |
| Pair product diversity | Distinct product_code for the directed pair in R, zero if absent | Coverage breadth of the observed pair | Cannot measure economic dependence or transaction volume. Influenced by sampling and classification granularity. | Yes |
| Direct product link | Membership of (exporter_code, importer_code) in T(p) | Observed connection or unobserved status | Cannot establish current buyer demand, profitability, or unmet need. Absence is particularly sensitive to missing rows. | Yes |
| Reverse pair observed | Membership of (importer_code, exporter_code) in R, excluding self | Evidence of a reciprocal observed market pair | Cannot imply trade balance or equivalent commercial access. A market outside the observed exporter set cannot have a reverse observation. | Yes |
| Product network | Distinct exporter_code, importer_code and directed pairs grouped by product_code | Context about the product's observed network | Cannot estimate actual market share or popularity independent of coverage. Broad categories can naturally have more links. | Yes |
| Reference mapping and ISO labels | Match flags and joins on country_code and product code. Carry country name and nullable ISO2/ISO3. | Traceability and display. Numeric keys identify markets. | A mapped area need not be a sovereign country. ISO blanks or historical labels do not establish data absence. | Yes, contextual |
| Source coverage and definitions | Year, eligibility, row cap, observed market counts, publisher and unit metadata | Qualify every result and distinguish verified fields from unresolved ones | Cannot extrapolate global trade or treat an unverified HS revision, monetary scale, currency or quantity unit as established. | Yes, contextual |

## Scoring feasibility

Evidence classification answers which facts were observed. Activity counts describe the size of parts of the recorded network. Exploration order can be user-controlled by category, market, and product filters with stable identifier ordering for pagination. None of these measures yields commercial opportunity probability or expected economic value.

Recommend categorical classification and no composite score. There is no ground truth for viable opportunities, performance over time, actual purchasing intent, tariffs and landed costs, pricing, margins, capacity, or lead times. The Excel export cap, the single year, and exporter asymmetry introduce selection effects. Absence should carry no positive score. A probability or confidence percentage would be uncalibrated.

Before considering prioritization, obtain verified multi-year coverage, validated units and revision, and task-specific outcome labels from independently sourced buyer or trade data. Define the prediction target and baseline, measure false positives especially in B and C, test on future periods and held-out markets, and report uncertainty and calibration if probabilities are ever proposed. Exposure or coverage biases should be evaluated separately from commercial outcomes.

## Phase 04.2 architecture and proposed schema

Reuse the shared eligibility predicate and enrichment validation from observed.py, the duplicate-grain check from route_intelligence.py, independent exporter and importer product groupings, numeric country reference keys, and the existing product and pair aggregates. The processed SQLite database is the query source. Parquet remains an independent reconciliation source. Use full pair membership and product-role data. Published Top-N lists are incomplete and cannot substitute for the full inputs.

Publish and cache small summary aggregates keyed by year, product, category and market. Generate detail on demand for a required product or market filter. Limit and paginate market-wide queries. Use parameterized SQL with indexed year/product/market keys or a derived lookup store if benchmarks show a need. Use stable ordering (product code, exporter code, importer code within a year), with a cursor bound to the release, filters and last key. Offer full generation only as an explicit streamed export if a consumer ever requires it. Do not make a full flattened candidate table the default persistence model.

Proposed versioned JSON contract for Phase 04.2:

| Scope | Fields |
| --- | --- |
| Metadata | schema_version, dataset_version, year, eligibility and grain, partial-coverage statement, exporter/importer counts, units and HS revision status, methodology version |
| Summary | gross_combinations, same_market_exclusions, A/B/C counts, external_combinations and per-product/market distributions |
| Query page | applied filters, records, next_cursor (nullable). Product and market query scopes use the same record model. |
| Candidate key | year (integer), exporter_code and importer_code (integers), product_code (string), stable composite identifier |
| Evidence | category enum A/B/C, export_role_observed, import_role_observed, product_link_observed, directional_pair_observed, reverse_pair_observed, role partner counts, role diversity, pair product count and product network counts |
| Reference and coverage | Product description and market names, mapping flags, nullable ISO labels, dataset limitation and observation semantics |

No score, probability, or expected value field is proposed. Boolean absence describes the supplied release. Reference labels should be joined at read time or carried in the paginated response, while counts are computed before pagination.

## Validation for Phase 04.2

Independently scan enriched Parquet with the current eligibility flags. Assert uniqueness at the published key grain, reference membership, directionality, string-code preservation, nullable ISO handling, same-market exclusion, and exhaustive disjoint categories. Reconcile A to eligible records minus observed self links and A+B+C to the external universe. Reconcile counts by product and by each market role and compare full observed counts with Country, Product and Route Intelligence. Add fixed fixtures with self-trade, reciprocal pairs, unobserved pairs, leading zeros, missing ISO identifiers, and tied pagination keys. Benchmark bounded queries and test that page traversal returns each candidate once.

For this assessment, a temporary read-only Parquet analysis reconciled all 238 Country, 4,577 Product, and 3,734 Route Intelligence profiles. The streamed classification matched a separate set calculation for every product. Both market-role summaries reconciled with the product summary and their independently computed gross and exclusion counts. All 100 legacy rows were checked against observed keys and their published breadth formula. All 11 existing tests passed.

## Future Synthetic Marketplace use

Reference codes and descriptions can seed product selection. Observed product roles can guide geographic diversity and supplier-country or importer-country associations. Category A can seed observed route contexts, while B and C can propose scenarios for later review. Listings may cover a range of products and geographies without reproducing the row-count distribution as a commercial proxy. Companies, listings, contacts, prices, offers, and RFQs would be fictional and need separate generation rules and clear provenance. No entity or simulated transaction is created by this assessment.
