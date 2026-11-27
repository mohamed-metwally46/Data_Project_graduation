# Marketplace decision register

The consolidated specification records the nine marketplace strategies. The draft marketplace policy distinguishes fixed targets, proposals and unresolved values. The SM-03 approvals below apply to the isolated company stage. [Consolidated specification](SYNTHETIC_MARKETPLACE_SPECIFICATION.md) · [Draft marketplace policy](../configs/synthetic/policy.v1.json)

## Fixed requirements and strategy

The pinned 2024 Trade Intelligence release supplies descriptive evidence. The first release must contain 300 products, 500 unique companies, 300 supplier roles, 200 importer roles, 1,000 listings, 600 RFQs, and 900 offers. Each company holds one initial role. Separate role assignments allow future multi-role companies. Use USD initially with currency carried explicitly, Decimal commercial values, fictional identities, reserved contact domains, and explicit synthetic labels. Listings and open RFQs require observed one-sided roles. Targeted RFQs and offers require A or controlled B evidence. Default commercial generation excludes C. Invalid and category C evaluation fixtures stay outside the import bundle.

## Proposed numerical defaults

| Decision | Proposal | Status |
| --- | --- | --- |
| Master seed | 42 | Approved for SM-03 company identity generation |
| Portfolio size | Approximately 4 products per supplier and 3 per importer | Proposed |
| Bilateral evidence | At least 80% A and at most 20% B | Proposed. Denominator and final caps pending. |
| Listing statuses | 850 active, 100 out of stock, 50 inactive | Proposed |
| RFQ types | 420 open, 180 targeted | Proposed |
| RFQs by number of offers | 120 with zero, 180 with one, 180 with two, 120 with three | Proposed |

The scenario arithmetic yields 600 RFQs and 900 offers. The 300 requests with two or three responses must be open. Of the proposed 420 open requests, 120 remain for zero or one response. This leaves enough requests for 180 targeted RFQs to have zero or one response on paper.

## Pending decisions and ownership

| Decision | Required before generation |
| --- | --- |
| Product categories and diversity | Confirm taxonomy source, category quotas, tie-break priorities and minimum coverage. |
| Business locations and geographic balance | Approve country and territory eligibility, aggregate/historical exclusions, concentration caps and separate exporter/importer allocation constraints. |
| Portfolios and active coverage | Agree which product and company coverage requirements are hard constraints and confirm portfolio sizes. |
| Commercial attributes | Approve category and product ranges, precision, currency/units validation, basis and rounding, stock and MOQ, and delivery terms. |
| Bilateral controls | Approve percentage caps and denominator. Count only records requiring bilateral evidence. Decide rounding and how targeted RFQs and their offers are tallied. |
| Listing and RFQ mix | Approve status and response distributions after feasibility is demonstrated. |
| Identity and reproducibility | Confirm the canonical keys and display-code prefixes for entities outside the company stage. |
| Backend | Confirm fields, ID mapping, relationships, delivery terms, idempotency and demo isolation with the Backend team. |
| Joint allocation | Validate commercial feasibility and approve commercial scenario parameters before commercial generation. |

The current configuration uses null for unresolved production values. The [SM-02 feasibility report](../reports/synthetic_joint_feasibility.json) records the tested proposals. A generation entry point requires separate approval of mandatory parameters and feasibility.

## SM-03 approval gates

All five SM-03 strategies are approved. The SM-03B user authorization, attachment `d044fc1c-4991-452b-b6e4-e5d57192afd8` sections 2, 7 and 20, confirms the exact root `9e5fdfc5-2675-57fe-8e94-81dc91ed9639`, population `globiq-marketplace-baseline-001`, `hierarchical_uuid5_v1`, role-neutral `identity-NNNNNN` keys and persistent registry. It authorizes isolated canonical company artifacts under the verified SM-02 population, configuration and schema. Seed 42 and deterministic monograms apply to this stage. At SM-03B publication, later stages still required separate authorization. Backend compatibility remains pending. [Authoritative configuration](../configs/synthetic/company_identity.v1.json) · [Stage authorization](SM03_COMPANY_STAGE_AUTHORIZATION.md)

## SM-04 architecture decisions

The user brief authorizes SM-04A provisional commercial planning. Attachment `4defc9c5-c0c8-4c4e-9c6d-65cf57f6ec87` sections 1 and 8 approve these seven Option D methods.

| Decision | Approved architecture |
| --- | --- |
| SM-04.R1 | Product-aware controlled measurement units with category defaults and explicit overrides |
| SM-04.R2 | Product-aware synthetic Decimal pricing, explicit basis and USD-first |
| SM-04.R3 | Product quantity bounds and integer ticks, with independent full fulfillment and no stock reservation |
| SM-04.R4 | Versioned canonical listing contract, dual product references, distinct entity namespaces and persistent registry |
| SM-04.R5 | Authoritative listing status and derived visibility and eligibility |
| SM-04.R6 | Joint deterministic feasibility planning on original allocation edges |
| SM-04.R7 | Independent validation, deterministic rebuild, quality review and atomic publication |

The exact numerical parameters, product and listing identifier keys, schema, commercial plan and quality review require separate approval. SM-04.R8 records company-to-listing dependency gating and authorization for planning and fixtures. SM-04B execution, Backend import and later marketplace stages remain blocked. [Commercial configuration](../configs/synthetic/commercial.v1.json) ? [Listing-stage authorization](SM04_LISTING_STAGE_AUTHORIZATION.md)

## SM-04A-R approved remediation

The product owner authorized the remediation methods in attachment `2875cb26-3605-4c00-b249-0274f7b78122`, sections 1 and 2. The authorization covers 13 offline-only catalog exclusions, one explicit synthetic specification per product, the six named form and unit corrections, shared identifier validation, complete implementation binding, production-shaped validation, registry safeguards, and an explicit Decimal and lexical policy. Replacement products, revised company portfolios and allocations, exact numerical proposals and listing execution require separate decisions. [Remediation evidence](../reports/sm04a_remediation_report.json)

## SM-04A-S adaptive scope strategy

The product owner selected Option D in attachment `eb48ea63-cba4-472c-bca8-27d7bba01b92`, sections 1 and 2. The 287-product ceiling excludes 13 offline-only codes and keeps the original Trade Intelligence, SM-02, and SM-03B inputs and portfolios immutable. The owner accepted the restriction-only coverage exceptions, subject to exact reconciliation. The full review accounts for the 47 outstanding profiles, and unresolved profiles stay outside the proposed scope.

Corrected provisional commercial planning may proceed after the product owner approves the exact eligible code set, specifications, numerical configuration, and any additional coverage exceptions. The ceiling approval grants no exact-profile, allocation revision, replacement, permanent identity, listing, RFQ, offer, Backend import, or release permission. [Exact pending scope package](SM04A_MARKETPLACE_SCOPE_APPROVAL.md)
