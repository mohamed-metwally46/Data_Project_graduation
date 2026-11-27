# Data quality report

## Method and results

Scanned every row from the three CSVs with product codes as text. Checked expected field counts, blank and whitespace-only values, common text missing markers where applicable, integer and decimal syntax, exact duplicate rows, reference-key uniqueness, and the candidate trade key (year, exporter, importer, product). Coverage uses one lookup per trade row and distinct-code counts per key. The audit wrote only documentation and the JSON report.

- No malformed records, exact duplicate rows, or repeated candidate trade keys occurred. Both reference join keys are unique.
- Quantity is blank in 44,579 trade rows (4.25%). Country ISO2 is blank for codes 490, 516, 697, and 711, affecting the importer in 13,867 trade rows and the exporter in zero. Other fields had zero blanks.
- ISO2 values BE, CS, DE, and SD and ISO3 values BEL, DEU, and SDN repeat across reference records. Some ISO-labeled values represent historical or aggregate entities, such as R20 and ZA1. Use the numeric country key when joining.
- Trade value ranges from 0.001 to 75,596,401.5. Nonblank quantity ranges from 0.001 to 755,268,502.4. All parsed measures are positive. Investigate the largest observations against the original release before setting any outlier rules. The JSON inventory records the rows with maximum values.
- The product reference has 347 leading-zero codes and one alphanumeric code, 9999AA. The trade file has 52,587 five-digit codes and 995,988 six-digit codes, with zero leading-zero strings. This pattern is consistent with lost zero padding during export.

## Join feasibility

| Lookup | Matched trade rows | Unmatched trade rows | Matched distinct codes |
| --- | ---: | ---: | ---: |
| Exporter to country_code | 1,048,575 (100%) | 0 | 29 / 29 |
| Importer to country_code | 1,048,575 (100%) | 0 | 226 / 226 |
| Raw HS Product Code to code | 995,988 (94.98%) | 52,587 | 4,249 / 4,577 (92.83%) |
| Product with candidate zero padding | 1,048,575 (100%) | 0 | 4,577 / 4,577 |

The candidate lookup tries an exact text match first. For unmatched five-digit numeric strings only, it tries prefixing one zero. For example, 80810 maps to 080810. This diagnostic produced no candidate trade-key collisions. Unique reference keys ensure a left join preserves the 1,048,575 input rows and leaves unmatched descriptions null in an exact join. All three lookups match on 995,988 rows using exact keys and on all 1,048,575 rows with the candidate product key. These counts were measured through lookups without writing an enriched dataset.

## Before cleaning

Obtain the original trade export and matching references with source row counts, HS revision, and documentation covering units, record grain, and null semantics. Re-run this audit against those inputs. Validate the product key recovery rule before applying it, preserving the observed code in a separate field if recovery is needed. Define handling for blank quantity and ISO2, then reconcile row counts and report unmatched and invalid records during enrichment. Treat the observed 2024 coverage as partial pending source verification.
