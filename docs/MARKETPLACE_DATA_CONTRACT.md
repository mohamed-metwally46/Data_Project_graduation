# Marketplace data contract proposal

**Version 0.1.0-draft. Backend compatibility pending confirmation.** This is a logical JSON transport proposal. No Backend implementation, formal schema, or import interface was available in the inspected workspace. [Draft JSON Schema](../schemas/marketplace_bundle.proposed.schema.json)

## Types and entity relationships

Each entity requires a lowercase UUID v5 external_id and a display_code. Fields in the required column below are in addition to those IDs. The source market code is proposed as a canonical numeric string for transport. Preserve its exact identity when mapping to the analytical integer key. Source product codes are normalized strings. Optional fields may be absent. A field may be null only where indicated.

| Entity | Required fields and types | Optional fields and relationships |
| --- | --- | --- |
| Market reference | source_market_code, name and location_kind as strings. iso2 and iso3 as nullable strings. business_location_eligible as boolean. | location_kind proposes country, territory, trade_area or historical. The location eligibility decision needs its own approved mapping. |
| Product | source_product_code, reference_description and category_code as strings. catalog_assignment_is_synthetic is true. | display_name as text. Reference description and external catalog assignment have separate provenance. |
| Company | market_id as UUID, name and industry as text, verification_status demo_unverified, is_synthetic true. | Nullable email and website use fictional .invalid domains. Phone, if present, is null. market_id references a business-eligible market. |
| Company role | company_id as UUID, role supplier or importer, is_synthetic true. | References a company. Future roles may coexist once approved. |
| Company-product association | role_id and product_id as UUIDs, observed_role exporter or importer, source market and product codes, source release ID and fingerprint, is_synthetic true. | References a role and product. Verify the source role and codes against the pinned release. |
| Listing | association_id as UUID, status, price object, available_quantity and minimum_order_quantity as decimal strings, is_synthetic true. | References a supplier association. Proposed status values are active, out_of_stock and inactive. The price unit supplies the listing quantity unit. |
| RFQ | importer_association_id and destination_market_id as UUIDs, open or targeted type, open or closed status, quantity decimal string, unit and currency, nullable target_supplier_role_id and evidence, is_synthetic true. | Optional nullable target_price and delivery_term_code. Open requests have null target and evidence. Targeted requests require a supplier role and bilateral evidence. |
| Offer | rfq_id and listing_id as UUIDs, quantity decimal string, price object, submitted or withdrawn status, bilateral evidence, is_synthetic true. | Optional nullable delivery_term_code. Listing association resolves supplier and product. The RFQ resolves buyer and requested product. |
| Release manifest | Draft contract version and status, marketplace_release_id, dataset_type synthetic_marketplace, is_synthetic true, policy version, configuration SHA-256, source release ID and fingerprint, UUID namespace, artifact hashes and counts. | Artifacts may use a bundle or separate ordered files after contract confirmation. If using a bundle, the manifest cannot include the hash of the bundle containing that manifest. |

The initial currency is USD. The proposed price object carries amount, currency, basis_quantity and unit. Amount, basis and quantity travel as decimal strings. The generator must use Decimal arithmetic, explicit quantization, and validation for positive prices, basis and normal quantities. Available stock can be zero. Backend input precision and status and unit codes remain pending. Optional timestamps, if later agreed, use ISO 8601 UTC and explicit nullability.

Bilateral evidence carries the Trade Intelligence relationship ID, A or B, product and directional market keys, observed link and directional pair indicators, source release ID, and fingerprint. An independent validator must confirm actual membership and category from the engine. Schema validation handles shape and conditional RFQ fields. It does not enforce entity counts, uniqueness, cross-entity foreign keys, identity ownership, decimal comparisons, or observed evidence. These require independent semantic validators. Schema data transport accepts isolated small fixtures.

## Import sequencing and versioning

Proposed order is manifest preflight, market references, products, companies, roles, associations, listings, RFQs, then offers. The Backend owns internal primary keys and should map incoming external IDs inside an isolated demo context. Verify hashes and dependency integrity before loading. Agree on idempotent import keys, transactional boundaries or rollback, and rejection of unsupported contract major versions. Treat semantic breaking changes as version changes. Keep evaluation fixtures outside any import bundle and use separate manifests.

## Questions for the Backend team

- Which models and required fields implement the proposed entities? Which primary-key types and external-ID uniqueness rules apply to each?
- Can one company own multiple role records? Are company-product portfolios represented explicitly? How are product categories and geographic references represented?
- How are listing stock and MOQ, request quantities, and quote prices stored? Which currency, unit, precision and rounding rules apply?
- Which enums, target fields, response constraints and delivery-term fields exist for listings, RFQs and offers?
- Which endpoint, command or job imports the dataset? What are its dependency order, idempotency, merge and rollback semantics?
- How will demo tenants or other isolation prevent fictional records from entering live search, verification, communications or transactions?
- What fixtures, schema version and acceptance results are required to confirm compatibility?

These mappings are proposals awaiting the Backend owner. No existing model or import behavior is inferred.

SM-03B uses the existing canonical intermediate schema v1.0.0 with source market and product keys, role assignments, a planning-slot mapping and an identity registry. Its approved SHA-256 is `f37213461ede31e9ab233a2727716706173afdb5e2d61f679b08feaa79406417`. The payload sets `backend_importable` and `full_marketplace_release` to false. A future adapter requires a confirmed Backend input contract. The Backend team still needs to reconcile the draft .invalid format above with the canonical .example policy and confirm external product ID mapping and operational demo isolation. [Canonical company schema](../schemas/company_stage.proposed.schema.json)

## Proposed commercial contracts

The commercial plan contains synthetic pricing and quantities keyed by structural planning IDs. The proposed canonical listing contract uses dual product references, a supplier-product association, Decimal amount and basis, stock, MOQ, ordering increment, nullable maximum order and authoritative status. Its fixture and intermediate envelopes require synthetic flags and exclude Backend import. Confirm the Backend field mapping, external ID resolution, exact Decimal persistence and derived visibility in a separately authorized adapter. [Commercial plan schema](../schemas/commercial_plan.v1.schema.json) ? [Proposed listing bundle schema](../schemas/listing_stage.proposed.schema.json)

## SM-04A-R interim listing contract

The v1.1.0 production-shaped schema records specification key, physical form, source reference, unit and suitable catalog disposition. A separate validator checks exact approved-scope cardinality, supplier role and association bindings, product/key derivation, bijective planning maps, exact commercial values and strict Decimal strings. The prior schemas remain bound to historical evidence. Scope and Backend mapping are still pending. [Listing schema](../schemas/listing_stage.remediation.v1.schema.json) ? [Validator](../src/synthetic/listing_population_validation.py)
