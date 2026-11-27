"""Deterministic fictional company identities and isolated fixture entry point."""
from itertools import product
import hashlib
import json
import re
from string import Formatter
import unicodedata

from src.analytics.release_validation import read_json
from src.synthetic.allocation import product_group
from src.synthetic.determinism import display_code, hierarchical_external_id, named_random_stream

CONFIG_PATH = "configs/synthetic/company_identity.v1.json"
FIXTURE_NAMESPACE = "699ac317-a77a-5efb-b877-0f75491992f2"
FIXTURE_MAX = 12
ROLES = ("supplier", "importer")
CONTRACT_VERSION = "1.0.0"
ROLE_TYPES = {
    "supplier": {"trading_company", "wholesale_distributor", "export_trading_company", "diversified_trading_company"},
    "importer": {"trading_company", "import_distribution_company", "procurement_sourcing_company", "diversified_trading_company"},
}
INDUSTRY_GROUPS = {"agriculture_and_food", "textiles_and_apparel", "diversified_trading", "general_trading"}
APPROVALS = ("sm02_baseline", "geography", "identity_templates", "uuid_namespace_and_keys",
             "backend_company_contract", "company_only_authorization")
FORBIDDEN = re.compile(
    r"\b(?:verified|certified|accredited|government|official|guaranteed|inc|llc|ltd|corp|plc|gmbh|"
    r"registered|revenue|transactions|factory|customers|inventory|capacity|shipping)\b", re.IGNORECASE,
)


def read_templates(root):
    settings = read_json(root / CONFIG_PATH)
    check_fixture_settings(settings)
    return settings


def template_fingerprint(settings):
    canonical = json.dumps(settings, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def safe_text(value, limit=400):
    return (isinstance(value, str) and 1 <= len(value) <= limit and value == value.strip()
            and all(c.isprintable() for c in value) and not FORBIDDEN.search(value))


def check_fixture_settings(settings):
    if (settings.get("version") != "1.0.0" or settings.get("status") != "fixture_only"
            or settings.get("fixture_namespace") != FIXTURE_NAMESPACE
            or type(settings.get("fixture_seed")) is not int or settings["fixture_seed"] < 0
            or settings.get("approvals") != dict.fromkeys(APPROVALS)):
        raise ValueError("SM-03A requires fixture-only settings and an isolated, unapproved namespace")
    if settings["approved_identity"] != {"master_seed": 42, "strategy": "deterministic_context_aware",
                                          "visual_strategy": "deterministic_monogram"}:
        raise ValueError("Invalid approved identity policy")
    presentation = settings["presentation"]
    if (presentation["profile_language"] != "en" or presentation["max_name_length"] != 100
            or presentation["max_description_length"] != 400
            or type(presentation["website_enabled"]) is not bool
            or presentation["verification_status"] != "not_verified"
            or not presentation["palettes"] or not set(presentation["palettes"]) <= {
                "forest_green", "ocean_blue", "slate", "warm_amber", "plum"}
            or not set(settings["industry_groups"].values()) <= INDUSTRY_GROUPS):
        raise ValueError("Invalid company presentation settings")
    if type(settings["max_name_attempts"]) is not int or not 1 <= settings["max_name_attempts"] <= 256:
        raise ValueError("Invalid collision search budget")
    for field in ("brand_starts", "brand_ends"):
        items = settings[field]
        if not items or any(not re.fullmatch(r"[A-Za-z]{2,12}", item) for item in items):
            raise ValueError("Invalid fictional brand components")
    for role in ROLES:
        entry = settings["role_templates"][role]
        if not entry["business_types"] or not set(entry["business_types"]) <= ROLE_TYPES[role]:
            raise ValueError(f"Incompatible controlled business type for {role}")
        for field in ("descriptors", "business_types", "descriptions"):
            if not entry[field] or not all(safe_text(value) for value in entry[field]):
                raise ValueError(f"Invalid identity template {role}/{field}")
        for template in entry["descriptions"]:
            parsed = list(Formatter().parse(template))
            substitutions = [field for _, field, _, _ in parsed if field is not None]
            if (sorted(substitutions) != ["focus", "market"] or any(spec or conversion for _,_,spec,conversion in parsed)
                    or role not in template.lower()
                    or not template.lower().startswith(("fictional", "synthetic demo"))):
                raise ValueError("Description requires explicit fictional role, market and portfolio focus")
    values = [*settings["group_labels"].values(), settings["mixed_focus"], settings["generic_focus"]]
    if not all(safe_text(value) for value in values):
        raise ValueError("Invalid portfolio presentation label")


def check_fixture_scope(plan, settings):
    check_fixture_settings(settings)
    if (plan.get("fixture_only") is not True
            or not str(plan.get("plan_id", "")).startswith("fixture-")
            or not str(plan.get("source", {}).get("release_id", "")).startswith("fixture-")
            or not 1 <= len(plan.get("company_slots", ())) <= FIXTURE_MAX):
        raise ValueError("SM-03A accepts only isolated fixture plans")


def normalized_brand(name):
    return "".join(char for char in unicodedata.normalize("NFKC", name).casefold() if char.isalnum())


def near_duplicate(left, right):
    """Exact, one replacement, or one insertion/deletion in normalized brands."""
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) <= 1
    if len(left) > len(right):
        left, right = right, left
    return len(right) - len(left) == 1 and any(
        left == right[:pos] + right[pos + 1:] for pos in range(len(right))
    )


