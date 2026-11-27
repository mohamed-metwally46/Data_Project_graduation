# SM-04A joint commercial feasibility

The planner consumes the exact Trade Intelligence release, original SM-02 allocation and published SM-03B company stage. It reuses the read-only release verifier, the independent structural validator, the existing company-stage validator and the relationship query engine. The allocation fixes all supplier, importer, product, status and offer edges. Only synthetic prices and quantities are assigned.

Each product has listing nodes, request nodes and original offer edges. First intersect the RFQ product range with each responding listing's possible order range and find common lattice ticks, using the least common multiple of zero-origin increments. Then propagate every linked request's quantity to its listing. The largest linked request determines required stock capacity, while the smallest limits MOQ. A shared listing is evaluated independently in each request. There is no stock reservation or deduction. A targeted request with no planned response retains its target and may be incompatible.

One product-aware target price is sampled for every RFQ. Targets are indicative and hard budgets are disabled. For a linked listing, the selected quote must admit a positive representable offer quote within the intersection of its variation and product bounds. If the first deterministic candidate fails, the planner scans the finite listing-quote domain in cyclic order, with a limit of 2,048 candidates per listing. Exhausting a finite domain proves the price conflict. Reaching the bound reports a search limit. Quantity feasibility for the baseline monotone bounds uses direct exact interval propagation.

SM-04A produces proposal values keyed by the original anonymous allocation IDs. Artifacts carry synthetic and planning-only flags. See validation, observed-evidence reconciliation, full quality diagnostics and reproducibility by following the planning manifest and readiness report. [Planning manifest](../data/planning/commercial_feasibility/commercial_plan_manifest.json) · [Readiness and measured timings](../reports/synthetic_commercial_readiness.json)

## Full-data execution

The pinned 2024 release, 94 provisional code-prefix groups, 187 eligible market candidates, exact SM-02 artifacts and immutable SM-03B bundle and report passed read-only verification. The existing SM-03B pointer also matched its reported SHA-256. The company validator independently checked its registry, portfolios and downstream references.

The proposal resolves all 300 products, 1,000 listings, 600 RFQ scenarios and 900 responses. All 900 responses can meet the full individual request. Zero responses were infeasible or unresolved. The validation preserved 850 active, 100 out-of-stock and 50 inactive listings. Inactive stock split 25 zero and 25 positive. All 420 open and 180 targeted requests retain the original response allocations, with 120 / 180 / 180 / 120 requests for counts zero through three. All 300 competitive scenarios, 1,080 Category A records and 300 distinct directional product relationships were preserved. The validator found zero Category B or C records.

| Stage | Seconds |
| --- | ---: |
| Full pinned source verification | 142.5949 |
| Read-only source engine initialization | 48.3144 |
| SM-02 hashes, loading and independent validation | 0.5225 |
| Serialized SM-03B independent verification | 4.3963 |
| Catalog inspection | 0.0001 |
| Profile resolution | 0.2204 |
| Graph construction | 0.0473 |
| Quantity solving | 0.2903 |
| Price solving | 0.8760 |
| Independent serialized validation per first build | 3.8452 |
| First-build serialization | 0.4840 |
| Quality diagnostics | 0.3279 |
| Second build and comparison | 6.9476 |
| Planning pointer publication | 0.0584 |
| Regression suite | 51.8192 |
| Full execution | 263.6947 |

The fallback ran zero search nodes. Peak process working set was 825,004,032 bytes, about 787 MiB. The 55-test suite passed, including the original 44 tests.

[Independent results](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/commercial_feasibility_report.json) ? [Run evidence](../reports/synthetic_commercial_readiness.json)

## SM-04A-R restriction impact and scope decision

The historical plan remains immutable evidence. The restriction-only projection excludes the 13 offline-only products and all their related allocations. It is the upper bound before the remaining product reviews, and it does not authorize any commercial plan. The offline company and market counts describe overlap with the historical plan and are not net losses.

| Measure | Historical | Offline affected/excluded | Remaining after restrictions only |
| --- | --- | --- | --- |
| Products | 300 | 13 | 287 |
| Distinct companies touched or retained | 500 | 76 | 500 |
| Supplier companies | 300 | 48 | 300 |
| Importer companies | 200 | 28 | 200 |
| Supplier associations | 1200 | 52 | 1148 |
| Importer associations | 600 | 29 | 571 |
| Listings | 1000 | 42 | 958 |
| Active listings | 850 | 37 | 813 |
| Out-of-stock listings | 100 | 3 | 97 |
| Inactive listings | 50 | 2 | 48 |
| Visible catalog listings | 950 | 40 | 910 |
| Generally available listings | 850 | 37 | 813 |
| RFQs | 600 | 26 | 574 |
| Open RFQs | 420 | 17 | 403 |
| Targeted RFQs | 180 | 9 | 171 |
| Allocated offers | 900 | 42 | 858 |
| Competitive RFQs | 300 | 13 | 287 |
| Category A records | 1080 | 51 | 1029 |
| Distinct directional product relationships | 300 | 13 | 287 |
| Active product coverage | 300 | 13 | 287 |
| Listed supplier coverage | 300 | 39 | 300 |
| Active supplier coverage | 300 | 35 | 300 |
| RFQ importer coverage | 200 | 24 | 199 |
| Combined market coverage | 92 | 22 | 92 |
| RFQs with 0 responses | 120 | 4 | 116 |
| RFQs with 1 responses | 180 | 9 | 171 |
| RFQs with 2 responses | 180 | 6 | 174 |
| RFQs with 3 responses | 120 | 7 | 113 |
| Supplier markets | 25 | 10 | 25 |
| Importer markets | 75 | 12 | 75 |
| Commercial groups | 15 | 7 | 13 |

