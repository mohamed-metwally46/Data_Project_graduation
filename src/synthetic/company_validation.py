"""Independent company-stage validation and failure-protected fixture writes."""
from collections import Counter
from itertools import product
import re
from pathlib import Path
import tempfile

from src.analytics.release_validation import read_json, schema_validator, unique_index
from src.pipeline import write_json
from src.synthetic.allocation import product_group
from src.synthetic.company_identity import (
    FIXTURE_NAMESPACE, check_fixture_scope, near_duplicate, normalized_brand, safe_text,
    template_fingerprint,
)
from src.synthetic.determinism import display_code, hierarchical_external_id, named_random_stream


def check(condition, reason):
    if not condition:
        raise ValueError(f"Company validation failed: {reason}")


def validate_company_stage(root, data, plan, geo, settings, observed_role):
    check_fixture_scope(plan, settings)
    return _validate_company_stage(root, data, plan, geo, settings, observed_role,
                                   cohort=plan["plan_id"], namespace=FIXTURE_NAMESPACE,
                                   seed=settings["fixture_seed"], fixture_only=True)


def validate_population(root, data, plan, geo, settings, observed_role):
    identity = settings["permanent_identity"]
    result = _validate_company_stage(root, data, plan, geo, settings, observed_role,
                                     cohort=identity["population_key"], namespace=identity["approved_root_namespace"],
                                     seed=settings["approved_identity"]["master_seed"], fixture_only=False)
    check(result["roles"] == {"supplier": 300, "importer": 200}
          and result["markets_by_role"] == {"supplier": 25, "importer": 75}
          and result["portfolios_by_role"] == {"supplier": 1200, "importer": 600}
          and (result["listing_refs"], result["rfq_refs"], result["targeted_rfq_supplier_refs"],
               result["offer_refs"]) == (1000, 600, 180, 900), "approved population totals")
    return result


