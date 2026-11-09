# 07 Report specification and traceability

Written before the build and agreed with the stakeholders in workshop 2 (`08_workshops_and_decisions.md`). Each page answers one set of questions for one audience; every visual traces back to a requirement and forward to a measure and a test.

## Global rules

- Canvas 1280 x 720, one theme (`powerbi/brewly_theme.json`): brown for revenue, green for good, red for below target.
- Year and Region slicers are synced across pages 1-3, so a choice made on one page carries to the next.
- Retail figures exclude incomplete partner weeks (DQ-06); the page says so wherever retail appears.
- Numbers on cards are shown in full (no "1.5M"); comparisons are shown as year-over-year % or gap to target.
- Page 5 is a QA page kept visible in the portfolio; in a production app it would be hidden.

## Page 1 — Overview (all three teams, weekly Monday review)

**Questions:** Are we growing? Which region drives orders? Which partner sells most?

```
+-------------------------------------------------------------------------------+
| [Year v] [Quarter v] [Region v]                                               |
+-------------------+-------------------+-------------------+-------------------+
| Refill revenue    | Active members    | New members       | Retail net revenue|
+-------------------+-------------------+-------------------+-------------------+
| Weekly refill orders by region (line)             | Partner net sell-out (bar)|
|                                                   +---------------------------+
|                                                   | Year over year (multi-row)|
+---------------------------------------------------+---------------------------+
```

| Visual | Fields | Filters and interactions | Requirement |
|---|---|---|---|
| 4 KPI cards | Refill Revenue, Active Members (8w), New Members, Retail Net Revenue | Year, Quarter, Region | BR-01, BR-03, BR-06 |
| Line | Week x Refill Orders, series Region | Cross-filters the bar | BR-06 |
| Bar | Partner x Retail Net Revenue | Complete weeks only | BR-01 |
| Multi-row card | YoY % for revenue, active members, new members, retail revenue | Blank when no prior year is selected | BR-10 |

## Page 2 — Acquisition (growth marketing, quarterly budget)

**Questions:** Where did acquisition money go, and what did a new member cost by quarter and region?

```
+-------------------------------------------------------------------------------+
| [Year v] [Region v]                                                           |
+--------------------------------------+----------------------------------------+
| Spend by channel (stacked column)    | New members (column) + blended CAC     |
|                                      | (line)                                 |
+--------------------------------------+----------------------------------------+
| Region table: spend, new members, blended CAC                                 |
+-------------------------------------------------------------------------------+
```

| Visual | Fields | Filters and interactions | Requirement |
|---|---|---|---|
| Stacked column | Quarter x Acquisition Spend, series Channel | CRM excluded | BR-03 |
| Combo | Quarter x New Members (column), Blended CAC (line) | — | BR-03, BR-04 |
| Table | Region, Acquisition Spend, New Members, Blended CAC | Title states channel CAC is out of scope (US-07) | BR-04, BR-07 |

## Page 3 — Retention and CX (growth and CX managers, monthly)

**Questions:** Do new members keep ordering? Which ticket types miss the 3-day SLA?

```
+-------------------------------------------------------------------------------+
| [Year v] [Region v]                                                           |
+---------------+---------------+---------------+---------------+---------------+
| Lapsed        | SLA met %     | Gap to target | Median days   | Tickets/1,000 |
+---------------+---------------+---------------+---------------+---------------+
| Cohort retention matrix (heatmap)       | Tickets by category (bar)           |
|                                         +-------------------------------------+
|                                         | SLA by category table (heatmap)     |
+-----------------------------------------+-------------------------------------+
```

| Visual | Fields | Filters and interactions | Requirement |
|---|---|---|---|
| 5 cards | Lapsed Members, CX SLA Met %, CX SLA Gap vs Target, Median Resolution Days, Tickets per 1,000 Active Members | Year, Region (Lapsed ignores Year by definition) | BR-05, BR-06 |
| Matrix | Join cohort x Month since join, Retention % (colour scale) | Not affected by slicers (cohort table has no week or region) | BR-06 |
| Bar | Category x CX Tickets | Cross-filters the table | BR-05 |
| Table | Category, CX Tickets, CX SLA Met % (colour scale), Median Resolution Days | — | BR-05 |

## Page 4 — Data quality (governance lead and data engineering, every refresh)

| Visual | Fields | Requirement |
|---|---|---|
| 2 cards | DQ Checks Passed, DQ Rows Fixed | BR-08 |
| Table | Check, source, rows failed before and after, status, rule, fix | BR-08 |
| Line | Week x Sell-out Store Coverage | BR-01, BR-08 |

## Page 5 — Test sheet (QA)

Tables holding every measure used in `06_test_cases_uat.md`, by year and by year and region, so a tester can read each expected value without building filters.

## Traceability matrix

| Requirement | User story | Page / visual | Measures | Tests |
|---|---|---|---|---|
| BR-01 Partner sell-out, incomplete weeks excluded | US-01 | P1 bar, P4 line | Retail Net Revenue (KRW), Sell-out Store Coverage | FT-08, BT-03 |
| BR-02 Device return rate | US-02 | P5 table | Device Return Rate | FT-09 |
| BR-03 Spend by channel, new members | US-03 | P1 cards, P2 column and combo | Acquisition Spend (KRW), New Members | FT-05, FT-06 |
| BR-04 Blended CAC by region | US-04 | P2 combo and table | Blended CAC (KRW) | FT-07 |
| BR-05 CX volume, SLA, resolution time | US-05 | P3 cards, bar, table | CX Tickets, CX SLA Met %, Median Resolution Days | FT-11, FT-12 |
| BR-06 Active, lapsed, retention | US-06 | P1 line and cards, P3 matrix | Refill Orders, Active Members (8w), Lapsed Members (12w+), Retention % | FT-01 to FT-04, FT-13, FT-14, BT-01 |
| BR-07 Channel CAC | US-07 (won't) | P2 table title | — | — |
| BR-08 Data-quality status | US-08 | P4 | DQ Checks Passed, DQ Rows Fixed | DEF-01 retest |
| BR-09 Definitions in the report | US-09 | Measure tooltips | All 26 measures | BT-04 |
| BR-10 Year-over-year and target comparison | US-10 | P1 multi-row card, P3 gap card | YoY % measures, CX SLA Gap vs Target | FT-15 to FT-19 |