No supplier or importer loses its entire eligible portfolio to the 13 restrictions. Of the affected companies, four suppliers and one importer hold more than one restricted association. After filtering, all 300 suppliers retain active catalog coverage and 199 of 200 importers retain RFQ coverage. The four medical-pack profiles and sole catalog-only group leave the earlier grouping coverage. See the machine report for exact group counts and the additional 47-product review hold.

### Per-product historical impact

All rows have the approved restricted_offline_qa disposition, with no explicit dedicated suitability flag in the original plan. Exact original review-note text is in the evidence JSON. The table contains historical scope counts and source labels.

| Source code | Source description | Original group | Supplier associations / distinct suppliers | Importer associations / distinct importers | Active / OOS / inactive | Open / targeted RFQs | Offers | Category A | Unique directional links |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 010600 | Animals: live, n.e.s. in chapter 1 | living_items | 4/4 | 2/2 | 3/1/0 | 1/1 | 4 | 5 | 1 |
| 220429 | Wine: still, in containers holding more than 2 litres | liquid_goods | 4/4 | 2/2 | 3/1/0 | 1/1 | 4 | 5 | 1 |
| 220890 | Spirits, liqueurs and other spirituous beverages: n.e.s. in heading no. 2208 | liquid_goods | 4/4 | 2/2 | 3/0/1 | 1/1 | 3 | 4 | 1 |
| 240220 | Cigarettes: containing tobacco | small_articles | 4/4 | 3/3 | 3/0/0 | 2/0 | 3 | 3 | 1 |
| 281410 | Ammonia: anhydrous | industrial_bulk | 4/4 | 2/2 | 3/0/0 | 1/1 | 4 | 5 | 1 |
| 300220 | Vaccines: for human medicine | medical_packs | 4/4 | 2/2 | 2/0/1 | 2/0 | 2 | 2 | 1 |
| 300239 | Vaccines: for veterinary medicine, for other uses than against foot and mouth disease | medical_packs | 4/4 | 2/2 | 3/0/0 | 1/1 | 3 | 4 | 1 |
| 300490 | Medicaments: consisting of mixed or unmixed products n.e.s. in heading no. 3004, for therapeutic or prophylactic uses, packaged for retail sale | medical_packs | 4/4 | 3/3 | 3/0/0 | 1/1 | 3 | 4 | 1 |
| 300660 | Pharmaceutical goods: chemical contraceptive preparations based on hormones or spermicides | medical_packs | 4/4 | 2/2 | 3/0/0 | 1/1 | 3 | 4 | 1 |
| 360690 | Ferro-cerium and other pyrophoric alloys in all forms: articles of combustible materials n.e.s. in chapter 36 | industrial_bulk | 4/4 | 2/2 | 3/0/0 | 1/1 | 4 | 5 | 1 |
| 382100 | Culture media, prepared: for development of micro-organisms | industrial_bulk | 4/4 | 3/3 | 3/0/0 | 2/0 | 3 | 3 | 1 |
| 681310 | Brake linings and pads: with a basis of asbestos, of other mineral substances or of cellulose | vehicle_parts | 4/4 | 2/2 | 3/0/0 | 1/1 | 4 | 5 | 1 |
| 930400 | Firearms: (eg spring, air or gas guns and pistols, truncheons), excluding those of heading no. 9307 | catalog_only_articles | 4/4 | 2/2 | 2/1/0 | 2/0 | 2 | 2 | 1 |

### Decision and revalidation boundary

The approved public counts cannot be preserved by a suitability filter. The recommended option is a separately approved reduced scope, preserving the current evidence and company portfolios. Another option is a separately approved replacement strategy and new structural allocation; replacement products may require compatible portfolio revisions. No replacement or upstream revision is authorized today.

The restriction-only projection has 1,237 compatible historical pairs, 858 originally allocated replies, 379 compatible nonresponding pairs and 282 structurally eligible incompatible pairs. Those figures reuse historical commercial values and explicitly exclude restricted products. After the 47 still-unresolved specifications and four unit changes are also withheld from numerical comparison, the unchanged-unit historical projection contains 1,019 compatible pairs for 236 codes. Neither projection constitutes corrected feasibility. The new report contains changed denominators and boundary diagnostics.

The supported production-shaped validator checked two independent isolated fixture bundles with 300 products and 1,000 listings each. Both serialized to 2,721,196 bytes with SHA-256 `715132c02a978d3225dd8af69e2c62ae94777ad548520139e9f0189853f5720b`. Both passed independent validation. The full repository suite passed all 66 tests. Corrected full-plan builds total zero.

[Exact impact, implementation bindings and run evidence](../reports/sm04a_remediation_report.json)

## SM-04A-S scope projection

The scope comparison now includes the final 279-product proposal, its original allocation references and the eight excluded unresolved codes. All 500 companies retain eligible portfolio associations, and the proposed scope preserves active listings for all 300 suppliers. The isolated scope-aware numerical fixture exercises the planning interface. The published scope evidence contains zero corrected full-plan builds. [Full comparison and review package](SM04A_MARKETPLACE_SCOPE_APPROVAL.md)
