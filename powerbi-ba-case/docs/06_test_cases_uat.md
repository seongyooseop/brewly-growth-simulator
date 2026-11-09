# 06 Functional tests and UAT

## Functional tests: measures reconcile to SQL

Each DAX measure is checked against an independent SQL query on the same clean tables (DuckDB, `../tests/expected_values.csv`, which also stores the SQL). A test passes when the Power BI value matches to the displayed precision. The Power BI values below were read from the model open in Power BI Desktop with `../tests/run_dax_tests.ps1` (results in `../tests/dax_results.csv`): 14 of 14 pass.

| Test | Measure | Filter | Expected (SQL) | Power BI | Result |
|---|---|---|---|---|---|
| FT-01 | Refill Orders | ISO year 2025 | 514,942 | 514,942 | Pass |
| FT-02 | Refill Revenue (KRW) | ISO year 2025 | 15,798,640,000 | 15,798,640,000 | Pass |
| FT-03 | Active Members (8w) | Week 2025-W52 | 46,936 | 46,936 | Pass |
| FT-04 | Active Members (8w) | Week 2025-W52, Seoul metro | 25,991 | 25,991 | Pass |
| FT-05 | New Members | ISO year 2025 | 34,400 | 34,400 | Pass |
| FT-06 | Acquisition Spend (KRW) | ISO year 2025 | 733,537,000 | 733,537,000 | Pass |
| FT-07 | Blended CAC (KRW) | ISO year 2025, Yeongnam | 22,238 | 22,238 | Pass |
| FT-08 | Retail Net Revenue (KRW) | ISO year 2025, complete weeks | 1,885,800,000 | 1,885,800,000 | Pass |
| FT-09 | Device Return Rate | ISO year 2025, complete weeks | 3.5% | 3.5% | Pass |
| FT-10 | CRM Messages Sent | ISO year 2025, excluding suppressed | 1,327,094 | 1,327,094 | Pass |
| FT-11 | CX Tickets | ISO year 2025 | 10,495 | 10,495 | Pass |
| FT-12 | CX SLA Met % | ISO year 2025, resolved tickets | 73.2% | 73.2% | Pass |
| FT-13 | Lapsed Members (12w+) | As of 2025-W52 | 59,029 | 59,029 | Pass |
| FT-14 | Retention % | Cohort 2024 Q1, month 3 | 46.5% | 46.5% | Pass |

Behaviour tests (no number):

| Test | Check | Result |
|---|---|---|
| BT-01 | Selecting a quarter, `Active Members (8w)` equals the value for that quarter's last week | Pass (2025 Q4 = 2025-W52 = 46,936) |
| BT-02 | Region slicer filters orders, spend, sell-out, CRM and CX pages consistently | Pass (sum over the three regions equals the total for all five facts) |
| BT-03 | 2025-W52 is excluded from `Retail Net Revenue (KRW)` and included in the "incl. incomplete" measure | Pass (blank vs 55,998,800) |
| BT-04 | Every measure shows its description as a tooltip in the Data pane | Pass (21 of 21 measures have a description) |

## Defects found in testing

| ID | Found by | Symptom | Root cause | Fix | Retest |
|---|---|---|---|---|---|
| DEF-01 | Test sheet (FT-03 table) | A row with a blank year showed 10,138 active members (and 5,687 / 2,377 / 2,074 by region) | Members who joined before 2024 have join weeks outside `Dim Week`, so the inactive join-week relationship adds a blank row to `Dim Week`. For that row `MAX ( week_id )` is blank, and the 8-week window fell back to week 0 | `Active Members (8w)` returns blank when there is no week in context | Pass: no blank-year rows (`DEF-01` in `dax_results.csv`) |

## UAT script

Each stakeholder completes their tasks in the report without help, then signs off or raises issues.

| Stakeholder | Tasks |
|---|---|
| Retail sales lead | Find last complete week's net sell-out for Partner B; find the partner with the highest device return rate; explain why 2025-W52 is not shown |
| Growth marketing manager | Compare 2025 Q3 and Q4 acquisition spend by channel; find the region with the lowest blended CAC in 2025; read month-3 retention for the latest cohort |
| CX manager | Find the category with the lowest SLA met % in 2025 and its median days; check whether the share of tickets per 1,000 active members rose in Q4 |
| Finance business partner | Confirm refill revenue and retail net revenue definitions in the tooltips match the KPI sheet |

## UAT issue log (simulated for this case)

| ID | Raised by | Issue | Resolution | Status |
|---|---|---|---|---|
| UAT-01 | Retail sales lead | Partner B revenue looked about 2% lower than the partner's own report | Partner reports gross sell-out; the dashboard shows net of returns by agreed definition. Added "net of returns" to the visual title and tooltip | Closed |
| UAT-02 | CX manager | Wanted open tickets counted as SLA misses | Kept the signed-off rule (resolved tickets only) and added an open-ticket count to the backlog for release 2 | Deferred |
| UAT-03 | Growth marketing manager | Asked again for CAC by channel | Confirmed as US-07 (won't, this release) with the two options for release 2 | Closed |

## Sign-off

| Stakeholder | Decision | Date |
|---|---|---|
| Retail sales lead | Approved | (simulated) |
| Growth marketing manager | Approved with US-07 deferred | (simulated) |
| CX manager | Approved with UAT-02 deferred | (simulated) |
| Data governance lead | Definitions approved | (simulated) |
