# Source data dictionary

Types describe the observed CSV tokens and proposed ingestion types. CSV fields are read as text before validation. Product identifiers should remain strings throughout processing.

| File | Exact header | Plan field | Observed type | Meaning and constraints |
| --- | --- | --- | --- | --- |
| trade_data.csv | Year | t | Integer | Observed year 2024 only |
| trade_data.csv | Exporter Country Code | i | Integer | Exporter identifier, joins to country_code |
| trade_data.csv | Importer Country Code | j | Integer | Importer identifier, joins to country_code |
| trade_data.csv | HS Product Code | code | String | Observed five or six digits. HS revision unverified. Preserve the raw token. |
| trade_data.csv | Trade Value | v | Decimal | Recorded trade value. Currency and scale unverified. |
| trade_data.csv | Quantity | q | Nullable decimal | Recorded quantity. Unit and meaning of blank unverified. Parse a blank as missing. |
| product_codes.csv | code | code | String | Unique reference identifier, six characters. Preserve leading zeros and alphanumeric 9999AA. |
| product_codes.csv | description | description | String | Reference product description. May contain quoted commas. |
| country_codes.csv | country_code | country_code | Integer | Unique numeric identifier from the supplied reference |
| country_codes.csv | country_name | country_name | String | Reference name, including historical entities or aggregates |
| country_codes.csv | country_iso2 | country_iso2 | Nullable string | Source label. Four blanks and repeated labels. |
| country_codes.csv | country_iso3 | country_iso3 | String | Source label. Includes repeated labels and values such as R20 and ZA1. |

The trade CSV uses descriptive headers where the plan uses short aliases. The observed candidate grain is one row per year, exporter, importer, and raw product code. That key is unique in the supplied file and awaits confirmation from the publisher. Use separate exporter and importer aliases when looking up the country reference twice. See the [quality report](DATA_QUALITY_REPORT.md) for product matching and [inventory](DATA_INVENTORY.md) for provenance.
