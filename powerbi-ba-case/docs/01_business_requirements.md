# 01 Business requirements

**Case:** BREWLY commercial performance dashboard · **Role played:** Business Analyst · **Data:** synthetic

## Background

BREWLY sells coffee machines through three retail partners and capsule refills to about 120,000 registered members in three Korean regions. Three teams run the business from different spreadsheets:

- Retail sales asks the analytics team for partner sell-out every week.
- Growth marketing asks for spend and new members by region.
- Customer service (CX) exports tickets from its own tool.

Each request goes through the analytics team, and the teams' numbers do not agree. Retail quotes gross sell-out while Finance uses net of returns. CRM "sends" include records that the holdout test suppressed. Quarters are cut by calendar month in one file and by ISO week in another.

## Stakeholders

| Stakeholder | What they decide | What they need from the data | Interview takeaway |
|---|---|---|---|
| Retail sales lead | Partner incentives, store priorities | Weekly net sell-out by partner and store, device returns | "I need last week's numbers on Monday, not Thursday. And I can't tell if a dip is real or a late file." |
| Growth marketing manager | Quarterly acquisition budget by channel and region | Spend by channel, new members, cost per new member | "I want CAC by channel." (Not possible yet: members are not tagged with a channel. See US-07.) |
| CX manager | Staffing, escalation rules | Ticket volume by category, time to resolve, SLA | "The 3-day SLA looks fine on average, but I hear device cases take a week." |
| Finance business partner | Revenue reporting | One definition of refill and retail revenue | "Every deck has a different revenue number." |
| Data engineering | Source pipelines | Clear rules for what counts as a data error | Owns the order, partner and CX feeds. |
| Data governance lead | KPI definitions | Signed-off metric definitions with an owner | Signs off `02_kpi_definitions.md`. |

## Problems to solve

1. **Slow access:** routine numbers depend on analyst requests.
2. **Conflicting definitions:** the same KPI is calculated differently by each team.
3. **Silent data issues:** duplicate loads, unit errors, late partner files and unmatched store codes reach the numbers people present.

## Objectives and success measures

| Objective | Measure | Target (case assumption) |
|---|---|---|
| Self-serve weekly view for three teams | Routine requests to the analytics team | -50% within 3 months of release |
| One set of definitions | KPIs with a signed-off definition and owner | 100% of KPIs on the dashboard |
| Trustworthy numbers | Data-quality checks run before each refresh, status visible | 6 of 6 checks visible on page 4 |

## Scope

**In scope (release 1):** weekly refill orders and revenue, active and lapsed members, cohort retention, acquisition spend, new members and blended CAC by region, partner sell-out and device returns, CRM message volume, CX tickets and SLA, data-quality status.

**Out of scope:**

- Channel-level CAC: needs channel attribution. The marketing-mix model in the main BREWLY project answers this.
- Member-level views and personal data. The dashboard shows aggregates only.
- Forecasts and real-time data. Refresh is weekly.

## Business requirements

| ID | Requirement | Priority | User story |
|---|---|---|---|
| BR-01 | Show partner net sell-out by week, partner and store, excluding weeks whose partner files are incomplete | Must | US-01 |
| BR-02 | Show device return rate | Should | US-02 |
| BR-03 | Show acquisition spend by channel and new members by quarter and region | Must | US-03 |
| BR-04 | Show blended cost per new member by region | Must | US-04 |
| BR-05 | Show CX ticket volume, SLA met % and median resolution days by category | Must | US-05 |
| BR-06 | Show active members, lapsed members and cohort retention | Must | US-06 |
| BR-07 | Show channel-level CAC | Won't (this release) | US-07 |
| BR-08 | Show data-quality check results for the current refresh | Must | US-08 |
| BR-09 | Every KPI shows its definition in the report | Should | US-09 |

## Non-functional requirements

- Refresh every Monday 10:00, after partner files arrive (Monday to Wednesday). Weeks below 95% store coverage are flagged, not hidden.
- Each page loads in under 5 seconds on the full dataset (about 1 million order rows).
- Reporting calendar: ISO weeks, quarters as 13-week blocks, so that 2024 and 2025 both have 52 weeks.
- Internal audience only. No personal data leaves the model.

## Assumptions

- One refill order is one capsule box: 28,000 KRW for basic machines and 34,000 KRW for premium (the source data holds order counts only).
- Partner sell-out and CX extracts are synthetic and generated for this case (`src/build_model.py`).
