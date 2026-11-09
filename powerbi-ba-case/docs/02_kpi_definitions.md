# 02 KPI definitions and business rules

Every KPI on the dashboard is defined once here, built once as a DAX measure in `_Measures`, and has one owner. The tooltip description of each measure repeats the definition (BR-09).

| KPI | Definition | Business rules and edge cases | Measure | Owner |
|---|---|---|---|---|
| Refill orders | Capsule refill orders | One order per member per week; duplicate loads removed (DQ-01) | `Refill Orders` | Growth |
| Refill revenue | Refill orders x box price | Price by device model: basic 28,000 KRW, premium 34,000 KRW (assumption) | `Refill Revenue (KRW)` | Finance |
| Active members | Members with a refill order in the last 8 weeks | Counted at the last selected week, so a quarter shows its final week (semi-additive) | `Active Members (8w)` | Growth |
| Lapsed members | Members whose last order is 12+ weeks before the latest data week | Uses the latest week regardless of filters; members who never ordered are excluded | `Lapsed Members (12w+)` | Growth |
| Retention % | Share of a join cohort ordering in the n-th 4-week period after joining | Only fully observed periods are shown; cohorts from 2024 Q1 | `Retention %` | Growth |
| New members | Machines registered in the period | From 2024 only; uses the inactive join-week relationship | `New Members` | Growth |
| Acquisition spend | Spend on referral, store trial, retail partner incentive and brand events | CRM costs are not acquisition spend | `Acquisition Spend (KRW)` | Growth |
| Blended CAC | Acquisition spend / new members | Region level only; channel CAC is out of scope (US-07) | `Blended CAC (KRW)` | Growth |
| Retail net revenue | Partner sell-out net of returns | Complete weeks only (at least 95% of stores reported, DQ-06); a second measure includes incomplete weeks | `Retail Net Revenue (KRW)` | Retail |
| Device return rate | Machines returned / machines sold | Returns are separate rows from sales (DQ-04) | `Device Return Rate` | Retail |
| CRM messages sent | Trigger and boost messages | Records suppressed by the holdout test are not sends | `CRM Messages Sent` | Growth |
| CX tickets | Tickets created in the period | Region from the member record when missing (DQ-05) | `CX Tickets` | CX |
| CX SLA met % | Resolved tickets closed within 3 days / resolved tickets | Open tickets are excluded until resolved | `CX SLA Met %` | CX |
| Median resolution days | Median days to resolve | Resolved tickets only | `Median Resolution Days` | CX |

## Calendar

- Week = ISO week starting Monday. `Dim Week[week_label]` shows `2025-W52`.
- Quarter = 13-week block of the ISO year (`2025 Q4` = ISO weeks 40-52).

## Model

Star schema, single-direction filters. Dimension → fact:

| From (many) | To (one) | Active |
|---|---|---|
| Fact Orders[member_id] | Dim Member[member_id] | Yes |
| Fact Orders[week_id] | Dim Week[week_id] | Yes |
| Dim Member[region_code] | Dim Region[region_code] | Yes |
| Dim Member[join_week_id] | Dim Week[week_id] | **No** (used by `New Members`) |
| Fact Spend[week_id / region_code / channel_code] | Dim Week / Dim Region / Dim Channel | Yes |
| Fact CRM Messages[week_id / region_code] | Dim Week / Dim Region | Yes |
| Fact Sellout[week_id / store_id / sku] | Dim Week / Dim Store / Dim Product | Yes |
| Dim Store[region_code] | Dim Region[region_code] | Yes |
| Fact CX Tickets[member_id / created_week_id] | Dim Member / Dim Week | Yes |

`Fact Cohort Retention` and `DQ Checks` stand alone. DAX for every measure: `../powerbi/measures.dax`.
