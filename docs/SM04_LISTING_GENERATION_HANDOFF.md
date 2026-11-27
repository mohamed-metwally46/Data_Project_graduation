# SM-04 listing handoff

The validated company input is stage `sm03b-68a129e0877cc0b7405db11375d2ef72ee862b7545075bd36c06099fa8e42363` for population `globiq-marketplace-baseline-001`. Use its canonical bundle, with 500 companies, 300 supplier roles, 200 importer roles, 1,800 portfolio associations, 500 slot mappings and the 500-entry persistent registry. [Stage manifest](../data/synthetic/stages/companies/company_stage_manifest.json)

The canonical schema is v1.0.0 with SHA-256 `f37213461ede31e9ab233a2727716706173afdb5e2d61f679b08feaa79406417`. The identity configuration fingerprint is `sha256:24503f5214ffb421b6becd738c7ac4616c9dbcfb9b378d8e41dea278e45cbedc`. Two independent full builds produced the same 2,219,027-byte bundle with SHA-256 `5d41f334d6c5bac78046e21ca231df826a9c5d844dc89bc47c6c753c1a1abce4`. Independent serialized validation confirmed role and market preservation and observed evidence for all 1,800 associations. [Validation report](../data/synthetic/stages/companies/populations/sm03b-68a129e0877cc0b7405db11375d2ef72ee862b7545075bd36c06099fa8e42363/company_validation_report.json) · [Run evidence](../reports/synthetic_company_readiness.json)

Use the original 1,000 listing allocations from `sm02-90bf5c26373c3d2c45f3fe7f371fbbe8a45b880825f9aa0ee9315de2a96b9ef3`. The slot mapping resolves every listing supplier and product, all 600 RFQ importers, all 180 targeted RFQ suppliers and all 900 planned offer suppliers. Preserve those planning records and relationships. [Approved SM-02 planning manifest](../data/planning/synthetic_marketplace/allocation_plan_manifest.json)

## Pending commercial and integration decisions

- Confirm product-specific measurement units, product-level price ranges, price basis and Decimal precision and rounding.
- Approve stock bounds, minimum order quantities and quantity increments.
- Establish RFQ requested quantity rules and verify offer fulfillment compatibility.
- Verify commercial feasibility across the preserved allocation.
- Confirm Backend field mappings, external product IDs and demo isolation.

SM-04 requires separate authorization. The company artifacts are intermediate and carry `backend_importable: false` and `full_marketplace_release: false`.

The later user brief authorizes SM-04A joint provisional planning and isolated fixtures. Listing population generation requires exact SM-04B approval. [Stage authorization](SM04_LISTING_STAGE_AUTHORIZATION.md)
