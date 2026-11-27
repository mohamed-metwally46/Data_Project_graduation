# SM-04A-S exact scope approval package

**The adaptive strategy is approved. The exact scope, product specifications, numerical configuration, and additional coverage effects await approval.** This is a planning-only proposal. It carries no permanent identifier or listing, RFQ, offer, import, or release authorization.

- Scope ID `sm04as-8f0ef371ba33b53d69293693a7127f897a11184ea9a71bf02ea7e7abba5cbf0d`
- Scope and specification review package `sha256:c2ba6877a9b8816c2ebf80ab509eae5de81f59c3dd53f54affc38d1670df1d75`
- Eligible product-set fingerprint `sha256:13ab2df07cc634ec162d6269828a44e33819fd2c89f938554bf40499a6df863a`
- Specification fingerprint `sha256:b900b4c01d63a8a9c20f09309ff92f2ad42d935c8caac60b1ce28462cfde07c1`
- Commercial configuration fingerprint `sha256:2c2b6438662b33e1aa65a7f705020d68043a96b5cb9d961d8ee7a28ba8a8c714`
- Coverage fingerprint `sha256:9f3312ff1cbe40d0019a39074a80191cce396dad6fad955009bcd012d8e52316`
- Implementation fingerprint `sha256:560599c4e295ae7645433a6b5865485177faa0cd92078f04c8c526aefbc00b79`

These fingerprints use compact UTF-8 JSON with insertion order and no BOM or newline. The package uses the existing varargs convention `fingerprint("sm04as-specification-and-scope-review-v1", package)`; both inputs appear in a JSON array. Upstream identities, schema and implementation files, artifact paths and hashes, and all code-membership hashes are bound in the published manifest.

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| [commercial.scope.proposed.v1.json](../data/planning/marketplace_scope/proposals/c2ba6877a9b8816c2ebf80ab509eae5de81f59c3dd53f54affc38d1670df1d75/commercial.scope.proposed.v1.json) | 942,391 | `0ee47c9bfe15c7433491f48059660a5e097bf40b63fbd0ac403a7e49f273c834` |
| [product_specification_review.json](../data/planning/marketplace_scope/proposals/c2ba6877a9b8816c2ebf80ab509eae5de81f59c3dd53f54affc38d1670df1d75/product_specification_review.json) | 272,142 | `5512185b74971747d2d875e48870629db9afb8837f6a682de42a4f6a0e981141` |
| [scope_coverage.json](../data/planning/marketplace_scope/proposals/c2ba6877a9b8816c2ebf80ab509eae5de81f59c3dd53f54affc38d1670df1d75/scope_coverage.json) | 24,531 | `0cc02cb2d5d45b7dad3ffb1e73d60ea5b248ce56655531c5b9913ae62ec39e8e` |
| [scope_projection.json](../data/planning/marketplace_scope/proposals/c2ba6877a9b8816c2ebf80ab509eae5de81f59c3dd53f54affc38d1670df1d75/scope_projection.json) | 1,255,040 | `0075d079c41eb1c2f5c4f8bdcda2750ffb78ad2a24748d31cb2073e9da7d1f8d` |

| Bound schema | Bytes | SHA-256 |
| --- | --- | --- |
| schemas/commercial.scope.proposed.v1.schema.json | 16156 | `3102deec9442a4ce871f75f6a6643c63719c129328004b646752c71348a653a4` |
| schemas/commercial_config.v1.schema.json | 11995 | `37e692dd7e1ce29e9f6a74d3c527c4be15ceb3adc539ff8ecfcfaf8937896243` |
| schemas/commercial_plan.v1.schema.json | 19408 | `1ae3096269f5d34647ba3337ab7376adcd8f32902d51ff0552cc8475f3107a2d` |
| schemas/commercial_remediation.v1.schema.json | 8763 | `368cadd2dfe43dabad78655c37067769a329a13db0fd08f75c8316380729fb2e` |
| schemas/listing_stage.remediation.v1.schema.json | 13483 | `6fbf41832a3ce92f39751b19ba3a6f00205116181aef0770e56710b36d0c5026` |
| schemas/marketplace_scope.v1.schema.json | 4928 | `4396d37ec586b76e4b6ad5fa6dca24ab78780c3455d59eec7b6b1cd37215e5e5` |

