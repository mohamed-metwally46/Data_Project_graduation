# SM-04A validation and quality checks

Independent validation reads the four serialized planning collections, validates the schema and compares every original allocation field by stable planning ID. It independently checks unit and Decimal precision, stock and MOQ, order increments, quote envelopes, exact full fulfillment and product-only totals. It verifies one-sided product role evidence and queries the engine for every applicable bilateral event. It checks the exact scenario histogram and targeted relationships, including unanswered requests. A failed check prevents candidate publication.

The planner serializes and validates two independent builds. It compares the bytes of all seven deterministic artifacts before publishing. SHA-256 and byte sizes are verified at the content-addressed directory before the planning pointer is replaced. Operational timings and working-set measurements live in the readiness report. Previous published artifacts remain addressable and the pointer is preserved on candidate validation failure.

The quality report measures price, stock, MOQ and quantity variation per product, boundary concentration, supplier and product listing coverage and RFQ candidate eligibility. It restricts candidate comparisons to the allocated catalog and baseline Category A evidence, then applies commercial rules separately. Missing eligible candidates in this synthetic catalog establish neither unmet demand nor absent real suppliers. Unanswered requests and unavailable targeted listings are preserved and reported. Price and quantity comparisons remain within consistent product and unit contexts. Specialist company coverage remains at zero in the verified company stage, while matching uses product portfolio associations.

Core commands are `python -m src.synthetic.commercial_stage plan`, `python -m src.synthetic.commercial_stage validate-plan`, `python -m src.synthetic.listing_stage fixture`, and `python -m unittest discover -s tests -v`. Unit and integration tests cover exact arithmetic, shared stock, blocked listing generation, tampering and failed publication. [Run evidence](../reports/synthetic_commercial_readiness.json)

## Measured quality

- Listing prices, stock values and offer prices vary within all 300 product groups when summarized by product. MOQ varies in 298 products and RFQ quantity varies in 291.
- Five listing prices were on their effective price band endpoints, eight positive stock values on stock bounds, and 124 MOQ values on MOQ bounds. The MOQ concentration remains visible for commercial review.
- There were 1,290 compatible request-listing combinations. Of these, 390 were eligible nonresponding combinations. Another 292 structurally eligible combinations were commercially incompatible.
- Of 120 unanswered requests, 111 had a compatible listing in the simulated catalog and nine did not. The original plan has no unanswered targeted requests.
- In fictional competitive scenario `RFQ-PLAN-0187`, three approved suppliers can each fulfill 6 PCS individually. Their offer quotes are USD 53.00, 56.96 and 52.94 per PCS. In unanswered scenario `RFQ-PLAN-0294`, three candidates can fulfill 60.500 KG and all remain nonresponding.

[Per-product and per-request diagnostics](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/commercial_quality_report.json)

## SM-04A-R validation evidence

The SM-04A-S scope checkpoint independently reconciles retained associations, listing statuses, RFQ types and targets, response relationships, and observed Category A triples. Two deterministic projection builds verify repeatability of scope artifacts. A fixture exercises the gated solver and scope-aware validation. Corrected full-plan validation and quality review remain pending. [Scope approval and workflow](SM04A_MARKETPLACE_SCOPE_APPROVAL.md)

The v1.1 validator checks serialized production-shaped fixtures against explicit scope/cardinality, product suitability and specification, exact source references, supplier roles and portfolios, recorded registry reservations and approved commercial plans. It checks canonical lexical forms and numerical domains independently. It rejects fixture publication and any actual execution with current authorization. Candidate metrics in the new report filter historical diagnostics by scope. Revalidation of a corrected commercial plan requires a structural decision. [Validation code](../src/synthetic/listing_population_validation.py) ? [Remediation evidence](../reports/sm04a_remediation_report.json)

## Corrected planning verification

Both full corrected builds independently validated all serialized profile, listing, RFQ and offer rows against the exact approved scope, original associations and observed SQLite evidence. The six deterministic artifacts matched byte for byte. All 76 tests passed, including the original 74. The corrected-stage tests exercise exact approval binding and reject a tampered serialized offer total. The historical commercial pointer and upstream stage pointers remain unchanged. [Validation and run evidence](../reports/sm04a_corrected_commercial_readiness.json)