def available_brand(choices, attempts, seed, cohort, neutral_key, used):
    rng = named_random_stream(seed, cohort, neutral_key, "brand")
    for candidate in rng.sample(choices, min(len(choices), attempts)):
        normalized = normalized_brand(candidate)
        if safe_text(candidate) and not any(near_duplicate(normalized, prev) for prev in used):
            used.append(normalized)
            return candidate
    raise ValueError("Fictional brand collision budget exhausted")


def fixture_company_id(namespace, cohort, neutral_key):
    if namespace != FIXTURE_NAMESPACE:
        raise ValueError("Only the isolated fixture namespace is permitted in SM-03A")
    return str(hierarchical_external_id(namespace, cohort, "company", neutral_key))


def portfolio_focus(settings, codes):
    groups = {product_group(code) for code in codes}
    if len(groups) != 1:
        return settings["mixed_focus"]
    return settings["group_labels"].get(next(iter(groups)), settings["generic_focus"])


def fictional_contacts(code):
    host = f"{code.lower()}.example"
    return f"sales@{host}", f"https://{host}"


def company_context(slot, selected, geo, provenance):
    """Resolve a single slot against the existing catalog, retaining only its assigned portfolio."""
    market, role = slot["market_code"], slot["role"]
    codes = slot["product_codes"]
    if (role not in ROLES or market not in geo or not geo[market][f"{role}_eligible"]
            or not codes or len(codes) != len(set(codes)) or not set(codes) <= selected.keys()):
        raise ValueError("Company slot has incompatible market, role or portfolio")
    products = [selected[code] for code in codes]
    if any(row.get("provisional_group", product_group(row["product_code"])) != product_group(row["product_code"])
           for row in products):
        raise ValueError("Assigned product prefix group disagrees with the catalog")
    groups = {product_group(r["product_code"]) for r in products}
    return {"slot_id": slot["slot_id"], "market_code": market, "market_name": geo[market]["name"],
            "role": role, "product_codes": list(codes),
            "reference_descriptions": [r.get("reference_description") for r in products],
            "groups": groups, "provenance": provenance}


def presentation_group(settings, context):
    if len(context["groups"]) > 1:
        return "diversified_trading"
    if not all(context["reference_descriptions"]):
        return "general_trading"
    group = next(iter(context["groups"]))
    return settings["industry_groups"].get(group, "general_trading")


def monogram(name, settings, seed, cohort, neutral):
    palette = named_random_stream(seed, cohort, neutral, "monogram").choice(
        settings["presentation"]["palettes"]
    )
    initials = "".join(word[0] for word in name.split()[:2]).upper()
    return {"type": "monogram", "initials": initials, "palette_key": palette}


def build_fixture_companies(plan, geo, settings, registry=()):
    """Return in-memory fixture collections in the isolated namespace."""
    check_fixture_scope(plan, settings)
    return _build_companies(plan, geo, settings, registry, cohort=plan["plan_id"],
                            namespace=settings["fixture_namespace"], seed=settings["fixture_seed"],
                            fixture_only=True)


