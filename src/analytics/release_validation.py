"""Independent Trade Intelligence reconciliation against enriched Parquet."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from time import perf_counter

from jsonschema import Draft202012Validator
import pyarrow.parquet as pq

from src.analytics.market_opportunity_intelligence import QueryError
from src.analytics.route_intelligence import product_composition


def require(condition, detail):
    if not condition:
        raise ValueError(f"Release reconciliation failed: {detail}")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def schema_validator(root, name):
    schema = read_json(root / "schemas" / f"{name}.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def unique_index(records, key):
    result = {}
    for row in records:
        identifier = key(row)
        require(identifier not in result, f"duplicate profile identifier {identifier}")
        result[identifier] = row
    return result


def reference_tables(root):
    with (root / "product_codes.csv").open(encoding="utf-8-sig", newline="") as stream:
        products = unique_index(csv.DictReader(stream), lambda row: row["code"])
    with (root / "country_codes.csv").open(encoding="utf-8-sig", newline="") as stream:
        countries = unique_index(csv.DictReader(stream), lambda row: int(row["country_code"]))
    overrides = read_json(root / "configs/country_iso2.json")
    labels = {}
    for code, row in countries.items():
        override = overrides.get(str(code))
        iso2 = row["country_iso2"] or None
        iso3 = row["country_iso3"] or None
        if override:
            require(iso3 == override["iso3"] and iso2 in (None, override["iso2"]),
                    f"country override {code}")
            iso2 = override["iso2"]
        labels[code] = {"code": code, "name": row["country_name"], "iso2": iso2, "iso3": iso3}
    return labels, {code: row["description"] for code, row in products.items()}


class ParquetEvidence:
    def __init__(self, root):
        self.labels, self.descriptions = reference_tables(root)
        self.links = defaultdict(set)
        self.pairs = defaultdict(set)
        self.exports, self.imports = defaultdict(set), defaultdict(set)
        self.destinations, self.sources = defaultdict(set), defaultdict(set)
        self.exp_records, self.imp_records = Counter(), Counter()
        self.outgoing, self.incoming = defaultdict(set), defaultdict(set)
        self.input_products = Counter()
        self.route_input_products = defaultdict(set)
        parquet = pq.ParquetFile(root / "data/processed/enriched_trade_data.parquet")
        self.input_rows = parquet.metadata.num_rows
        self.provenance = json.loads(parquet.schema_arrow.metadata[b"globiq.dataset"])
        self.year = None
        fields = ["year", "exporter_code", "importer_code", "product_code", "invalid_fields",
                  "exporter_matched", "importer_matched", "product_matched"]
        for batch in parquet.iter_batches(columns=fields):
            for y, e, i, p, invalid, em, im, pm in zip(*(c.to_pylist() for c in batch.columns)):
                if p is not None:
                    self.input_products[p] += 1
                    if invalid is None and em and im:
                        self.route_input_products[y, e, i].add(p)
                if invalid is not None or not (em and im and pm):
                    continue
                if self.year is None:
                    self.year = y
                require(y == self.year and isinstance(p, str) and p in self.descriptions
                        and e in self.labels and i in self.labels, "Parquet year or reference")
                require((e, i) not in self.links[p], f"duplicate eligible key {y}:{e}:{p}:{i}")
                self.links[p].add((e, i))
                self.pairs[e, i].add(p)
                self.exports[e].add(p)
                self.imports[i].add(p)
                self.destinations[p, e].add(i)
                self.sources[p, i].add(e)
                self.exp_records[e] += 1
                self.imp_records[i] += 1
                self.outgoing[e].add(i)
                self.incoming[i].add(e)
        require(self.year is not None, "empty eligible data")
        self.total = sum(self.exp_records.values())

    def fingerprint(self):
        digest = hashlib.sha256()
        items = ([self.labels, self.descriptions, self.provenance],)
        for item in items:
            digest.update((json.dumps(item, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")) + "\n").encode())
        for product, links in sorted(self.links.items()):
            for exporter, importer in sorted(links):
                digest.update((json.dumps([self.year, product, exporter, importer],
                                          separators=(",", ":")) + "\n").encode())
        return "sha256:" + digest.hexdigest()

    def category(self, p, e, i):
        if (e, i) in self.links[p]:
            return "A"
        return "B" if (e, i) in self.pairs else "C"

    def candidate_totals(self):
        products = {}
        markets = {"exporter": defaultdict(Counter), "importer": defaultdict(Counter)}
        total = Counter()
        for p, links in self.links.items():
            exporters = {e for e, _ in links}
            importers = {i for _, i in links}
            result = Counter()
            for role, own, opposite, neighbors, direct in (
                ("exporter", exporters, importers, self.outgoing, self.destinations),
                ("importer", importers, exporters, self.incoming, self.sources),
            ):
                role_total = Counter()
                for code in own:
                    skipped = int(code in opposite)
                    external = len(opposite) - skipped
                    a = len(direct[p, code]) - int(code in direct[p, code])
                    ab = len(neighbors[code] & opposite) - int(code in neighbors[code] and code in opposite)
                    counts = Counter(A=a, B=ab-a, C=external-ab, excluded=skipped)
                    require(min(counts.values()) >= 0, f"candidate partition {p}")
                    role_total.update(counts)
                    markets[role][code].update(counts)
                if role == "exporter":
                    result = role_total
                else:
                    require(role_total == result, f"independent role intersection {p}")
            products[p] = result
            total.update(result)
        return total, products, markets


def pct(n, d):
    return round(100 * n / d, 6) if d else None


def check_counts(row, counts):
    categories = {key: counts[key] for key in "ABC"}
    external = sum(categories.values())
    require((row["category_counts"], row["external_relationships"], row["same_market_exclusions"],
             row["gross_combinations"]) == (categories, external, counts["excluded"],
                                            external + counts["excluded"]), "candidate counts")


def reconcile(evidence, outputs):
    ev = evidence
    country = unique_index(outputs["country_intelligence"]["records"], lambda r: r["code"])
    product = unique_index(outputs["product_intelligence"]["records"], lambda r: r["product_code"])
    route = unique_index(outputs["route_intelligence"]["records"],
                         lambda r: (r["exporter"]["code"], r["importer"]["code"]))
    market = outputs["market_opportunity_summary"]
    require(country.keys() == ev.labels.keys(), "country profile coverage")
    require(product.keys() == ev.input_products.keys(), "product profile coverage")
    require(route.keys() == ev.pairs.keys(), "route coverage")
    require(len({r["route_id"] for r in route.values()}) == len(route), "route IDs")
    for code, r in country.items():
        require({f: r[f] for f in ev.labels[code]} == ev.labels[code] and r["year"] == ev.year,
                f"country labels/year {code}")
        expected = (ev.exp_records[code], ev.imp_records[code], len(ev.outgoing.get(code, ())),
                    len(ev.incoming.get(code, ())), len(ev.exports.get(code, ())), len(ev.imports.get(code, ())))
        require(tuple(r[k] for k in ("export_record_count", "import_record_count", "export_destinations",
                                    "import_sources", "distinct_exported_products",
                                    "distinct_imported_products")) == expected, f"country dimensions {code}")
    for code, r in product.items():
        links = ev.links.get(code, ())
        expected = (len(links), len({e for e, _ in links}), len({i for _, i in links}), len(links))
        require(tuple(r[k] for k in ("record_count", "exporters", "importers", "distinct_routes")) == expected
                and r["reference_mapped"] == (code in ev.descriptions)
                and r["description"] == ev.descriptions.get(code)
                and r["input_row_count"] == ev.input_products[code] and r["year"] == ev.year, f"product {code}")
    unobserved = sorted(ev.descriptions.keys() - ev.input_products.keys())
    pc = outputs["product_intelligence"]["reference_coverage"]
    mapped = len(ev.input_products.keys() & ev.descriptions.keys())
    require(pc["unobserved_reference_codes"] == unobserved
            and pc["unobserved_reference_products"] == len(unobserved)
            and pc["mapped_products"] == mapped and pc["unmapped_products"] == len(product)-mapped,
            "product reference coverage")
    for (e, i), r in route.items():
        n = len(ev.pairs[e, i])
        reverse = e != i and (i, e) in ev.pairs
        key = f"{ev.year}:{e}:{i}"
        require(r["route_id"] == key and r["year"] == ev.year
                and r["product_composition"] == {"query_route_id": key, "ordering": "product_code_ascending",
                                                  "eligible_products_tied": n > 1}
                and r["record_count"] == r["distinct_products"] == n
                and r["reverse_observed"] == reverse and r["self_trade"] == (e == i)
                and r["reverse_route_id"] == (f"{ev.year}:{i}:{e}" if reverse else None), f"route {key}")
        for role, code in (("exporter", e), ("importer", i)):
            require(r[role] == {**ev.labels[code], "reference_mapped": True}, f"route labels {key}")
        scope = ev.route_input_products[ev.year, e, i]
        mapped_on_pair = len(scope & ev.descriptions.keys())
        require(r["product_reference_coverage"] == {
            "observed_normalized_products": len(scope), "mapped_products": mapped_on_pair,
            "unmapped_products": len(scope)-mapped_on_pair, "mapped_percent": pct(mapped_on_pair, len(scope)),
        }, f"route reference coverage {key}")
        require(r["relative_coverage"] == {
            "percent_of_dataset_records": pct(n, ev.total),
            "percent_of_exporter_records": pct(n, ev.exp_records[e]),
            "percent_of_importer_records": pct(n, ev.imp_records[i]),
            "percent_of_exporter_products": pct(n, len(ev.exports[e])),
            "percent_of_importer_products": pct(n, len(ev.imports[i])),
        }, f"route percentages {key}")
    total, products, markets = ev.candidate_totals()
    check_counts(market["universe"], total)
    require(market["universe"]["category_percentages"] == {
        key: pct(total[key], sum(total[c] for c in "ABC")) for key in "ABC"
    }, "category percentage denominator")
    market_products = unique_index(market["products"], lambda r: r["product_code"])
    require(market_products.keys() == products.keys(), "market product coverage")
    for code, r in market_products.items():
        check_counts(r, products[code])
        links = ev.links[code]
        require((r["observed_exporters"], r["observed_importers"]) ==
                (len({e for e, _ in links}), len({i for _, i in links}))
                and r["reference_mapped"] and r["description"] == ev.descriptions[code], f"market product {code}")
    for role, observed in (("exporter", ev.exports), ("importer", ev.imports)):
        indexed = unique_index(market["markets"][role], lambda r: r["market"]["code"])
        require(indexed.keys() == markets[role].keys(), f"{role} market coverage")
        for code, r in indexed.items():
            check_counts(r, markets[role][code])
            require(r["market"] == {**ev.labels[code], "reference_mapped": True}
                    and r["role"] == role and r["observed_product_diversity"] == len(observed[code]), role)
    self_records = sum(len(keys) for (e,i), keys in ev.pairs.items() if e == i)
    require(total["A"] == ev.total - self_records, "direct external links")
    reciprocal = sum(e < i and (i,e) in ev.pairs for e,i in ev.pairs)
    for name, obj in outputs.items():
        metadata = obj["metadata"]
        year = metadata.get("year")
        require(year == ev.year, f"{name} release year")
        coverage = metadata["coverage"] if name == "market_opportunity_summary" else metadata
        require(all(coverage.get(k) == v for k,v in ev.provenance.items()), f"{name} provenance")
    return {"year": ev.year, "eligible_records": ev.total, "unique_composite_keys": ev.total,
            "duplicated_composite_keys": 0, "records_on_duplicated_composite_keys": 0,
            "self_trade_records": self_records, "observed_exporters": len(ev.exports),
            "observed_importers": len(ev.imports), "country_profiles": len(country),
            "zero_observation_country_profiles": sum(code not in ev.exp_records and code not in ev.imp_records
                                                     for code in country),
            "product_profiles": len(product), "mapped_products": mapped, "unmapped_products": len(product)-mapped,
            "unobserved_reference_products": len(unobserved), "directional_routes": len(route),
            "routes_with_reverse": reciprocal * 2, "reciprocal_pairs": reciprocal,
            "market_universe": market["universe"]}


def validate_queries(root, ev, db, engine):
    validator = schema_validator(root, "market_relationship_query")
    validator.validate(engine.query_relationships(product_code=min(ev.links)))
    p = max(sorted(ev.links), key=lambda k: len({e for e,_ in ev.links[k]})*len({i for _,i in ev.links[k]}))
    e, i = min(pair for pair in ev.pairs if pair[0] != pair[1])
    scenarios = [
        (p, None, None, None), (None, e, None, None), (None, None, i, None),
        (None, e, i, None), (p, None, None, "A"), (p, None, None, "B"), (p, None, None, "C"),
        (min(ev.pairs[e,i]), e, i, "A"),
    ]
    checked = 0
    lookup_categories = set()
    start = perf_counter()
    for pfilter, efilter, ifilter, category in scenarios:
        page_size = 7
        sample = []
        total = 0
        for code in ([pfilter] if pfilter else sorted(ev.links)):
            exporters = sorted({x for x,_ in ev.links[code]})
            importers = sorted({y for _,y in ev.links[code]})
            for exporter in exporters:
                if efilter is not None and exporter != efilter:
                    continue
                for importer in importers:
                    if importer == exporter or (ifilter is not None and importer != ifilter):
                        continue
                    classification = ev.category(code, exporter, importer)
                    if category and classification != category:
                        continue
                    total += 1
                    if len(sample) < 2 * page_size:
                        sample.append((code, exporter, importer, classification))
        records = []
        for page in (1, 2):
            result = engine.query_relationships(pfilter, efilter, ifilter, category, page, page_size)
            validator.validate(result)
            require(result == engine.query_relationships(pfilter, efilter, ifilter, category, page, page_size),
                    "stable query pagination")
            pagination = result["pagination"]
            require(pagination["total_matches"] == total
                    and pagination["total_pages"] == (total+page_size-1)//page_size
                    and pagination["returned_count"] == len(result["records"])
                    and result["metadata"]["dataset_version"] == engine.metadata["dataset_version"],
                    "filtered query metadata")
            records.extend(result["records"])
            checked += 1
        for row, (code, exporter, importer, c) in zip(records, sample, strict=True):
            rid = f"{ev.year}:{exporter}:{code}:{importer}"
            pair = ev.pairs.get((exporter, importer), ())
            exp = {a for a,_ in ev.links[code]}
            imp = {b for _,b in ev.links[code]}
            require(row["relationship_id"] == rid and row["category"] == c
                    and row["product_link_observed"] == (c == "A") and row["directional_pair_observed"] == bool(pair)
                    and row["reverse_pair_observed"] == ((importer, exporter) in ev.pairs)
                    and row["reverse_product_link_observed"] == ((importer, exporter) in ev.links[code])
                    and row["product_description"] == ev.descriptions[code]
                    and str(ev.year) in row["explanation"], f"query classification {rid}")
            require(row["evidence"] == {
                "exporter_product_destinations": len(ev.destinations[code,exporter]),
                "importer_product_sources": len(ev.sources[code,importer]),
                "pair_product_count": len(pair), "other_pair_product_count": len(pair) - (c == "A"),
                "product_exporters": len(exp), "product_importers": len(imp),
                "exporter_product_diversity": len(ev.exports[exporter]),
                "importer_product_diversity": len(ev.imports[importer]),
            }, f"query evidence {rid}")
            for role, market in (("exporter",exporter), ("importer",importer)):
                require(row[role] == {**ev.labels[market], "reference_mapped": True}, f"query labels {rid}")
            if c not in lookup_categories:
                require(engine.lookup_id(rid) == row, f"individual lookup {rid}")
                lookup_categories.add(c)
    for filters in ({}, {"exporter_code": e, "importer_code": e}, {"product_code": p, "page": 0}):
        try:
            engine.query_relationships(**filters)
        except QueryError:
            continue
        raise ValueError("Invalid query unexpectedly succeeded")
    unobserved = sorted(ev.descriptions.keys() - ev.input_products.keys())
    if unobserved:
        response = engine.query_relationships(product_code=unobserved[0])
        validator.validate(response)
        require(response["empty_reason"] == "product_unobserved" and not response["records"], "empty query")
    detail = product_composition(db, ev.year, e, i)
    require([r["product_code"] for r in detail] == sorted(ev.route_input_products[ev.year,e,i]),
            "route detail product keys")
    for r in detail:
        require(r["record_count"] == int(r["product_code"] in ev.pairs[e,i])
                and r["description"] == ev.descriptions.get(r["product_code"])
                and r["reference_mapped"] == (r["product_code"] in ev.descriptions), "route detail fields")
    return {"query_pages": checked, "lookup_categories": sorted(lookup_categories),
            "route_detail_products": len(detail), "validation_seconds": perf_counter()-start}
