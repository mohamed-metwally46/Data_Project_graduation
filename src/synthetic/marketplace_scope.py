"""Build and independently reconcile a product-filtered projection of pinned allocations."""
from collections import Counter
from pathlib import Path

from src.analytics.release_validation import read_json, unique_index
from src.synthetic.commercial_config import commercial_context, require, resolve_profiles
from src.synthetic.commercial_remediation import ALLOWED, OFFLINE, REVIEW, RESTRICTED
from src.synthetic.planning import fingerprint

REVIEW_CONFIG = Path("configs/synthetic/commercial.scope.review.v1.json")
APPROVAL_EVIDENCE = Path("configs/synthetic/commercial.scope.approval.v1.json")
CEILING = 287
RELATIONS = {"listings":("listing_allocations","listing_id"), "rfqs":("rfq_allocations","request_id"),
             "offers":("offer_allocations","offer_id")}
FLAGS = {"is_synthetic":True,"is_planning_artifact":True,"backend_importable":False,
         "full_marketplace_release":False,"listing_generation_authorized":False}
# Independent synthetic scenario assumptions. These values are proposals.
DOMAINS = {
    "liquids":("liquid_goods","liquid","L",["L","ML"],"1 litre of the stated liquid",
               ["20","480"],["2","28"],"0.5",["4","90"]),
    "bulk":("industrial_bulk","bulk_net_mass","KG",["KG","G","TONNE"],"1 kg net material excluding packaging",
            ["16","420"],["2","24"],"0.5",["4","65"]),
    "pieces":("small_articles","standalone_item","PCS",["PCS"],"1 complete named saleable item",
              ["15","280"],["1","22"],"1",["2","55"]),
    "area":("fabric_area","area_material","M2",["M2"],"1 square metre of directly measured saleable surface",
            ["15","280"],["2","25"],"0.5",["3","60"]),
    "length":("length_goods","length_material","M",["M"],"1 linear metre of the named material",
              ["18","360"],["2","24"],"0.5",["3","65"]),
    "specialist":("high_value_items","standalone_item","PCS",["PCS"],"1 complete named fictional item",
                  ["4","36"],["1","4"],"1",["1","9"]),
    "equipment":("specialized_equipment","standalone_item","PCS",["PCS"],"1 complete named replacement component",
                 ["10","160"],["1","14"],"1",["1","28"]),
}


def read_decisions(root, remediation):
    rules = read_json(root / REVIEW_CONFIG)
    pending = {c for c,p in remediation["products"].items() if p["disposition"] == REVIEW}
    require(rules["version"] == "1.0.0" and rules["strategy"] == "adaptive_scope_option_d"
            and rules["ceiling"] == CEILING and rules["exact_approval"] is None
            and rules["decisions"].keys() == pending and len(pending) == 47,
            "SCOPE_REVIEW_CATALOG_MISMATCH", "exact outstanding review membership")
    for code, branch in rules["decisions"].items():
        require((len(branch) == 2 if branch[0] == "exclude" else len(branch) == 4 and branch[0] in DOMAINS)
                and all(isinstance(x,str) and x.strip() for x in branch),
                "INVALID_SCOPE_REVIEW_DECISION",code)
    return rules


