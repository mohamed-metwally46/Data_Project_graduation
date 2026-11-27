# Globiq — Synthetic Marketplace Generation Specification

## Document Control

| Attribute | Value |
|---|---|
| Project | Globiq |
| Workstream | E — Synthetic Marketplace Data Generation |
| Document version | 1.1.0 |
| Methodology status | All nine strategy decisions approved |
| Implementation status | SM-01 foundation prepared. See the readiness report. |
| Backend contract status | Contract-first strategy approved. Backend compatibility pending confirmation. |
| Source dataset year | 2024 |
| Geographic scope | Global, subject to evidence and geographic eligibility |
| Delivery format | Versioned JSON release |

## 1. Purpose

Build a realistic, reproducible, internally consistent and explicitly synthetic international B2B marketplace dataset.

The marketplace shall use validated Trade Intelligence observations to inform product selection, geographic allocation and commercial relationships.

Generated companies, listings, prices, quantities, RFQs and offers must never be represented as verified real-world businesses or commercial activities.

The dataset will support:

- Marketplace browsing and demonstration.
- Backend development and integration.
- Frontend development.
- Marketplace search and filtering.
- Future intelligent product matching.
- Future intelligent supplier recommendations.
- Controlled AI evaluation scenarios.

The initial marketplace is a demonstration environment, not a verified commercial trading network.

## 2. Approved Generation Targets

| Entity | Required count |
|---|---:|
| Selected marketplace products | 300 |
| Unique synthetic companies | 500 |
| Supplier roles | 300 |
| Importer roles | 200 |
| Product listings | 1,000 |
| RFQs | 600 |
| Offers | 900 |

The initial release shall contain 300 supplier-only companies and 200 importer-only companies.

Company identities and role assignments must remain logically separate to support future multiple-role companies.

The primary marketplace entity count is 3,300, excluding auxiliary associations, role assignments, market references, manifests and evaluation fixtures.

## 3. Source Trade Intelligence Release

The generator shall consume the pinned Trade Intelligence release below. SM-01 verifies it read-only without substituting another release.

Release ID:

`ti-3349f6e0cb6dde75fe7d5323af71463748cad3232bc7bcb476c6ff6dcd8cd41b`

Dataset fingerprint:

`sha256:4b65676dc1766ebd869df52fef1c3786beffb11fcc838a99eb14a3818e4c136e`

Analytical baseline verified during SM-01:

| Metric | Value |
|---|---:|
| Eligible records | 1,048,575 |
| Country and trade-area profiles | 238 |
| Observed exporters | 29 |
| Observed importers | 226 |
| Observed products | 4,577 |
| Directional trade routes | 3,734 |
| Reciprocal market pairs | 198 |
| External product-market relationships | 7,271,733 |
| Category A relationships | 1,048,575 |
| Category B relationships | 4,694,268 |
| Category C relationships | 1,528,890 |

Verify actual source artifacts and the release manifest before consuming these results.

Do not use reported statistics as substitutes for source validation.

The Trade Intelligence release must remain read-only during synthetic generation.

## 4. Approved Methodology Decisions

| ID | Approved policy |
|---|---|
| SM-01.1 | Balanced Product Diversity |
| SM-01.2 | Evidence-Based Balanced Global Distribution |
| SM-01.3 | Extensible Hybrid Role Architecture |
| SM-01.4 | Adaptive Evidence-Based Policy |
| SM-01.5 | Context-Aware Synthetic Identity Architecture |
| SM-01.6 | Configurable Product-Aware Commercial Generation |
| SM-01.7 | Evidence-Based Commercial Scenario Generation |
| SM-01.8 | Versioned Contract-First JSON Architecture with UUID v5 and display codes |
| SM-01.9 | Modular, Configuration-Driven, Release-Oriented Pipeline |

These decisions govern the entire Workstream E implementation.

Numerical allocation parameters proposed during methodology discussions must remain configurable and must not be treated as independently approved mandatory thresholds unless explicitly confirmed.

## 5. Product Selection Policy

### 5.1 Eligibility

Select 300 distinct observed products from the validated release.

Each product must:

