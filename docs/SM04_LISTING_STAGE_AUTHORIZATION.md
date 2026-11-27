# SM-04 stage authorization

**Current commercial planning gate: `EXACT_SCOPE_APPROVAL_REQUIRED`.** The adaptive ceiling is approved, and the exact SM-04A-S proposal awaits review. SM-04B requires a later listing-only execution package. The SM-04A package below remains historical evidence and was never approved for execution. [SM-04A-S scope package](SM04A_MARKETPLACE_SCOPE_APPROVAL.md)

The user brief authorizes SM-04A and all seven Option D architecture decisions. The exact numerical configuration, plan, product and listing keys, canonical schemas, quality review and execution each require separate SM-04B approval. [Decision register](MARKETPLACE_DECISION_REGISTER.md) · [Authoritative proposal configuration](../configs/synthetic/commercial.v1.json)

Run `python -m src.synthetic.listing_stage readiness` for the exact package, its fingerprint and current blockers. The package binds the proposal to the commercial configuration file and semantic fingerprint, all canonical schema hashes, identifier policy fingerprint, resolved profiles and deterministic plan artifacts. Recorded approvals must cite the exact package fingerprint with a nonempty approval evidence reference. A stale or changed proposal invalidates such bindings. The review package is regenerated from verified artifact hashes.

SM-04B needs explicit authorization limited to the isolated 300 canonical product references, 1,000 canonical listings, persistent registry and planning mappings. Its publication must independently revalidate serialized values from the exact approved plan. The current execution stops at the planning and fixture boundary. Backend import requires a confirmed adapter contract and separate authorization. SM-05 and SM-06 remain blocked.

## Exact approval package for review

Package fingerprint `sha256:1ae2075cc7b6203557003416f49bef2f5f815fb05ed55dd0cdb9cab6b854bb91`

| Binding | Exact value |
| --- | --- |
| Plan identity | `sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d` |
| Commercial configuration v1.0.0 semantic fingerprint | `sha256:d4061563e261596d18094ddaeb4f02f5242786bbf7f9ee2d8bdadb315eb375d1` |
| Commercial configuration v1.0.0 file SHA-256 | `535310c23c23715e5d82c9b8b905227727710c4dce3c2576d9e92b4e7ebf6d2f` |
| Resolved profile fingerprint | `sha256:b9f74b75d4f2a04a014aecf92fc5440dff885b2c0c92bc087641fc8857506f8e` |
| Identifier policy fingerprint | `sha256:4d0c8f1db426cf95d8c24e3b6baecaf3975cf235cb8d50ada0a3b2f682df4c24` |
| Deterministic plan content fingerprint | `sha256:60b91020d135d199b53ec8ed8939f642ac00e1ab76b57417a659c6235b992b6e` |
| Solver implementation fingerprint | `sha256:a11b1fd8c7d1603f12cecb18f1b8238e9ba91209635c32c51ca9ca4b9097dcef` |

The proposed product key uses the `product` entity token and ordered tuple `["globiq-trade-reference-2024-v1","<normalized string code>"]`. The proposed listing key uses `listing` and ordered tuple `["<supplier UUID>","<canonical product UUID>","default"]`. Both use the approved population and UUID hierarchy. The isolated fixture product for `010600` is `cbfaeac3-71c0-52aa-b85c-d4c394cd026c`. The isolated fixture listing example is `fb51050e-3b24-59e2-adae-e5a094b16411` with display code `LST-000001`. [Encoding and registry rules](SYNTHETIC_LISTING_GENERATION.md)

| Schema | Version | SHA-256 |
| --- | --- | --- |
| [commercial_config.v1](../schemas/commercial_config.v1.schema.json) | 1.0.0 | `37e692dd7e1ce29e9f6a74d3c527c4be15ceb3adc539ff8ecfcfaf8937896243` |
| [commercial_plan.v1](../schemas/commercial_plan.v1.schema.json) | 1.0.0 | `1ae3096269f5d34647ba3337ab7376adcd8f32902d51ff0552cc8475f3107a2d` |
| [listing_stage.proposed](../schemas/listing_stage.proposed.schema.json) | 1.0.0 | `5c0c6cb62b43351503e021120a4b347edb0689425490b6873d087f247346784e` |

| Published artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| [commercial_feasibility_report.json](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/commercial_feasibility_report.json) | 972 | `8f481d804b77a77569f7367f35c17b6e39cc74cf9a1a2ef1f39babdb05613eb3` |
| [commercial_quality_report.json](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/commercial_quality_report.json) | 547,431 | `9d3ba2ed2dc082c76418bd7dc06ab603760fac21dbd2b8bc6c67b2abe974bd11` |
| [listing_commercial_plan.json](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/listing_commercial_plan.json) | 665,498 | `37ce8e0ce8bae0c536b0c2364a7fdb86738384d7754d72036e12521ad8538ca3` |
| [offer_commercial_plan.json](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/offer_commercial_plan.json) | 675,755 | `23ad64b8583055c6abc745c4fa8f4753acb612b6a8ab8e20d27db60e1f0ccffc` |
| [product_commercial_review.md](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/product_commercial_review.md) | 105,773 | `32433e528022b61e36dba6fc228338201ebb0ecb352d9063d0d0b25ed465e6b8` |
| [resolved_product_profiles.json](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/resolved_product_profiles.json) | 543,769 | `c2e6906b87aa6c64d3cff579361c44a8dc0e85c988a43fdadb6a6bcbe63d739c` |
| [rfq_commercial_plan.json](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/rfq_commercial_plan.json) | 448,045 | `0c5d3f98c8e6407ca6353e1a3344aa8d30ffc3fd07cd18c4b4d12d8d975ecf5e` |
| [Planning manifest](../data/planning/commercial_feasibility/commercial_plan_manifest.json) | 9,853 | `e49ff88b819e3a1234486258b0cd6d01ca4125ef52e9161f2a24bb40f6fbecd1` |

Both independent builds matched every listed content artifact. The manifest holds build-level hashes. The seven content artifacts total 2,987,243 bytes.

Review the 121 flagged product profiles, the demo unit assumptions, simulated price and stock bands, candidate coverage and MOQ boundary concentration. For concepts represented as undefined example items or packages, approve or replace the demo convention before approving the exact parameters. [300-product review table](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/product_commercial_review.md) ? [Commercial quality report](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/commercial_quality_report.json)

A future exact listing-generation package requires an approved marketplace scope, resolved commercial specifications, reviewed exact configuration, finalized identifiers and schemas, validated corrected feasibility, reproducibility, quality review, fixture/production validator readiness, and explicit listing-only authorization. No historic approval transfers.
