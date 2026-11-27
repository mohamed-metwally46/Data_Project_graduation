"""Independently verify serialized proposal values and reconcile approved relationships."""
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction

from src.analytics.release_validation import schema_validator, unique_index
from src.synthetic.commercial_config import commercial_context, dec, normalized_price, quantity_ticks, require, round_ratio
from src.synthetic.commercial_planning import KEYS, STRUCTURAL, basic_availability, eligibility

EXPECTED = {"profiles": 300, "listings": 1000, "rfqs": 600, "offers": 900}


@commercial_context
def validate_plan(root, data, config, expected_profiles, allocation, bindings, engine):
    schema_validator(root, "commercial_plan.v1").validate(data)
    require(data["metadata"]["bindings"] == bindings, "ALLOCATION_MISMATCH", "commercial provenance")
    require({name: len(data[name]) for name in EXPECTED} == EXPECTED,
            "ALLOCATION_MISMATCH", "fixed collection lengths")
    by_code = unique_index(data["profiles"], lambda row: row["product_code"])
    require(by_code == {p["product_code"]: p for p in expected_profiles},
            "UNRESOLVED_PRODUCT_PROFILE", "resolved profiles changed after serialization")
    collections = {}
    for name, id_field in KEYS.items():
        original = unique_index(allocation[STRUCTURAL[name]], lambda row: row[id_field])
        actual = unique_index(data[name], lambda row: row[id_field])
        require(actual.keys() == original.keys(), "ALLOCATION_MISMATCH", name)
        for ref, row in original.items():
            require(all(actual[ref][k] == v for k, v in row.items()),
                    "ALLOCATION_MISMATCH", name, planning_reference=ref, product_code=row["product_code"])
        collections[name] = actual
    slots = unique_index(allocation["company_slots"], lambda row: row["slot_id"])
    units = config["units"]
    category_records = Counter()
    relationships = set()

    def role_evidence(slot, code, role):
        market = slots[slot]["market_code"]
        links = engine.products[code]
        require(slots[slot]["role"] == role and code in slots[slot]["product_codes"]
                and market in (links.exports if role == "supplier" else links.imports),
                "ROLE_EVIDENCE_MISMATCH", role, product_code=code, planning_slot=slot)
        return market

    def bilateral(row, supplier_slot, buyer_market, ref):
        code = row["product_code"]
        market = role_evidence(supplier_slot, code, "supplier")
        evidence = engine.lookup_relationship(code, market, buyer_market)
        require(evidence is not None and evidence["category"] == row["category"] == "A",
                "BILATERAL_EVIDENCE_MISMATCH", "observed Category A required",
                planning_reference=ref, product_code=code)
        category_records[row["category"]] += 1
        relationships.add((market, code, buyer_market))

    def price_check(original, p, kind, anchor, ref):
        amount = dec(original["amount"])
        precision = p["quoted_price_precision"]
        low, high = (dec(v) for v in p["price_variation"][kind])
        require(original["basis_quantity"] == p["price_basis_quantity"]
                and original["basis_unit"] == p["price_basis_unit"] and original["currency"] == p["currency"]
                and amount > 0 and amount.scaleb(precision) == amount.scaleb(precision).to_integral_value()
                and dec(p["price_bounds"][0]) <= amount <= dec(p["price_bounds"][1])
                and anchor * (1 + low) <= amount <= anchor * (1 + high),
                "PRICE_DOMAIN_CONFLICT", kind, planning_reference=ref, product_code=p["product_code"])

    statuses, inactive_stock = Counter(), Counter()
    for ref, listing in collections["listings"].items():
        code = listing["product_code"]
        p = by_code[code]
        role_evidence(listing["supplier_slot_id"], code, "supplier")
        require(listing["unit"] == p["measurement_unit"]
                and listing["maximum_order_quantity"] == p["maximum_order_quantity"]
                and listing["quantity_increment"] == p["quantity_increment"],
                "INCOMPATIBLE_UOM", "listing product configuration", listing_id=ref, product_code=code)
        precision = p["quantity_precision"]
        step = quantity_ticks(p["quantity_increment"], precision)
        stock, moq = (quantity_ticks(listing[key], precision) for key in ("stock", "moq"))
        minimum, maximum = (quantity_ticks(value, precision) for value in p["moq_bounds"])
        require(minimum <= moq <= maximum and moq % step == 0,
                "MOQ_CONSTRAINT_CONFLICT", "MOQ outside domain", listing_id=ref, product_code=code)
        active = basic_availability(listing["status"], stock)["matching"]
        if stock:
            lo, hi = (quantity_ticks(value, precision) for value in p["stock_bounds"])
            require(lo <= stock <= hi, "INSUFFICIENT_MAXIMUM_STOCK", "stock outside configured domain",
                    listing_id=ref, product_code=code)
        if active:
            limit = quantity_ticks(p["maximum_order_quantity"], precision) if p["maximum_order_quantity"] else stock
            require(moq > 0 and moq <= min(stock, limit), "MOQ_CONSTRAINT_CONFLICT",
                    "active listing has no valid order", listing_id=ref, product_code=code)
        statuses[listing["status"]] += 1
        if listing["status"] == "inactive":
            inactive_stock["positive" if stock else "zero"] += 1
        price_check(listing["price"], p, "listing", dec(p["reference_price"]), ref)

    for ref, request in collections["rfqs"].items():
        code = request["product_code"]
        p = by_code[code]
        market = role_evidence(request["buyer_slot_id"], code, "importer")
        require(market == request["destination_market"] and request["unit"] == p["measurement_unit"],
                "ALLOCATION_MISMATCH", "RFQ market or unit", request_id=ref, product_code=code)
        qty = dec(request["requested_quantity"])
        quantity_ticks(request["requested_quantity"], p["quantity_precision"])
        require(dec(p["rfq_quantity_bounds"][0]) <= qty <= dec(p["rfq_quantity_bounds"][1])
                and qty % dec(p["quantity_increment"]) == 0,
                "NO_VALID_QUANTITY_INCREMENT", "request violates bounds or increment",
                request_id=ref, product_code=code)
        price_check(request["target_price"], p, "rfq", dec(p["reference_price"]), ref)
        if request["type"] == "targeted":
            bilateral(request, request["target_supplier_slot_id"], market, ref)

    respondents = defaultdict(set)
    for ref, offer in collections["offers"].items():
        code = offer["product_code"]
        p = by_code[code]
        request = collections["rfqs"][offer["request_id"]]
        listing = collections["listings"][offer["listing_id"]]
        supplier = offer["supplier_slot_id"]
        require(supplier not in respondents[offer["request_id"]]
                and listing["product_code"] == request["product_code"] == code
                and supplier == listing["supplier_slot_id"] and (request["type"] == "open"
                    or request["target_supplier_slot_id"] == supplier),
                "ALLOCATION_MISMATCH", "allocated responder and product", offer_id=ref)
        respondents[offer["request_id"]].add(supplier)
        bilateral(offer, supplier, request["destination_market"], ref)
        qty = dec(request["requested_quantity"])
        maximum = dec(listing["maximum_order_quantity"]) if listing["maximum_order_quantity"] else dec(listing["stock"])
        require(offer["unit"] == request["unit"] == listing["unit"]
                and dec(offer["offered_quantity"]) == qty and listing["status"] == "active"
                and dec(listing["moq"]) <= qty <= min(maximum, dec(listing["stock"]))
                and qty % dec(listing["quantity_increment"]) == 0,
                "FULFILLMENT_CONFLICT", "shared stock cannot fulfill the individual scenario",
                offer_id=ref, listing_id=offer["listing_id"], request_id=offer["request_id"], product_code=code)
        price_check(offer["price"], p, "offer", dec(listing["price"]["amount"]), ref)
        exact_price = normalized_price(offer["price"], request["unit"], units, p["permitted_units"])
        amount = round_ratio(exact_price * Fraction(qty), config["total_precision"])
        require(dec(offer["extended_product_value"]) == amount
                and offer["extended_product_value"] == format(amount, "f"),
                "EXTENDED_VALUE_MISMATCH", "product-only total", offer_id=ref)

    require(all(len(respondents[ref]) == r["response_count"] for ref, r in collections["rfqs"].items()),
            "ALLOCATION_MISMATCH", "individual RFQ response counts")
    histogram = Counter(str(len(respondents[ref])) for ref in collections["rfqs"])
    types = Counter(r["type"] for r in collections["rfqs"].values())
    require(statuses == {"active":850, "out_of_stock":100, "inactive":50}
            and inactive_stock == {"zero":25,"positive":25}
            and types == {"open":420,"targeted":180} and histogram == {"0":120,"1":180,"2":180,"3":120}
            and category_records == {"A":1080} and len(relationships) == 300,
            "ALLOCATION_MISMATCH", "fixed commercial scenario and evidence totals")
    return {"status":"passed", "counts":EXPECTED, "listing_statuses":dict(statuses),
            "inactive_stock":dict(inactive_stock), "rfq_types":dict(types),
            "response_histogram":dict(histogram), "competitive_rfqs":histogram["2"]+histogram["3"],
            "full_fulfillment_responses":len(collections["offers"]), "infeasible_responses":0,
            "unresolved_scenarios":0, "bilateral_records":{k:category_records[k] for k in "ABC"},
            "unique_bilateral_relationships":len(relationships),
            "findings":[{"severity":"INFO","code":"PROVISIONAL_SCENARIOS_VALIDATED",
                         "detail":"Independent scenarios use full quantities without stock reservations."}]}


