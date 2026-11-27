"""Solve a product dependency graph without reallocating any SM-02 relationship."""
from collections import defaultdict
from decimal import Decimal
from math import lcm
from time import perf_counter

from src.synthetic.commercial_config import (
    FLAGS, commercial_context, dec, decimal_text, extended, price_domain, quantity_ticks, require,
)
from src.synthetic.determinism import named_random_stream

VERSION = "joint_integer_lattice_v1"
SEARCH_LIMIT = 2048
STATUS = {"active", "out_of_stock", "inactive"}
OUTPUTS = {"listings": "listing_commercial_plan.json", "rfqs": "rfq_commercial_plan.json",
           "offers": "offer_commercial_plan.json"}
KEYS = {"listings": "listing_id", "rfqs": "request_id", "offers": "offer_id"}
STRUCTURAL = {"listings": "listing_allocations", "rfqs": "rfq_allocations", "offers": "offer_allocations"}


def common_interval(domains, increments):
    """Bounds are closed and every order increment is measured from zero."""
    lo = max(1, *(lower for lower, _ in domains))
    hi = min(upper for _, upper in domains)
    lattice = lcm(*increments)
    return (lo + lattice - 1) // lattice, hi // lattice, lattice


@commercial_context
def sampled_quantity(config, name, ref, domains, increments, precision, **context):
    lower, upper, lattice = common_interval(domains, increments)
    require(lower <= upper, "NO_VALID_QUANTITY_INCREMENT", "empty positive quantity lattice",
            planning_reference=ref, intervals=domains, increments=increments, **context)
    ticks = named_random_stream(config["master_seed"], name, ref).randint(lower, upper) * lattice
    return decimal_text(Decimal(ticks).scaleb(-precision))


@commercial_context
def price_record(config, profile, kind, ref, anchor, *, linked_offer=False, effort=None):
    precision = profile["quoted_price_precision"]
    lo, hi = price_domain(profile["price_bounds"], anchor, profile["price_variation"][kind], precision)
    require(lo <= hi, "PRICE_DOMAIN_CONFLICT", f"empty {kind} price envelope",
            planning_reference=ref, product_code=profile["product_code"], envelope_ticks=[lo, hi])
    candidate = named_random_stream(config["master_seed"], kind + ".price", ref).randint(lo, hi)
    ticks = candidate
    if linked_offer:
        for offset in range(min(hi - lo + 1, SEARCH_LIMIT)):
            ticks = lo + (candidate - lo + offset) % (hi - lo + 1)
            quote = Decimal(ticks).scaleb(-precision)
            minimum, maximum = price_domain(profile["price_bounds"], quote, profile["price_variation"]["offer"],
                                            precision)
            if minimum <= maximum:
                effort["search_nodes"] += offset
                break
        else:
            exhausted = hi - lo + 1 <= SEARCH_LIMIT
            require(False, "PRICE_DOMAIN_CONFLICT" if exhausted else "SEARCH_LIMIT_REACHED",
                    "no representable offer price found within the listing quote domain",
                    product_code=profile["product_code"], listing_id=ref,
                    listing_domain_ticks=[lo,hi], search_limit=SEARCH_LIMIT,
                    offer_variation=profile["price_variation"]["offer"])
    return {"amount": decimal_text(Decimal(ticks).scaleb(-precision)), "currency": profile["currency"],
            "basis_quantity": profile["price_basis_quantity"], "basis_unit": profile["price_basis_unit"]}


def basic_availability(status, stock):
    require(status in STATUS and (stock > 0 if status == "active" else stock == 0 if status == "out_of_stock"
                                  else stock >= 0), "STATUS_CONFLICT", "stock and listing status disagree")
    return {"visible": status != "inactive", "matching": status == "active"}


@commercial_context
def eligibility(listing, request, profile, units, bilateral_category):
    """Evaluate a structurally validated listing against one independent scenario."""
    from src.synthetic.commercial_config import CommercialError, convert

    if listing["product_code"] != request["product_code"]:
        return "PRODUCT_MISMATCH"
    if listing["status"] == "out_of_stock":
        return "OUT_OF_STOCK"
    if listing["status"] != "active":
        return "LISTING_NOT_ACTIVE"
    if bilateral_category != "A":
        return "UNSUPPORTED_MARKET_RELATIONSHIP"
    expected_unit = profile["measurement_unit"]
    try:
        qty = convert(request["requested_quantity"], request["unit"], expected_unit,
                      units, profile["permitted_units"])
    except CommercialError as error:
        return "INCOMPATIBLE_UNIT" if error.finding["code"] == "INCOMPATIBLE_UOM" else "INVALID_REQUESTED_QUANTITY"
    if qty <= 0:
        return "INVALID_REQUESTED_QUANTITY"
    if qty % dec(listing["quantity_increment"]):
        return "INVALID_QUANTITY_INCREMENT"
    if qty < dec(listing["moq"]):
        return "BELOW_MINIMUM_ORDER_QUANTITY"
    if listing["maximum_order_quantity"] is not None and qty > dec(listing["maximum_order_quantity"]):
        return "ABOVE_MAXIMUM_ORDER_QUANTITY"
    if qty > dec(listing["stock"]):
        return "INSUFFICIENT_STOCK"
    return "ELIGIBLE"


