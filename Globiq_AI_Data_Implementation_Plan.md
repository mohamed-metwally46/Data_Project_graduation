# Globiq -- AI & Data Implementation Plan

## 1. Approved Project Scope

  Area                         Decision
  ---------------------------- -----------------------------------------------
  Geographic scope             Global
  Synthetic marketplace size   Balanced
  Backend handoff              JSON
  Initial AI approach          Analytics, rule-based scoring, and embeddings

### Synthetic Marketplace Targets

  Entity               Target
  ------------------ --------
  Products                300
  Unique companies        500
  Supplier roles          300
  Importer roles          200
  Listings              1,000
  Offers / RFQs         1,500

These are generation targets, not counts extracted from the trade
dataset. A company may hold both supplier and importer roles if the
agreed Backend model supports this. The target is 500 unique companies.

## 2. Objectives and Core Principles

The AI and Data work has two tracks:

1.  **Trade Intelligence:** Process international trade records and
    generate country, product, and trade-route analytics.
2.  **Synthetic Marketplace Data:** Generate realistic but explicitly
    synthetic marketplace entities to populate the Globiq MVP.

Real trade data may guide product and geographic selection. It must not
be used to imply that generated companies, contacts, listings, prices,
offers, or transactions are real.

## 3. Data Sources

### 3.1 Trade Data

The sample contains these fields:

  Column   Expected meaning
  -------- -----------------------
  `t`      Year
  `i`      Exporter country code
  `j`      Importer country code
  `code`   Product code
  `v`      Trade value
  `q`      Quantity

Confirm the exact definitions and units of `v` and `q` using the source
documentation before publishing financial or quantity-based conclusions.

### 3.2 Product Reference

  Column          Meaning
  --------------- ---------------------
  `code`          Product code
  `description`   Product description

Use this reference to add readable descriptions to trade records.
Preserve codes as strings, including leading zeros and special formats.

### 3.3 Country Reference

  Column           Meaning
  ---------------- ----------------------------
  `country_code`   Numeric country identifier
  `country_name`   Country name
  `country_iso2`   ISO alpha-2 code
  `country_iso3`   ISO alpha-3 code

Use the complete country reference file to validate coverage. A partial
sample cannot establish that every trade record can be mapped.

## 4. Data Relationships and Enrichment

  Trade field   Reference field   Enriched attribute
  ------------- ----------------- ---------------------
  `i`           `country_code`    Exporter country
  `j`           `country_code`    Importer country
  `code`        `code`            Product description

Rename country-reference columns before joining the same reference table
twice. Validate reference-key uniqueness before joining to prevent
accidental row multiplication.

The enriched dataset should contain:

-   Year
-   Exporter code, name, ISO2, and ISO3
-   Importer code, name, ISO2, and ISO3
-   Product code and description
-   Trade value
-   Quantity

Unmatched country and product codes must be retained or separately
reported, never silently discarded.

## 5. Workstream A -- Project Setup

### Tasks

-   Create or configure the AI project repository.
-   Set up the Python environment.
-   Pin and document dependency versions.
-   Create the project directory structure.
-   Configure logging and application settings.
-   Add a `.gitignore` for local environments, generated files, and
    large raw datasets.
-   Document installation and execution instructions.

### Suggested libraries

  Library      Purpose
  ------------ ---------------------------------------
  pandas       Data ingestion and tabular processing
  numpy        Numerical operations
  pyarrow      Parquet support
  matplotlib   Data visualization
  seaborn      Exploratory data analysis
  pydantic     Data and configuration validation
  pytest       Automated testing

### Deliverables

-   Project repository
-   Dependency file
-   Initial README
-   Reproducible local setup

### Acceptance criteria

-   The project runs in a clean Python environment.
-   Dependencies and versions are documented.
-   Core scripts can be executed from the command line.
-   Processing scripts do not modify raw source files.

## 6. Workstream B -- Data Ingestion and Profiling

### Tasks

1.  Load the Trade Data, Product Reference, and Country Reference files.
2.  Record row counts, column counts, and column names.
3.  Inspect data types and parsing issues.
4.  Check missing values and duplicate records.
5.  Identify unique years, countries, and products in the trade data.
6.  Compare trade country codes with the country reference.
7.  Compare trade product codes with the product reference.
8.  Inspect value and quantity distributions and flag suspicious
    records.
