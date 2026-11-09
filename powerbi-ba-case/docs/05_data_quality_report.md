# 05 Data-quality report

Six checks run on the source extracts before every refresh (`src/build_model.py`). All six found issues in this refresh, and all six are resolved or flagged in the model. Results load into the `DQ Checks` table and appear on page 4 of the report.

| Check | Source | Rule | Rows checked | Failed before | Root cause | Fix | Prevention |
|---|---|---|---|---|---|---|---|
| DQ-01 | Orders | One refill order per member per week | 1,027,023 | 2,221 | The Yeongnam batch for week 61 was loaded twice | Removed duplicate (member, week) rows | Make the load idempotent: unique key on (member_id, week) |
| DQ-02 | Marketing spend | Weekly spend between 1% and 10,000% of the channel-region median | 1,248 | 8 | Rest of Korea brand-event spend for weeks 40-47 was entered in thousand KRW | Multiplied those rows by 1,000 | Spend template with a fixed currency unit and range validation |
| DQ-03 | Retail sell-out | Store code matches the store master | 11,406 | 3,595 | Partner B sends its own codes (`st012`); Partner A drops zero padding (`ST-12 `) | Normalised to `ST-012` through the store master | Agree a code list with partners; reject unknown codes at load |
| DQ-04 | Retail sell-out | Units are non-negative | 11,406 | 376 | Returns arrive as negative rows in the same file | Split into `units_returned`; net revenue = gross - returns | Separate return field in the partner file spec |
| DQ-05 | CX tickets | Every ticket has a region | 20,269 | 597 | The CX tool export leaves region blank when it fails to look up the member's address (about 3% of tickets, all contact channels) | Filled region from the member record | Make region a required field, or derive it at source |
| DQ-06 | Retail sell-out | At least 95% of stores reported for the week | 104 weeks | 1 week | Partner C's file for 2025-W52 had arrived for only 3 of its 8 stores, so 25 of 30 stores reported | Flagged the week (`sellout_complete = 0`); retail KPIs exclude it until the file lands | Late-file alert to the partner manager on Wednesday |

## What would have gone wrong without the checks

- **DQ-01:** refill orders for the Yeongnam week would have been doubled, a spike that would look like a promotion effect.
- **DQ-02:** Rest of Korea brand-event spend for those eight weeks would have looked almost free, lowering blended CAC.
- **DQ-03:** 3,595 sell-out rows (about a third) would have dropped out of the store-level view on join.
- **DQ-04:** negative units would have netted against sales and hidden the return rate.
- **DQ-06:** the last week would have shown a fall in Partner C sales that is only a late file.

The raw extracts with the issues are in `../data/raw_extract/`, the clean tables in `../data/model/`.