@commercial_context
def proposed_configuration(base, remediation, decisions, selected):
    from src.synthetic.sm04a_remediation import check_domains

    source = unique_index(selected, lambda r:r["product_code"])
    require(source.keys() == remediation["products"].keys(), "SCOPE_REVIEW_CATALOG_MISMATCH", "catalog coverage")
    output = {}
    effective = {}
    for code, rule in sorted(remediation["products"].items()):
        branch = decisions["decisions"].get(code)
        spec = rule["specification"]
        override = rule["commercial_override"]
        group = rule["commercial_group"]
        suitability = rule["disposition"]
        if suitability == OFFLINE:
            state, note = "offline_only", "Offline-only policy. Historical reference retained."
        elif branch and branch[0] == "exclude":
            state, note = "unresolved_excluded", branch[1]
        elif branch:
            kind, name, price, excluded = branch
            group, form, unit, allowed, basis, stock, moq, step, rfq = DOMAINS[kind]
            spec = {
                "specification_key":f"globiq-{code}-demo-v1","specification_version":"1.0.0",
                "display_name":"Synthetic "+name,"physical_form":form,"saleable_unit_definition":basis,
                "canonical_uom":unit,"allowed_uoms":allowed,"excluded_forms":[excluded],
                "measurement_assumptions":["Applies to this single demo presentation within the reference description.",
                                           "Only explicitly permitted same-dimension conversions are supported.",
                                           "Commercial terms are independent synthetic assumptions."],
                "is_synthetic":True,
            }
            override = {"reference_price":price,"stock":stock,"moq":moq,"increment":step,"rfq":rfq}
            state, note = "new_proposal", f"{kind} scenario domain and explicit per-product synthetic reference price."
            suitability = ALLOWED
        else:
            state, note = "existing_proposal", "Carry forward the exact SM-04A-R specification and resolved numerical proposal."
        if spec is not None:
            require(suitability == ALLOWED and spec["is_synthetic"] is True
                    and spec["canonical_uom"] in spec["allowed_uoms"]
                    and all(base["units"][u]["dimension"] == base["units"][spec["canonical_uom"]]["dimension"]
                            for u in spec["allowed_uoms"]),
                    "INCOMPATIBLE_SCOPE_SPECIFICATION",code)
            original = base["products"][code]
            effective[code] = {**original,"group":group,"parameters":{
                **original.get("parameters",{}),
                "unit":spec["canonical_uom"],"permitted_units":spec["allowed_uoms"],
            }}
            if override:
                effective[code]["reference_price"] = override["reference_price"]
                effective[code]["parameters"].update({k:v for k,v in override.items() if k != "reference_price"})
        output[code] = {"reference_description":source[code]["reference_description"],
                        "suitability":suitability,"disposition":state,"specification":spec,
                        "resolution":note,"decision_group":branch[0] if branch and branch[0] != "exclude" else state,
                        "commercial_group":group if spec is not None else None,
                        "commercial_terms":None,"exact_approval":False}
    profiles = resolve_profiles({**base,"products":effective}, [source[c] for c in effective])
    for p in profiles:
        check_domains(p, {"offer_allocations":[{"product_code":p["product_code"]}]})
        output[p["product_code"]]["commercial_terms"] = p
    require(sum(p["disposition"] == "existing_proposal" for p in output.values()) == 240,
            "SCOPE_REVIEW_CATALOG_MISMATCH","existing proposals")
    return {"version":"1.0.0",**FLAGS,"exact_approval":False,"strategy":decisions["strategy"],"products":output,
            "unit_registry":base["units"],"decimal_policy":remediation["decimal_policy"],"price_variation":base["variation"],
            "master_seed":base["master_seed"],"hard_budgets":False,"fulfillment":base["fulfillment"]}


def membership(configuration):
    products = configuration["products"]
    included = {c for c,p in products.items() if p["disposition"] in {"existing_proposal","new_proposal"}
                and p["suitability"] == ALLOWED and p["specification"] and p["commercial_terms"]}
    offline = {c for c,p in products.items() if p["disposition"] == "offline_only" and p["suitability"] == OFFLINE}
    unresolved = {c for c,p in products.items() if p["disposition"] == "unresolved_excluded"
                  and p["suitability"] == REVIEW and p["specification"] is None and p["commercial_terms"] is None}
    require(offline == RESTRICTED and included | offline | unresolved == products.keys()
            and len(included) <= CEILING and all(p["exact_approval"] is False for p in products.values()),
            "SCOPE_MEMBERSHIP_MISMATCH", "offline, unresolved or scope ceiling")
    return included,offline,unresolved


def _portfolio_refs(allocation, company):
    slots = unique_index(allocation["company_slots"],lambda r:r["slot_id"])
    assignments = unique_index(company["slot_company_mapping"],lambda r:r["planning_slot_id"])
    associations = unique_index(company["company_products"],lambda r:(r["company_external_id"],r["source_product_code"]))
    require(slots.keys() == assignments.keys(), "SCOPE_PORTFOLIO_MISMATCH","company slots")
    rows = []
    for key,s in sorted(slots.items()):
        m = assignments[key]
        require(m["market_code"] == s["market_code"] and m["initial_role"] == s["role"]
                and m["product_codes"] == s["product_codes"],
                "SCOPE_PORTFOLIO_MISMATCH",key)
        for code in sorted(s["product_codes"]):
            a = associations[(m["company_external_id"],code)]
            require(a["role_external_id"] == m["role_external_id"] and a["source_market_code"] == s["market_code"]
                    and a["observed_role"] == ("exporter" if s["role"] == "supplier" else "importer"),
                    "SCOPE_PORTFOLIO_MISMATCH",key)
            rows.append({"slot_id":key,"role":s["role"],"product_code":code,"market_code":s["market_code"],
                         "association_external_id":a["external_id"],"company_display_code":m["display_code"]})
    require(len(rows) == len(associations), "SCOPE_PORTFOLIO_MISMATCH","company association cardinality")
    return slots,rows