9.  Determine whether files are complete or truncated.
10. Review source documentation to confirm field definitions and
    measurement units.

### Deliverables

-   `data_inventory.json`
-   `data_quality_report.json`
-   `data_profiling_report.md`
-   `01_data_exploration.ipynb`

### Acceptance criteria

-   All three input files can be read.
-   Dataset sizes and schemas are recorded.
-   Missing values and duplicates are quantified.
-   Country and product mapping coverage is measured.
-   Data-quality issues are documented.
-   Product codes retain their original string representation.

## 7. Workstream C -- Data Cleaning and Enrichment

### Cleaning tasks

-   Standardize column names.
-   Apply explicit data types.
-   Preserve product codes as strings.
-   Validate country and product codes against their references.
-   Identify negative or otherwise invalid values and quantities.
-   Handle missing values using documented rules.
-   Avoid arbitrary mean or median imputation for missing trade values
    or quantities.
-   Retain invalid records in a separate output for investigation.
-   Define duplicate handling based on the source record grain and
    documentation.

### Enrichment tasks

-   Join exporter codes to the country reference.
-   Join importer codes to the country reference.
-   Join product codes to the product reference.
-   Add readable names and ISO identifiers.
-   Track unmatched records and mapping coverage.
-   Verify that reference joins do not unexpectedly increase
    trade-record counts.

### Deliverables

-   `trade_data_clean.parquet`
-   `enriched_trade_data.parquet`
-   `invalid_trade_records.parquet`
-   `cleaning_report.json`
-   `DATA_DICTIONARY.md`

### Acceptance criteria

-   The enriched schema is documented.
-   Successful mappings are correct.
-   Unmatched records are measurable.
-   Row counts before and after joins are reconciled.
-   Raw source data is not overwritten.

## 8. Workstream D -- Trade Intelligence and Analytics

**Workstream D completed for the validated 2024 release.** Country, Product,
Route and Market Relationship Intelligence share one logical dataset identity.
The release passed independent Parquet reconciliation, schema checks, artifact
integrity, public-query checks and byte-identical regeneration. See the
[release workflow](docs/TRADE_INTELLIGENCE_RELEASE.md) and the
[Workstream E handoff](docs/SYNTHETIC_MARKETPLACE_HANDOFF.md).

### 8.1 Country Analytics

Calculate, where supported by coverage and confirmed units:

-   Total export value
-   Total import value
-   Number of export destinations
-   Number of import sources
-   Top exported products
-   Top imported products
-   Top export destinations
-   Top import sources

Calculate trade balance only when dataset coverage and value definitions
make the comparison valid.

### 8.2 Product Analytics

**Verified status:** The 2024 Product Intelligence release contains 4,577
observed profiles and reconciles to 1,048,575 eligible records in the enriched
Parquet. The JSON output passes its schema. Rankings use observed record
counts while trade-value and quantity units remain unverified. See the
[Product Intelligence methodology](docs/PRODUCT_INTELLIGENCE.md).

For each product, calculate:

-   Total trade value
-   Total quantity, where available and comparable
-   Number of exporting countries
-   Number of importing countries
-   Top exporting countries
-   Top importing countries
-   Most active trade routes

### 8.3 Trade Route Analytics

**Verified status:** The 2024 Route Intelligence release contains 3,734
directional profiles. Its 1,048,575 eligible records have unique composite
keys and reconcile with the enriched Parquet and both Country and Product
Intelligence. The JSON passes its schema. See the
[Route Intelligence methodology](docs/ROUTE_INTELLIGENCE.md) for full product
composition queries and the limits on interpreting record counts.

For each exporter-importer pair, calculate:

-   Total trade value
-   Total quantity, where valid
-   Number of traded products
-   Top products by trade value
-   Trade value breakdown by product

### 8.4 Potential Market Opportunities

