# SM-02 joint allocation feasibility

The SM-02 [planning manifest](../data/planning/synthetic_marketplace/allocation_plan_manifest.json) points to an anonymous allocation witness, geographic eligibility records for all source references, and a compact product eligibility profile for each observed product. The planning files use planning-only labels and are incompatible with the draft Backend import bundle. Company portfolios are embedded in slots. Listings, RFQs and offers reference their parent allocation slots and use distinct planning ID namespaces.

## Construction and checks

A four-product block assigns four supplier slots four products each. It assigns two or three importer slots three products each, covering every block product. The proposed mix uses 25 blocks with two importers and 50 with three. A rotation gives every supplier listings across the block and every importer at least one planned RFQ. Start with three distinct listing positions per product, then add 100 fourth positions using a named random stream. Reserve active listings for the required respondents and fill the proposed availability mix deterministically.

Every product has one open multi-response request and one request with at most one response. The baseline puts all 180 one-response requests in the targeted category and all 120 unanswered requests in the open category. Required respondents are chosen from distinct active supplier slots. Suppliers in a block share the same exporter market, and their importer is in the block's distinct destination market. This construction provides Category A evidence for every bilateral record. Using distinct slots can supply competition in a single exporter market. Geographic origin breadth is a separate indicator.

The validator reads serialized records and checks fixed totals, eligibility, role namespaces, portfolios, unique listing pairs, active product coverage, scenario mix, actual respondent counts, distinct suppliers, scope restrictions, and all references. It calls the pinned Market Relationship engine for every targeted RFQ and planned offer. It separately counts unique directional links. The evidence denominator is 180 targeted RFQs plus 900 offers. Open requests do not enter it. Integer cross-multiplication enforces the proposed 80/20 bounds without rounding errors. All proposed scenario parameters remain pending approval.

## Running and reproducing

Install requirements-dev.txt and run from the repository root.

```powershell
python -m src.synthetic.planning plan
python -m src.synthetic.planning validate
python -m src.synthetic.planning inspect
python -m src.synthetic.planning compare-scenarios
python -m unittest discover -s tests -v
```

The profile command prints source and geography profile totals. The plan and validate commands reverify the source read-only. Use --scenario for an explicit compatible scenario file. Inspect and compare-scenarios read the recorded artifacts or report. Construction is repeated with the same loaded inputs, named streams and ordering. Both allocations are serialized and their bytes and content fingerprints are compared. The manifest binds the source, scenario, configuration, content fingerprint and artifact SHA-256 hashes. Failed checks prevent a new manifest pointer from being published. Measured times are recorded separately from deterministic content. [Planning benchmark](../reports/synthetic_planning_benchmark.json)

The additional tighter supplier cap is evaluated by a necessary capacity bound. When eligible observed exporter markets multiplied by the cap falls below 300, the scenario is proven infeasible before other constraints enter. This differs from a greedy search that finds no solution.

## Measured baseline

The published witness covers 300 products in 94 prefix groups. It assigns 300 supplier slots across 25 markets and 200 importer slots across 75 markets. The maximum share of one market is 6.67% for suppliers and 1.50% for importers. The portfolios contain 1,200 supplier-product associations and 600 importer-product associations. The witness provides active listings and RFQs for every selected product, and at least one RFQ for every importer slot.

All 1,080 applicable bilateral records use Category A evidence, representing 300 distinct directional product relationships. There are 300 requests with competing suppliers. The cap-eight alternative is infeasible because 25 observed eligible exporter markets can supply at most 200 slots under that cap.

A separate enriched Parquet check independently reconciled all 4,577 product profiles and all 1,080 bilateral records in the published witness. The 30-test repository suite passed. The [feasibility report](../reports/synthetic_joint_feasibility.json) records the check and gives the complete category and market distributions.

The measured local plan run took about 269 seconds, including 205 seconds for full pinned source verification and 47 seconds for engine initialization. Profiling took 1.26 seconds, selection 6.85 seconds, allocation 0.012 seconds, and serialized-witness validation 0.21 seconds. The repeat allocation took 7.43 seconds with the indexes loaded. Peak process working set was about 820 MB. These measurements include local development conditions and do not imply a service guarantee.

## Commercial conditions and approvals

Active is an allocation status for structural feasibility. Actual units, price basis, stock, MOQ, request and offer quantity ranges, delivery terms and the ability to fulfill requested quantities require later approval and validation. No commercial values or final entity IDs are part of this witness. The input is a partial single-year extract with unverified trade units and classification revision. Observed links do not establish real companies, capacity or demand.

See the [SM-03 handoff](SM03_COMPANY_PLANNING_HANDOFF.md), [decision register](MARKETPLACE_DECISION_REGISTER.md), and [detailed feasibility report](../reports/synthetic_joint_feasibility.json).