## Scope comparison

The last column measures the eight unresolved codes on their own historical rows. Companies and markets can overlap with the retained group and do not represent net losses.

| Metric | Historical | Restriction-only ceiling | Previously resolved | Proposed eligible | Remaining unresolved |
| --- | --- | --- | --- | --- | --- |
| products | 300 | 287 | 240 | 279 | 8 |
| companies | 500 | 500 | 499 | 500 | 47 |
| supplier companies | 300 | 300 | 300 | 300 | 32 |
| importer companies | 200 | 200 | 199 | 200 | 15 |
| supplier associations | 1200 | 1148 | 960 | 1116 | 32 |
| importer associations | 600 | 571 | 478 | 556 | 15 |
| listings | 1000 | 958 | 802 | 932 | 26 |
| active | 850 | 813 | 683 | 792 | 21 |
| out of stock | 100 | 97 | 80 | 96 | 1 |
| inactive | 50 | 48 | 39 | 44 | 4 |
| visible catalog | 950 | 910 | 763 | 888 | 22 |
| generally available | 850 | 813 | 683 | 792 | 21 |
| rfqs | 600 | 574 | 480 | 558 | 16 |
| open rfqs | 420 | 403 | 339 | 392 | 11 |
| targeted rfqs | 180 | 171 | 141 | 166 | 5 |
| competitive rfqs | 300 | 287 | 240 | 279 | 8 |
| offers | 900 | 858 | 712 | 835 | 23 |
| responding suppliers | 300 | 298 | 284 | 295 | 18 |
| unique directional relationships | 300 | 287 | 240 | 279 | 8 |
| supplier markets | 25 | 25 | 25 | 25 | 6 |
| importer markets | 75 | 75 | 75 | 75 | 8 |
| combined markets | 92 | 92 | 92 | 92 | 13 |
| active product coverage | 300 | 287 | 240 | 279 | 8 |
| rfq product coverage | 300 | 287 | 240 | 279 | 8 |
| active supplier coverage | 300 | 300 | 298 | 300 | 21 |
| listed supplier coverage | 300 | 300 | 300 | 300 | 26 |
| rfq importer coverage | 200 | 199 | 196 | 199 | 13 |
| RFQs with 0 responses | 120 | 116 | 99 | 113 | 3 |
| RFQs with 1 responses | 180 | 171 | 141 | 166 | 5 |
| RFQs with 2 responses | 180 | 174 | 149 | 168 | 6 |
| RFQs with 3 responses | 120 | 113 | 91 | 111 | 2 |
| category A records | 1080 | 1029 | 853 | 1001 | 28 |
| category B records | 0 | 0 | 0 | 0 | 0 |
| category C records | 0 | 0 | 0 | 0 | 0 |

The exact member sets below and the proposal configuration distinguish suitability, resolved specification, eligibility projection, and actual approval status.