**Phases 04.1 and 04.2 verified:** The feasibility assessment and query
engine reconcile 7,271,733 external relationships across three evidence
categories. The engine publishes a versioned summary and supports bounded
on-demand queries. Independent Parquet, schema, pagination, and analytics
regression checks passed. See the [query implementation and benchmarks](docs/MARKET_OPPORTUNITY_INTELLIGENCE.md),
[methodology](docs/MARKET_OPPORTUNITY_METHODOLOGY.md) and
[feasibility report](reports/market_opportunity_feasibility.json).

Build an explainable analytical process to identify potential
connections between exporting and importing markets.

Tasks:

1.  Identify countries importing each product.
2.  Identify countries exporting each product.
3.  Connect relevant exporter and importer markets.
4.  Calculate indicators using available trade values and quantities.
5.  Rank potential opportunities using documented rules.
6.  Explain why each opportunity was identified.

Limitations:

-   A potential opportunity is an analytical signal, not proof of unmet
    demand.
-   Missing trade routes do not prove that no trade exists.
-   A single-year snapshot cannot establish market growth or forecast
    future demand.
-   Market concentration and market-share metrics require appropriate
    coverage and denominators.

### Deliverables

-   `country_analytics.json`
-   `product_analytics.json`
-   `trade_routes.json`
-   `market_opportunities.json`
-   Analytics methodology documentation

### Acceptance criteria

-   Aggregations reconcile with the cleaned dataset.
-   Top-N results are deterministic and correctly ordered.
-   Missing or incomplete coverage is disclosed.
-   Opportunity scores have documented inputs and explanations.
-   Units and measurement definitions are documented.

## 9. Workstream E -- Synthetic Marketplace Data Generation

**SM-01 foundation verified.** The pinned 2024 Trade Intelligence release
passed read-only verification. The nine approved strategies, fixed targets,
draft configuration, and proposed Backend contract are documented in the
[marketplace specification](docs/SYNTHETIC_MARKETPLACE_SPECIFICATION.md) and
[readiness report](reports/synthetic_marketplace_readiness.json).
The approved initial split is 600 RFQs and 900 offers with exactly one role
per company.

**SM-02 structural witness verified.** The provisional anonymous allocation
meets the fixed targets. See the [planning manifest](data/planning/synthetic_marketplace/allocation_plan_manifest.json)
and [feasibility analysis](docs/SYNTHETIC_JOINT_ALLOCATION_FEASIBILITY.md).
Full generation remains blocked pending commercial feasibility, configuration
approval and Backend contract confirmation. The exact SM-02 allocation is
approved for the isolated SM-03 company stage.

**SM-03A foundation verified.** The source and serialized SM-02 witness
passed read-only validation. The [company foundation](docs/SYNTHETIC_COMPANY_GENERATION.md)
uses isolated fixtures for names, neutral UUID mappings, role and portfolio
preservation, and independent validation. See the
[readiness report](reports/synthetic_company_readiness.json).
**SM-03B company population complete.** The approved root UUID, canonical
keys, seed and exact immutable allocation produced 500 companies with 300
supplier roles across 25 markets, 200 importer roles across 75 markets and
1,800 preserved portfolio associations. Independent validation resolved all
500 slots and every downstream planning reference. The full regression suite
passed and two independent builds produced byte-identical bundles. The
[isolated stage manifest](data/synthetic/stages/companies/company_stage_manifest.json)
identifies the validated outputs. The [SM-04 handoff](docs/SM04_LISTING_GENERATION_HANDOFF.md)
records outstanding commercial and Backend dependencies. Later stages require
separate authorization.

**SM-04A commercial proposal validated.** The isolated plan resolves 300
product profiles, 1,000 listing scenarios, 600 RFQ scenarios and 900 offer
scenarios using the exact SM-02 and SM-03B inputs. All 900 allocated
responses support full fulfillment in independent scenarios. Two full
serialized builds matched byte for byte and all 55 tests passed. The exact
configuration, schemas, identifiers, plan and SM-04B execution still need
approval. [Commercial plan](data/planning/commercial_feasibility/commercial_plan_manifest.json) ·
[SM-04B approval package](docs/SM04_LISTING_STAGE_AUTHORIZATION.md)