@commercial_context
def solve(config, profiles, allocation, timings):
    started = perf_counter()
    product = {p["product_code"]: p for p in profiles}
    listings = {r["listing_id"]: r for r in allocation["listing_allocations"]}
    requests = {r["request_id"]: r for r in allocation["rfq_allocations"]}
    offers = allocation["offer_allocations"]
    edges = defaultdict(list)
    for offer in offers:
        edges[offer["request_id"]].append(listings[offer["listing_id"]])
    zero_inactive = set(sorted(
        (k for k, a in listings.items() if a["status"] == "inactive"),
        key=lambda k: (named_random_stream(config["master_seed"], "listing.inactive_stock", k).getrandbits(128), k)
    )[:config["inactive_zero"]])
    dimensions = {}
    for code, p in product.items():
        precision = p["quantity_precision"]
        def ticks(value):
            return quantity_ticks(value, precision)
        step = ticks(p["quantity_increment"])
        stock = tuple(ticks(v) for v in p["stock_bounds"])
        moq = tuple(ticks(v) for v in p["moq_bounds"])
        rfq = tuple(ticks(v) for v in p["rfq_quantity_bounds"])
        ceiling = min(stock[1], ticks(p["maximum_order_quantity"])) if p["maximum_order_quantity"] else stock[1]
        floor = ((moq[0] + step - 1) // step) * step
        dimensions[code] = (precision, step, stock, moq, rfq, (floor, ceiling))
    timings["constraint_graph"] = perf_counter() - started
    started = perf_counter()
    outgoing = defaultdict(list)
    quantities = {}
    for ref, request in sorted(requests.items()):
        code = request["product_code"]
        precision, step, _, _, rfq, capability = dimensions[code]
        linked = edges[ref]
        require(all(r["status"] == "active" and r["product_code"] == code for r in linked)
                and len(linked) == request["response_count"],
                "ALLOCATION_MISMATCH", "RFQ edge changed", request_id=ref, product_code=code)
        qty = sampled_quantity(config, "rfq.quantity", ref, [rfq, *[capability for _ in linked]],
                               [step] * (1 + len(linked)), precision, product_code=code,
                               responding_listings=[r["listing_id"] for r in linked])
        quantities[ref] = qty
        for row in linked:
            outgoing[row["listing_id"]].append(quantity_ticks(qty, precision))

    listing_quantities = {}
    for ref, listing in sorted(listings.items()):
        code = listing["product_code"]
        precision, step, stock, moq, _, capability = dimensions[code]
        linked = outgoing[ref]
        active = listing["status"] == "active"
        if active:
            floor, ceiling = capability
            max_link = max(linked, default=floor)
            minimum_stock = max(stock[0], max_link)
            max_moq = min(moq[1], min(linked, default=ceiling))
        else:
            minimum_stock = stock[0]
            max_moq = moq[1]
        minimum = sampled_quantity(config, "listing.moq", ref, [(moq[0], max_moq)], [step], precision,
                                   product_code=code)
        minimum_stock = max(minimum_stock, quantity_ticks(minimum, precision)) if active else minimum_stock
        if listing["status"] == "out_of_stock" or ref in zero_inactive:
            amount = "0"
        else:
            require(minimum_stock <= stock[1], "INSUFFICIENT_MAXIMUM_STOCK", "stock lower bound exceeds maximum",
                    listing_id=ref, product_code=code, lower_ticks=minimum_stock, maximum_ticks=stock[1])
            ticks = named_random_stream(config["master_seed"], "listing.stock", ref).randint(minimum_stock, stock[1])
            amount = decimal_text(Decimal(ticks).scaleb(-precision))
        listing_quantities[ref] = amount, minimum
    timings["quantity_solving"] = perf_counter() - started
    started = perf_counter()
    commercial_listings = {}
    timings["search_nodes"] = 0
    for ref, row in sorted(listings.items()):
        p = product[row["product_code"]]
        stock, moq = listing_quantities[ref]
        commercial_listings[ref] = {
            **row, **FLAGS, "unit": p["measurement_unit"], "stock": stock, "moq": moq,
            "quantity_increment": p["quantity_increment"], "maximum_order_quantity": p["maximum_order_quantity"],
            "price": price_record(config, p, "listing", ref, dec(p["reference_price"]),
                                  linked_offer=bool(outgoing[ref]), effort=timings),
            "commercial_provenance": "synthetic_listing_planning_values",
        }
    commercial_requests = {}
    for ref, row in sorted(requests.items()):
        p = product[row["product_code"]]
        commercial_requests[ref] = {
            **row, **FLAGS, "unit": p["measurement_unit"], "requested_quantity": quantities[ref],
            "target_price": price_record(config, p, "rfq", ref, dec(p["reference_price"])),
            "target_price_binding": False, "commercial_provenance": "synthetic_rfq_planning_values",
        }
    commercial_offers = []
    for row in sorted(offers, key=lambda r: r["offer_id"]):
        p = product[row["product_code"]]
        unit = p["measurement_unit"]
        request = commercial_requests[row["request_id"]]
        listing = commercial_listings[row["listing_id"]]
        qty = request["requested_quantity"]
        price = price_record(config, p, "offer", row["offer_id"], dec(listing["price"]["amount"]))
        commercial_offers.append({
            **row, **FLAGS, "unit": unit, "offered_quantity": qty, "price": price,
            "extended_product_value": extended(price, qty, unit, config["units"], p["permitted_units"],
                                               config["total_precision"]),
            "fulfillment": "full_independent_no_reservation", "commercial_provenance": "synthetic_offer_planning_values",
        })
    timings["price_solving"] = perf_counter() - started
    return {"listings": list(commercial_listings.values()), "rfqs": list(commercial_requests.values()),
            "offers": commercial_offers}
