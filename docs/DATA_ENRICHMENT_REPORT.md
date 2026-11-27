# Data enrichment report

The source, clean and enriched datasets each contain 1,048,575 rows. All three joins preserved row count with unique reference keys. No invalid trade rows, repeated normalized candidate keys, or unmatched join keys were found.

| Measure | Before | After |
| --- | ---: | ---: |
| Product rows matched | 995,988 (94.98%) | 1,048,575 (100%) |
| Trade rows with missing ISO2 on a matched country | 13,867 | 8,340 |
| Missing quantity rows | 44,579 | 45 |

All 52,587 previous product misses matched after normalization. The pipeline filled 44,534 quantities and preserved source quantity values.

## ISO2 verification

| Country key | Source ISO3 label | Result |
| --- | --- | --- |
| 516 Namibia | NAM | Recovered NA for 5,527 trade rows. [UN Group of Experts on Geographical Names](https://ungegn.un.org/dashboard/countries/details?id=516) |
| 490 Other Asia, nes | S19 | Kept null. This key denotes an unspecified trade area. [UN Comtrade](https://uncomtrade.org/docs/areas-not-elsewhere-specified/) |
| 697 Europe EFTA, nes | R20 | Kept null. The UN trade partner table has a blank alpha-2 for this record. [UN Comtrade partner table](https://comtradeplus.un.org/en/reference-tables?table=partner) |
| 711 Southern African Customs Union (...1999) | ZA1 | Kept null. The historical key denotes a customs union. [UN Statistics Division historical classification](https://digitallibrary.un.org/record/286187/files/ST_ESA_STAT_SER.M_49_Rev.4-EN.pdf) |

The process checks each configured mapping against the numeric key, existing ISO3 and any existing ISO2. It rejects duplicate or conflicting country keys. Original ISO labels and country keys are preserved. The verified override and its source are versionable in [country_iso2.json](../configs/country_iso2.json). As noted in the audit, repeated ISO labels can occur across historical and current reference keys.

The [enrichment summary](../reports/enrichment_summary.json) contains per-join validations, and the [unmatched report](../reports/unmatched_records.json) includes code frequencies when lookups fail. The enriched database includes a view that exposes the full unmatched records. The dataset covers only the provided Excel export, which reached the worksheet cap.
