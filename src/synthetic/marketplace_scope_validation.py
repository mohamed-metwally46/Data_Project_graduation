"""Independent validation and approval checks for an eligibility-filtered scope."""
from collections import Counter
from contextlib import closing
import sqlite3

from src.analytics.observed import ELIGIBLE_ROWS
from src.analytics.release_validation import schema_validator, unique_index
from src.synthetic.commercial_config import canonical_decimal, commercial_context, dec, extended, format_canonical_decimal, require
from src.synthetic.commercial_planning import solve
from src.synthetic.marketplace_scope import RELATIONS, coverage, membership, scope_counts
from src.synthetic.planning import fingerprint

PACKAGE_METHOD = "sm04as-specification-and-scope-review-v1"


def observed_evidence(root, source_manifest, products):
    database = root/source_manifest["inputs"]["processed_sqlite"]["path"]
    with closing(sqlite3.connect(database.as_uri()+"?mode=ro&immutable=1",uri=True)) as db:
        observed = {(code,e,i) for code,e,i in db.execute(
            f"SELECT product_code, exporter_code, importer_code FROM enriched_trade_data WHERE {ELIGIBLE_ROWS}"
        ) if code in products}
    return observed


def validate_projection(root, projection, diagnostics, allocation, company, config, bindings, observed):
    schema_validator(root,"marketplace_scope.v1").validate(projection)
    schema_validator(root,"commercial.scope.proposed.v1").validate(config)
    included,offline,unresolved=membership(config)
    selected=unique_index(allocation["selected_products"],lambda r:r["product_code"])
    require(included|offline|unresolved == selected.keys()
            and projection["included_product_codes"] == sorted(included)
            and projection["offline_only_product_codes"] == sorted(offline)
            and projection["unresolved_product_codes"] == sorted(unresolved)
            and projection["exclusion_reasons"] == {**dict.fromkeys(offline,"RESTRICTED_OFFLINE_QA"),
                                                    **dict.fromkeys(unresolved,"SPECIFICATION_REVIEW_REQUIRED")}
            and unique_index(projection["historical_products"],lambda r:r["product_code"]) == selected
            and projection["specification_keys"] == {c:config["products"][c]["specification"]["specification_key"] for c in included}
            and projection["bindings"] == bindings,
            "SCOPE_MEMBERSHIP_MISMATCH","catalog, specifications or provenance")
    slots=unique_index(allocation["company_slots"],lambda r:r["slot_id"])
    maps=unique_index(company["slot_company_mapping"],lambda r:r["planning_slot_id"])
    roles=unique_index(company["company_roles"],lambda r:r["external_id"])
    companies=unique_index(company["companies"],lambda r:r["external_id"])
    company_to_slot=unique_index(company["slot_company_mapping"],lambda r:r["company_external_id"])
    associations={}
    for a in company["company_products"]:
        code=a["source_product_code"]
        m=company_to_slot[a["company_external_id"]]
        slot=slots[m["planning_slot_id"]]
        role=roles[a["role_external_id"]]
        require(role["company_external_id"] == a["company_external_id"] and role["role"] == slot["role"]
                and slot["market_code"] == a["source_market_code"] == companies[a["company_external_id"]]["market_code"]
                and m["role_external_id"] == a["role_external_id"] and code in slot["product_codes"],
                "SCOPE_PORTFOLIO_MISMATCH",m["planning_slot_id"])
        if code in included:
            require(a["external_id"] not in associations, "DUPLICATE_SCOPE_ASSOCIATION",code)
            associations[a["external_id"]]={"slot_id":m["planning_slot_id"],"role":slot["role"],"product_code":code,
                  "market_code":slot["market_code"],"association_external_id":a["external_id"],"company_display_code":m["display_code"]}
    actual_assoc=unique_index(projection["portfolio_associations"],lambda r:r["association_external_id"])
    require(actual_assoc==associations and {(r["slot_id"],r["product_code"]) for r in actual_assoc.values()}==
            {(s["slot_id"],c) for s in slots.values() for c in set(s["product_codes"])&included}
            and slots.keys()==maps.keys(),"SCOPE_PORTFOLIO_MISMATCH","exact retained associations")
    by_relation={}
    for key,(section,id_field) in RELATIONS.items():
        expected=unique_index([r for r in allocation[section] if r["product_code"] in included],lambda r:r[id_field])
        actual=unique_index(projection[key],lambda r:r[id_field])
        require(expected == actual,"SCOPE_RELATIONSHIP_MISMATCH",section)
        by_relation[key]=actual
    listings,rfqs,offers=(by_relation[k] for k in ("listings","rfqs","offers"))
    role_lookup={(r["slot_id"],r["product_code"]):r["role"] for r in associations.values()}
    for listing in listings.values():
        require(role_lookup.get((listing["supplier_slot_id"],listing["product_code"])) == "supplier",
                "ORPHAN_SCOPE_LISTING",listing["listing_id"])
    response=Counter()
    evidence={}
    for r in rfqs.values():
        require(role_lookup.get((r["buyer_slot_id"],r["product_code"]))=="importer"
                and slots[r["buyer_slot_id"]]["market_code"]==r["destination_market"],
                "ORPHAN_SCOPE_RFQ",r["request_id"])
        if r["type"]=="targeted":
            evidence[("targeted_rfq",r["request_id"])]=(r["product_code"],slots[r["target_supplier_slot_id"]]["market_code"],r["destination_market"])
    respondents=set()
    for o in offers.values():
        r,l=rfqs[o["request_id"]],listings[o["listing_id"]]
        pair=(r["request_id"],o["supplier_slot_id"])
        require(l["status"]=="active" and l["product_code"]==r["product_code"]==o["product_code"]
                and l["supplier_slot_id"]==o["supplier_slot_id"] and pair not in respondents
                and (r["type"]!="targeted" or r["target_supplier_slot_id"]==o["supplier_slot_id"]),
                "ORPHAN_SCOPE_OFFER",o["offer_id"])
        respondents.add(pair)
        response[o["request_id"]]+=1
        evidence[("offer",o["offer_id"])]=(o["product_code"],slots[o["supplier_slot_id"]]["market_code"],r["destination_market"])
    require(all(response[r["request_id"]]==r["response_count"] for r in rfqs.values()),
            "SCOPE_RESPONSE_COUNT_MISMATCH","approved RFQ allocations")
    actual=unique_index(projection["bilateral_evidence"],lambda r:(r["kind"],r["reference"]))
    require({k:(v["product_code"],v["exporter_market"],v["importer_market"]) for k,v in actual.items()}==evidence
            and all(a in observed and a[1]!=a[2] for a in evidence.values()),
            "SCOPE_EVIDENCE_MISMATCH","Category A observed triples")
    independent=scope_counts(included,list(associations.values()),
                             {k:list(v.values()) for k,v in by_relation.items()},list(actual.values()))
    require(independent==projection["counts"]==diagnostics["scope_counts"]["proposed"]
            and diagnostics==coverage(allocation,company,config),
            "SCOPE_COVERAGE_MISMATCH","independent coverage recalculation")
    content={k:v for k,v in projection.items() if k!="scope_id"}
    require("sm04as-"+fingerprint("scope-projection-v1",content).split(":")[1]==projection["scope_id"],
            "SCOPE_FINGERPRINT_MISMATCH","projection content")
    return {"status":"validated_proposed_scope","counts":independent,"corrected_feasibility_validated":False}


