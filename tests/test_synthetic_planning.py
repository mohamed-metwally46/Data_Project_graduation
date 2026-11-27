from contextlib import closing
from copy import deepcopy
import sqlite3
import unittest

from src.analytics.market_opportunity_intelligence import MarketRelationshipEngine
from src.synthetic.allocation import NoPlan, geography, profile, product_group, supplier_bound
from src.synthetic.planning import fingerprint, make_plan
from src.synthetic.planning_validation import validate_plan


def fixture():
    codes = [f"{group:02d}{number:04d}" for group in (1, 2) for number in range(1, 5)]
    locations = [(4, "Origin 4", "AF", "AFG"), (8, "Origin 8", "AL", "ALB"),
                 (12, "Destination 12", "DZ", "DZA"), (24, "Destination 24", "AO", "AGO"),
                 (490, "Aggregate", None, None), (700, "Unresolved", None, None),
                 (16, "Territory", "AS", "ASM")]
    rows = [(2024, p, e, i) for p in codes for e in (4, 8) for i in (12, 24)]
    scope = {"complete_global_coverage": False, "source": "Fixture", "limitation": "Fixture",
             "trade_value_unit": None, "quantity_unit": None, "hs_revision": None}
    with closing(sqlite3.connect(":memory:")) as db:
        db.row_factory = sqlite3.Row
        db.executescript("""
          CREATE TABLE country(code,name,iso2,iso3);
          CREATE TABLE product(code,description);
          CREATE TABLE enriched_trade_data(year,product_code,exporter_code,importer_code,
             invalid_fields,exporter_matched,importer_matched,product_matched);
        """)
        db.executemany("INSERT INTO country VALUES (?,?,?,?)", locations)
        db.executemany("INSERT INTO product VALUES (?,?)", [(p, "Fixture " + p) for p in codes])
        db.executemany("INSERT INTO enriched_trade_data VALUES (?,?,?,?,NULL,1,1,1)", rows)
        engine = MarketRelationshipEngine(db, {"rows": {"enriched": len(rows)}, "metadata": scope,
            "join_validation": {k: {"before": len(rows), "after": len(rows), "reference_keys_unique": True}
                                for k in ("exporter", "importer", "product")}})
    scenario = {"scenario_id": "fixture", "supplier_market_cap": 4, "importer_market_cap": 3,
                "product_prefix_cap": 4, "geography": {
                  "source_code_crosswalk": {}, "territorial_market_codes": [16],
                  "historical_market_codes": [], "statistical_market_codes": [490],
                  "special_review_market_codes": []}}
    geo = geography(engine.countries, scenario, {"source": "Fixture",
        "rows": {iso3: [c, "Fixture region", iso2] for c, _, iso2, iso3 in locations if iso3}})
    profiles, stats = profile(engine, geo)
    policy = {
        "source": {"release_id": "fixture", "year": 2024,
                   "dataset_fingerprint": engine.metadata["dataset_version"]},
        "targets": {"products": 8, "companies": 13, "supplier_roles": 8, "importer_roles": 5,
                    "listings": 26, "rfqs": 16, "offers": 24},
        "default_allowed_bilateral_categories": ["A", "B"],
        "proposed_defaults": {"master_seed": 42, "products_per_supplier": 4, "products_per_importer": 3,
            "offers_per_rfq": {"0": 4, "1": 4, "2": 4, "3": 4},
            "rfq_types": {"open": 12, "targeted": 4},
            "listing_statuses": {"active": 22, "out_of_stock": 2, "inactive": 2},
            "bilateral_percent": {"a_min": 80, "b_max": 20, "c": 0}},
    }
    return policy, scenario, engine, geo, profiles, stats


class PlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy, cls.scenario, cls.engine, cls.geo, cls.profiles, cls.stats = fixture()
        cls.plan, _ = make_plan(cls.policy, cls.scenario, cls.engine, cls.geo, cls.profiles)

    def validate(self, plan):
        return validate_plan(plan, self.engine, self.geo, self.scenario, self.policy)

    def test_geographic_and_product_eligibility(self):
        self.assertEqual(self.geo[490]["classification"], "statistical_aggregate")
        self.assertEqual(self.geo[700]["classification"], "unresolved")
        self.assertIsNone(self.geo[700]["iso2"])
        self.assertFalse(self.geo[16]["supplier_eligible"])
        self.assertTrue(self.geo[4]["supplier_eligible"])
        self.assertEqual(product_group("010001"), "prefix-01")
        self.assertIsNone(product_group("9999AA"))
        self.assertEqual(self.profiles["010001"]["category_a_count"], 4)
        self.assertEqual(self.stats["products_with_two_or_more_direct_origin_markets"], 8)
        self.assertEqual(self.stats["products_with_three_or_more_direct_origin_markets"], 0)

    def test_complete_witness_and_serialized_replay(self):
        result = self.validate(self.plan)
        self.assertEqual(result["counts"], {"products": 8, "company_slots": 13, "supplier_slots": 8,
                                            "importer_slots": 5, "listings": 26, "rfqs": 16, "offers": 24})
        self.assertEqual(result["active_product_coverage"], 8)
        self.assertEqual(result["rfq_importer_slot_coverage"], 5)
        self.assertEqual(result["bilateral_evidence"]["denominator"], 28)
        self.assertEqual(result["bilateral_evidence"]["combined"], {"A": 28, "B": 0, "C": 0})
        self.assertEqual(result["distinct_supplier_competition_requests"], 8)
        self.assertEqual(len(result["category_distribution"]), 2)
        replay, _ = make_plan(self.policy, self.scenario, self.engine, self.geo, self.profiles)
        self.assertEqual(self.plan, replay)
        self.assertEqual(fingerprint(self.plan), fingerprint(replay))

    def test_validator_rejects_broken_links_coverage_and_population_fields(self):
        def invalidate(edit, message):
            plan = deepcopy(self.plan)
            edit(plan)
            with self.assertRaisesRegex(ValueError, message):
                self.validate(plan)

        invalidate(lambda p: p.update(source={}), "pinned source")
        invalidate(lambda p: p.update(importable=True), "planning-only")
        invalidate(lambda p: p["company_slots"][0].update(name="Fixture"), "scope protection")
        invalidate(lambda p: p["company_slots"][0].update(market_code=490), "slot market")
        invalidate(lambda p: p["company_slots"][0].update(role="importer"), "role slot namespace")
        invalidate(lambda p: p["company_slots"][0]["product_codes"].pop(), "portfolio capacity")
        invalidate(lambda p: p["company_slots"][0]["product_codes"].__setitem__(0, "000000"), "unselected product")
        invalidate(lambda p: p["listing_allocations"][1].update(
            supplier_slot_id=p["listing_allocations"][0]["supplier_slot_id"]), "duplicate supplier-product")
        invalidate(lambda p: p["listing_allocations"][0].update(status="inactive"), "listing status")
        invalidate(lambda p: p["rfq_allocations"][0].update(target_supplier_slot_id="SUP-SLOT-0001"), "open RFQ target")
        invalidate(lambda p: next(r for r in p["rfq_allocations"] if r["type"]=="targeted").update(response_count=2),
                   "targeted RFQ")
        invalidate(lambda p: p["offer_allocations"][0].update(listing_id="missing"), "unresolved offer")
        invalidate(lambda p: p["offer_allocations"][0].update(category="C"), "bilateral category")
        invalidate(lambda p: p["offer_allocations"][1].update(**{
            key:p["offer_allocations"][0][key] for key in ("listing_id","supplier_slot_id")}),
                   "duplicate competing supplier")

    def test_proven_capacity_bound_is_not_search_failure(self):
        with self.assertRaises(NoPlan) as caught:
            supplier_bound(2, 3, 8)
        self.assertEqual(caught.exception.status, "proven_infeasible")
        proposed = {**self.scenario, "supplier_market_cap": 5, "importer_market_cap": 1}
        with self.assertRaises(NoPlan) as caught:
            make_plan(self.policy, proposed, self.engine, self.geo, self.profiles)
        self.assertEqual(caught.exception.status, "no_solution_found")


if __name__ == "__main__":
    unittest.main()
