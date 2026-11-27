# Marketplace identifiers and deterministic execution

## Approved company-stage identifiers

The approved root for the company stage is `9e5fdfc5-2675-57fe-8e94-81dc91ed9639`, derived as UUID v5 from NAMESPACE_URL and `urn:globiq:synthetic-marketplace:1`. The authorized population key is `globiq-marketplace-baseline-001`. [Identifier utility](../src/synthetic/determinism.py) · [Approval record](SM03_COMPANY_STAGE_AUTHORIZATION.md)

The approved `hierarchical_uuid5_v1` encodes names as compact UTF-8 JSON with NFC text.

1. Population namespace is UUID v5 under the root over `["globiq-population-v1","globiq-marketplace-baseline-001"]`.
2. Entity namespace is UUID v5 under the population namespace over `["globiq-entity-v1",entity]`. The supported entity types are `company`, `company_role`, and `company_product`.
3. External ID is UUID v5 under the entity namespace over `["globiq-marketplace-key-v1",entity,[ordered logical keys]]`.

Population keys are lowercase ASCII, start with a letter, and contain letters, digits or hyphens. Company keys use `identity-NNNNNN` with a nonzero six-digit ordinal. Role keys use a lowercase company UUID v5 followed by the role code. Association keys use a lowercase role UUID v5 followed by the verbatim normalized text product code. JSON types and separators remain stable.

| Entity | Stable key fields |
| --- | --- |
| Market reference | Source market key and source market namespace |
| Product | Source code and explicit source classification namespace |
| Company | Stable demo cohort and opaque role-neutral identity slot key |
| Company role | Company external ID and role code |
| Product association | Role external ID and normalized source product code for the company stage |
| Listing | Supplier association external ID and stable variant slot if approved |
| RFQ | Importer association external ID and scenario slot |
| Offer | RFQ external ID and supplier role external ID for the one-current-offer model |

A baseline company receives its role-neutral key and `CMP-NNNNNN` display code in sorted original planning-slot order. The independent validator checks both assignments, key uniqueness and UUID uniqueness. Changing identity semantics requires a documented version or namespace migration with Backend agreement. The Backend mapping between external and internal identifiers awaits confirmation. Other entity keys in the table remain proposals.

SM-03A uses a separate fixture UUID root. The company stage registry stores population, original plan and slot, neutral key, UUID, display code, reserved name and brand, and identity status. Keep retired keys and display codes reserved. A revised allocation requires explicit continuity reconciliation against the published registry. A replacement business receives a new key. A retained company's UUID depends on the approved namespace, population and persistent key, so it survives edits to names, descriptions and roles.

Display codes are for presentation. Foreign keys use external IDs. The transport keeps source market and product identifiers in distinct fields. Display-code prefixes for other entities remain proposals.

## Named random streams

Derive each random stream as SHA-256 over compact UTF-8 JSON containing the domain tag globiq-marketplace-rng-v1, an approved integer master seed, and the ordered NFC stream labels. Seed a private Python random.Random instance with the digest interpreted as a big-endian integer. A call with the same named path restarts that stream, so a caller should keep the instance for a sequence or derive per-item paths. Work in one stream cannot advance another.

SM-03B uses master seed 42. Reproduction depends on the implementation, Python runtime and dependencies, source release, policy version, approved configuration and deterministic visitation order. Treat differences in random API behavior across Python versions as a release compatibility issue.

## SM-04 proposed identifiers

The approved namespace architecture extends to proposed `product` and `listing` entity tokens. Product keys scope the verbatim normalized source product code to `globiq-trade-reference-2024-v1`. Listing keys use the supplier UUID, canonical product UUID and variant, initially `default`. These exact encodings and display-code and registry rules require SM-04B review. Fixture UUIDs use an isolated namespace. [Exact proposal and fixture workflow](SYNTHETIC_LISTING_GENERATION.md)

## SM-04A-R identity enforcement

Shared product keys accept the fixed source context and an exact six-digit ASCII source code or `9999AA`. Shared listing keys accept two lowercase RFC-variant UUID v5 strings and the `default` variant for this baseline. The supported application path accepts only the isolated listing fixture namespace today. The older SM-01 generic probe in the standard URL namespace retains its typed demo inputs. That namespace is outside the marketplace hierarchy.

The former fixture UUIDs, company namespace and every persisted company, role and portfolio ID reconcile against the hardened implementation. Material changes to physical form or the saleable unit require identity review. Within a plan, retired reservations survive and new display codes append beyond reserved ordinals. Cross-plan reuse and reactivation require a separate authorized migration. [Remediation evidence](../reports/sm04a_remediation_report.json)
