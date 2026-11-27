# Globiq AI & Data

The [implementation plan](Globiq_AI_Data_Implementation_Plan.md) defines the project scope. This workspace contains the read-only source CSVs, audit documentation, and a reproducible Python pipeline for cleaning, enrichment, and count-based Trade Intelligence.

## Run locally

Use Python 3.12 or newer with SQLite support. The core pipeline and analytics use the standard library. Install the pinned PyArrow dependency to export Parquet and run its integration test. Run these commands from the project root.

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.pipeline
python -m src.export.parquet
python -m src.analytics.trade
```

Keep trade_data.csv, product_codes.csv, and country_codes.csv in the project root. Use `Get-FileHash *.csv` to compare source fingerprints with the [audit inventory](reports/data_inventory.json).

The pipeline writes data/processed/trade.sqlite with trade_data_clean, enriched_trade_data, invalid_trade_records, reference tables, dataset metadata, and an unmatched_trade_records view. The Parquet exporter publishes the clean, enriched, and invalid tables as typed files alongside the database. The pipeline also writes validation reports under reports/. The analytics command reads the validated database and writes country_analytics.json, product_analytics.json, trade_routes.json, and market_opportunities.json under data/processed/analytics/.

## Findings and methodology

The supplied Excel export reaches the worksheet row cap and provides partial coverage for 2024. All 1,048,575 rows were preserved through cleaning and enrichment. Product matching reached 100% with the approved normalization. Analytics use counts because the units for trade value and quantity remain unverified.

- [Source inventory](docs/DATA_INVENTORY.md)
- [Initial audit](docs/DATA_QUALITY_REPORT.md)
- [Source data dictionary](docs/DATA_DICTIONARY.md)
- [Cleaning rules](docs/DATA_CLEANING_RULES.md)
- [Enrichment report](docs/DATA_ENRICHMENT_REPORT.md)
- [Assumptions, limitations and analytics methodology](docs/DATA_ASSUMPTIONS_AND_LIMITATIONS.md)

- [Country Intelligence](docs/COUNTRY_INTELLIGENCE.md)
- [Product Intelligence](docs/PRODUCT_INTELLIGENCE.md)
- [Trade Route Intelligence](docs/ROUTE_INTELLIGENCE.md)
- [Market Relationship Intelligence](docs/MARKET_OPPORTUNITY_INTELLIGENCE.md)

- [Validated Trade Intelligence release workflow](docs/TRADE_INTELLIGENCE_RELEASE.md)
- [Release architecture and fingerprinting](docs/TRADE_INTELLIGENCE_ARCHITECTURE.md)
- [Workstream E analytical handoff](docs/SYNTHETIC_MARKETPLACE_HANDOFF.md)

## Synthetic Marketplace foundation

SM-01 prepares the configuration and proposed contract. With the development dependencies installed, run `python -m src.synthetic.foundation check-config` to validate the draft and `python -m src.synthetic.foundation verify-source` to revalidate the approved Trade Intelligence release read-only.

- [Marketplace specification](docs/SYNTHETIC_MARKETPLACE_SPECIFICATION.md)
- [Architecture and feasibility design](docs/SYNTHETIC_MARKETPLACE_ARCHITECTURE.md)
- [Proposed data contract](docs/MARKETPLACE_DATA_CONTRACT.md)
- [Decision register](docs/MARKETPLACE_DECISION_REGISTER.md)
- [SM-01 readiness report](reports/synthetic_marketplace_readiness.json)

## SM-02 allocation planning

Use `python -m src.synthetic.planning plan` to construct the provisional anonymous plan from the pinned release and `python -m src.synthetic.planning validate` to check the serialized witness independently. Use `inspect` for the manifest and `compare-scenarios` for the recorded comparison.

- [Planning artifact manifest](data/planning/synthetic_marketplace/allocation_plan_manifest.json)
- [Product and geographic selection](docs/PRODUCT_MARKET_SELECTION.md)
- [Joint allocation feasibility](docs/SYNTHETIC_JOINT_ALLOCATION_FEASIBILITY.md)
- [SM-03 handoff](docs/SM03_COMPANY_PLANNING_HANDOFF.md)

## SM-03 synthetic companies

SM-03B generated and validated 500 synthetic companies, with 300 supplier roles, 200 importer roles and 1,800 preserved portfolio links. Two independent full builds produced identical company bundles. The published output is an isolated intermediate stage. Backend compatibility and commercial generation remain pending. [Company stage manifest](data/synthetic/stages/companies/company_stage_manifest.json)

Run `python -m src.synthetic.company_stage readiness` to verify the input and published stage hashes and see the recorded checks. Use `inspect-identifiers` for the approved UUID root and `validate-config` for the schema hash. To rebuild the approved population, run `python -m src.synthetic.company_stage generate` with the development dependencies installed. It reruns the full test suite and independent source and allocation checks before publishing to the isolated company stage.

- [Company generation and validation](docs/SYNTHETIC_COMPANY_GENERATION.md)
- [Stage approval](docs/SM03_COMPANY_STAGE_AUTHORIZATION.md)
- [Run evidence and measurements](reports/synthetic_company_readiness.json)
- [SM-04 handoff and pending decisions](docs/SM04_LISTING_GENERATION_HANDOFF.md)

## SM-04 commercial planning

SM-04A published a validated provisional plan for 300 product profiles, 1,000 listing scenarios, 600 RFQs and 900 offers. All 900 planned responses passed independent full-fulfillment checks. SM-04B still requires approval of the exact package. [Planning manifest](data/planning/commercial_feasibility/commercial_plan_manifest.json) · [Run evidence](reports/synthetic_commercial_readiness.json)

Use `python -m src.synthetic.commercial_stage inspect-inputs` to inspect the pinned source, allocation and company-stage bindings. Use `validate-config` or `resolve-profiles` to review proposed units, prices and quantities for all 300 products. The original `plan` command produced and checked two independent historical proposals. A corrected plan requires an approved marketplace scope. Use `validate-plan` to revalidate a published proposal and `quality` for the diagnostics.

- [Proposed commercial configuration](docs/SYNTHETIC_COMMERCIAL_CONFIGURATION.md)
- [Commercial feasibility and solver workflow](docs/SYNTHETIC_COMMERCIAL_FEASIBILITY.md)
- [Listing fixture and canonical contract](docs/SYNTHETIC_LISTING_GENERATION.md)
- [Stage authorization and approval package](docs/SM04_LISTING_STAGE_AUTHORIZATION.md)

## Analysis notebooks

Open the notebooks in Jupyter or VS Code to see the saved charts and analysis. To rerun the cells, install Pillow in the notebook's Python kernel with `python -m pip install pillow==12.3.0`. Each notebook reads its analytical artifact from the validated release manifest and checks the artifact's SHA-256 hash.

- [Country Intelligence](notebooks/01_country_intelligence.ipynb)
- [Product Intelligence](notebooks/02_product_intelligence.ipynb)
- [Trade Route Intelligence](notebooks/03_route_intelligence.ipynb)
- [Market Relationship Intelligence](notebooks/04_market_relationship_intelligence.ipynb)

## SM-04A-R scope decision

Run `python -m src.synthetic.sm04a_remediation inspect` for read-only reconciliation or `python -m src.synthetic.sm04a_remediation report` for verified remediation evidence and the full test suite. The historical `commercial_stage plan` entry point stays gated. Use the scope-aware preparation workflow for the current checkpoint. Historical artifacts remain available. [Scope assessment](docs/SYNTHETIC_COMMERCIAL_FEASIBILITY.md) ? [Remediation evidence](reports/sm04a_remediation_report.json)

## SM-04A-S proposed marketplace scope

The product owner approved the adaptive strategy with a 287-product ceiling. The independently verified proposal retains 279 products, 932 listings, 558 RFQs, and 835 offers from the pinned allocation. The exact scope, specifications, commercial values, and coverage effects await approval. Run `python -m src.synthetic.sm04a_scope verify-proposal` to verify the package and `prepare-planning` to check the exact approval gate. [Scope decision](docs/SM04A_MARKETPLACE_SCOPE_APPROVAL.md) [47-product review](docs/SM04A_PRODUCT_SPECIFICATION_REVIEW.md)
