# Workstream E analytical handoff

The validated Trade Intelligence release is ready as a descriptive input to future marketplace generation. Generation policies and Backend contracts still require approval. This handoff does not create marketplace entities.

## Verify and pin a release

1. Run python -m src.analytics.release validate against the intended processed workspace.
2. Read the manifest status and record its release ID, dataset fingerprint, methodology version, and relevant schema versions in any later generation configuration or output provenance.
3. Read analytics from the manifest's recorded artifact directory and verify their SHA-256 hashes. To use Route or Market Relationship Intelligence queries, verify the SQLite input hash and match the initialized engine's dataset version to the manifest. Recheck if inputs or the published release change.
4. Keep original reference fields and observed evidence distinguishable in any downstream export.

## Use the artifacts with explicit policy

| Downstream decision | Input and guardrail |
| --- | --- |
| Product selection | Product Intelligence supplies normalized codes, descriptions, reference status and observed breadth. Reference descriptions are real source information. The selected demo catalog is a policy choice. |
| Geographic selection | Country Intelligence provides observed roles, partner breadth and product diversity. Country keys include trade areas and historical entities, so decide allowed entities before generating companies. |
| Supplier and importer product associations | Use observed product roles and full counts from the Market Relationship summary and filtered queries. An observed role is evidence of activity in this source, without verified company identity or capacity. |
| Directional supplier-buyer contexts | Use Route Intelligence and complete composition queries for observed pairs. Use category A for observed product links if approved. Categories B and C are compatibility scenarios and require an explicit choice before simulated use. |
| Diversity and validation | Apply approved product and geographic quotas independently of source frequency. Validate IDs, roles, selected categories and directional policy against the pinned release. Retain the evidence category or rule that motivated each synthetic association. |

Any later company, contact, listing, price, offered quantity, offer, RFQ or simulated transaction is fictional. Keep observation and reference provenance separate from synthetic data flags. Counts and categories carry no claims about buyer intent, supplier capacity, price, demand, or viability.

## Decisions needed before marketplace generation

SM-01 recorded the approved strategy and fixed targets. See the
[decision register](MARKETPLACE_DECISION_REGISTER.md) for the numerical
parameters and Backend mappings still pending.

- Product inclusion and diversity policy.
- Geographic coverage and eligible market types.
- Supplier/importer role counts, overlap policy and assignment strategy.
- Whether and how categories A, B and C can influence simulated relationships.
- Independent synthetic price, quantity and unit assumptions, including label and validation rules.
- Backend schemas, IDs, constraints and handoff format.

The 2024 extract reached Excel's worksheet cap. Global coverage, value currency and scale, quantity units, and HS revision remain unverified. Use the source as one input to scenario selection and record any approved synthetic assumptions.
