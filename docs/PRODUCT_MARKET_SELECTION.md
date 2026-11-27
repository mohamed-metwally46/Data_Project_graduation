# SM-02 product and market selection

## Source and geographic eligibility

SM-02 reads the pinned 2024 Trade Intelligence manifest through the SM-01 read-only verifier. It uses the normalized codes, reference descriptions, full product-role lists and actual directional evidence from the existing engine. It leaves the validated release and its source artifacts untouched.

The [M49 snapshot](../configs/synthetic/m49_reference.json) matches the source numeric market identity and ISO labels, with a documented India code crosswalk. The planner keeps the original trade market key for all evidence joins. The geography rules hold territories and separately represented areas, historical entities, statistical areas and special trade codes outside the baseline. This includes custom reporting areas whose trade boundary may extend beyond a single business location. Unmatched or conflicting geographic references remain unresolved and ineligible. M49 regions support a diversity tie-break. An M49 match is a provisional geographic candidate and establishes no business registration, legal eligibility or Backend mapping. Source ISO nulls stay null. The trade release's already verified Namibia ISO2 is retained. [UN M49 overview](https://unstats.un.org/unsd/methodology/m49/overview) · [UN Comtrade custom reporting areas](https://uncomtrade.org/docs/reporter-country-codes-and-their-custom-areas/) · [UN Comtrade statistical areas](https://uncomtrade.org/docs/areas-not-elsewhere-specified/)

For each reference, the published geography profile records the source labels, class, region where matched, independent role-eligibility flags, rationale, provenance, and review status. Observed role presence is a further allocation gate. Approve territorial inclusion and confirm Backend location identifiers before using this provisional mapping for generation.

## Product eligibility and grouping

For every observed mapped product, the profile includes its text code, reference description, eligible exporter and importer markets, eligible A and B counts, total external combinations, and direct origin breadth by importer summarized as maximum and number of importer markets with two or three origins. To retrieve the exact A/B relationships, query the existing Market Relationship engine for that product and apply the published market eligibility flags. The planner reads compact observed bit masks and does not generate the full candidate universe.

A code with six ASCII digits is grouped by its first two characters, preserving leading zeros. This is a provisional diversity grouping defined on the supplied normalized source codes. Codes without a numeric prefix grouping remain visible and are excluded from baseline selection. These groups carry no verified HS revision or commercial category mapping. A preliminary candidate needs a reference description and at least one geographically eligible directly observed external relationship.

The eligibility assessment covers all 238 references. It retains 187 provisional country candidates and holds out 34 territories or separately represented areas, eight historical entities, three statistical aggregates, and six special-review entries. Three source references still have missing ISO2 identifiers. The eligible source roles cover 25 observed exporter markets and 187 observed importer markets.

Before the geographic filter, 4,211 products have a buyer market reached by at least three distinct exporter markets. After filtering, 4,462 products have two or more observed origins for at least one buyer and 4,167 have three or more. Of the 4,577 observed mapped products, 4,573 retain an eligible direct relationship. The filter leaves 6,225,906 external combinations, including 936,492 Category A and 4,164,433 Category B. These are counts of observed market linkage or compatibility, with supplier-slot competition established separately by the allocation proof.

## Selection method

The planner selects 75 disjoint blocks of four products. A block shares one directly observed exporter-to-importer pair for all four codes. This provides a concrete bridge from selection to portfolio, listing and RFQ feasibility. Supplier and importer roles have independently tracked caps and region counts. Each new block prefers unused exporter and importer markets, then lower allocated same-region slot totals, then lower current market load. Seeded pair tie-breaks and numeric market keys make the order stable.

Within a pair, pick products from the least represented available prefix, then favor eligible exporter breadth, importer breadth and the maximum directly observed origin breadth at an importer. Text product code breaks remaining ties. The provisional prefix cap is 12, supplier cap 20 and importer cap 6. This is a lexicographic selection rule with no weighted commercial score or use of prices, quantities or observation-count ranking. If a pair cannot supply four eligible unselected products within the cap, try the next pair. An exhausted greedy pass reports no solution found.

See the [manifest](../data/planning/synthetic_marketplace/allocation_plan_manifest.json) for the versioned artifacts and the [feasibility report](../reports/synthetic_joint_feasibility.json) for geographic coverage, group counts, role distributions, and geography-driven relationship loss.