Marketplace data generated in this workstream is synthetic. Real trade
patterns may guide product and country selection, but generated
companies, contacts, listings, prices, quantities, offers, and RFQs must
not be presented as real-world facts.

### 9.1 Product Selection

Select 300 products from the product reference data, prioritizing
products present in the trade dataset and providing useful geographic
and category coverage.

Suggested fields:

-   Product ID
-   HS code
-   Product name
-   Product description
-   Category
-   Unit, where reliably defined
-   Synthetic-data indicator where appropriate

Reference descriptions are source data, not synthetic claims. A
generated marketplace listing for a reference product is still
synthetic.

### 9.2 Company Generation

Generate 500 unique companies.

Suggested fields:

-   Company ID
-   Company name
-   Country
-   Business type
-   Industry
-   Synthetic contact details
-   Demo verification status
-   `is_synthetic: true`

Do not use real company identities or contact details without an
appropriate source and permission. Demo verification status must not
imply actual business verification.

### 9.3 Supplier and Importer Roles

Assign supplier and importer roles using documented generation rules
informed by trade patterns.

Targets:

-   300 supplier roles
-   200 importer roles

A company may hold both roles if supported by the data model. Keep the
total number of unique companies at 500.

Trade patterns can inform plausible country-product combinations, but do
not prove that a generated company actually exports or imports a
product.

### 9.4 Listing Generation

Generate 1,000 listings.

Suggested fields:

-   Listing ID
-   Supplier ID
-   Product ID
-   Supplier country
-   Price
-   Currency
-   Available quantity
-   Unit
-   Minimum order quantity
-   Listing status
-   `is_synthetic: true`

Generate prices, stock quantities, and minimum order quantities using
explicit configurable rules. Do not treat aggregate trade value divided
by quantity as a verified market or supplier price.

### 9.5 Offers and RFQs

Generate 600 RFQs and 900 offers in the initial release. Confirm the
transport fields and import requirements with the Backend team.

Suggested fields:

-   Record ID
-   Record type
-   Buyer or importer ID
-   Supplier ID, when applicable
-   Product ID
-   Related listing or RFQ ID, where applicable
-   Requested quantity
-   Unit
-   Target or offered price
-   Currency
-   Destination country
-   Delivery terms
-   Status
-   `is_synthetic: true`

Final relationship rules must follow the Backend data model.

### 9.6 Synthetic Data Validation

-   Enforce unique IDs.
-   Validate all foreign-key relationships.
-   Ensure each listing references an existing supplier and product.
-   Ensure each RFQ references an existing buyer and product.
-   Ensure each offer references valid related entities.
-   Validate positive prices and quantities where required.
-   Validate units and currencies.
-   Mark generated marketplace records as synthetic.
-   Use a fixed random seed for reproducible generation.
-   Document generation rules and assumptions.

### Deliverables

-   `products.json`
-   `companies.json`
-   `listings.json`
-   `rfqs.json`
-   `offers.json`
-   Synthetic generation configuration
-   Synthetic data validation report

## 10. Workstream F -- AI Features

Implement the first version using explainable rules and embeddings.
Consider more complex machine-learning models only when suitable labeled
data and evaluation criteria are available.

### 10.1 Supplier Matching

Input may include product or description, quantity and unit, destination
country, and optional price or delivery constraints.

Processing steps:

1.  Identify the requested product.
2.  Resolve it to the catalog and, where appropriate, an HS code.
3.  Normalize quantity and unit.
4.  Filter suppliers and listings using hard constraints.
5.  Calculate a match score.
6.  Rank eligible results.
7.  Return explanations for each recommendation.

### 10.2 Product Matching

Use text embeddings to compare user-entered product descriptions with
catalog descriptions.

Tasks:

-   Normalize product text.
-   Generate catalog embeddings.
-   Generate query embeddings.
-   Retrieve semantically similar products.
-   Apply category or HS-code constraints where appropriate.
-   Return top matches with similarity information.
-   Provide a confirmation path for ambiguous matches.

Text similarity alone must not be treated as authoritative customs
classification.

### 10.3 Recommendation Scoring

