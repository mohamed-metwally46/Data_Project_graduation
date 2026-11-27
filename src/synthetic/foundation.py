"""SM-01 policy and read-only verification of the pinned analytical source."""
import argparse
import json
from pathlib import Path

from jsonschema.exceptions import SchemaError, ValidationError

from src.analytics.release import MANIFEST, validate
from src.analytics.release_validation import read_json, schema_validator


POLICY_PATH = Path("configs/synthetic/policy.v1.json")
SOURCE = {
    "release_id": "ti-3349f6e0cb6dde75fe7d5323af71463748cad3232bc7bcb476c6ff6dcd8cd41b",
    "dataset_fingerprint": "sha256:4b65676dc1766ebd869df52fef1c3786beffb11fcc838a99eb14a3818e4c136e",
    "year": 2024,
}
TARGETS = {"products": 300, "companies": 500, "supplier_roles": 300, "importer_roles": 200,
           "listings": 1000, "rfqs": 600, "offers": 900}


def load_policy(root, path=None):
    policy = read_json(path if path is not None else root / POLICY_PATH)
    schema_validator(root, "synthetic_marketplace_policy").validate(policy)
    if policy["source"] != SOURCE or policy["targets"] != TARGETS:
        raise ValueError("Configuration changed the approved source pin or fixed entity targets")
    proposed = policy["proposed_defaults"]
    distribution = proposed["offers_per_rfq"]
    checks = (
        (sum(proposed["listing_statuses"].values()), TARGETS["listings"], "listing statuses"),
        (sum(proposed["rfq_types"].values()), TARGETS["rfqs"], "RFQ types"),
        (sum(distribution.values()), TARGETS["rfqs"], "RFQ response scenarios"),
        (sum(int(offers) * count for offers, count in distribution.items()),
         TARGETS["offers"], "offers across scenarios"),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise ValueError(f"Proposed {label} total {actual} does not match {expected}")
    competing = sum(count for offers, count in distribution.items() if int(offers) > 1)
    if competing > proposed["rfq_types"]["open"]:
        raise ValueError("Proposed competing quotations exceed open RFQs")
    return policy


def require_generation_ready(policy):
    if (policy["generation_status"] != "ready" or policy["contract_status"] != "approved"
            or any(value is None for value in policy["unresolved"].values())
            or policy["proposed_defaults"]["status"] != "approved"):
        raise ValueError("Marketplace generation is blocked pending approval and joint feasibility")


def verify_pinned_source(root, policy):
    manifest_path = root / MANIFEST
    manifest = read_json(manifest_path)
    expected = policy["source"]
    if expected != SOURCE or manifest.get("status") != "validated" or any(
        manifest.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("Trade Intelligence manifest does not match the approved validated source pin")
    results = validate(root)
    if (any(results.get(key) != expected[key] for key in ("release_id", "dataset_fingerprint"))
            or results.get("status") != "validated" or read_json(manifest_path) != manifest):
        raise ValueError("Pinned Trade Intelligence source changed during verification")
    return {"verification": results, "statistics": manifest["statistics"],
            "manifest": MANIFEST.as_posix()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check-config", "verify-source"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--policy", type=Path)
    args = parser.parse_args()
    try:
        policy = load_policy(args.root, args.policy)
        result = (verify_pinned_source(args.root, policy) if args.command == "verify-source"
                  else {"configuration_version": policy["configuration_version"],
                        "configuration_valid": True, "targets": policy["targets"],
                        "defaults_status": policy["proposed_defaults"]["status"],
                        "contract_status": policy["contract_status"],
                        "generation_status": policy["generation_status"]})
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, SchemaError, ValidationError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
