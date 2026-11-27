# SM-04A proposed commercial configuration

The configuration resolves one profile for each code in the exact SM-02 catalog. Every code has an explicit assignment. Resolution applies commercial group defaults, then configured product overrides. It preserves leading zeros, reference descriptions and provisional source group labels. Commercial groups are review groupings for simulated purchases. The official classification revision remains unverified. [Configuration](../configs/synthetic/commercial.v1.json)

A profile includes a canonical unit, an allowlist of convertible units, quantity precision and ordering increment, stock and MOQ ranges, RFQ quantity bounds, optional maximum order, reference price, price bounds, price basis and variations. Broad descriptions retain per-product review notes. For a count-based profile, PCS may denote an unspecified demo item or retail pack. SET has no assumed conversion to pieces. Product or package contents, dimensions, grades, density, potency and specifications require separate evidence.

The registry defines exact conversion ratios in a shared base unit within each dimension. Conversion requires both units to appear in the product allowlist and an exactly representable target quantity. Price comparison converts the basis to the product unit and retains the exact ratio. There are no cross-dimension, item-to-set or currency conversions.

Product-specific reference overrides take precedence. Other product reference prices use master seed 42 and a deterministic 80–120% scaling of the explicit commercial group reference, rounded to the quoted precision. The default product band is 50–150% of that reference. Quoted ranges intersect the product band and the scenario-specific variation. The proposed listing, RFQ target and offer variations are −20% to +20%, −15% to +10%, and −10% to +5%, respectively. Offer variation is relative to its allocated listing price. USD is encoded explicitly with a one-canonical-unit basis, two fractional quoted digits, up to eight digits for normalized display, and two digits for extended values. Round once at the final boundary using ROUND_HALF_UP. Extended values use the original quote and exact basis conversion and exclude shipping, insurance, tax and duties.

Positive stock can occupy any quantity tick. MOQ and order quantities must align with the configured increment from zero. Count and set units use whole ticks. The price domain and quantity lattice are checked by product. Provisional inactive stock splits 25 zero to 25 positive, while the original listing statuses remain authoritative.

These are synthetic numerical proposals. Source units, trade value currency and scaling, and the official classification revision are unverified. The observed extract is partial and supplies evidence for relationships. Prices are generated from the proposal configuration, with zero use of observed value divided by observed quantity.

Use the commercial manifest to locate the complete machine-readable profiles and the human-readable 300-product review table. [Planning manifest](../data/planning/commercial_feasibility/commercial_plan_manifest.json)

## Resolved baseline

All 300 products resolved. There are 239 assignments to reviewed category-default groups and 61 explicit group overrides. In total, 90 profiles have a group or numerical override and 210 resolve through group defaults alone. Review notes apply to 121 profiles and no profile remains unresolved for provisional planning.

- Canonical units include 164 PCS, 97 KG, 16 L, 14 M2, 1 M3, 6 M, 2 SET.
- Commercial group counts are living items 3, food bulk 47, liquid goods 16, industrial bulk 44, small articles 107, medical packs 4, fabric area 14, timber volume 1, textile mass 6, length goods 6, vehicle parts 9, high value items 17, tool sets 2, specialized equipment 23, catalog only articles 1.

[Complete 300-product review table](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/product_commercial_review.md) ? [Machine-readable profiles](../data/planning/commercial_feasibility/plans/sm04a-32558594b63919d38b643c249ef06aa8ba882430a330c30ef2ab959fec02910d/resolved_product_profiles.json)

## SM-04A-R specification proposal

SM-04A-S adds a complete proposed configuration bound to the scope manifest. It preserves the 240 existing proposed specifications and exact commercial parameters, proposes 39 named single-item forms and numerical domains, and excludes eight remaining unresolved profiles. Values remain synthetic and await exact approval. [47-product review](SM04A_PRODUCT_SPECIFICATION_REVIEW.md)

The v1.1.0 overlay keeps the old configuration available byte for byte. It records all 300 profile dispositions, prior notes and severity, definitions and outstanding product decisions. With the approved six corrections, 240 profiles have a proposed explicit specification, 47 need human review and 13 are offline-only. Examples include one saleable pair for footwear, one unopened synthetic retail pack, one hand-tool assortment, and separate mass, length, area and volume conventions. PCS pair or pack definitions have no implicit conversion to their components. Display the explicit saleable-unit label.

Existing units and default quote variations remain in place unless a named correction requires a new basis. The four unit changes receive independently proposed ranges without converting earlier numbers. The liquid corrections retain the previous L/ML basis and bind it to liquid-only specifications. USD stays at two quote decimals, with listing -20%/+20%, RFQ -15%/+10%, offer -10%/+5%, and product bounds 50?150% of reference.

The v1.1 candidate contract uses a local 28-digit HALF_EVEN context, traps invalid operation, division by zero and overflow, and uses HALF_UP for final USD totals. USD quotes/totals use fixed two places. Count fields are integral strings. Positive non-count quantities and quantity denominators use fixed unit scale. Zero stock is exactly `"0"`. Conversion uses exact rational ratios and checks representability. [Complete profile proposal](../configs/synthetic/commercial.remediation.v1.json)
