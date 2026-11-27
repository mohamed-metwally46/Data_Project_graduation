"""Versioned evidence queries over observed trade relationships."""
import argparse
from collections import defaultdict
from contextlib import closing
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from time import perf_counter

from src.analytics.observed import ELIGIBLE_ROWS, validate_enrichment
from src.analytics.route_intelligence import open_database, percentage
from src.pipeline import write_json
from src.preprocessing.trade import normalize_product_code

SCHEMA_VERSION = "1.0"
CATEGORIES = ("A", "B", "C")
MAX_PAGE_SIZE = 500
EXPLANATIONS = {
    "A": "This directional product relationship was observed in the supplied {year} extract.",
    "B": ("Both product roles were observed. The directional pair was observed for other products, "
          "while this product relationship was unobserved in the supplied {year} extract."),
    "C": ("Both product roles were observed. This directional pair and product relationship "
          "were unobserved in the supplied {year} extract."),
}


class QueryError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass
class ProductLinks:
    exports: dict = field(default_factory=dict)
    imports: dict = field(default_factory=dict)
    exporter_mask: int = 0
    importer_mask: int = 0


def bit_indices(mask):
    while mask:
        lowest = mask & -mask
        yield lowest.bit_length() - 1
        mask ^= lowest


def category_masks(external, direct, pair):
    return external & direct, external & pair & ~direct, external & ~pair & ~direct


def universe(counts, exclusions):
    external = sum(counts)
    return {"gross_combinations": external + exclusions, "same_market_exclusions": exclusions,
            "external_relationships": external, "category_counts": dict(zip(CATEGORIES, counts, strict=True))}


