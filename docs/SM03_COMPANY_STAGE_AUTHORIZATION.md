# SM-03 company-stage authorization

The authoritative SM-03 approval record is [company_identity.v1.json](../configs/synthetic/company_identity.v1.json). It binds approval to the exact existing SM-02 plan ID, configuration and content fingerprints, source identity, and all three artifact hashes and sizes. The SM-01 configuration remains byte-identical because it participates in the validated plan fingerprint.

| Decision | Recorded approval |
| --- | --- |
| SM-03.R1 | Exact SM-02 baseline and its demo geographic mapping. This does not confer legal business-location status. |
| SM-03.R2 | Population and entity-specific UUID v5 hierarchy, exact root `9e5fdfc5-2675-57fe-8e94-81dc91ed9639`, population `globiq-marketplace-baseline-001`, canonical role-neutral `identity-NNNNNN` keys and the persistent identity registry. |
| SM-03.R3 | Canonical AI/Data schema and separate Backend adapter boundary. Actual Backend compatibility remains pending. |
| SM-03.R4 | Deterministic context-aware profiles with seed 42 and deterministic monograms from the approved baseline templates. |
| SM-03.R5 | SM-03A fixture work and SM-03B company-only generation authorized. Each SM-03B run requires company-specific technical verification. Later stages and Backend import require separate authorization. |

The approval evidence is the SM-03B user attachment `d044fc1c-4991-452b-b6e4-e5d57192afd8`, sections 2, 7 and 20. The configuration records the company-only approval separately from the fixture approval fields.

## Stage-specific gates

The company gate requires reverified source and plan integrity, an approved exact root UUID and recorded approval reference, review of the canonical keys, valid canonical schema and configuration, passing fixture engine and validator checks, and verified artifact isolation. Backend field mappings and commercial price, stock, MOQ and quantity configurations remain dependencies for later stages. They do not gate isolated canonical company artifacts. The full marketplace guard remains effective independently.

Run `python -m src.synthetic.company_stage readiness` for status, `inspect-identifiers` for the namespace and identity settings, or `validate-config` for the internal schema version and hash. The `generate` command reruns the regression suite, input checks and independent source and plan validation before generating IDs. The command validates the serialized company bundle and checks a second independent build before publishing.

SM-04, SM-05, SM-06 and Backend import are unauthorized. The company-stage manifest declares the artifacts synthetic and intermediate, with both Backend import and full marketplace release flags set to false. It records approved provenance and validation, and its pointer is replaced only after artifact hashes are checked. [SM-03 readiness report](../reports/synthetic_company_readiness.json)