def _evidence(rows, slots):
    r = {row["request_id"]:row for row in rows["rfqs"]}
    return sorted([
        {"reference":a["request_id"],"kind":"targeted_rfq","category":a["category"],
         "product_code":a["product_code"],"exporter_market":slots[a["target_supplier_slot_id"]]["market_code"],
         "importer_market":a["destination_market"]} for a in rows["rfqs"] if a["type"] == "targeted"
    ] + [
        {"reference":a["offer_id"],"kind":"offer","category":a["category"],"product_code":a["product_code"],
         "exporter_market":slots[a["supplier_slot_id"]]["market_code"],
         "importer_market":r[a["request_id"]]["destination_market"]} for a in rows["offers"]
    ], key=lambda row:(row["kind"],row["reference"]))


def scope_counts(codes, portfolio, rows, evidence):
    role_slots = {role:{a["slot_id"] for a in portfolio if a["role"] == role} for role in ("supplier","importer")}
    markets = {role:{a["market_code"] for a in portfolio if a["role"] == role} for role in role_slots}
    status = Counter(a["status"] for a in rows["listings"])
    kind = Counter(a["type"] for a in rows["rfqs"])
    response = Counter(a["response_count"] for a in rows["rfqs"])
    active = [a for a in rows["listings"] if a["status"] == "active"]
    category = Counter(a["category"] for a in evidence)
    return {
        "products":len(codes),"companies":sum(map(len,role_slots.values())),
        "supplier_companies":len(role_slots["supplier"]),"importer_companies":len(role_slots["importer"]),
        "supplier_associations":sum(a["role"]=="supplier" for a in portfolio),
        "importer_associations":sum(a["role"]=="importer" for a in portfolio),
        "listings":len(rows["listings"]),"active":status["active"],"out_of_stock":status["out_of_stock"],
        "inactive":status["inactive"],"visible_catalog":status["active"]+status["out_of_stock"],
        "generally_available":status["active"],"rfqs":len(rows["rfqs"]),"open_rfqs":kind["open"],
        "targeted_rfqs":kind["targeted"],"responses":{str(i):response[i] for i in range(4)},
        "competitive_rfqs":response[2]+response[3],"offers":len(rows["offers"]),
        "responding_suppliers":len({a["supplier_slot_id"] for a in rows["offers"]}),
        "category_records":{c:category[c] for c in "ABC"},
        "unique_directional_relationships":len({(a["product_code"],a["exporter_market"],a["importer_market"])
                                                for a in evidence}),
        "supplier_markets":len(markets["supplier"]),"importer_markets":len(markets["importer"]),
        "combined_markets":len(markets["supplier"]|markets["importer"]),
        "active_product_coverage":len({a["product_code"] for a in active}),
        "rfq_product_coverage":len({a["product_code"] for a in rows["rfqs"]}),
        "active_supplier_coverage":len({a["supplier_slot_id"] for a in active}),
        "listed_supplier_coverage":len({a["supplier_slot_id"] for a in rows["listings"]}),
        "rfq_importer_coverage":len({a["buyer_slot_id"] for a in rows["rfqs"]}),
    }


def _subset(codes, allocation, portfolio, slots):
    rows = {key:sorted((r for r in allocation[section] if r["product_code"] in codes),key=lambda a:a[id_field])
            for key,(section,id_field) in RELATIONS.items()}
    return [a for a in portfolio if a["product_code"] in codes], rows, _evidence(rows,slots)


