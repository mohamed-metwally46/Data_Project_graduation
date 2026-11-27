"""Reconcile serialized production-shaped listing candidates against exact bound inputs."""
import json

from src.analytics.release_validation import schema_validator, unique_index
from src.synthetic.commercial_config import canonical_decimal, commercial_context, dec, format_canonical_decimal, require
from src.synthetic.commercial_remediation import STRUCTURAL_BLOCK, validate_specification
from src.synthetic.determinism import CLASSIFICATION_CONTEXT, hierarchical_external_id
from src.synthetic.listing_stage import FIXTURE_NAMESPACE, FIXTURE_POPULATION

SCHEMA = "listing_stage.remediation.v1"
COMMERCIAL_FIELDS = ("price","unit","stock","moq","quantity_increment","maximum_order_quantity","status")
REGISTRY_FIELDS = ("external_id","logical_key","display_code","population_id","supplier_external_id",
                   "product_external_id","variant")


def canonical_listing_terms(row, units):
    """Version 1.1 lexical encoding without numerical changes to exact approved terms."""
    scale = units[row["unit"]]["precision"]
    price = row["price"]
    changes = {key:format_canonical_decimal(dec(row[key]),scale,allow_zero_stock=key=="stock")
               for key in ("stock","moq","quantity_increment","maximum_order_quantity")
               if row[key] is not None}
    return {**row,**changes,"price":{**price,"amount":format_canonical_decimal(dec(price["amount"]),2),
            "basis_quantity":format_canonical_decimal(dec(price["basis_quantity"]),scale)}}


def _unique_object(pairs):
    obj = dict(pairs)
    require(len(obj) == len(pairs), "DUPLICATE_JSON_MEMBER", "repeated JSON object member")
    return obj


def validate_serialized(root, path, **expected):
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    return validate_population_bundle(root, data, **expected)