def require_exact_approval(package, approval):
    exact = fingerprint(PACKAGE_METHOD,package)
    expected={
        "package_fingerprint":exact,"scope_id":package["scope_id"],
        "eligible_codes_fingerprint":package["eligible_codes_fingerprint"],
        "specification_fingerprint":package["specification_fingerprint"],
        "configuration_fingerprint":package["configuration_fingerprint"],
        "coverage_fingerprint":package["coverage_fingerprint"],
        "authorize":"corrected_provisional_commercial_planning_only",
    }
    require(isinstance(approval,dict) and set(approval)=={*expected,"authority"}
            and all(approval[k]==v for k,v in expected.items())
            and isinstance(approval.get("authority"),str) and approval["authority"].strip(),
            "EXACT_SCOPE_APPROVAL_REQUIRED","exact eligible codes, specifications, commercial values and coverage exceptions")
    return exact


def planning_inputs(package, approval, projection, config, diagnostics):
    """Prepare inputs for the shared solver after explicit approval of verified artifacts."""
    require_exact_approval(package,approval)
    included,_,_=membership(config)
    require(projection["scope_id"]==package["scope_id"]
            and "sm04as-"+fingerprint("scope-projection-v1",{k:v for k,v in projection.items() if k!="scope_id"}).split(":")[1]==package["scope_id"]
            and projection["included_product_codes"]==sorted(included)
            and fingerprint(sorted(included))==package["eligible_codes_fingerprint"]
            and fingerprint(config)==package["configuration_fingerprint"]
            and fingerprint({c:config["products"][c]["specification"] for c in sorted(included)})==package["specification_fingerprint"]
            and fingerprint(diagnostics)==package["coverage_fingerprint"],
            "EXACT_SCOPE_BINDING_CHANGED","approved scope projection, configuration or coverage")
    profiles=[]
    for code in sorted(included):
        row=config["products"][code]
        terms=row["commercial_terms"]
        scale=terms["quantity_precision"]
        canonical={k:format_canonical_decimal(dec(terms[k]),scale)
                   for k in ("price_basis_quantity","quantity_increment","maximum_order_quantity")
                   if terms[k] is not None}
        spec=row["specification"]
        profiles.append({**terms,**canonical,"scope_specification":{
            "specification_key":spec["specification_key"],"physical_form":spec["physical_form"]}})
    return (
        {"master_seed":config["master_seed"],"units":config["unit_registry"],"total_precision":2,
         "inactive_zero":package["proposed_inactive_zero"]},
        profiles,
        {section:projection[key] for key,(section,_) in RELATIONS.items()},
    )


