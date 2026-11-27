"""Proposed product profiles, controlled units, and exact commercial arithmetic."""
from decimal import Context, Decimal, DivisionByZero, InvalidOperation, Overflow, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
from fractions import Fraction
from functools import wraps
import re

from src.analytics.release_validation import read_json
from src.synthetic.determinism import named_random_stream

CONFIG = "configs/synthetic/commercial.v1.json"
DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
PRODUCT = re.compile(r"[0-9]{6}|9999AA")
DECISIONS = {f"SM-04.R{i}": "D" for i in range(1, 8)}
APPROVALS = ("commercial_configuration", "commercial_plan", "product_key", "listing_key",
             "schemas", "quality_review", "execution")
FLAGS = {"is_synthetic": True, "is_planning_artifact": True,
         "backend_importable": False, "full_marketplace_release": False}
DECIMAL_POLICY = {"version": "1.0.0", "precision": 28, "rounding": "ROUND_HALF_EVEN",
                  "final_money_rounding": "ROUND_HALF_UP",
                  "traps": ["InvalidOperation", "DivisionByZero", "Overflow"],
                  "usd_scale": 2, "quantity_scale": "fixed_configured", "zero_stock": "0"}
_ARITHMETIC = Context(prec=28, rounding=ROUND_HALF_EVEN,
                      traps=[InvalidOperation, DivisionByZero, Overflow])


def commercial_context(function):
    @wraps(function)
    def controlled(*args, **kwargs):
        with localcontext(_ARITHMETIC):
            return function(*args, **kwargs)
    return controlled


class CommercialError(ValueError):
    def __init__(self, code, detail, **context):
        self.finding = {"severity": "BLOCKER", "code": code, "detail": detail, **context}
        super().__init__(f"{code}: {detail}")


def require(condition, code, detail, **context):
    if not condition:
        raise CommercialError(code, detail, **context)


def dec(value):
    require(isinstance(value, str) and DECIMAL.fullmatch(value) is not None and len(value) <= 24,
            "INVALID_DECIMAL", repr(value))
    return Decimal(value)


def decimal_text(value):
    return format(value, "f")


@commercial_context
def format_canonical_decimal(value, scale, *, allow_zero_stock=False):
    if allow_zero_stock and value.is_zero() and not value.is_signed():
        return "0"
    require(value.is_finite() and value > 0 and value == value.quantize(quantum(scale)),
            "NONCANONICAL_DECIMAL", f"expected an exact positive value with scale {scale}")
    return format(value, f".{scale}f")


def canonical_decimal(text, scale, *, allow_zero_stock=False):
    value = dec(text)
    require(text == format_canonical_decimal(value,scale,allow_zero_stock=allow_zero_stock),
            "NONCANONICAL_DECIMAL", f"expected a positive fixed-scale decimal with scale {scale}")
    return value


def quantum(precision):
    return Decimal(1).scaleb(-precision)


@commercial_context
def quantity_ticks(value, precision):
    scaled = dec(value) / quantum(precision)
    require(scaled == scaled.to_integral_value() and scaled >= 0, "INVALID_QUANTITY_PRECISION", value)
    return int(scaled)


@commercial_context
def convert(value, source, target, units, permitted):
    require(source in permitted and target in permitted and source in units and target in units
            and units[source]["dimension"] == units[target]["dimension"],
            "INCOMPATIBLE_UOM", f"{source} to {target}")
    quantity_ticks(value, units[source]["precision"])
    ratio = Fraction(dec(value)) * Fraction(dec(units[source]["factor"])) / Fraction(dec(units[target]["factor"]))
    scale = 10 ** units[target]["precision"]
    ticks = ratio * scale
    require(ticks.denominator == 1, "INVALID_QUANTITY_PRECISION", f"{value} {source} in {target}")
    return Decimal(ticks.numerator).scaleb(-units[target]["precision"])


def normalized_price(price, target, units, permitted):
    basis = convert(price["basis_quantity"], price["basis_unit"], target, units, permitted)
    require(basis > 0 and dec(price["amount"]) > 0, "PRICE_DOMAIN_CONFLICT", "nonpositive price or basis")
    return Fraction(dec(price["amount"])) / Fraction(basis)


@commercial_context
def round_ratio(ratio, precision):
    scaled = ratio * 10 ** precision
    magnitude = abs(scaled)
    cents, remainder = divmod(magnitude.numerator, magnitude.denominator)
    cents += 2 * remainder >= magnitude.denominator
    return Decimal(cents if scaled >= 0 else -cents).scaleb(-precision)


def extended(price, quantity, unit, units, permitted, precision):
    basis_rate = normalized_price(price, unit, units, permitted)
    return decimal_text(round_ratio(basis_rate * Fraction(dec(quantity)), precision))


@commercial_context
def price_domain(bounds, anchor, variation, precision):
    lower = max(dec(bounds[0]), anchor * (1 + dec(variation[0])))
    upper = min(dec(bounds[1]), anchor * (1 + dec(variation[1])))
    import math

    return max(1, math.ceil(Fraction(lower) * 10 ** precision)), math.floor(Fraction(upper) * 10 ** precision)