@commercial_context
def quality_report(data, allocation, config, engine):
    slots = {r["slot_id"]: r for r in allocation["company_slots"]}
    listings = defaultdict(list)
    requests = defaultdict(list)
    offers = defaultdict(list)
    for portfolio, key in ((listings,"listings"),(requests,"rfqs"),(offers,"offers")):
        for row in data[key]:
            portfolio[row["product_code"]].append(row)
    per_rfq = []
    product_quality = []
    listing_coverage = Counter(r["supplier_slot_id"] for r in data["listings"])
    request_stats = Counter()
    samples = {}
    for p in data["profiles"]:
        code = p["product_code"]
        unit = p["measurement_unit"]
        group_listings, group_offers = listings[code], offers[code]
        for request in requests[code]:
            target = request["target_supplier_slot_id"]
            candidates = Counter()
            target_listing = []
            for listing in group_listings:
                supplier = listing["supplier_slot_id"]
                if target and target != supplier:
                    continue
                exporter = slots[supplier]["market_code"]
                destination = request["destination_market"]
                observation = engine.lookup_relationship(code, exporter, destination) if exporter != destination else None
                category = observation["category"] if observation else None
                reason = eligibility(listing, request, p, config["units"], category)
                candidates[reason] += 1
                if reason == "ELIGIBLE" or category == "A":
                    candidates["CATEGORY_A_CANDIDATE"] += 1
                if target:
                    target_listing.append({"status":listing["status"],"eligibility":reason,
                                           "listing_id":listing["listing_id"]})
            eligible = candidates["ELIGIBLE"]
            count = request["response_count"]
            per_rfq.append({"request_id":request["request_id"], "product_code":code, "type":request["type"],
                            "recorded_responses":count,"allocated_catalog_candidates":sum(v for k,v in candidates.items()
                                if k != "CATEGORY_A_CANDIDATE"),"structurally_eligible_candidates":candidates["CATEGORY_A_CANDIDATE"],
                            "commercially_compatible":eligible,"eligible_nonresponding":eligible-count,
                            "valid_but_incompatible":candidates["CATEGORY_A_CANDIDATE"]-eligible,
                            "reason_counts":dict(candidates), "target_listing":target_listing})
            require(eligible >= count, "FULFILLMENT_CONFLICT", "eligible candidate recount",
                    request_id=request["request_id"], product_code=code)
            request_stats["compatible_candidates"] += eligible
            request_stats["eligible_nonresponding"] += eligible-count
            request_stats["valid_but_incompatible"] += candidates["CATEGORY_A_CANDIDATE"]-eligible
            if count == 0:
                request_stats["unanswered_with_compatible_candidate" if eligible else
                              "unanswered_without_compatible_candidate"] += 1
            label = "competitive" if count > 1 else "unanswered_targeted" if not count and target else (
                "unanswered_open" if not count else "single_response")
            if label not in samples:
                samples[label] = {"request":request,"offers":[r for r in group_offers
                    if r["request_id"] == request["request_id"]],"quality":per_rfq[-1]}
        amounts = [dec(row["price"]["amount"]) for row in group_listings]
        stocks = [dec(row["stock"]) for row in group_listings]
        moqs = [dec(row["moq"]) for row in group_listings]
        rfq_quantities = [dec(row["requested_quantity"]) for row in requests[code]]
        offer_prices = [dec(row["price"]["amount"]) for row in group_offers]
        initial_domain = [dec(x) for x in p["initial_price_domains"]["listing"]]
        stock_end = [dec(x) for x in p["stock_bounds"]]
        moq_end = [dec(x) for x in p["moq_bounds"]]
        def summary(values):
            return {"unique":len(set(values)), "min":str(min(values)) if values else None,
                    "max":str(max(values)) if values else None}
        product_quality.append({"product_code":code,"unit":unit,"listings":len(amounts),
            "active_listings":sum(r["status"] == "active" for r in group_listings),
            "listing_prices":summary(amounts),"relative_listing_price_range":str(
              (max(amounts)-min(amounts))/dec(p["reference_price"])),
            "stocks":summary(stocks),"moqs":summary(moqs),"rfq_quantities":summary(rfq_quantities),
            "offer_prices":summary(offer_prices),"price_boundary_count":sum(v in initial_domain for v in amounts),
            "positive_stock_boundary_count":sum(v in stock_end for v in stocks),
            "moq_boundary_count":sum(v in moq_end for v in moqs)})
    return {"unit_distribution":dict(Counter(p["measurement_unit"] for p in data["profiles"])),
            "commercial_groups":dict(Counter(p["commercial_group"] for p in data["profiles"])),
            "category_default_assignments":sum(p["group_assignment"] == "reviewed_category_default" for p in data["profiles"]),
            "product_overrides":sum(p["group_assignment"] == "product_override" or bool(p["override_fields"]) for p in data["profiles"]),
            "manual_review_profiles":sum(bool(p["review_notes"]) for p in data["profiles"]),
            "unresolved_profiles":0,"rfq_diagnostics":dict(request_stats),"by_rfq":per_rfq,
            "listing_counts_by_supplier":dict(sorted(listing_coverage.items())), "by_product":product_quality,
            "samples":samples}
