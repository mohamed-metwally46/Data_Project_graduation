"""Validate a serialized anonymous allocation plan against the pinned evidence."""
from collections import Counter, defaultdict
from statistics import mean, median

from src.synthetic.allocation import product_group


def check(condition, detail):
    if not condition:
        raise ValueError(f"Planning validation failed: {detail}")


FIELDS = {
    "selected_products": "product_code reference_description provisional_group anchor_exporter anchor_importer",
    "company_slots": "slot_id role market_code product_codes",
    "listing_allocations": "listing_id supplier_slot_id product_code status",
    "rfq_allocations": "request_id buyer_slot_id product_code destination_market type response_count target_supplier_slot_id category",
    "offer_allocations": "offer_id request_id listing_id supplier_slot_id product_code category",
}


def index(plan, section, key, expected):
    rows = plan[section]
    check(len(rows) == expected, f"{section} fixed count")
    result = {}
    for row in rows:
        check(set(row) == {*FIELDS[section].split(), "planning_only"} and row["planning_only"] is True,
              f"{section} scope protection")
        check(isinstance(row[key], str) and row[key] not in result, f"{section} unique identifiers")
        result[row[key]] = row
    return result


def validate_plan(plan, engine, geo, scenario, policy):
    targets, defaults = policy["targets"], policy["proposed_defaults"]
    check(set(plan) == {*FIELDS, "planning_only", "importable", "source", "scenario_id"}
          and plan["planning_only"] is True and plan["importable"] is False, "planning-only envelope")
    check(plan["source"] == policy["source"] and plan["scenario_id"] == scenario["scenario_id"]
          and engine.metadata["dataset_version"] == policy["source"]["dataset_fingerprint"], "pinned source")
    products = index(plan, "selected_products", "product_code", targets["products"])
    slots = index(plan, "company_slots", "slot_id", targets["companies"])
    listings = index(plan, "listing_allocations", "listing_id", targets["listings"])
    requests = index(plan, "rfq_allocations", "request_id", targets["rfqs"])
    offers = index(plan, "offer_allocations", "offer_id", targets["offers"])
    categories = Counter()
    for code, row in products.items():
        check(code in engine.products and row["reference_description"] == engine.descriptions[code]
              and bool(row["reference_description"]), f"mapped observed product {code}")
        category = product_group(code)
        check(category is not None and category == row["provisional_group"], f"group {code}")
        categories[category] += 1
        exporter, importer = row["anchor_exporter"], row["anchor_importer"]
        check(exporter != importer and geo.get(exporter, {}).get("supplier_eligible")
              and geo.get(importer, {}).get("importer_eligible"), f"anchor geography {code}")
        evidence = engine.lookup_relationship(code, exporter, importer)
        check(evidence is not None and evidence["category"] == "A", f"direct product anchor {code}")
    check(max(categories.values()) <= scenario["product_prefix_cap"], "prefix concentration cap")

    roles = {"supplier": Counter(), "importer": Counter()}
    portfolios = {"supplier": [], "importer": []}
    product_roles = {"supplier": Counter(), "importer": Counter()}
    for slot_id, slot in slots.items():
        role, market, codes = slot["role"], slot["market_code"], slot["product_codes"]
        check(role in roles and slot_id.startswith("SUP-SLOT-" if role == "supplier" else "IMP-SLOT-")
              and slot_id[-4:].isdigit() and len(slot_id) == 13, "role slot namespace")
        check(type(market) is int and geo.get(market, {}).get(f"{role}_eligible"), f"slot market {slot_id}")
        expected_size = defaults[f"products_per_{role}"]
        check(isinstance(codes, list) and len(codes) == len(set(codes)) == expected_size,
              f"portfolio capacity {slot_id}")
        roles[role][market] += 1
        portfolios[role].append(len(codes))
        for code in codes:
            check(code in products, f"unselected product {code}")
            observed_roles = engine.products[code].exports if role == "supplier" else engine.products[code].imports
            check(market in observed_roles, f"portfolio evidence {slot_id}/{code}")
            product_roles[role][code] += 1
    for role, counts in roles.items():
        check(sum(counts.values()) == targets[f"{role}_roles"], f"{role} count")
        check(max(counts.values()) <= scenario[f"{role}_market_cap"], f"{role} concentration cap")
        check(product_roles[role].keys() == products.keys(), f"{role} product coverage")

    slot_listings, product_listings, active = Counter(), Counter(), Counter()
    pairs = set()
    statuses = Counter()
    for listing_id, row in listings.items():
        supplier, code, status = row["supplier_slot_id"], row["product_code"], row["status"]
        check(listing_id.startswith("LIST-PLAN-") and supplier in slots and slots[supplier]["role"] == "supplier"
              and code in slots[supplier]["product_codes"], f"listing portfolio {listing_id}")
        check((supplier, code) not in pairs, f"duplicate supplier-product listing {supplier}/{code}")
        pairs.add((supplier, code))
        statuses[status] += 1
        slot_listings[supplier] += 1
        product_listings[code] += 1
        if status == "active":
            active[code] += 1
    check(statuses == Counter(defaults["listing_statuses"]), "listing status distribution")
    check(slot_listings.keys() == {sid for sid,s in slots.items() if s["role"] == "supplier"}
          and product_listings.keys() == active.keys() == products.keys(), "listing coverage")

    evidence_counts = {"targeted_rfqs": Counter(), "offers": Counter()}
    unique_links = defaultdict(set)
    def verify_link(row, supplier, buyer, code, section):
        check(supplier in slots and slots[supplier]["role"] == "supplier"
              and code in slots[supplier]["product_codes"], "bilateral supplier portfolio")
        e, i = slots[supplier]["market_code"], slots[buyer]["market_code"]
        check(e != i, "same-market bilateral record")
        evidence = engine.lookup_relationship(code, e, i)
        check(evidence is not None and evidence["category"] in policy["default_allowed_bilateral_categories"]
              and row["category"] == evidence["category"], "bilateral category mismatch or exclusion")
        evidence_counts[section][row["category"]] += 1
        unique_links[row["category"]].add((e, code, i))

    types, response_counts, buyer_coverage, request_products = Counter(), Counter(), set(), set()
    for request_id, row in requests.items():
        buyer, code = row["buyer_slot_id"], row["product_code"]
        check(request_id.startswith("RFQ-PLAN-") and buyer in slots and slots[buyer]["role"] == "importer"
              and row["destination_market"] == slots[buyer]["market_code"] and code in slots[buyer]["product_codes"],
              f"RFQ portfolio {request_id}")
        kind, number = row["type"], row["response_count"]
        check(type(number) is int and 0 <= number <= 3 and kind in ("targeted", "open"), f"RFQ type {request_id}")
        if kind == "open":
            check(row["target_supplier_slot_id"] is None and row["category"] is None, "open RFQ target")
        else:
            check(number <= 1, "targeted RFQ cannot require competing responses")
            verify_link(row, row["target_supplier_slot_id"], buyer, code, "targeted_rfqs")
        types[kind] += 1
        response_counts[str(number)] += 1
        buyer_coverage.add(buyer)
        request_products.add(code)
    check(types == Counter(defaults["rfq_types"]) and response_counts == Counter(defaults["offers_per_rfq"]),
          "RFQ scenario distribution")
    check(buyer_coverage == {sid for sid,s in slots.items() if s["role"] == "importer"}
          and request_products == products.keys(), "importer and product RFQ coverage")

    respondents = defaultdict(set)
    for offer_id, row in offers.items():
        check(offer_id.startswith("OFFER-PLAN-") and row["request_id"] in requests
              and row["listing_id"] in listings, f"unresolved offer reference {offer_id}")
        request, listing = requests[row["request_id"]], listings[row["listing_id"]]
        supplier, code = row["supplier_slot_id"], row["product_code"]
        check(listing["status"] == "active" and listing["product_code"] == request["product_code"] == code
              and listing["supplier_slot_id"] == supplier, f"active offer listing and product {offer_id}")
        check(supplier not in respondents[row["request_id"]], "duplicate competing supplier")
        respondents[row["request_id"]].add(supplier)
        if request["type"] == "targeted":
            check(request["target_supplier_slot_id"] == supplier and request["category"] == row["category"],
                  "targeted response supplier or category")
        verify_link(row, supplier, request["buyer_slot_id"], code, "offers")
    for request_id, row in requests.items():
        check(len(respondents[request_id]) == row["response_count"], f"response allocation {request_id}")
    combined = evidence_counts["targeted_rfqs"] + evidence_counts["offers"]
    denominator = types["targeted"] + len(offers)
    thresholds = defaults["bilateral_percent"]
    check(sum(combined.values()) == denominator and combined["C"] == 0
          and 100*combined["A"] >= thresholds["a_min"]*denominator
          and 100*combined["B"] <= thresholds["b_max"]*denominator, "bilateral policy denominator or limits")

    geographic = {}
    for role, counts in roles.items():
        regions = Counter()
        for code, n in counts.items():
            regions[geo[code]["region"]] += n
        geographic[role] = {"distinct_markets": len(counts), "slots_by_market": dict(sorted(counts.items())),
                            "slots_by_region": dict(sorted(regions.items())),
                            "max_market_share_percent": round(100*max(counts.values())/sum(counts.values()), 6),
                            "unused_eligible_observed_markets": sorted(
                                code for code,row in geo.items() if row[f"{role}_eligible"]
                                and code in (engine.export_products if role == "supplier" else engine.import_products)
                                and code not in counts)}
    def complete(counter):
        return {c: counter[c] for c in "ABC"}

    return {
        "structural_feasibility": "validated_provisional",
        "commercial_feasibility": "conditional_on_approved_units_stock_moq_and_quantity_bounds",
        "category_distribution": dict(sorted(categories.items())),
        "geographic_allocation": geographic,
        "portfolio_statistics": {
            role: {"total_associations": sum(sizes), "min": min(sizes), "median": median(sizes),
                   "mean": mean(sizes), "max": max(sizes),
                   "slots_per_product": dict(sorted(product_roles[role].items()))}
            for role, sizes in portfolios.items()
        },
        "counts": {"products": len(products), "company_slots": len(slots), "supplier_slots": sum(roles["supplier"].values()),
                   "importer_slots": sum(roles["importer"].values()), "listings": len(listings),
                   "rfqs": len(requests), "offers": len(offers)},
        "listing_statuses": dict(statuses), "active_product_coverage": len(active),
        "unused_supplier_portfolio_capacity": sum(portfolios["supplier"]) - len(listings),
        "rfq_types": dict(types), "response_distribution": dict(response_counts),
        "rfq_product_coverage": len(request_products), "rfq_importer_slot_coverage": len(buyer_coverage),
        "distinct_supplier_competition_requests": sum(len(v) > 1 for v in respondents.values()),
        "covered_markets_and_portfolios": True,
        "bilateral_evidence": {**{section: complete(counts) for section, counts in evidence_counts.items()},
                               "denominator": denominator, "combined": complete(combined),
                               "unique_relationships": {c: len(unique_links[c]) for c in "ABC"}},
    }