def _build_companies(plan, geo, settings, registry, *, cohort, namespace, seed, fixture_only, timings=None):
    from time import perf_counter

    plan_id = plan["plan_id"]
    settings_scope = ["fixture" if fixture_only else "population", cohort]
    choices = tuple(dict.fromkeys("".join(parts) for parts in product(
        settings["brand_starts"], settings["brand_ends"])))
    selected = {row["product_code"]: row for row in plan["selected_products"]}
    provenance = {"allocation_plan_id": plan_id, **plan["source"]}
    registry_started = perf_counter()
    prior = {row["originating_planning_slot_id"]: row for row in registry}
    if (len(prior) != len(registry) or any(r["population_id"] != cohort or r["originating_plan_id"] != plan_id
            for r in registry) or not prior.keys() <= {slot["slot_id"] for slot in plan["company_slots"]}):
        raise ValueError("Registry belongs to a different population or requires explicit identity reconciliation")
    used = [normalized_brand(r["reserved_brand"]) for r in registry]
    reserved_keys = {r["persistent_company_key"] for r in registry}
    reserved_codes = {r["display_code"] for r in registry}
    if len(reserved_keys) != len(registry) or len(reserved_codes) != len(registry):
        raise ValueError("Duplicate persistent identity registry key or display code")
    next_ordinal = max((int(r["persistent_company_key"].split("-")[-1]) for r in registry), default=0)
    registry_seconds = perf_counter() - registry_started
    payload = {key: [] for key in ("companies", "company_roles", "company_products", "slot_company_mapping",
                                    "identity_registry")}
    for slot in sorted(plan["company_slots"], key=lambda row: row["slot_id"]):
        context = company_context(slot, selected, geo, provenance)
        role, market = context["role"], context["market_code"]
        previous = prior.get(slot["slot_id"])
        registry_started = perf_counter()
        if previous is None:
            next_ordinal += 1
            while display_code("CMP", next_ordinal) in reserved_codes:
                next_ordinal += 1
            neutral = f"identity-{next_ordinal:06d}"
            code = display_code("CMP", next_ordinal)
            uid = str(hierarchical_external_id(namespace, cohort, "company", neutral))
            registry_seconds += perf_counter() - registry_started
            brand = available_brand(choices, settings["max_name_attempts"], seed, cohort, neutral, used)
        else:
            neutral, code, uid, brand = (previous[k] for k in ("persistent_company_key", "display_code",
                                                              "external_id", "reserved_brand"))
            if uid != str(hierarchical_external_id(namespace, cohort, "company", neutral)) or previous["identity_status"] != "active":
                raise ValueError("Registry entry cannot reuse a retired or mismatched identity")
            registry_seconds += perf_counter() - registry_started
        options = settings["role_templates"][role]

        def choose(field):
            return named_random_stream(seed, *settings_scope, neutral, field).choice(options[field])

        focus = portfolio_focus(settings, context["product_codes"])
        email, website = fictional_contacts(code)
        role_id = str(hierarchical_external_id(namespace, cohort, "company_role", uid, role))
        name = previous["reserved_name"] if previous else f'{brand} {choose("descriptors")}'
        description = choose("descriptions").format(market=context["market_name"], focus=focus)
        if not safe_text(name, 100) or not safe_text(description):
            raise ValueError("Generated name or description violates text policy")
        payload["companies"].append({
            "external_id": uid, "display_code": code, "brand": brand, "name": name,
            "description": description, "profile_language": settings["presentation"]["profile_language"],
            "industry_group": presentation_group(settings, context),
            "portfolio_focus": focus, "business_type": choose("business_types"), "market_code": market,
            "email": email, "website": website if settings["presentation"]["website_enabled"] else None,
            "phone": None, "street_address": None,
            "tax_identifier": None, "registration_number": None,
            "visual_identity": monogram(name, settings, seed, cohort, neutral),
            "verification_status": settings["presentation"]["verification_status"], "is_synthetic": True,
            "population_id": cohort, "provenance": provenance,
        })
        payload["company_roles"].append({"external_id": role_id, "company_external_id": uid, "role": role})
        payload["slot_company_mapping"].append({
            "planning_slot_id": slot["slot_id"], "plan_id": plan_id, "company_external_id": uid,
            "identity_slot_key": neutral, "display_code": code, "market_code": market,
            "role_external_id": role_id, "product_codes": list(context["product_codes"]), "initial_role": role,
        })
        registry_started = perf_counter()
        payload["identity_registry"].append({
            "population_id": cohort, "persistent_company_key": neutral,
            "originating_planning_slot_id": slot["slot_id"], "originating_plan_id": plan_id,
            "external_id": uid, "display_code": code, "identity_status": "active",
            "reserved_brand": brand, "reserved_name": name,
        })
        registry_seconds += perf_counter() - registry_started
        for product_code in context["product_codes"]:
            payload["company_products"].append({
                "external_id": str(hierarchical_external_id(namespace, cohort, "company_product", role_id, product_code)),
                "company_external_id": uid, "role_external_id": role_id, "source_product_code": product_code,
                "source_market_code": market, "observed_role": "exporter" if role == "supplier" else "importer",
                **plan["source"],
            })
    if timings is not None:
        timings["registry_generation"] = registry_seconds
    return {"metadata": {"contract_version": CONTRACT_VERSION, "stage": "SM-03A" if fixture_only else "SM-03B",
                         "fixture_only": fixture_only, "importable": False, "plan_id": plan_id,
                         "population_id": cohort, "identifier_algorithm": "hierarchical_uuid5_v1",
                         "is_synthetic": True, "is_intermediate": True,
                         "backend_importable": False, "full_marketplace_release": False,
                         "source": plan["source"], "template_version": settings["version"],
                         "configuration_fingerprint": template_fingerprint(settings),
                         "identity_namespace": namespace},
            **payload}