- Included: 020230, 020329, 020721, 030342, 030343, 030349, 040120, 040690, 051191, 060299, 060310, 070200, 071022, 071290, 071320, 080410, 080710, 081340, 090111, 090121, 090210, 091099, 100590, 100890, 110290, 110311, 110710, 120740, 120991, 121190, 130212, 130219, 150990, 151490, 151590, 160100, 160239, 160250, 170199, 170490, 180631, 180632, 180690, 190230, 190490, 190530, 190590, 200410, 200899, 200990, 210390, 210420, 210690, 220190, 220210, 220290, 230400, 230910, 230990, 240110, 240310, 240391, 251020, 251611, 252329, 260111, 260300, 270900, 271000, 281820, 284020, 290511, 293390, 293490, 293629, 310210, 310520, 320890, 320990, 321490, 321590, 330210, 330300, 330499, 330590, 330741, 340119, 340211, 340220, 340290, 340399, 350610, 350691, 350699, 370790, 381400, 382000, 391910, 392020, 392330, 392350, 392690, 400829, 401010, 401099, 401693, 401699, 410229, 410422, 410431, 420221, 420222, 420229, 420292, 420299, 430310, 430390, 440391, 442090, 442190, 450410, 450490, 460210, 460290, 470710, 481820, 481840, 482110, 482190, 490110, 490199, 491000, 491110, 491199, 510710, 520100, 520842, 530720, 531010, 540249, 540794, 550320, 550810, 560790, 560900, 570190, 570232, 570500, 580610, 580632, 590390, 590610, 600299, 610442, 610729, 610910, 610990, 611030, 611090, 611592, 620343, 620433, 620442, 620462, 620530, 620630, 620690, 621050, 630140, 630231, 630293, 630631, 630900, 640299, 640319, 640340, 640399, 640411, 650590, 650610, 650700, 660110, 660199, 670419, 670490, 680293, 680911, 690790, 691190, 691200, 700910, 701110, 701399, 701910, 711319, 711590, 711620, 711790, 720230, 720249, 720449, 730410, 730630, 731815, 731816, 731822, 731824, 731829, 732690, 740721, 741220, 750300, 760120, 760200, 761510, 761690, 780199, 790790, 800700, 810890, 820551, 820559, 820600, 820740, 830150, 830241, 830260, 830790, 840991, 842123, 847193, 847199, 847330, 847990, 848190, 850434, 850940, 851110, 851829, 851830, 852520, 852810, 853400, 853650, 853690, 853710, 854441, 860729, 860900, 870120, 870332, 870421, 870810, 870892, 870899, 871690, 901590, 902130, 903140, 903289, 910221, 910229, 910299, 911410, 920210, 920290, 940330, 940350, 940360, 940540, 950390, 950490, 950691, 950699, 960321, 960390, 960910, 960990, 970110
- Offline only: 010600, 220429, 220890, 240220, 281410, 300220, 300239, 300490, 300660, 360690, 382100, 681310, 930400
- Excluded unresolved: 382390, 430130, 710239, 880330, 890400, 901890, 970500, 970600

## Coverage exceptions

The only importer without an RFQ remains `CMP-000043` (`IMP-SLOT-0043`), the restriction-only exception. Every company retains a portfolio, every supplier retains an active listing, all eligible products retain an active listing and an RFQ, and all supplier and importer markets are retained.

Compared with the restriction-only ceiling, the eight exclusions remove 26 listing allocations, 16 RFQs, 23 offers, 8 competitive scenarios and 3 distinct responding suppliers. These reductions require explicit acceptance with the exact scope. The 13 commercial groups represented after restriction are still represented.

## Workflow and verification

Run `python -m src.synthetic.sm04a_scope verify-proposal` to reverify the proposal. The `prepare-planning` command requires an explicit exact-package approval record, then verifies the bound projection and prepares shared-solver inputs. No such record exists for this checkpoint. The numerical adapter and independent commercial checks ran on an isolated fixture only.

After exact approval, execute two corrected provisional builds within the approved scope. Independently check every retained listing, RFQ, offer, quantity lattice, price envelope, allocation reference, observed relationship and original response count. Recompute competition, candidate compatibility, unanswered scenarios, diversity, and price/quantity boundaries using corrected scope denominators. Publish corrected planning evidence separately. Production listing authorization remains its own checkpoint.

AI & Data should use the scope and specification bindings before constructing candidate inputs. Backend contracts should enforce suitability, exact source identity, unit and specification; Backend mapping remains pending. Frontend display should present the synthetic item, form, saleable basis, currency and unit and omit offline and unresolved profiles. QA should retain original evidence and distinguish scope validation, isolated fixture execution and corrected full-plan validation.

[Scope manifest](../data/planning/marketplace_scope/scope_manifest.json) · [Run evidence](../reports/sm04a_scope_resolution_report.json) · [Product decision package](SM04A_PRODUCT_SPECIFICATION_REVIEW.md)

## Proposed exact approval

> I approve scope and specification package sha256:c2ba6877a9b8816c2ebf80ab509eae5de81f59c3dd53f54affc38d1670df1d75 for 279 products, 932 retained listings, 558 retained RFQs, and 835 retained offers, and the exact configuration sha256:2c2b6438662b33e1aa65a7f705020d68043a96b5cb9d961d8ee7a28ba8a8c714. I accept the eight unresolved product exclusions and the resulting reduction of 8 competitive scenarios and 3 distinct responding suppliers from the restriction-only ceiling, along with the already accepted RFQ coverage exception for CMP-000043. I authorize corrected provisional commercial feasibility planning only.