- Have a valid source product code.
- Have a mapped reference description.
- Preserve its original normalized code as a string.
- Have observed exporter and importer evidence.
- Support the required marketplace allocation policy.

Do not assume a verified HS classification revision.

### 5.2 Selection Methodology

Use balanced product diversity rather than selecting exclusively by record count.

Consider:

- Product category representation.
- Geographic diversity.
- Observed exporter diversity.
- Observed importer diversity.
- Observed directional relationships.
- Supplier and importer allocation feasibility.
- Commercial configuration availability.
- Listing and RFQ coverage feasibility.

Use deterministic selection and documented tie-breaking rules.

Category mappings must have documented provenance.

Do not infer commercial popularity, demand, profitability or market value from observed record counts.

### 5.3 Product Provenance

Distinguish real product reference information from generated marketplace attributes.

Reference descriptions are source data.

Marketplace categories, presentation attributes, commercial configurations and demo catalog assignments may be generated or curated.

Mark generated attributes appropriately.

## 6. Geographic Selection Policy

Apply evidence-based balanced global distribution.

Allocate supplier and importer markets independently.

Use observed product-market roles for assigned company portfolios.

Maintain geographic diversity where supported by eligible markets and avoid excessive concentration through documented configurable allocation constraints.

Distinguish sovereign countries, territories and statistical trade areas.

A reference entry must not automatically be considered a valid business-registration location.

Use an explicitly documented business-location eligibility policy.

Preserve missing ISO identifiers in analytical references. Do not fabricate geographic identifiers.

Unsupported geographic expansion must not occur silently.

The marketplace must not claim that the supplied dataset establishes complete global trade coverage.

## 7. Company Role and Portfolio Policy

Generate exactly 500 unique synthetic companies.

Initial role allocation:

- 300 supplier-only companies.
- 200 importer-only companies.
- Zero dual-role companies in the first release.

The architecture shall support future multiple-role assignments without duplicating company identities.

Each company shall have an eligible geographic market and a product portfolio consistent with its assigned role.

Supplier-product associations require observed export evidence.

Importer-product associations require observed import evidence.

Proposed portfolio planning defaults:

- Approximately four products per supplier.
- Approximately three products per importer.

These are configurable planning assumptions, not mandatory commercial facts.

Every selected product should have supplier and importer representation, subject to joint allocation feasibility.

Do not introduce unsupported product associations to satisfy allocation targets.

## 8. Market Relationship Evidence Policy

Use entity-specific evidence rules.

### Category A

The exact directional exporter-product-importer relationship was observed in the pinned dataset.

### Category B

Both product roles were observed, and the directional market pair was observed for other products, but the specific product relationship was unobserved.

### Category C

Both product roles were observed, but neither the specific product relationship nor the directional market pair was observed.

### 8.1 Entity-Level Evidence Rules

| Entity | Evidence requirement |
|---|---|
| Product | Valid observed product reference |
| Supplier | Eligible market and observed exporter role |
| Importer | Eligible market and observed importer role |
| Supplier-product association | Observed market-product export role |
| Importer-product association | Observed market-product import role |
| Listing | Valid supplier-product association |
| Open RFQ | Valid importer-product association |
| Targeted RFQ | Valid product roles and permitted bilateral relationship |
| Offer | Valid supplier, importer, product and permitted bilateral relationship |

### 8.2 Bilateral Relationship Policy

Category A is the primary generation foundation.

Category B is permitted under controlled synthetic scenario rules.

Category C is excluded from the default marketplace commercial population and reserved for isolated evaluation or intelligence exploration.

The proposed bilateral distribution is:

- At least 80% Category A.
- At most 20% Category B.
- Zero Category C.

These percentages require final configuration approval and feasibility verification.

The denominator must include commercial records requiring bilateral evidence. Open RFQs without identified suppliers are excluded.

Targeted RFQs and their associated offers must have consistent relationship evidence.

The generator must not weaken evidence requirements to achieve numerical targets.

### 8.3 Evidence Provenance

Record applicable:

- Source release ID.
- Dataset fingerprint.
- Product code.
- Exporter market identifier.
- Importer market identifier.
- Relationship identifier.
- Evidence category.
- Observed relationship indicators.