Start with a configurable rule-based scoring model.

  Factor                    Initial weight
  ----------------------- ----------------
  Product match                        35%
  Trade-route relevance                20%
  Quantity match                       20%
  Price compatibility                  15%
  Verification status                  10%

These weights are initial hypotheses and must be evaluated. Synthetic
verification fields must be distinguished from real verification.

### 10.4 Evaluation

Define evaluation cases and expected outcomes for:

-   Product matching relevance
-   Supplier ranking quality
-   Constraint handling
-   Explanation quality
-   No-match behavior
-   Ambiguous product descriptions

### Deliverables

-   Supplier matching module
-   Product matching module
-   Configurable recommendation scoring
-   Evaluation dataset or test cases
-   AI feature documentation

## 11. Workstream G -- Backend Integration and JSON Handoff

The Backend team must confirm final entity schemas and relationship
rules before the export format is considered final.

### Tasks

-   Agree on entity and field names.
-   Define required and optional fields.
-   Define field types and allowed values.
-   Agree on ID formats and foreign-key relationships.
-   Agree on date, currency, and measurement-unit formats.
-   Define null and unknown-value representation.
-   Define synthetic-data indicators.
-   Create JSON Schemas or Pydantic models for validation.
-   Export files in the agreed structure.
-   Test importing JSON into a Backend development environment.

### Suggested export structure

``` json
{
  "metadata": {
    "dataset_type": "synthetic_marketplace",
    "is_synthetic": true,
    "version": "1.0"
  },
  "products": [],
  "companies": [],
  "listings": [],
  "rfqs": [],
  "offers": []
}
```

This is a proposed envelope, not a confirmed Backend contract. The final
structure must follow Backend requirements.

### Deliverables

-   JSON export files
-   JSON Schemas or Pydantic validation models
-   `BACKEND_INTEGRATION.md`
-   Import validation report

### Acceptance criteria

-   All exported files pass schema validation.
-   Entity relationships are valid.
-   Backend can import the files in its development environment.
-   Synthetic records are clearly labeled.
-   Export generation is reproducible.

## 12. Workstream H -- Testing and Quality Assurance

### Data tests

-   Input schema validation
-   Missing-value checks
-   Duplicate checks
-   Country-code mapping tests
-   Product-code mapping tests
-   Join row-count reconciliation
-   Aggregation reconciliation

### Marketplace tests

-   Unique IDs
-   Valid entity references
-   Valid roles
-   Valid prices and quantities
-   Valid currencies and units
-   Synthetic labeling
-   Reproducible generation

### AI tests

-   Product matching test cases
-   Supplier matching test cases
-   Ranking consistency
-   Constraint handling
-   No-result behavior
-   Explanation completeness

### Integration tests

-   JSON schema validation
-   Backend import tests
-   Referential integrity
-   Compatibility with agreed field names and types

## 13. Proposed Repository Structure

``` text
globiq-ai/
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   └── synthetic/
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_data_cleaning.ipynb
│   ├── 03_data_enrichment.ipynb
│   ├── 04_country_analytics.ipynb
│   ├── 05_product_analytics.ipynb
│   ├── 06_trade_routes.ipynb
│   └── 07_synthetic_data_analysis.ipynb
├── src/
│   ├── ingestion/
│   ├── validation/
│   ├── preprocessing/
│   ├── enrichment/
│   ├── analytics/
│   ├── synthetic_generation/
│   ├── matching/
│   ├── recommendation/
│   └── export/
├── schemas/
│   ├── trade_schema.py
│   ├── product_schema.py
│   ├── company_schema.py
│   └── marketplace_schema.py
├── configs/
├── tests/
├── reports/
├── docs/
│   ├── DATA_DICTIONARY.md
│   ├── DATA_QUALITY_REPORT.md
│   ├── PIPELINE_DOCUMENTATION.md
│   └── BACKEND_INTEGRATION.md
├── requirements.txt
├── README.md
└── .gitignore
```

## 14. Definition of Done

A task is complete when:

-   Code and configuration are committed in the agreed project location.
-   Inputs and outputs are documented.
-   Relevant input validation is implemented.
-   Automated tests cover core behavior and important edge cases.
-   Unsupported assumptions are not presented as facts.
-   Raw source data remains unchanged.
-   Outputs are reproducible where applicable.
-   Relevant documentation is updated.
-   Dependencies on other workstreams are resolved or explicitly
    recorded.

