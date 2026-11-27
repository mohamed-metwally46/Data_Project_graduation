# Data cleaning rules

Run the reproducible Python commands in the [README](../README.md). The input files stay in the project root. All generated database tables are stored in data/processed/trade.sqlite.

| Input | Validation and transformation |
| --- | --- |
| Source CSV | Read UTF-8 with explicit headers and field counts. Header or row-width errors stop processing with the source path and line where applicable. |
| Year and country keys | Parse positive integers. Country reference keys must be unique, including after parsing. |
| Product codes | Preserve the original as text. Prefix one zero to a five-digit numeric code, keep six-digit strings and the recognized legacy code 9999AA, and flag unexpected formats. Join using the normalized string and report misses against the supplied product reference. |
| Trade value and quantity | Preserve source tokens. Parse finite positive numbers into numeric fields. Flag invalid nonblank measures and keep blank quantity null before imputation. |
| Missing quantity | Compute the arithmetic mean of eligible observed quantities for each matched normalized product. Fill blank quantities from that product's mean only. Preserve the original token and the observed numeric value. Record the result in quantity_processed and set quantity_was_imputed to 1 only for filled rows. |
| Invalid or repeated records | Preserve invalid rows with field-level reasons and expose them in invalid_trade_records. Report repeated normalized candidate keys for review. |

The approved product-level mean is a temporary assumption. It uses eligible observations from the available export, weights each observation equally, and can be sensitive to large shipments and uneven route coverage. Six products had no eligible quantity observations. Their 45 missing amounts remain null. Analytics currently use record counts and exclude quantity entirely pending source unit verification.

The supplied Excel-to-CSV file reaches the worksheet limit with its header and provides partial geographic coverage.