class MarketRelationshipEngine:
    """Load one release and reuse its immutable-by-convention observed indexes."""

    def __init__(self, db, summary):
        started = perf_counter()
        validate_enrichment(db, summary)
        self.countries = {row["code"]: dict(row) for row in db.execute(
            "SELECT code,name,iso2,iso3 FROM country ORDER BY code"
        )}
        self.descriptions = dict(db.execute("SELECT code,description FROM product"))
        self.markets = tuple(self.countries)
        self.bits = {code: 1 << pos for pos, code in enumerate(self.markets)}
        self.products = defaultdict(ProductLinks)
        self.outgoing = defaultdict(int)
        self.incoming = defaultdict(int)
        self.pair_products = defaultdict(int)
        self.export_products = defaultdict(list)
        self.import_products = defaultdict(list)
        provenance = summary["metadata"]
        hasher = hashlib.sha256()

        def fingerprint(value):
            hasher.update((json.dumps(value, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")) + "\n").encode("utf-8"))

        fingerprint([self.countries, self.descriptions, provenance])
        load_seconds = perf_counter() - started
        last = None
        year = None
        eligible = 0
        self_links = 0
        mark = perf_counter()
        cursor = db.execute(f"""
            SELECT year, product_code, exporter_code, importer_code
            FROM enriched_trade_data WHERE {ELIGIBLE_ROWS}
            ORDER BY product_code, exporter_code, importer_code, year
        """)
        load_seconds += perf_counter() - mark
        while True:
            mark = perf_counter()
            batch = cursor.fetchmany(8192)
            load_seconds += perf_counter() - mark
            if not batch:
                break
            for row in batch:
                key = tuple(row)
                y, product, exporter, importer = key
                if last == key:
                    raise ValueError(f"Duplicate eligible relationship: {key}")
                if year is not None and year != y:
                    raise ValueError("Market Relationship Intelligence requires a single eligible year")
                if (product not in self.descriptions or normalize_product_code(product) != product
                        or exporter not in self.bits or importer not in self.bits):
                    raise ValueError(f"Invalid eligible reference key: {key}")
                year, last = y, key
                eligible += 1
                self_links += exporter == importer
                fingerprint(key)
                data = self.products[product]
                ebit, ibit = self.bits[exporter], self.bits[importer]
                data.exports[exporter] = data.exports.get(exporter, 0) | ibit
                data.imports[importer] = data.imports.get(importer, 0) | ebit
                data.exporter_mask |= ebit
                data.importer_mask |= ibit
                self.outgoing[exporter] |= ibit
                self.incoming[importer] |= ebit
                self.pair_products[exporter, importer] += 1
        if year is None:
            raise ValueError("No eligible trade records")
        for product, data in sorted(self.products.items()):
            for exporter in data.exports:
                self.export_products[exporter].append(product)
            for importer in data.imports:
                self.import_products[importer].append(product)
        self.product_codes = tuple(sorted(self.products))
        self.metadata = {
            "schema_version": SCHEMA_VERSION,
            "dataset_version": "sha256:" + hasher.hexdigest(),
            "year": year,
            "eligibility": ELIGIBLE_ROWS,
            "record_grain": ["year", "exporter_code", "importer_code", "product_code"],
            "eligible_records": eligible,
            "unique_composite_keys": eligible,
            "observed_self_links": self_links,
            "observed_exporters": len(self.export_products),
            "observed_importers": len(self.import_products),
            "observed_products": len(self.products),
            "observed_routes": len(self.pair_products),
            "reciprocal_pairs": sum(e < i and (i, e) in self.pair_products for e, i in self.pair_products),
            "coverage": {**provenance, "absence_meaning": "Unobserved in the supplied extract."},
        }
        self.load_seconds = load_seconds
        self.initialization_seconds = perf_counter() - started

    @classmethod
    def from_files(cls, database, summary_path):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        with closing(open_database(database)) as db:
            return cls(db, summary)

    def counts_by_role(self, data, role):
        if role == "exporter":
            groups, opposite, pairs = data.exports, data.importer_mask, self.outgoing
        else:
            groups, opposite, pairs = data.imports, data.exporter_mask, self.incoming
        for market, observed in groups.items():
            external = opposite & ~self.bits[market]
            counts = tuple(mask.bit_count() for mask in category_masks(external, observed, pairs[market]))
            yield market, counts, int(bool(opposite & self.bits[market]))

    def summary(self):
        total = [0, 0, 0, 0]
        roles = {role: defaultdict(lambda: [0, 0, 0, 0]) for role in ("exporter", "importer")}
        products = []
        for code in self.product_codes:
            data = self.products[code]
            perspectives = {}
            for role, summaries in roles.items():
                product_total = [0, 0, 0, 0]
                for market, counts, excluded in self.counts_by_role(data, role):
                    for index, value in enumerate((*counts, excluded)):
                        summaries[market][index] += value
                        product_total[index] += value
                perspectives[role] = product_total
            numbers = perspectives["exporter"]
            if numbers != perspectives["importer"]:
                raise ValueError(f"Candidate role counts do not reconcile for {code}")
            entry = universe(numbers[:3], numbers[3])
            if entry["gross_combinations"] != len(data.exports) * len(data.imports):
                raise ValueError(f"Candidate universe does not reconcile for {code}")
            for index, value in enumerate(numbers):
                total[index] += value
            products.append({
                "product_code": code, "description": self.descriptions[code],
                "reference_mapped": True, "observed_exporters": len(data.exports),
                "observed_importers": len(data.imports), **entry,
            })
        if total[0] != self.metadata["eligible_records"] - self.metadata["observed_self_links"]:
            raise ValueError("Category A does not reconcile with eligible external trade records")
        markets = {}
        for role, observed in (("exporter", self.export_products), ("importer", self.import_products)):
            markets[role] = [
                {"market": self.market(code), "role": role, "observed_product_diversity": len(observed[code]),
                 **universe(values[:3], values[3])}
                for code, values in sorted(roles[role].items())
            ]
        combined = universe(total[:3], total[3])
        combined["percentage_denominator"] = "All external relationships"
        combined["category_percentages"] = {
            key: percentage(count, combined["external_relationships"])
            for key, count in combined["category_counts"].items()
        }
        return {"metadata": deepcopy(self.metadata), "universe": combined, "products": products, "markets": markets}

    def market(self, code):
        return {**self.countries[code], "reference_mapped": True}

    def normalize_filters(self, product_code, exporter_code, importer_code, category):
        if product_code is not None:
            if not isinstance(product_code, str):
                raise QueryError("invalid_product", "Product codes must be strings")
            normalized = normalize_product_code(product_code)
            if normalized not in self.descriptions:
                raise QueryError("unknown_product", f"Unknown product code: {product_code}")
            product_code = normalized
        for market in (exporter_code, importer_code):
            if market is not None and (type(market) is not int or market not in self.bits):
                raise QueryError("unknown_market", f"Unknown numeric market identifier: {market}")
        if exporter_code is not None and exporter_code == importer_code:
            raise QueryError("same_market", "External relationships require different markets")
        if category is not None and category not in CATEGORIES:
            raise QueryError("invalid_category", "Category must be A, B or C")
        if product_code is None and exporter_code is None and importer_code is None:
            raise QueryError("unbounded_query", "Specify a product, exporter, or importer")
        return product_code, exporter_code, importer_code, category

    def matching_blocks(self, product, exporter, importer, category):
        """Count and retain compact bitmask blocks, without constructing candidates."""
        sources = []
        if product is not None:
            sources.append((product,))
        if exporter is not None:
            sources.append(self.export_products.get(exporter, ()))
        if importer is not None:
            sources.append(self.import_products.get(importer, ()))
        blocks = []
        total = 0
        for code in min(sources, key=len):
            data = self.products.get(code)
            if data is None or (importer is not None and importer not in data.imports):
                continue
            importers = self.bits[importer] if importer is not None else data.importer_mask
            for e in ((exporter,) if exporter is not None else data.exports):
                if e not in data.exports:
                    continue
                mask = importers & ~self.bits[e]
                if category is not None:
                    mask = category_masks(mask, data.exports[e], self.outgoing[e])[CATEGORIES.index(category)]
                if mask:
                    size = mask.bit_count()
                    total += size
                    blocks.append((code, e, mask, size))
        return blocks, total

    def page_keys(self, blocks, offset, limit):
        keys = []
        for code, exporter, mask, size in blocks:
            if offset >= size:
                offset -= size
                continue
            for position in bit_indices(mask):
                if offset:
                    offset -= 1
                    continue
                keys.append((code, exporter, self.markets[position]))
                if len(keys) == limit:
                    return keys
        return keys

    def relationship(self, product, exporter, importer):
        data = self.products[product]
        ibit, ebit = self.bits[importer], self.bits[exporter]
        direct = bool(data.exports[exporter] & ibit)
        pair_products = self.pair_products.get((exporter, importer), 0)
        category = "A" if direct else "B" if pair_products else "C"
        year = self.metadata["year"]
        return {
            "relationship_id": f"{year}:{exporter}:{product}:{importer}", "year": year,
            "dataset_version": self.metadata["dataset_version"], "coverage": deepcopy(self.metadata["coverage"]),
            "product_code": product, "product_description": self.descriptions[product],
            "product_reference_mapped": True,
            "exporter": self.market(exporter), "importer": self.market(importer), "category": category,
            "product_link_observed": direct, "directional_pair_observed": bool(pair_products),
            "reverse_pair_observed": (importer, exporter) in self.pair_products,
            "reverse_product_link_observed": bool(data.imports.get(exporter, 0) & ibit),
            "evidence": {
                "exporter_product_destinations": data.exports[exporter].bit_count(),
                "importer_product_sources": data.imports[importer].bit_count(),
                "pair_product_count": pair_products, "other_pair_product_count": pair_products - direct,
                "product_exporters": len(data.exports), "product_importers": len(data.imports),
                "exporter_product_diversity": len(self.export_products[exporter]),
                "importer_product_diversity": len(self.import_products[importer]),
            },
            "explanation": EXPLANATIONS[category].format(year=year),
        }

    def empty_reason(self, product, exporter, importer):
        if product is not None and product not in self.products:
            return "product_unobserved"
        if exporter is not None and exporter not in self.export_products:
            return "exporter_role_unobserved"
        if importer is not None and importer not in self.import_products:
            return "importer_role_unobserved"
        return "no_matches"

    def query_relationships(self, product_code=None, exporter_code=None, importer_code=None,
                            category=None, page=1, page_size=50):
        product, exporter, importer, category = self.normalize_filters(
            product_code, exporter_code, importer_code, category
        )
        if type(page) is not int or page < 1:
            raise QueryError("invalid_page", "Page must be a positive integer")
        if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
            raise QueryError("invalid_page_size", f"Page size must be between 1 and {MAX_PAGE_SIZE}")
        blocks, total = self.matching_blocks(product, exporter, importer, category)
        pages = (total + page_size - 1) // page_size
        keys = self.page_keys(blocks, (page - 1) * page_size, page_size)
        return {
            "metadata": deepcopy(self.metadata),
            "filters": {"product_code": product, "exporter_code": exporter,
                        "importer_code": importer, "category": category},
            "pagination": {
                "page": page, "page_size": page_size, "total_matches": total, "total_pages": pages,
                "returned_count": len(keys), "has_previous": pages > 0 and page > 1,
                "has_next": page < pages,
            },
            "empty_reason": (
                None if keys else "page_out_of_range" if total or page > 1
                else self.empty_reason(product, exporter, importer)
            ),
            "records": [self.relationship(*key) for key in keys],
        }

    def lookup_relationship(self, product_code, exporter_code, importer_code):
        if None in (product_code, exporter_code, importer_code):
            raise QueryError("invalid_relationship", "Lookup requires a product, exporter and importer")
        product, exporter, importer, _ = self.normalize_filters(
            product_code, exporter_code, importer_code, None
        )
        data = self.products.get(product)
        if data is None or exporter not in data.exports or importer not in data.imports:
            return None
        return self.relationship(product, exporter, importer)

    def lookup_id(self, relationship_id):
        try:
            year, exporter, product, importer = relationship_id.split(":")
            if (year != str(self.metadata["year"]) or str(int(exporter)) != exporter
                    or str(int(importer)) != importer or normalize_product_code(product) != product):
                raise ValueError
        except (AttributeError, ValueError):
            raise QueryError("invalid_relationship_id", "Expected current YEAR:EXPORTER:PRODUCT:IMPORTER") from None
        return self.lookup_relationship(product, int(exporter), int(importer))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/processed/trade.sqlite"))
    parser.add_argument("--enrichment-summary", type=Path, default=Path("reports/enrichment_summary.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    summary = commands.add_parser("summary")
    summary.add_argument("--output", type=Path, default=Path("data/processed/analytics/market_opportunity_summary.json"))
    query = commands.add_parser("query")
    query.add_argument("--product")
    query.add_argument("--exporter", type=int)
    query.add_argument("--importer", type=int)
    query.add_argument("--category")
    query.add_argument("--page", type=int, default=1)
    query.add_argument("--page-size", type=int, default=50)
    lookup = commands.add_parser("lookup")
    lookup.add_argument("relationship_id")
    args = parser.parse_args()
    engine = MarketRelationshipEngine.from_files(args.database, args.enrichment_summary)
    try:
        if args.command == "summary":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.output, engine.summary())
            print(args.output)
        elif args.command == "query":
            print(json.dumps(engine.query_relationships(
                args.product, args.exporter, args.importer, args.category, args.page, args.page_size)))
        else:
            print(json.dumps(engine.lookup_id(args.relationship_id)))
    except QueryError as error:
        parser.exit(2, json.dumps({"error": error.code, "message": str(error)}) + "\n")


if __name__ == "__main__":
    main()