## 15. Risks and Mitigations

  -----------------------------------------------------------------------
  Risk                    Potential impact        Mitigation
  ----------------------- ----------------------- -----------------------
  Missing country codes   Incomplete country      Report unmatched codes
                          analytics               and mapping coverage

  Missing product codes   Product descriptions    Preserve unknown codes
                          unavailable             and report them

  Large source files      High memory usage and   Use chunk processing
                          slow processing         and Parquet

  Unconfirmed measurement Incorrect analytics     Verify source
  units                                           documentation before
                                                  publishing metrics

  Synthetic data mistaken Misleading marketplace  Clearly label generated
  for real data           experience              entities and records

  Backend schema changes  Rework in export and    Agree on a versioned
                          integration             contract before final
                                                  export

  Limited historical      Unsupported trend       Disclose coverage and
  coverage                claims                  avoid unsupported
                                                  forecasts

  Duplicate reference     Row multiplication      Validate key uniqueness
  keys                    during joins            before joining
  -----------------------------------------------------------------------

## 16. Immediate Execution Backlog

Start with these tasks in order:

  -----------------------------------------------------------------------
  ID                      Task                    Expected output
  ----------------------- ----------------------- -----------------------
  GLOB-01                 Project setup           Repository,
                                                  environment, README

  GLOB-02                 Data ingestion          Loaded source files and
                                                  data inventory

  GLOB-03                 Data profiling          Data quality and
                                                  profiling reports

  GLOB-04                 Reference validation    Country and product
                                                  mapping reports

  GLOB-05                 Data cleaning           Clean trade dataset and
                                                  invalid-record output

  GLOB-06                 Data enrichment         Enriched trade dataset
  -----------------------------------------------------------------------

Do not begin synthetic generation or AI recommendation development until
the source data has been profiled and relevant schemas and assumptions
have been validated.

## 17. Required Inputs and Dependencies

Confirm access to:

1.  The complete Trade Data file.
2.  The complete Product Reference file.
3.  The complete Country Reference file.
4.  Source documentation defining trade fields and measurement units.
5.  The Backend team's expected JSON schemas, or an agreed process for
    defining them.
6.  The AI repository location and development conventions.

The first execution milestone is a validated data inventory and
profiling report. It will establish actual dataset sizes, coverage,
limitations, and the appropriate processing strategy.

## SM-04A-R commercial remediation

Persist the historical SM-04A commercial plan and its original bindings. Apply explicit product suitability and specifications, scoped identifier checks, fixed Decimal serialization and production-shaped candidate validation. The 13 restrictions reduce historical scope, so corrected full-data planning requires a separate structural scope decision. SM-04B, SM-05, SM-06, Backend import and marketplace publication remain blocked. [Remediation evidence](reports/sm04a_remediation_report.json)

## SM-04A-S adaptive marketplace scope

The product owner approved the adaptive strategy and its 287-product ceiling. The 47-profile review adds 39 proposals and keeps eight unresolved profiles excluded. The proposed 279-product scope has 932 original listing allocations, 558 RFQs, and 835 offers. Independent scope validation and two matching deterministic builds passed. Exact scope and specification approval, commercial values and coverage acceptance, corrected commercial feasibility, and later listing-only approval are pending. [Approval package](docs/SM04A_MARKETPLACE_SCOPE_APPROVAL.md)

## SM-04A corrected commercial feasibility

The product owner approved the exact 279-product MVP scope and commercial configuration. Two complete corrected builds matched byte for byte, all 76 tests passed, and independent serialized validation confirmed full fulfillment for all 835 planned offers across 558 RFQs and 932 listing plans. The isolated corrected plan is published with a pending exact SM-04B package. SM-04B, SM-05, SM-06, Backend import, and marketplace release remain blocked. [Corrected planning manifest](data/planning/commercial_feasibility/corrected_plan_manifest.json) · [SM-04B authorization](docs/SM04_LISTING_STAGE_AUTHORIZATION.md)