def solve_for_approved_scope(package, approval, projection, config, diagnostics):
    """Use only the approved projection. The CLI verifies published inputs before this boundary."""
    solver_config, profiles, allocation = planning_inputs(package,approval,projection,config,diagnostics)
    measures={}
    result=solve(solver_config,profiles,allocation,measures)
    specs={row["product_code"]:row["scope_specification"] for row in profiles}
    for rows in result.values():
        for row in rows:
            row.update(specs[row["product_code"]])
    validate_scoped_commercial(result,projection,profiles,solver_config)
    return result, measures


@commercial_context
def validate_scoped_commercial(candidate, projection, profiles, policy):
    """Reconcile exact scoped relationships and independently check commercial constraints."""
    product=unique_index(profiles,lambda r:r["product_code"])
    require(product.keys()==set(projection["included_product_codes"]),
            "SCOPED_COMMERCIAL_MISMATCH","approved profile membership")
    collections={}
    for key,(_,id_field) in RELATIONS.items():
        original=unique_index(projection[key],lambda r:r[id_field])
        actual=unique_index(candidate[key],lambda r:r[id_field])
        require(len(actual)==projection["counts"][key] and actual.keys()==original.keys()
                and all(all(actual[ref][k]==v for k,v in row.items()) and all(actual[ref].get(k)==v
                        for k,v in product[row["product_code"]]["scope_specification"].items())
                        for ref,row in original.items()),
                "SCOPED_COMMERCIAL_MISMATCH",key)
        collections[key]=actual

    def price(p, record, kind, anchor):
        quote=canonical_decimal(record["amount"],p["quoted_price_precision"])
        lo,hi=map(dec,p["price_variation"][kind])
        minimum,maximum=map(dec,p["price_bounds"])
        require(record["currency"]==p["currency"] and record["basis_quantity"]==p["price_basis_quantity"]
                and record["basis_unit"]==p["price_basis_unit"] and minimum<=quote<=maximum
                and anchor*(1+lo)<=quote<=anchor*(1+hi),
                "SCOPED_PRICE_CONFLICT",p["product_code"])
        return quote

    inactive_zero=0
    for row in collections["listings"].values():
        p=product[row["product_code"]]
        scale=p["quantity_precision"]
        stock=canonical_decimal(row["stock"],scale,allow_zero_stock=True)
        moq=canonical_decimal(row["moq"],scale)
        inc=dec(p["quantity_increment"])
        minimum,maximum=map(dec,p["moq_bounds"])
        lower,upper=map(dec,p["stock_bounds"])
        max_order=p["maximum_order_quantity"]
        require(row["unit"]==p["measurement_unit"] and row["quantity_increment"]==p["quantity_increment"]
                and row["maximum_order_quantity"]==max_order and minimum<=moq<=maximum and moq%inc==0
                and (stock==0 or lower<=stock<=upper)
                and (row["status"]!="active" or stock>=moq and (max_order is None or dec(max_order)>=moq))
                and (row["status"]!="out_of_stock" or stock==0), "SCOPED_QUANTITY_CONFLICT",row["listing_id"])
        inactive_zero+=row["status"]=="inactive" and stock==0
        price(p,row["price"],"listing",dec(p["reference_price"]))
    require(inactive_zero==policy["inactive_zero"],"SCOPED_QUANTITY_CONFLICT","inactive zero stock count")
    for row in collections["rfqs"].values():
        p=product[row["product_code"]]
        qty=canonical_decimal(row["requested_quantity"],p["quantity_precision"])
        lower,upper=map(dec,p["rfq_quantity_bounds"])
        require(row["unit"]==p["measurement_unit"] and lower<=qty<=upper
                and qty%dec(p["quantity_increment"])==0 and row["target_price_binding"] is False,
                "SCOPED_QUANTITY_CONFLICT",row["request_id"])
        price(p,row["target_price"],"rfq",dec(p["reference_price"]))
    for row in collections["offers"].values():
        p=product[row["product_code"]]
        r=collections["rfqs"][row["request_id"]]
        l=collections["listings"][row["listing_id"]]
        qty=canonical_decimal(row["offered_quantity"],p["quantity_precision"])
        ceiling=dec(l["maximum_order_quantity"]) if l["maximum_order_quantity"] else dec(l["stock"])
        require(row["unit"]==r["unit"]==l["unit"] and l["status"]=="active" and row["category"]=="A"
                and row["offered_quantity"]==r["requested_quantity"] and dec(l["moq"])<=qty<=min(dec(l["stock"]),ceiling)
                and row["fulfillment"]=="full_independent_no_reservation",
                "SCOPED_FULFILLMENT_CONFLICT",row["offer_id"])
        price(p,row["price"],"offer",dec(l["price"]["amount"]))
        require(row["extended_product_value"]==extended(row["price"],row["offered_quantity"],row["unit"],
                     policy["units"],p["permitted_units"],policy["total_precision"]),
                "SCOPED_EXTENDED_VALUE_MISMATCH",row["offer_id"])
