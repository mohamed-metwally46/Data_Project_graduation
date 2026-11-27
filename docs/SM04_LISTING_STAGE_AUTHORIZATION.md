# SM-04 stage authorization

**Corrected provisional planning is validated. SM-04B awaits explicit listing-only execution approval.** The historical SM-04A package below remains preserved. The current package is documented at the end of this file. [Corrected planning manifest](../data/planning/commercial_feasibility/corrected_plan_manifest.json)

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

## Current exact SM-04B review package

- Exact listing-only review package fingerprint `sha256:35fea3b4bab5c4b1b7b63618dde85b2a9e19495a76ea0eed172c6d4c601df5ef`
- Corrected commercial plan `sm04ac-c0a3f73dd4605fc700801412dcd8fe2d9ccc3e1280e21d7349725f0c96942b67`
- Deterministic content fingerprint `sha256:c0a3f73dd4605fc700801412dcd8fe2d9ccc3e1280e21d7349725f0c96942b67`
- Approved scope package `sha256:c2ba6877a9b8816c2ebf80ab509eae5de81f59c3dd53f54affc38d1670df1d75`
- Approved commercial configuration `sha256:2c2b6438662b33e1aa65a7f705020d68043a96b5cb9d961d8ee7a28ba8a8c714`
- Corrected implementation fingerprint `sha256:85bd599db2b75953ba7389cff1c3ffda4195b257cba421e8c5b5a2641c0b29dc`
- Identifier policy fingerprint `sha256:4d0c8f1db426cf95d8c24e3b6baecaf3975cf235cb8d50ada0a3b2f682df4c24`

The canonical package is embedded in the corrected planning manifest. Its digest uses the existing compact UTF-8 JSON varargs procedure with the domain `sm04b-exact-listing-review-v1`. Both independent full builds matched every deterministic artifact below. The package binds the full validation, two build hash maps, corrected quality findings and accepted coverage exceptions.

| Corrected planning artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| [commercial_feasibility_report.json](../data/planning/commercial_feasibility/corrected_plans/sm04ac-c0a3f73dd4605fc700801412dcd8fe2d9ccc3e1280e21d7349725f0c96942b67/commercial_feasibility_report.json) | 1,872 | `ace5e73cb44d6d75c3e82836b75bea80d86d79f841ab25b1ab674ebc46cc99db` |
| [commercial_quality_report.json](../data/planning/commercial_feasibility/corrected_plans/sm04ac-c0a3f73dd4605fc700801412dcd8fe2d9ccc3e1280e21d7349725f0c96942b67/commercial_quality_report.json) | 519,835 | `eaf44ef73aeb6fe466812fd4f2d73ce622ed299969cbc86f2b6ee55441e5a9c7` |
| [listing_commercial_plan.json](../data/planning/commercial_feasibility/corrected_plans/sm04ac-c0a3f73dd4605fc700801412dcd8fe2d9ccc3e1280e21d7349725f0c96942b67/listing_commercial_plan.json) | 719,638 | `97174192aa5ab6cd754fc9ff4047800572288d5b25e0f73d9c831672875f4881` |
| [offer_commercial_plan.json](../data/planning/commercial_feasibility/corrected_plans/sm04ac-c0a3f73dd4605fc700801412dcd8fe2d9ccc3e1280e21d7349725f0c96942b67/offer_commercial_plan.json) | 715,890 | `7432ad8486802b2839c0bd341fe191934ff2ca6f7e4e756cc14368ecc58a752c` |
| [resolved_product_profiles.json](../data/planning/commercial_feasibility/corrected_plans/sm04ac-c0a3f73dd4605fc700801412dcd8fe2d9ccc3e1280e21d7349725f0c96942b67/resolved_product_profiles.json) | 821,160 | `afeb221b1b186678e0efa002feccc8e7540de36c84745a44b9d7419ee1e41629` |
| [rfq_commercial_plan.json](../data/planning/commercial_feasibility/corrected_plans/sm04ac-c0a3f73dd4605fc700801412dcd8fe2d9ccc3e1280e21d7349725f0c96942b67/rfq_commercial_plan.json) | 479,493 | `7bdb3fabbc8451acea57770221c81dca0952447911055bd5d0e6ad00968c7de5` |

| Bound schema | SHA-256 |
| --- | --- |
| [schemas/commercial.scope.proposed.v1.schema.json](../schemas/commercial.scope.proposed.v1.schema.json) | `3102deec9442a4ce871f75f6a6643c63719c129328004b646752c71348a653a4` |
| [schemas/commercial_config.v1.schema.json](../schemas/commercial_config.v1.schema.json) | `37e692dd7e1ce29e9f6a74d3c527c4be15ceb3adc539ff8ecfcfaf8937896243` |
| [schemas/commercial_plan.v1.schema.json](../schemas/commercial_plan.v1.schema.json) | `1ae3096269f5d34647ba3337ab7376adcd8f32902d51ff0552cc8475f3107a2d` |
| [schemas/commercial_remediation.v1.schema.json](../schemas/commercial_remediation.v1.schema.json) | `368cadd2dfe43dabad78655c37067769a329a13db0fd08f75c8316380729fb2e` |
| [schemas/listing_stage.remediation.v1.schema.json](../schemas/listing_stage.remediation.v1.schema.json) | `6fbf41832a3ce92f39751b19ba3a6f00205116181aef0770e56710b36d0c5026` |
| [schemas/marketplace_scope.v1.schema.json](../schemas/marketplace_scope.v1.schema.json) | `4396d37ec586b76e4b6ad5fa6dca24ab78780c3455d59eec7b6b1cd37215e5e5` |
| [schemas/commercial_plan.corrected.v1.schema.json](../schemas/commercial_plan.corrected.v1.schema.json) | `e86ea661956681e67636b833174d95f91b48d470e29033b5ec8a168a16a2aec8` |

Product identities use the `product` entity token and logical key `["globiq-trade-reference-2024-v1","<normalized source code>"]`. Listing identities use `listing` and `["<supplier UUID>","<product UUID>","default"]`. Both use `hierarchical_uuid5_v1` under the approved root and population. Listing display identifiers use `LST-NNNNNN` and preserve registry reservations. The package includes the exact policies and fixture examples. Permanent product and listing UUID derivation has not run.

The future isolated population target is 279 canonical product references and 932 listings, registry entries and mappings. The listing split remains 792 active, 96 out of stock and 44 inactive. After explicit listing-only authorization, verify exact package bindings, implement the authorized population path, validate every production-shaped serialized record, reconcile all mappings and registry entries, independently reproduce the full listing stage, and publish only to the isolated listing pointer. Backend compatibility remains unconfirmed.

> I approve SM-04B package `sha256:35fea3b4bab5c4b1b7b63618dde85b2a9e19495a76ea0eed172c6d4c601df5ef` and authorize only the isolated population of 279 canonical product references and 932 canonical listings, including their permanent product and listing UUIDs, persistent listing registry and planning-to-listing mappings, with 792 active, 96 out of stock, and 44 inactive listings. Authorization covers exact reuse of the bound plan and schemas, independent validation, reproducibility verification, and isolated listing-stage publication. RFQ and offer generation, Backend import, and full marketplace publication remain blocked.

[Corrected planning manifest](../data/planning/commercial_feasibility/corrected_plan_manifest.json) · [Run evidence](../reports/sm04a_corrected_commercial_readiness.json)
