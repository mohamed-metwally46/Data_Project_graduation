"""Deterministic primitives for the proposed marketplace contract."""
import hashlib
import json
import random
import re
import unicodedata
from uuid import NAMESPACE_URL, UUID, uuid5

PRODUCT_CODE = re.compile(r"(?:[0-9]{6}|9999AA)", re.ASCII)
UUID5_CODE = re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-5[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}")
CLASSIFICATION_CONTEXT = "globiq-trade-reference-2024-v1"
LISTING_FIXTURE_ROOT = "c97a6984-c193-5da2-8da8-f97c7a560025"
LISTING_FIXTURE_POPULATION = "fixture-listing-commercial"
COMMERCIAL_ENTITIES = {"product", "listing"}


def _label(value):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Labels must be nonempty text without surrounding whitespace")
    return unicodedata.normalize("NFC", value)


def canonical_json(parts):
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def external_id(namespace, entity, *logical_key):
    """Return a UUID v5 from a versioned, typed logical key."""
    # SM-01 exercises typed generic keys in the standard URL namespace.
    # This compatibility path cannot derive a marketplace entity UUID.
    legacy_product_probe = (entity == "product" and str(namespace) == str(NAMESPACE_URL)
                            and len(logical_key) == 1)
    if entity in COMMERCIAL_ENTITIES and not legacy_product_probe:
        raise ValueError("Commercial identities require scoped hierarchical derivation")
    return _external_id(namespace, entity, *logical_key)


def _external_id(namespace, entity, *logical_key):
    if not logical_key:
        raise ValueError("At least one logical key field is required")
    normalized = [part if type(part) is int and part > 0 else _label(part)
                  for part in logical_key]
    return uuid5(UUID(str(namespace)), canonical_json(["globiq-marketplace-key-v1", _label(entity), normalized]))


def display_code(prefix, ordinal):
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z]{2,5}", prefix):
        raise ValueError("Display prefix must have two to five uppercase letters")
    if type(ordinal) is not int or not 1 <= ordinal <= 999_999:
        raise ValueError("Display ordinal must be between 1 and 999999")
    return f"{prefix}-{ordinal:06d}"


def population_namespace(root, population_key):
    if not isinstance(population_key, str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,79}", population_key):
        raise ValueError("Invalid population key")
    return uuid5(UUID(str(root)), canonical_json(["globiq-population-v1", population_key]))


def entity_namespace(population, entity):
    if entity not in ("company", "company_role", "company_product", "product", "listing"):
        raise ValueError("Unsupported marketplace entity namespace")
    return uuid5(UUID(str(population)), canonical_json(["globiq-entity-v1", entity]))


def hierarchical_external_id(root, population_key, entity, *logical_key):
    if entity in COMMERCIAL_ENTITIES:
        if str(root) != LISTING_FIXTURE_ROOT or population_key != LISTING_FIXTURE_POPULATION:
            raise ValueError("Commercial population identity derivation is unauthorized")
        if entity == "product":
            valid = (len(logical_key) == 2 and logical_key[0] == CLASSIFICATION_CONTEXT
                     and isinstance(logical_key[1], str) and PRODUCT_CODE.fullmatch(logical_key[1]))
        else:
            valid = (len(logical_key) == 3 and logical_key[2] == "default"
                     and all(isinstance(value, str) and UUID5_CODE.fullmatch(value) for value in logical_key[:2]))
        if not valid:
            raise ValueError(f"Invalid {entity} logical key")
    if entity == "company" and (
        len(logical_key) != 1 or not isinstance(logical_key[0], str)
        or not re.fullmatch(r"identity-(?!000000)[0-9]{6}", logical_key[0])
    ):
        raise ValueError("Invalid neutral company identity key")
    if entity in ("company_role", "company_product"):
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
        suffix = r"(supplier|importer)" if entity == "company_role" else r"([0-9]{6}|9999AA)"
        if (len(logical_key) != 2 or not all(isinstance(part, str) for part in logical_key)
                or not re.fullmatch(uuid_pattern, logical_key[0])
                or not re.fullmatch(suffix, logical_key[1])):
            raise ValueError(f"Invalid {entity} logical key")
    return _external_id(entity_namespace(population_namespace(root, population_key), entity),
                        entity, *logical_key)


def named_random_stream(master_seed, *stream_path):
    """Derive an isolated Python PRNG instance without process-dependent hashing."""
    if type(master_seed) is not int or master_seed < 0 or not stream_path:
        raise ValueError("A nonnegative integer seed and a named stream path are required")
    key = canonical_json(["globiq-marketplace-rng-v1", master_seed, [_label(p) for p in stream_path]])
    return random.Random(int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest(), "big"))
