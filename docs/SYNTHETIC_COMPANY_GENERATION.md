# SM-03 synthetic company foundation

## Status and inputs

SM-03B uses the SM-03A company identity, role, portfolio and validation tooling under the approved permanent root. The configuration records the five strategy decisions, exact canonical key approval and company-only authorization. The fixture path uses a distinct UUID root. The full marketplace guard applies independently. [Stage authorization](SM03_COMPANY_STAGE_AUTHORIZATION.md)

The source is the pinned 2024 Trade Intelligence release. The only allocation input for this stage is the SM-02 manifest and its serialized witness. The inspection command checks source and artifact hashes, plan version and identity, configuration/content fingerprints, provisional flags, canonical region labels and recorded counts. The full SM-02 validator independently checks the evidence from the existing source. The earlier Africa region correction is present in the supplementary geography snapshot and the Trade Intelligence source digests still match.

```powershell
python -m src.synthetic.planning validate
python -m src.synthetic.company_stage inspect-inputs
python -m src.synthetic.company_stage readiness
python -m src.synthetic.company_stage inspect-identifiers
python -m src.synthetic.company_stage validate-config
python -m unittest discover -s tests -v
python -m src.synthetic.company_stage generate
```

## Identity model

The [template configuration](../configs/synthetic/company_identity.v1.json) contains 144 fictional brand components and 20 role-compatible descriptors. The context builder reads the slot's market label, source product codes, reference descriptions and provisional grouping from the existing plan. Mixed prefix groups use diversified trading. A coherently mapped group can use a specialist presentation category. Unresolved specialization uses general trading. Role-compatible business types use controlled codes. English-first descriptions carry a language tag, explicit fictional labeling and contextual geography and portfolio focus. Name and description limits are 100 and 400 characters.

Collision checks normalize names and brands using Unicode NFKC, case folding and alphanumeric characters. The builder rejects exact normalized brand matches and brand variants within one insertion, deletion or substitution. Candidate combinations and collision retries are deterministic in stable slot order. Exhaustion raises an error. The quality report also checks normalized full names within one edit. The checks cover the generated cohort. Legal and trademark clearance is outside this synthetic identity process.

The approved identity seed is 42. Named streams select brand candidates, descriptors, business types, descriptions and monogram palettes independently. Monogram initials come from the first two words of the company name. The palette is a configurable key for later Frontend mapping. The registry retains reserved names and keys during expansion. The UUID hierarchy excludes mutable names, descriptions and roles. [Identifier policy](MARKETPLACE_IDENTIFIER_POLICY.md)

## Contacts and scope

Companies use `sales@cmp-######.example`. Websites, phone numbers, street addresses, tax identifiers and registration numbers are null in the approved population. Verification is `not_verified` and `is_synthetic` is true. Schema and independent checks reject malformed or operational contacts, unsupported claims and additional transport fields.

A future Backend and Frontend must enforce demo isolation at tenant, search, workflow and outbound service boundaries. Block communications, orders, verification and production exports involving synthetic identities. The display must explain that profiles are fictional. A synthetic flag is only one input to those protections.

## Contract and validation

The [canonical intermediate schema v1.0.0](../schemas/company_stage.proposed.schema.json) separates companies, roles, portfolios, slot mappings and the identity registry. It specifies isolated fixture and intermediate formats. Source product strings and market keys remain intact. The Backend mapping is a separate pending contract. The older .invalid contact representation in the bundle awaits reconciliation with the .example canonical company-stage policy.

The independent validator checks schema shape and UUID version, unique names and identifiers, one-to-one slot mapping, exact market and role preservation, observed product-role evidence, and correspondence with the original portfolio. It resolves supplier and importer mappings for listing, RFQ and offer references, including targeted RFQ suppliers. A fixture write validates before atomic replacement. The full SM-02 witness remains read-only and is not passed to the fixture generator. The fixture entry point requires a fixture marker, fixture IDs, a separate namespace and at most 12 slots.

SM-03B runs the full regression suite and independent source and allocation checks before instantiating the approved slots. It serializes two full builds, checks byte equality, and independently validates the serialized bundle. The isolated company pointer references a content-addressed directory containing the bundle and quality report. Publication checks their hashes before replacing the pointer. The manifest records hashes, counts, approvals and reproducibility separately from operational timings and memory measurements. [Readiness and run measurements](../reports/synthetic_company_readiness.json)

## Verified results and measurements

SM-03B passed every company-stage gate. Independent read-only checks verified the pinned 2024 release, SM-02 allocation and all three approved artifact hashes and sizes. The allocation preserved 300 selected products and 1,080 Category A bilateral records across 300 unique relationships, with zero B or C records. RFQ counts for zero, one, two and three planned offers were 120, 180, 180 and 120.

The independently validated bundle contains 300 supplier-only companies in 25 markets and 200 importer-only companies in 75 markets. Each supplier retained four assigned products and each importer retained three. All 1,800 role and product links had observed trade evidence. There are 500 unique UUID v5 company IDs, 500 persistent keys, 500 display codes, 500 normalized names, 500 registry entries and 500 one-to-one slot mappings. The mappings resolve all 1,000 listings, 600 importing RFQ slots, 180 targeted RFQ suppliers and 900 offer suppliers in the plan. The 44-test regression suite passed.

The published stage is `sm03b-68a129e0877cc0b7405db11375d2ef72ee862b7545075bd36c06099fa8e42363`. Both complete builds produced the same 2,219,027-byte canonical bundle, including metadata and all five collections. The manifest records both build hashes and each collection fingerprint. The quality report contains results for every market and includes fictional examples from the portfolios present. The population has 497 diversified and three general trading profiles. The approved presentations yield zero specialist profiles. The 500 names use 73 configured brand stems and had zero whole-name warnings within one normalized edit. There are 176 distinct descriptions, ranging from 91 to 141 characters with a mean of 113.1. All companies use reserved contacts and have monograms.

| Measured operation | Seconds |
| --- | ---: |
| Full pinned source verification | 194.575 |
| Source engine initialization and geographic and product profiling | 51.261 |
| Independent verification of the approved allocation | 0.532 |
| First build, including registry | 1.990 |
| Registry work within the first build | 0.121 |
| Both bundle serialization writes | 0.399 |
| Rebuild and byte comparison | 2.055 |
| Independent serialized population validation | 4.942 |
| Company-stage publication | 0.030 |
| Elapsed time through publication, including the regression suite | 286.874 |

The Windows process peak working set was 822,054,912 bytes, approximately 784 MiB. The measurement excludes the regression-suite child process.

- [Stage manifest](../data/synthetic/stages/companies/company_stage_manifest.json)
- [Population quality report](../data/synthetic/stages/companies/populations/sm03b-68a129e0877cc0b7405db11375d2ef72ee862b7545075bd36c06099fa8e42363/company_validation_report.json)
- [Readiness and operational measurements](../reports/synthetic_company_readiness.json)
- [SM-04 handoff](SM04_LISTING_GENERATION_HANDOFF.md)

The canonical schema SHA-256 is `f37213461ede31e9ab233a2727716706173afdb5e2d61f679b08feaa79406417`. In the earlier SM-03A run, 42 tests passed and ten three-company fixture builds produced identical 10,029-byte payloads. Median generation, independent validation and serialization took 8.94 ms, 96.72 ms and 0.20 ms respectively. Peak working set was 49.6 MB including input inspection.
