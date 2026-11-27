# Data inventory

Audit date November 24, 2026. Counts exclude one header per file.

| Input | Rows | Columns | Bytes | Line endings | Observed scope |
| --- | ---: | ---: | ---: | --- | --- |
| trade_data.csv | 1,048,575 | 6 | 33,949,754 | CRLF | 2024 only, 29 exporters, 226 importers, 3,734 directed pairs, 4,577 distinct raw product codes |
| product_codes.csv | 5,022 | 2 | 525,748 | LF | 5,022 unique codes |
| country_codes.csv | 238 | 4 | 5,585 | CRLF | 238 unique numeric identifiers, including historical and aggregate entities |

All three files decode as UTF-8 without a BOM. Every data record parsed with the expected field count, and each file ends with a newline. The [JSON inventory](../reports/data_inventory.json) includes SHA-256 fingerprints, column profiles, boundary records, and unmatched code frequencies.

## Completeness and provenance

The trade file appears capped or truncated. Its 1,048,576 lines including the header exactly equal Excel's worksheet row limit. Exporter codes are nondecreasing and stop at 100. The last valid record is for exporter 100, importer 528, product 950691. A valid final record can occur in an export capped at a whole-row boundary. The file contains 226 distinct country codes across both roles, with only 29 exporters. This evidence supports a cap but does not establish the export mechanism or the number of omitted rows. [Microsoft Excel specifications](https://support.microsoft.com/en-us/excel/excel-specifications-and-limits)

The references have no visibly partial final records. Their completeness relative to a specific release remains unverified. Neither the supplied filenames nor accompanying materials establish an original publisher archive, expected row counts, release identifiers, matching HS revision, or export history. CEPII BACI is a candidate because its bilateral annual HS data and companion references resemble these files. CEPII publishes several HS revisions covering 2024, so the similarity does not establish a specific release or verify local units. [CEPII BACI database](https://www.international-economics.eu/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37)
