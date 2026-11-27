"""Construct an anonymous SM-02 allocation witness."""
from collections import Counter

from src.analytics.market_opportunity_intelligence import bit_indices, category_masks
from src.synthetic.determinism import named_random_stream


class NoPlan(ValueError):
    """A documented planning bound or a deterministic search failure."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def geography(countries, scenario, geodata):
    overrides = scenario["geography"]
    special = {
        code: label for key, label in (
            ("territorial_market_codes", "territory_or_separate_area"),
            ("historical_market_codes", "historical"),
            ("statistical_market_codes", "statistical_aggregate"),
            ("special_review_market_codes", "special_review"),
        ) for code in overrides[key]
    }
    result = {}
    custom_trade_codes = {251, 579, 757, 842}
    comtrade = "https://uncomtrade.org/docs/reporter-country-codes-and-their-custom-areas/"
    for code, row in sorted(countries.items()):
        ref = geodata["rows"].get(row["iso3"])
        expected = overrides["source_code_crosswalk"].get(str(code), code)
        matched = bool(ref and ref[0] == expected and ref[2] == row["iso2"])
        if code in special:
            group = special[code]
            if code in custom_trade_codes:
                reason = "Custom trade reporting area. The business-location mapping needs review."
            else:
                reason = f"Explicit provisional exclusion by class: {group}."
        elif matched:
            group = "country_candidate"
            reason = "M49 numeric identity and ISO identifiers reconcile with the source crosswalk."
        else:
            group = "unresolved"
            reason = "No unambiguous M49 reference match under the provisional crosswalk."
        result[code] = {**row, "market_code": code, "classification": group,
                        "region": ref[1] if matched else None,
                        "supplier_eligible": group == "country_candidate",
                        "importer_eligible": group == "country_candidate",
                        "reason": reason,
                        "mapping_provenance": comtrade if code in custom_trade_codes or str(code) in
                        overrides["source_code_crosswalk"] else geodata["source"],
                        "review_status": "provisional_pending_backend_review"}
    return result


def product_group(code):
    return f"prefix-{code[:2]}" if code.isascii() and code.isdigit() and len(code) == 6 else None


def profile(engine, geo):
    supplier_mask = sum(engine.bits[c] for c, row in geo.items() if row["supplier_eligible"])
    importer_mask = sum(engine.bits[c] for c, row in geo.items() if row["importer_eligible"])
    profiles = {}
    breadth_before = 0
    for code in engine.product_codes:
        data = engine.products[code]
        breadth_before += any((mask & ~engine.bits[i]).bit_count() >= 3 for i, mask in data.imports.items())
        exp_mask = data.exporter_mask & supplier_mask
        imp_mask = data.importer_mask & importer_mask
        exporters = [engine.markets[i] for i in bit_indices(exp_mask)]
        importers = [engine.markets[i] for i in bit_indices(imp_mask)]
        a, b = 0, 0
        for exporter in exporters:
            counts = category_masks(imp_mask & ~engine.bits[exporter], data.exports[exporter],
                                    engine.outgoing[exporter])
            a += counts[0].bit_count()
            b += counts[1].bit_count()
        degrees = [(i, (data.imports[i] & exp_mask & ~engine.bits[i]).bit_count()) for i in importers]
        max_origins = max((n for _, n in degrees), default=0)
        group = product_group(code)
        profiles[code] = {
            "product_code": code, "reference_description": engine.descriptions[code],
            "provisional_group": group,
            "eligible_exporters": exporters, "eligible_importers": importers,
            "category_a_count": a, "category_b_count": b,
            "eligible_external_combinations": len(exporters) * len(importers) - (exp_mask & imp_mask).bit_count(),
            "max_direct_exporter_markets_for_one_importer": max_origins,
            "importer_markets_with_two_or_more_direct_origins": sum(n >= 2 for _, n in degrees),
            "importer_markets_with_three_or_more_direct_origins": sum(n >= 3 for _, n in degrees),
            "preliminary_eligible": bool(group and a and engine.descriptions[code]),
        }
    classifications = Counter(row["classification"] for row in geo.values())
    statistics = {
        "reference_markets": len(geo), "geographic_classifications": dict(sorted(classifications.items())),
        "missing_iso2_markets": sum(row["iso2"] is None for row in geo.values()),
        "missing_iso3_markets": sum(row["iso3"] is None for row in geo.values()),
        "eligible_business_location_candidates": classifications["country_candidate"],
        "eligible_observed_exporters": sum(c in engine.export_products for c in geo if geo[c]["supplier_eligible"]),
        "eligible_observed_importers": sum(c in engine.import_products for c in geo if geo[c]["importer_eligible"]),
        "mapped_observed_products": len(profiles),
        "provisional_product_groups": len({r["provisional_group"] for r in profiles.values()} - {None}),
        "ungrouped_products": sum(r["provisional_group"] is None for r in profiles.values()),
        "three_origin_product_breadth_before_geography": breadth_before,
        "products_with_eligible_exporters": sum(bool(r["eligible_exporters"]) for r in profiles.values()),
        "products_with_eligible_importers": sum(bool(r["eligible_importers"]) for r in profiles.values()),
        "products_with_eligible_a_relationship": sum(r["category_a_count"] > 0 for r in profiles.values()),
        "products_with_two_or_more_direct_origin_markets": sum(
            r["max_direct_exporter_markets_for_one_importer"] >= 2 for r in profiles.values()),
        "products_with_three_or_more_direct_origin_markets": sum(
            r["max_direct_exporter_markets_for_one_importer"] >= 3 for r in profiles.values()),
        "products_failing_preliminary_eligibility": sum(not r["preliminary_eligible"] for r in profiles.values()),
        "eligible_category_a_relationships": sum(r["category_a_count"] for r in profiles.values()),
        "eligible_category_b_relationships": sum(r["category_b_count"] for r in profiles.values()),
        "eligible_external_relationships": sum(r["eligible_external_combinations"] for r in profiles.values()),
    }
    statistics["eligible_category_c_relationships"] = (
        statistics["eligible_external_relationships"] - statistics["eligible_category_a_relationships"]
        - statistics["eligible_category_b_relationships"]
    )
    return profiles, statistics


def supplier_bound(eligible_exporters, cap, demand):
    if eligible_exporters * cap < demand:
        raise NoPlan("proven_infeasible", f"{eligible_exporters} eligible exporters x cap {cap} < {demand} supplier slots")


def select_clusters(engine, geo, profiles, scenario, targets, defaults):
    """Choose disjoint four-product groups with direct bilateral evidence."""
    market_count = sum(row["supplier_eligible"] and code in engine.export_products for code, row in geo.items())
    supplier_bound(market_count, scenario["supplier_market_cap"], targets["supplier_roles"])
    if (defaults["products_per_supplier"], defaults["products_per_importer"]) != (4, 3):
        raise NoPlan("unsupported_scenario", "This witness planner requires the proposed four/three portfolio sizes")
    size = 4
    clusters_needed = targets["products"] // size
    extra_buyers = targets["importer_roles"] - 2 * clusters_needed
    if targets["products"] % size or clusters_needed * size != targets["supplier_roles"] or not 0 <= extra_buyers <= clusters_needed:
        raise NoPlan("unsupported_scenario", "Target sizes do not fit this constructive witness")
    by_pair = {}
    acceptable = {c for c,r in profiles.items() if r["preliminary_eligible"]}
    for (e, i), count in sorted(engine.pair_products.items()):
        if count < size or e == i or not geo[e]["supplier_eligible"] or not geo[i]["importer_eligible"]:
            continue
        codes = [p for p in engine.export_products[e] if p in acceptable
                 and engine.products[p].exports[e] & engine.bits[i]]
        if len(codes) >= size:
            by_pair[e, i] = codes
    seed = defaults["master_seed"]
    rng = named_random_stream(seed, "sm02", "pair-tiebreak")
    ties = {key: rng.random() for key in by_pair}
    selected = set()
    categories, supply, demand, supply_regions, demand_regions = (Counter() for _ in range(5))
    clusters = []
    for index in range(clusters_needed):
        buyers = 3 if (index + 1) * extra_buyers // clusters_needed > index * extra_buyers // clusters_needed else 2
        possible = [
            (e, i) for e, i in by_pair
            if supply[e] + size <= scenario["supplier_market_cap"] and demand[i] + buyers <= scenario["importer_market_cap"]
        ]
        def market_key(pair):
            e, i = pair
            return (int(supply[e] > 0) + int(demand[i] > 0),
                    supply_regions[geo[e]["region"]] + demand_regions[geo[i]["region"]],
                    supply[e] + demand[i], ties[pair], e, i)

        for e, i in sorted(possible, key=market_key):
            chosen = []
            local = Counter()
            for _ in range(size):
                choices = (
                    code for code in by_pair[e, i] if code not in selected and code not in chosen
                    and categories[profiles[code]["provisional_group"]] + local[profiles[code]["provisional_group"]]
                    < scenario["product_prefix_cap"]
                )
                def product_key(code):
                    r = profiles[code]
                    group = r["provisional_group"]
                    return (categories[group] + local[group], -len(r["eligible_exporters"]),
                            -len(r["eligible_importers"]), -r["max_direct_exporter_markets_for_one_importer"], code)
                best = min(choices, key=product_key, default=None)
                if best is None:
                    break
                chosen.append(best)
                local[profiles[best]["provisional_group"]] += 1
            if len(chosen) == size:
                break
        else:
            raise NoPlan("no_solution_found", f"Deterministic greedy search stopped after {index} of {clusters_needed} clusters")
        selected.update(chosen)
        categories.update(local)
        supply[e] += size
        demand[i] += buyers
        supply_regions[geo[e]["region"]] += size
        demand_regions[geo[i]["region"]] += buyers
        clusters.append((e, i, chosen, buyers))
    return clusters


def build_allocations(clusters, profiles, defaults, targets):
    """Construct all listing, request and quote allocation slots."""
    seed = defaults["master_seed"]
    products = sorted(code for _, _, group, _ in clusters for code in group)
    distribution = defaults["offers_per_rfq"]
    multi = [int(n) for n, total in sorted(distribution.items()) if int(n) > 1 for _ in range(total)]
    singles = [int(n) for n, total in sorted(distribution.items()) if int(n) <= 1 for _ in range(total)]
    targeted = defaults["rfq_types"]["targeted"]
    if (len(multi), len(singles), targets["rfqs"]) != (len(products), len(products), 2 * len(products)):
        raise NoPlan("unsupported_scenario", "The baseline design uses one competing request and one zero/one-response request per product")
    if targeted > len(singles) or len(singles) - singles.count(0) < targeted:
        raise NoPlan("unsupported_scenario", "Targeted requests must fit the baseline one-response slots")
    named_random_stream(seed, "sm02", "response-scenarios").shuffle(multi)
    secondary = [("targeted", 1)] * targeted + [("open", 1)] * (singles.count(1)-targeted) + [("open", 0)] * singles.count(0)
    named_random_stream(seed, "sm02", "request-types").shuffle(secondary)
    needed = dict(zip(products, multi, strict=True))
    request_mix = dict(zip(products, secondary, strict=True))
    company_slots, listings, rfqs, offers, selected = [], [], [], [], []

    extras = targets["listings"] - 3 * len(products)
    active_extras = defaults["listing_statuses"]["active"] - sum(multi)
    convertible = [p for p in products if needed[p] == 2]
    if not (0 <= extras <= len(products) and 0 <= active_extras <= len(convertible)):
        raise NoPlan("unsupported_scenario", "Listing or active capacity does not fit the baseline witness")
    named_random_stream(seed, "sm02", "listing-variants").shuffle(products)
    named_random_stream(seed, "sm02", "active-variants").shuffle(convertible)
    fourth = set(products[:extras])
    extra_active = set(convertible[:active_extras])
    supplier_count, importer_count = 0, 0
    inactive_remaining = defaults["listing_statuses"]["inactive"]

    def add_request(code, buyer, listings_for_product, kind, responses, seed_position):
        request_id = f"RFQ-PLAN-{len(rfqs)+1:04d}"
        # Rotate responding suppliers while preserving a distinct slot for each response.
        active = [r for r in listings_for_product if r["status"] == "active"]
        offset = seed_position % len(active)
        respondents = (active[offset:] + active[:offset])[:responses]
        request = {"request_id": request_id, "buyer_slot_id": buyer["slot_id"], "product_code": code,
                   "destination_market": buyer["market_code"], "type": kind, "response_count": responses,
                   "target_supplier_slot_id": respondents[0]["supplier_slot_id"] if kind == "targeted" else None,
                   "category": "A" if kind == "targeted" else None, "planning_only": True}
        rfqs.append(request)
        for listing in respondents:
            offers.append({"offer_id": f"OFFER-PLAN-{len(offers)+1:04d}", "request_id": request_id,
                           "listing_id": listing["listing_id"], "supplier_slot_id": listing["supplier_slot_id"],
                           "product_code": code, "category": "A", "planning_only": True})

    for exporter, importer, group, buyer_count in clusters:
        suppliers, buyers = [], []
        for n in range(4):
            supplier_count += 1
            suppliers.append({"slot_id": f"SUP-SLOT-{supplier_count:04d}", "role": "supplier", "market_code": exporter,
                              "product_codes": group.copy(), "planning_only": True})
        for n in range(buyer_count):
            importer_count += 1
            portfolio = [group[(n+j) % 4] for j in range(3)]
            buyers.append({"slot_id": f"IMP-SLOT-{importer_count:04d}", "role": "importer", "market_code": importer,
                           "product_codes": portfolio, "planning_only": True})
        company_slots.extend(suppliers + buyers)
        buyer_allocations = Counter()
        for position, code in enumerate(group):
            selected.append({"product_code": code, "reference_description": profiles[code]["reference_description"],
                             "provisional_group": profiles[code]["provisional_group"],
                             "anchor_exporter": exporter, "anchor_importer": importer, "planning_only": True})
            rotated = suppliers[position:] + suppliers[:position]
            planned = []
            for n, supplier in enumerate(rotated[:4 if code in fourth else 3]):
                if n < needed[code] + int(code in extra_active):
                    status = "active"
                elif inactive_remaining:
                    inactive_remaining -= 1
                    status = "inactive"
                else:
                    status = "out_of_stock"
                planned.append({"listing_id": f"LIST-PLAN-{len(listings)+1:04d}",
                                "supplier_slot_id": supplier["slot_id"], "product_code": code,
                                "status": status, "planning_only": True})
                listings.append(planned[-1])
            eligible_buyers = [b for b in buyers if code in b["product_codes"]]
            # The first buyer_count products each give a distinct buyer its first RFQ.
            buyer = (buyers[position] if position < buyer_count else
                     min(eligible_buyers, key=lambda b: (buyer_allocations[b["slot_id"]], b["slot_id"])))
            add_request(code, buyer, planned, "open", needed[code], position)
            buyer_allocations[buyer["slot_id"]] += 1
            buyer = min(eligible_buyers, key=lambda b: (buyer_allocations[b["slot_id"]], b["slot_id"]))
            kind, responses = request_mix[code]
            add_request(code, buyer, planned, kind, responses, position+1)
            buyer_allocations[buyer["slot_id"]] += 1
    return {"planning_only": True, "importable": False, "selected_products": selected, "company_slots": company_slots,
            "listing_allocations": listings, "rfq_allocations": rfqs, "offer_allocations": offers}