@commercial_context
def validate_population_bundle(root, data, *, scope, catalog, policies, company, allocation,
                               commercial, commercial_profiles, units):
    """The fixture path uses the same schema, scope and semantic checks as future publication."""
    schema_validator(root, SCHEMA).validate(data)
    meta = data["metadata"]
    fixture = scope["fixture_only"] is True
    if not fixture:
        require(False, STRUCTURAL_BLOCK, "production scope is not approved")
    require(scope["root_namespace"] == FIXTURE_NAMESPACE and scope["population_id"] == FIXTURE_POPULATION
            and scope["plan_id"].startswith("fixture-") and scope["structural_plan_id"].startswith("fixture-")
            and scope["company_stage_id"].startswith("fixture-") and scope["source_release"].startswith("fixture-"),
            "INVALID_FIXTURE_SCOPE", "fixture trust inputs require independent namespaces and provenance")
    binding = {k:scope[k] for k in ("fixture_only","population_id","plan_id","configuration_fingerprint")}
    require(all(meta[k] == v for k,v in binding.items()), "LISTING_SCOPE_MISMATCH", "candidate metadata")
    require(len(data["products"]) == scope["product_count"] > 0
            and len(data["listings"]) == scope["listing_count"] > 0
            and len(data["planning_to_listing"]) == scope["listing_count"]
            and len(data["identity_registry"]) == scope["listing_count"],
            "POPULATION_CARDINALITY_MISMATCH", "approved fixture scope")

    def identity(entity, *key):
        return str(hierarchical_external_id(scope["root_namespace"],scope["population_id"],entity,*key))

    product_rows = unique_index(data["products"], lambda row:row["source_product_code"])
    product_ids = unique_index(data["products"], lambda row:row["external_id"])
    source_catalog = unique_index(catalog, lambda row:row["product_code"])
    profiles = unique_index(commercial_profiles, lambda row:row["product_code"])
    require(source_catalog.keys() == product_rows.keys() == profiles.keys(),
            "PRODUCT_REFERENCE_MISMATCH", "candidate product coverage")
    for code, item in product_rows.items():
        spec = validate_specification(item, policies.get(code))
        require(item["reference_description"] == source_catalog[code]["reference_description"]
                and item["classification_context"] == CLASSIFICATION_CONTEXT
                and item["external_id"] == identity("product", CLASSIFICATION_CONTEXT, code)
                and spec["specification_key"] == item["specification_key"],
                "PRODUCT_REFERENCE_MISMATCH", code)

    roles = unique_index(company["company_roles"], lambda row:row["external_id"])
    companies = unique_index(company["companies"], lambda row:row["external_id"])
    assocs = unique_index(company["company_products"], lambda row:row["external_id"])
    slots = unique_index(company["slot_company_mapping"], lambda row:row["planning_slot_id"])
    structures = unique_index(allocation, lambda row:row["listing_id"])
    quantities = unique_index(commercial, lambda row:row["listing_id"])
    listed = unique_index(data["listings"], lambda row:row["planning_listing_id"])
    listing_ids = unique_index(data["listings"], lambda row:row["external_id"])
    unique_index(data["listings"], lambda row:tuple(row["logical_key"]))
    unique_index(data["listings"], lambda row:row["display_code"])
    registry = unique_index(data["identity_registry"], lambda row:row["external_id"])
    unique_index(data["identity_registry"], lambda row:row["display_code"])
    mapping = unique_index(data["planning_to_listing"], lambda row:row["planning_listing_id"])
    unique_index(data["planning_to_listing"], lambda row:row["listing_external_id"])
    require(structures.keys() == quantities.keys() == listed.keys() == mapping.keys()
            and registry.keys() == listing_ids.keys(),
            "PLAN_RELATIONSHIP_MISMATCH", "exact listing, commercial, registry and mapping coverage")
    for ref, item in listed.items():
        approved = structures[ref]
        values = quantities[ref]
        code = approved["product_code"]
        spec = validate_specification(item, policies.get(code))
        validate_specification({**values,"unit":values["unit"]}, policies.get(code))
        require(item["source_product_code"] == code
                and item["product_external_id"] in product_ids
                and product_ids[item["product_external_id"]]["source_product_code"] == code,
                "PRODUCT_REFERENCE_MISMATCH", ref)
        slot = slots.get(approved["supplier_slot_id"], {})
        supplier = companies.get(item["supplier_external_id"], {})
        role = roles.get(item["supplier_role_external_id"], {})
        assoc = assocs.get(item["supplier_product_association_external_id"], {})
        require(slot.get("company_external_id") == item["supplier_external_id"]
                and slot.get("role_external_id") == item["supplier_role_external_id"]
                and slot.get("initial_role") == "supplier" and code in slot.get("product_codes", ())
                and supplier.get("market_code") == item["market_code"]
                and item["market_code"] == slot.get("market_code")
                and role.get("company_external_id") == item["supplier_external_id"] and role.get("role") == "supplier"
                and assoc.get("company_external_id") == item["supplier_external_id"]
                and assoc.get("role_external_id") == item["supplier_role_external_id"]
                and assoc.get("source_product_code") == code and assoc.get("source_market_code") == item["market_code"]
                and assoc.get("observed_role") == "exporter",
                "SUPPLIER_ASSOCIATION_MISMATCH", ref)
        key = [item["supplier_external_id"], item["product_external_id"], "default"]
        uid = item["external_id"]
        require(item["logical_key"] == key and item["variant"] == "default"
                and uid == identity("listing",*key) and item["population_id"] == scope["population_id"],
                "LISTING_IDENTITY_MISMATCH", ref)
        require(registry[uid] == {**{k:item[k] for k in REGISTRY_FIELDS},"originating_plan_id":scope["plan_id"],
                                   "originating_planning_listing_id":ref,"identity_status":"active"}
                and mapping[ref] == {"planning_listing_id":ref,"listing_external_id":uid,
                                     "display_code":item["display_code"]},
                "LISTING_REGISTRY_MISMATCH", ref)
        require(item["provenance"] == {
            "source_release":scope["source_release"],"structural_plan_id":scope["structural_plan_id"],
            "company_stage_id":scope["company_stage_id"],"commercial_plan_id":scope["plan_id"],
            "configuration_fingerprint":scope["configuration_fingerprint"],
            "configuration_version":scope["configuration_version"],
        } and values["supplier_slot_id"] == approved["supplier_slot_id"] and values["product_code"] == code
          and item["status"] == approved["status"] and all(item[k] == values[k] for k in COMMERCIAL_FIELDS),
                "COMMERCIAL_PLAN_VALUE_MISMATCH", ref)
        price = item["price"]
        profile = profiles[code]
        scale = units[spec["canonical_uom"]]["precision"]
        amount = canonical_decimal(price["amount"],2)
        basis = canonical_decimal(price["basis_quantity"],scale)
        stock = canonical_decimal(item["stock"],scale,allow_zero_stock=True)
        moq = canonical_decimal(item["moq"],scale)
        increment = canonical_decimal(item["quantity_increment"],scale)
        limit = item["maximum_order_quantity"]
        maximum = canonical_decimal(limit,scale) if limit is not None else None
        stock_low, stock_high = map(dec,profile["stock_bounds"])
        moq_low, moq_high = map(dec,profile["moq_bounds"])
        price_low, price_high = map(dec,profile["price_bounds"])
        variation_low, variation_high = map(dec,profile["price_variation"]["listing"])
        reference = dec(profile["reference_price"])
        require(price["currency"] == "USD" and price["basis_unit"] == item["unit"] and basis == 1
                and profile["measurement_unit"] == item["unit"]
                and increment == dec(profile["quantity_increment"])
                and (maximum is None if profile["maximum_order_quantity"] is None
                     else maximum == dec(profile["maximum_order_quantity"]))
                and price_low <= amount <= price_high
                and reference*(1+variation_low) <= amount <= reference*(1+variation_high)
                and (stock == 0 or stock_low <= stock <= stock_high) and moq_low <= moq <= moq_high
                and moq % increment == 0 and (maximum is None or maximum >= moq)
                and (item["status"] != "active" or stock >= moq)
                and (item["status"] != "out_of_stock" or stock == 0)
                and (item["status"] != "active" or stock > 0),
                "INVALID_CANONICAL_COMMERCIAL_VALUE", ref)
    return {"status":"production_shaped_fixture_validated", "products":len(product_rows), "listings":len(listed)}


def validate_for_publication(root, serialized_path, **expected):
    """Publication boundary. Fixture validation never grants write authority."""
    outcome = validate_serialized(root, serialized_path, **expected)
    require(False, STRUCTURAL_BLOCK, "no production scope is authorized for publication")
    return outcome