def _exceptions(codes, portfolio, rows, slots, displays):
    seen = {r["slot_id"] for r in portfolio}
    active_suppliers = {r["supplier_slot_id"] for r in rows["listings"] if r["status"] == "active"}
    buyers = {r["buyer_slot_id"] for r in rows["rfqs"]}
    def missing(ids, role=None):
        return [{"slot_id":k,"display_code":displays[k]} for k,r in sorted(slots.items())
                if k not in ids and (role is None or r["role"] == role)]
    return {"companies_without_portfolio":missing(seen),
            "suppliers_without_active_listing":missing(active_suppliers,"supplier"),
            "importers_without_rfq":missing(buyers,"importer"),
            "products_without_active_listings":sorted(codes-{r["product_code"] for r in rows["listings"] if r["status"]=="active"}),
            "products_without_rfqs":sorted(codes-{r["product_code"] for r in rows["rfqs"]})}


def coverage(allocation, company, config):
    codes,offline,unresolved=membership(config)
    slots,portfolio=_portfolio_refs(allocation,company)
    displays={r["planning_slot_id"]:r["display_code"] for r in company["slot_company_mapping"]}
    source=set(config["products"])
    original={c for c,p in config["products"].items() if p["disposition"]=="existing_proposal"}
    areas={"historical":source,"restriction_only":source-offline,"previously_resolved":original,
           "proposed":codes,"remaining_unresolved":unresolved}
    brackets={}
    exceptions={}
    for name,subset in areas.items():
        assoc,rows,evidence=_subset(subset,allocation,portfolio,slots)
        brackets[name]=scope_counts(subset,assoc,rows,evidence)
        if name in {"restriction_only","proposed"}:
            exceptions[name]=_exceptions(subset,assoc,rows,slots,displays)
    assoc,rows,evidence=_subset(codes,allocation,portfolio,slots)
    group_count = Counter(config["products"][c]["commercial_group"] for c in codes)
    return {**FLAGS,"scope_counts":brackets,"exceptions":exceptions,
            "additional_exceptions":{
                key:[v for v in values if v not in exceptions["restriction_only"][key]]
                for key,values in exceptions["proposed"].items()},
            "competition_scenarios_below_ceiling":brackets["restriction_only"]["competitive_rfqs"]-brackets["proposed"]["competitive_rfqs"],
            "commercial_groups":dict(sorted(group_count.items())),
            "units":dict(sorted(Counter(config["products"][c]["specification"]["canonical_uom"] for c in codes).items())),
            "active_listings_by_product":dict(sorted(Counter(r["product_code"] for r in rows["listings"]
                                                           if r["status"]=="active").items())),
            "listings_by_supplier":dict(sorted(Counter(r["supplier_slot_id"] for r in rows["listings"]).items())),
            "offers_by_product":dict(sorted(Counter(r["product_code"] for r in rows["offers"]).items())),
            "supplier_markets":sorted({a["market_code"] for a in assoc if a["role"]=="supplier"}),
            "importer_markets":sorted({a["market_code"] for a in assoc if a["role"]=="importer"}),
            "eligible_scope_approved":False}


def build_projection(allocation, company, config, bindings):
    included,offline,unresolved = membership(config)
    slots,portfolio = _portfolio_refs(allocation,company)
    selected = unique_index(allocation["selected_products"],lambda r:r["product_code"])
    require(selected.keys() == config["products"].keys(), "SCOPE_MEMBERSHIP_MISMATCH","pinned source catalog")
    assoc,rows,evidence = _subset(included,allocation,portfolio,slots)
    content = {**FLAGS,"version":"1.0.0","approval_status":"proposed","bindings":bindings,
               "included_product_codes":sorted(included),"offline_only_product_codes":sorted(offline),
               "unresolved_product_codes":sorted(unresolved),
               "exclusion_reasons":{**dict.fromkeys(sorted(offline),"RESTRICTED_OFFLINE_QA"),
                                    **dict.fromkeys(sorted(unresolved),"SPECIFICATION_REVIEW_REQUIRED")},
               "historical_products":[selected[k] for k in sorted(selected)],
               "specification_keys":{c:config["products"][c]["specification"]["specification_key"] for c in sorted(included)},
               "portfolio_associations":assoc,**rows,"bilateral_evidence":evidence,
               "counts":scope_counts(included,assoc,rows,evidence)}
    return {"scope_id":"sm04as-"+fingerprint("scope-projection-v1",content).split(":")[1],**content}