Do not treat categories as commercial success probabilities, risk scores or proof of actual demand.

## 9. Synthetic Company Identity Policy

Generate context-aware fictional company identities using:

- Geographic context.
- Commercial role.
- Product portfolio.
- Industry.
- Business type.
- Configurable naming and description templates.

Company names must be unique within the generated dataset after normalization.

Do not copy real company identities or contacts.

Do not claim worldwide legal or trademark uniqueness for generated names.

### 9.1 Contact and Verification Policy

Use reserved fictional domains for email and website attributes.

Phone numbers should be null by default.

Do not generate operational fictional contacts, real personal data, fabricated certificates or misleading registration information.

Verification status must indicate that the company is not genuinely verified.

Do not fabricate customer reviews, ratings or completed transactions.

Every synthetic company must have `is_synthetic: true`.

The Backend and Frontend must clearly distinguish demo companies from real businesses and prevent operational commercial interactions with fictional identities.

## 10. Commercial Attribute Policy

Use configurable product-aware commercial generation.

Commercial values must not be calculated from unverified source trade values or quantities.

### 10.1 Pricing

Use:

- Category-level commercial defaults.
- Product-specific overrides.
- Explicit synthetic minimum and maximum prices.
- Synthetic product baselines.
- Deterministic controlled variation.
- Explicit price basis and measurement unit.

Use Decimal arithmetic for monetary calculations.

Do not claim generated values are current market prices.

Do not assign arbitrary country-specific price advantages based on unsupported economic assumptions.

### 10.2 Quantities

Define allowed units, quantity increments and precision for each product.

Generate:

- Available quantity.
- Minimum order quantity.
- Requested quantity.
- Offered quantity.

Active in-stock listings must satisfy:

`0 < minimum_order_quantity <= available_quantity`

Normal full-quantity in-stock offers must satisfy the applicable listing MOQ and stock constraints.

A buyer request may exceed available supplier stock without making the RFQ invalid.

Do not create falsely fulfillable offers for incompatible quantities.

### 10.3 Currency

The initial release shall use USD.

The architecture must support future additional currencies.

No live currency conversion service is required.

Currency, unit and price basis must be explicit.

When price is specified for a basis quantity other than one, calculate total product value as:

`unit_price × offered_quantity / price_basis_quantity`

Apply documented Decimal rounding rules.

### 10.4 Delivery Terms

Delivery-term attributes must use approved controlled values.

Do not generate unsupported logistics charges, delivery guarantees or claims about shipping feasibility.

Confirm applicable delivery-term fields with the Backend team.

## 11. Listing Generation Policy

Generate exactly 1,000 listings.

Each listing must reference:

- An existing eligible supplier.
- An existing selected product.
- A valid supplier-product association.
- An approved commercial configuration.

Use at most one listing per supplier-product pair by default.

Ensure supplier and product coverage.

The proposed status allocation is:

- 850 active.
- 100 out of stock.
- 50 inactive.

These are provisional scenario defaults.

Every selected product should have at least one active listing.

Out-of-stock listings must not be treated as immediately available inventory.

Active listing coverage and competing-offer feasibility must be evaluated together before generation.

## 12. RFQ Generation Policy

Generate exactly 600 RFQs.

Each RFQ must reference:

- An existing eligible importer.
- An existing selected product.
- A valid importer-product association.
- A requested quantity and measurement unit.
- Currency and target price where applicable.
- Destination market.
- RFQ type and status.

Support:

- Open RFQs.
- Targeted RFQs.

The proposed initial allocation is 420 open RFQs and 180 targeted RFQs.

A targeted RFQ requires an eligible supplier and permitted bilateral evidence.

A targeted RFQ may have at most one current response from its targeted supplier.

Open RFQs may receive responses from multiple eligible suppliers.

## 13. Offer Generation Policy

Generate exactly 900 offers.

Each offer must reference:

- An existing RFQ.
- An existing eligible supplier.
- An existing listing for the requested product.
- A permitted bilateral market relationship.

Product, supplier, listing, currency, measurement unit and commercial attributes must be consistent.

Do not create duplicate current offers from the same supplier for the same RFQ.

Proposed RFQ response distribution:

| Offers per RFQ | Number of RFQs | Total offers |
|---:|---:|---:|
| 0 | 120 | 0 |
| 1 | 180 | 180 |
| 2 | 180 | 360 |
| 3 | 120 | 360 |
| Total | 600 | 900 |

This is a configurable scenario proposal.

Multiple competing responses must belong to open RFQs.

Validate the joint feasibility of RFQ types, response counts, active listings, distinct eligible suppliers and evidence distribution before generation.

Use primarily open RFQs and submitted offers.

Advanced negotiation, orders, payments, accepted commercial commitments and completed transactions remain outside the initial generation scope.

Unaccepted offers do not automatically reserve or reduce inventory.

## 14. Evaluation Dataset Policy

Maintain a strict separation between the importable marketplace dataset and deliberately constructed evaluation fixtures.

Evaluation scenarios may include:

- Fully compatible matches.
- Price mismatches.
- MOQ mismatches.
- Stock mismatches.
- Product mismatches.
- Unit mismatches.
- No-match scenarios.
- Multiple competing suppliers.
- Invalid foreign keys for negative validation tests.
- Isolated Category C scenarios.

Do not include deliberately invalid records in the main marketplace release.

Evaluation fixtures must not count toward the approved marketplace entity targets.

Evaluation fixtures are not a substitute for independently designed AI evaluation cases.

## 15. Backend Contract

Use versioned contract-first JSON delivery.

The AI and Data system owns the generated external dataset.

The Backend owns its database schema, internal primary keys, persistence and import behavior.

Both teams must agree on:

- Entity definitions.
- Required and optional fields.
- JSON schemas.
- Entity relationships.
- Identifier mappings.
- Currency and unit representations.
- Decimal precision.
- Status enumerations.
- Delivery-term fields.
- Synthetic-data isolation.
- Import idempotency.
- Failure and rollback behavior.

Do not claim Backend compatibility before verifying the actual contract.

The proposed entity model contains:

- Market references.
- Products.
- Companies.
- Company roles.
- Company-product associations.
- Listings.
- RFQs.
- Offers.
- Marketplace release metadata.

The physical database model may differ from the JSON delivery model.

## 16. Identifier Policy

Use deterministic UUID v5 external identifiers and human-readable display codes.

Preserve source identifiers independently from generated marketplace identifiers.

Use a fixed, versioned Globiq namespace and canonical logical entity keys.

Define identity stability rules for regeneration and configuration changes.

Human-readable display codes must not act as the sole foreign-key mechanism.

Changes to mutable values such as price, stock or display name should not automatically replace the underlying entity identity.

Do not reuse an identifier for a materially different entity.

Prevent collisions with real marketplace records.

The final namespace and identity-key formats require explicit contract definition.

## 17. Proposed Data Representation

| Attribute | Representation |
|---|---|
| External entity ID | UUID string |
| Source product code | String |
| Source market ID | String |
| ISO identifiers | String or null |
| Currency | Three-letter currency code |
| Monetary amount | Decimal string |
| Quantity | Decimal string with unit-specific precision |
| Unit | Controlled unit code |
| Timestamp | ISO 8601 UTC |
| Status | Controlled enumeration |
| Synthetic indicator | Boolean |
| Schema version | Version string |
| Unknown optional value | JSON null |
| Dataset fingerprint | SHA-256 identifier |

Final precision, field lengths, enumerations and nullability require Backend agreement.

## 18. System Architecture

Use a modular, configuration-driven, release-oriented Python pipeline.

Logical components:

1. Source release reader and verifier.
2. Configuration and policy validator.
3. Product and geographic selection planner.
4. Joint allocation feasibility planner.
5. Company and role generator.
6. Product portfolio allocator.
7. Synthetic commercial attribute engine.
8. Listing generator.
9. RFQ generator.
10. Offer generator.
11. Independent validator.
12. JSON exporter.
13. Release manager.
14. CLI and reporting interfaces.

Use a shared generation context containing the validated source release, configuration, schemas, identity policy and deterministic random streams.

Reuse existing repository utilities where appropriate.

Do not introduce unnecessary microservices, queues, paid APIs or external databases.

## 19. Generation Pipeline

Execute stages in dependency order:

1. Verify the source Trade Intelligence release.
2. Validate the approved configuration and contracts.
3. Evaluate joint product, geographic and commercial allocation feasibility.
4. Finalize the selected product and market plan.
5. Generate companies and assign roles.
6. Generate company-product associations.
7. Generate listings.
8. Generate RFQs.
9. Generate offers.
10. Run independent validation.
11. Verify deterministic regeneration.
12. Publish a validated marketplace release.

Feasibility planning may jointly evaluate proposed product selection, market selection and downstream allocation before the selection plan is finalized.

Do not silently relax mandatory policies when constraints are infeasible.

## 20. Reproducibility

Use:

- A fixed master seed.
- Independently derived deterministic random streams.
- Stable ordering.
- Deterministic UUID v5 generation.
- Versioned configuration.
- Pinned relevant dependencies.
- Canonical serialization.
- Documented numerical rounding.
- Pinned Trade Intelligence release.

The proposed initial master seed is 42.

The final value must be included in the approved generation configuration.

Identical relevant inputs and configuration must produce identical deterministic analytical content.

Separate operational timestamps and performance measurements from deterministic content comparisons.

Document any expected byte-level differences.

## 21. Validation Architecture

Implement independent validation covering:

### Source Integrity

Verify source release identity, fingerprint, schemas and referenced artifact integrity.

### Configuration

Verify policy versions, targets, allowed values and commercial range consistency.

### Structural Validation

Validate all generated entity artifacts against their applicable JSON schemas.

### Referential Integrity

Verify unique identifiers and valid foreign-key relationships.

### Evidence Validation

Independently verify observed roles and permitted bilateral categories.

### Commercial Validation

Verify prices, quantity constraints, MOQ, stock, units, currency, price basis and status compatibility.

### Business Policy Validation

Verify entity counts, role allocation, required product coverage, configured scenario distributions and synthetic labeling.

### Reproducibility and Release Validation

Verify deterministic regeneration, artifact integrity and safe publication.

Mandatory failures must prevent release publication.

Warnings may describe configurable objectives only where the approved policy permits deviation.

## 22. Release Management

Generate artifacts in an unpublished staging directory.

Publish only after all required validation checks pass.

The release shall include a machine-readable manifest containing:

- Marketplace release identifier.
- Schema versions.
- Dataset type.
- Synthetic-data designation.
- Source Trade Intelligence release identifier and fingerprint.
- Configuration identity.
- Generator version.
- Random seed.
- Target and actual entity counts.
- Artifact hashes and sizes.
- Validation status.
- Validation evidence.
- Known limitations.

The release identity must depend on relevant inputs and contracts, not solely on generation timestamps.

Avoid circular hashing dependencies.

Update the validated release pointer last.

Failed generation must preserve any previously validated release.

## 23. Export Package

Proposed artifacts:

- `manifest.json`
- `markets.json`
- `products.json`
- `companies.json`
- `company_roles.json`
- `company_products.json`
- `listings.json`
- `rfqs.json`
- `offers.json`
- `validation_report.json`

The exact packaging must follow the confirmed Backend contract.

Do not duplicate authoritative role assignments unnecessarily.

Keep evaluation fixtures outside the importable artifact set.

## 24. Backend Import Requirements

The Backend should:

1. Verify release metadata, schema compatibility and artifact integrity.
2. Resolve market and product references.
3. Import companies and establish external-ID mappings.
4. Import roles and product associations.
5. Import listings.
6. Import RFQs.
7. Import offers.
8. Reconcile imported counts and relationships.
9. Commit or activate the release only after successful validation.

Repeated imports must follow an explicit idempotency policy.

Synthetic imports must never overwrite genuine businesses or commercial data.

Actual Backend import acceptance belongs to the relevant integration milestone.

## 25. Testing Strategy

Provide:

- Deterministic unit tests.
- Configuration and schema tests.
- Referential integrity tests.
- Evidence classification tests.
- Commercial constraint tests.
- Business policy tests.
- Negative validation fixtures.
- Integration tests.
- Full-data release validation.
- Reproducibility tests.
- Failure protection tests.
- Backend acceptance tests during integration.

Preserve existing Trade Intelligence behavior and regression tests.