@commercial_context
def resolve_profiles(config, selected):
    products = {row["product_code"]: row for row in selected}
    require(len(products) == len(selected) and products.keys() == config["products"].keys(),
            "UNRESOLVED_PRODUCT_PROFILE", "selected catalog and explicit profile assignments differ",
            missing=sorted(products.keys() - config["products"].keys()),
            extra=sorted(config["products"].keys() - products.keys()))
    profiles = []
    for code, row in sorted(products.items()):
        override = config["products"][code]
        group = config["groups"][override["group"]]
        values = group | override.get("parameters", {})
        unit = values["unit"]
        usable = values["permitted_units"]
        require(unit in usable and len(usable) == len(set(usable))
                and all(u in config["units"] and config["units"][u]["dimension"] == config["units"][unit]["dimension"]
                        for u in usable), "INCOMPATIBLE_UOM", "profile unit list", product_code=code)
        seed = named_random_stream(config["master_seed"], "product.reference_price", code)
        precision = config["quoted_price_precision"]
        reference = dec(override["reference_price"]) if "reference_price" in override else (
            dec(group["group_reference"]) * Decimal(seed.randint(80, 120)) / 100
        ).quantize(quantum(precision), rounding=ROUND_HALF_UP)
        require(reference > 0 and reference == reference.quantize(quantum(precision)),
                "PRICE_DOMAIN_CONFLICT", "reference price precision or sign", product_code=code)
        bounds = values.get("price_bounds", [decimal_text(reference * Decimal("0.5")),
                                            decimal_text(reference * Decimal("1.5"))])
        variation = config["variation"] | override.get("variation", {})
        q_precision = config["units"][unit]["precision"]
        step = quantity_ticks(values["increment"], q_precision)
        require(step > 0, "NO_VALID_QUANTITY_INCREMENT", "nonpositive order increment", product_code=code)
        for field in ("stock", "moq", "rfq"):
            lo, hi = [quantity_ticks(v, q_precision) for v in values[field]]
            require(0 < lo <= hi, "EMPTY_QUANTITY_DOMAIN", field, product_code=code)
        if values["maximum_order"] is not None:
            require(quantity_ticks(values["maximum_order"], q_precision) > 0,
                    "EMPTY_QUANTITY_DOMAIN", "maximum order", product_code=code)
        require(dec(bounds[0]) > 0 and dec(bounds[0]) <= reference <= dec(bounds[1]),
                "PRICE_DOMAIN_CONFLICT", "reference outside configured domain", product_code=code)
        domains = {}
        for kind in ("listing", "rfq", "offer"):
            lo, hi = (dec(v) for v in variation[kind])
            require(-1 < lo <= hi, "PRICE_DOMAIN_CONFLICT", f"{kind} variation", product_code=code)
            domain = price_domain(bounds, reference, variation[kind], precision)
            require(domain[0] <= domain[1], "PRICE_DOMAIN_CONFLICT", f"{kind} has no representable price",
                    product_code=code)
            if kind != "offer":
                domains[kind] = [decimal_text(Decimal(tick).scaleb(-precision)) for tick in domain]
        profiles.append({
            **row, **FLAGS, "commercial_group": override["group"], "group_assignment": override["group_assignment"],
            "review_notes": override["review_notes"], "measurement_unit": unit, "permitted_units": usable,
            "quantity_precision": q_precision, "reference_price": decimal_text(reference),
            "reference_price_source": "product_override" if "reference_price" in override else "seeded_group_reference",
            "price_bounds": bounds, "price_variation": variation, "initial_price_domains": domains,
            "currency": config["currency"], "price_basis_quantity": "1", "price_basis_unit": unit,
            "quoted_price_precision": precision, "stock_bounds": values["stock"], "moq_bounds": values["moq"],
            "quantity_increment": values["increment"], "rfq_quantity_bounds": values["rfq"],
            "maximum_order_quantity": values["maximum_order"],
            "configuration_version": config["version"],
            "override_fields": sorted(set(override) - {"group", "group_assignment", "review_notes"}
                                      | set(override.get("parameters", {}))),
            "commercial_provenance": "proposed_synthetic_parameters",
        })
    return profiles


def load_config(root):
    from src.analytics.release_validation import schema_validator

    config = read_json(root / CONFIG)
    schema_validator(root, "commercial_config.v1").validate(config)
    require(config["approved_architecture"] == DECISIONS and config["sm04b_approvals"] == dict.fromkeys(APPROVALS),
            "UNAPPROVED_COMMERCIAL_CONFIGURATION", "SM-04A approval scope changed")
    for name, unit in config["units"].items():
        require(dec(unit["factor"]) > 0 and unit["fractional"] == (unit["precision"] > 0)
                and (unit["dimension"] not in {"count", "set"} or unit["precision"] == 0),
                "INVALID_UNIT_REGISTRY", name)
    return config