def _validate_company_stage(root, data, plan, geo, settings, observed_role, *,
                            cohort, namespace, seed, fixture_only):
    schema_validator(root, "company_stage.proposed").validate(data)
    meta = data["metadata"]
    plan_id = plan["plan_id"]
    check(meta["source"] == plan["source"] and meta["plan_id"] == plan_id
          and meta["population_id"] == cohort and meta["identity_namespace"] == namespace
          and meta["fixture_only"] is fixture_only
          and meta["stage"] == ("SM-03A" if fixture_only else "SM-03B")
          and meta["configuration_fingerprint"] == template_fingerprint(settings), "stage provenance")
    slots = unique_index(plan["company_slots"], lambda row: row["slot_id"])
    catalog = unique_index(plan["selected_products"], lambda row: row["product_code"])
    companies = unique_index(data["companies"], lambda row: row["external_id"])
    roles = unique_index(data["company_roles"], lambda row: row["external_id"])
    assignments = unique_index(data["company_roles"], lambda row: row["company_external_id"])
    maps = unique_index(data["slot_company_mapping"], lambda row: row["planning_slot_id"])
    registry = unique_index(data["identity_registry"], lambda row: row["originating_planning_slot_id"])
    associations = unique_index(data["company_products"], lambda row: row["external_id"])
    keyed = unique_index(data["company_products"],
                         lambda row: (row["role_external_id"], row["source_product_code"]))
    check(maps.keys() == slots.keys() and assignments.keys() == companies.keys()
          and len(companies) == len(roles) == len(slots)
          and {m["company_external_id"] for m in maps.values()} == companies.keys(),
          "slot-to-company bijection and one role per company")
    check(len({m["identity_slot_key"] for m in maps.values()}) == len(maps)
          and len({c["display_code"] for c in companies.values()}) == len(companies)
          and registry.keys() == slots.keys(), "unique identity/display keys and complete registry")
    possible_brands = {"".join(parts) for parts in product(settings["brand_starts"], settings["brand_ends"])}
    seen_names = set()
    seen_brands = []
    expected = set()
    markets_by_role = {"supplier": set(), "importer": set()}
    portfolios_by_role = Counter()
    for ordinal, sid in enumerate(sorted(slots), 1):
        slot = slots[sid]
        mapping = maps[sid]
        uid = mapping["company_external_id"]
        company = companies[uid]
        role = assignments[uid]
        market, slot_role = slot["market_code"], slot["role"]
        keys = slot["product_codes"]
        markets_by_role[slot_role].add(market)
        portfolios_by_role[slot_role] += len(keys)
        if not fixture_only:
            check(mapping["identity_slot_key"] == f"identity-{ordinal:06d}"
                  and mapping["display_code"] == display_code("CMP", ordinal), f"baseline key assignment {sid}")
        check(market in geo and geo[market][f"{slot_role}_eligible"]
              and company["market_code"] == mapping["market_code"] == market, f"planned market {sid}")
        check(role["role"] == slot_role and role["external_id"] == mapping["role_external_id"]
              and mapping["initial_role"] == slot_role
              and role["external_id"] == str(hierarchical_external_id(namespace, cohort,
                                                                     "company_role", uid, slot_role)),
              f"exact initial role {sid}")
        check(mapping["plan_id"] == plan_id
              and uid == str(hierarchical_external_id(namespace, cohort,
                                                     "company", mapping["identity_slot_key"]))
              and mapping["display_code"] == company["display_code"]
              and mapping["product_codes"] == keys and bool(keys) and len(keys) == len(set(keys)),
              f"slot provenance {sid}")
        check(registry[sid] == {"population_id": cohort, "originating_plan_id": plan_id,
                               "originating_planning_slot_id": sid, "external_id": uid,
                               "persistent_company_key": mapping["identity_slot_key"],
                               "display_code": company["display_code"], "identity_status": "active",
                               "reserved_brand": company["brand"], "reserved_name": company["name"]}
              and company["population_id"] == meta["population_id"] == cohort
              and company["provenance"] == {"allocation_plan_id": plan_id, **plan["source"]},
              f"persistent identity registry {sid}")

        brand, name = company["brand"], company["name"]
        normalized = normalized_brand(name)
        brand_key = normalized_brand(brand)
        options = settings["role_templates"][slot_role]
        check(normalized not in seen_names and not any(near_duplicate(brand_key, b) for b in seen_brands)
              and brand in possible_brands and name in {f"{brand} {v}" for v in options["descriptors"]}
              and safe_text(name, 100), f"unique fictional brand and normalized name {sid}")
        seen_names.add(normalized)
        seen_brands.append(brand_key)
        groups = {product_group(code) for code in keys}
        focus = (settings["group_labels"].get(next(iter(groups)), settings["generic_focus"])
                 if len(groups) == 1 else settings["mixed_focus"])
        check(set(keys) <= catalog.keys(), f"selected product set {sid}")
        industry = "diversified_trading" if len(groups) > 1 else "general_trading"
        if len(groups) == 1 and all(catalog[code].get("reference_description") for code in keys):
            industry = settings["industry_groups"].get(next(iter(groups)), industry)
        visual = company["visual_identity"]
        palette = named_random_stream(seed, cohort, mapping["identity_slot_key"], "monogram").choice(
            settings["presentation"]["palettes"])
        check(company["portfolio_focus"] == focus and company["description"] in {
                  t.format(market=geo[market]["name"], focus=focus) for t in options["descriptions"]}
              and company["business_type"] in options["business_types"]
              and company["industry_group"] == industry
              and company["profile_language"] == settings["presentation"]["profile_language"]
              and safe_text(company["description"])
              and visual == {"type": "monogram", "palette_key": palette,
                             "initials": "".join(word[0] for word in name.split()[:2]).upper()},
              f"context and synthetic identity claims {sid}")
        hostname = company["display_code"].lower() + ".example"
        check(re.fullmatch(r"cmp-[0-9]{6}\.example", hostname) is not None
              and company["email"] == "sales@" + hostname
              and company["website"] == ("https://" + hostname if settings["presentation"]["website_enabled"] else None),
              f"reserved .example contacts {sid}")
        source_role = "exporter" if slot_role == "supplier" else "importer"
        for code in keys:
            assoc_key = (role["external_id"], code)
            expected.add(assoc_key)
            check(code in catalog and assoc_key in keyed and observed_role(code, market, source_role),
                  f"selected product and observed role evidence {sid}/{code}")
            row = keyed[assoc_key]
            check(row["company_external_id"] == uid and row["source_market_code"] == market
                  and row["observed_role"] == source_role
                  and all(row[k] == value for k, value in plan["source"].items())
                  and row["external_id"] == str(hierarchical_external_id(namespace, cohort,
                                                                      "company_product", *assoc_key)),
                  f"portfolio association provenance {sid}/{code}")
    check(expected == keyed.keys() and len(associations) == len(expected), "exact portfolio preservation")

    listing_ids = unique_index(plan["listing_allocations"], lambda row: row["listing_id"])
    request_ids = unique_index(plan["rfq_allocations"], lambda row: row["request_id"])
    offer_ids = unique_index(plan["offer_allocations"], lambda row: row["offer_id"])
    def downstream(slot_id, role, code):
        check(slot_id in maps and assignments[maps[slot_id]["company_external_id"]]["role"] == role
              and (maps[slot_id]["role_external_id"], code) in keyed, "unresolved downstream slot/portfolio")
    for listing in listing_ids.values():
        downstream(listing["supplier_slot_id"], "supplier", listing["product_code"])
    for request in request_ids.values():
        code, buyer = request["product_code"], request["buyer_slot_id"]
        downstream(buyer, "importer", code)
        check(request["destination_market"] == maps[buyer]["market_code"], "RFQ destination preserved")
        if request["type"] == "targeted":
            downstream(request["target_supplier_slot_id"], "supplier", code)
    for offer in offer_ids.values():
        supplier, code = offer["supplier_slot_id"], offer["product_code"]
        check(offer["request_id"] in request_ids and offer["listing_id"] in listing_ids, "unresolved downstream offer")
        downstream(supplier, "supplier", code)
        listing, request = listing_ids[offer["listing_id"]], request_ids[offer["request_id"]]
        check(listing["supplier_slot_id"] == supplier and listing["product_code"] == request["product_code"] == code
              and (request["type"] != "targeted" or request["target_supplier_slot_id"] == supplier),
              "downstream offer reference consistency")
    return {"status": "validated_fixture" if fixture_only else "passed",
            "companies": len(companies), "role_assignments": len(roles),
            "roles": dict(Counter(row["role"] for row in roles.values())),
            "markets_by_role": {role: len(markets) for role, markets in markets_by_role.items()},
            "portfolio_associations": len(associations), "portfolios_by_role": dict(portfolios_by_role),
            "slot_mappings": len(maps), "registry_entries": len(registry),
            "listing_refs": len(listing_ids), "rfq_refs": len(request_ids),
            "targeted_rfq_supplier_refs": sum(r["type"] == "targeted" for r in request_ids.values()),
            "offer_refs": len(offer_ids)}


def write_validated_fixture(path, root, data, plan, geo, settings, observed_role):
    """Validate before replacing a caller-supplied fixture file."""
    check(not path.resolve().is_relative_to((root / "data").resolve()), "fixture output isolation")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=path.parent) as work:
        staged = Path(work) / path.name
        write_json(staged, data)
        outcome = validate_company_stage(root, read_json(staged), plan, geo, settings, observed_role)
        staged.replace(path)
    return outcome