Test coverage must be based on required behavior, not an arbitrary test count.

## 26. Documentation Deliverables

Maintain appropriate documentation covering:

- Approved generation specification.
- System architecture.
- Product and geographic selection.
- Allocation feasibility.
- Company identity and role generation.
- Commercial attribute policies.
- JSON contracts and data dictionary.
- Identifier policy.
- Validation and test methodology.
- Release generation and reproduction.
- Backend integration requirements.

Consolidate related documents where appropriate.

Every implementation milestone must document its actual outputs, commands, validation results, limitations and remaining dependencies.

## 27. Workstream E Execution Roadmap

### SM-01 — Methodology Consolidation and Implementation Foundation

Inspect the existing repository, consolidate approved decisions, verify the source release, establish the configuration foundation and prepare the versioned contract proposal.

No marketplace entity generation.

### SM-02 — Product and Geographic Selection

Implement deterministic balanced selection and joint allocation feasibility.

Finalize the selected 300-product catalog and eligible geographic allocation plan.

### SM-03 — Synthetic Company Generation

Generate 500 fictional companies, assign roles and establish eligible product portfolios.

### SM-04 — Listing Generation

Generate and validate 1,000 listings.

### SM-05 — RFQ and Offer Generation

Generate and validate 600 RFQs and 900 offers.

### SM-06 — Integration, Validation and Release

Produce the validated, reproducible marketplace release and Backend handoff package.

## 28. Outstanding Configuration and Contract Decisions

The following must be resolved through repository inspection, feasibility analysis and explicit agreement:

- Final product-category mapping and quotas.
- Geographic eligibility and concentration limits.
- Exact portfolio distribution.
- Final bilateral evidence percentage constraints.
- Product-level price and quantity configurations.
- Allowed measurement-unit codes and precision.
- Listing status distribution.
- Open and targeted RFQ distribution.
- Exact RFQ response scenario allocation.
- Delivery-term representation.
- UUID namespace and canonical logical keys.
- Master seed.
- Backend-required fields and schema compatibility.
- Import and synthetic isolation behavior.

Proposed defaults may be documented and evaluated but must not be silently promoted into mandatory approved requirements.

## 29. Definition of Done

Workstream E is complete when:

- Approved methodology is documented.
- Source Trade Intelligence release integrity is verified.
- Backend data contract is agreed.
- Joint generation feasibility is established.
- All approved entity counts are satisfied.
- Required product and geographic coverage passes validation.
- Entity identifiers are unique and reproducible.
- All required relationships resolve.
- Evidence policies are satisfied.
- Commercial constraints pass validation.
- Synthetic labeling and contact safety pass validation.
- Applicable schemas validate.
- Deterministic regeneration is demonstrated.
- Independent release validation passes.
- Failure protection is verified.
- Automated regression and integration tests pass.
- The validated release and Backend handoff are documented.

Do not mark actual Backend database integration complete until the corresponding import acceptance tests have passed.

## 30. Limitations and Scope Boundaries

The source dataset is a potentially truncated single-year 2024 trade extract.

Trade value currency, monetary scale, quantity units and classification revision remain unverified.

The source cannot establish actual global market shares, supplier capacity, unmet demand, profitability, market growth or future demand.

Synthetic commercial values are demonstration assumptions.

Do not introduce:

- Real-company acquisition.
- Live market pricing.
- Real commercial transactions.
- Payment processing.
- Demand forecasting.
- Commercial opportunity scoring.
- Production recommendation services.
- Embedding-based search.
- Production HTTP APIs.

These capabilities belong to separate approved workstreams.

## Related engineering records

- [Architecture and SM-02 feasibility design](SYNTHETIC_MARKETPLACE_ARCHITECTURE.md)
- [Proposed Backend transport contract](MARKETPLACE_DATA_CONTRACT.md)
- [Identifier and randomness policy](MARKETPLACE_IDENTIFIER_POLICY.md)
- [Decision register](MARKETPLACE_DECISION_REGISTER.md)
- [Versioned draft configuration](../configs/synthetic/policy.v1.json)
- [Verified SM-01 readiness report](../reports/synthetic_marketplace_readiness.json)
