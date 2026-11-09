# 03 User stories

Priority uses MoSCoW. Acceptance criteria are written so that each one can be checked in the report and, where it has a number, against `../tests/expected_values.csv`.

## US-01 Partner sell-out (Must)

As the **retail sales lead**, I want weekly net sell-out by partner and store, so that I can review partner performance every Monday without asking the analytics team.

- Given the year 2025 is selected, when I open page 1, then retail net revenue shows 1,885,800,000 KRW (FT-08).
- Given a week where fewer than 95% of stores have reported, when I look at retail figures, then that week is excluded and the coverage card shows the share of stores reported.
- Given I select one partner, when I drill to stores, then each store's revenue is net of returns.

## US-02 Device returns (Should)

As the **retail sales lead**, I want the device return rate, so that I can spot partners with a return problem.

- Given 2025 is selected, the return rate shows 3.5% (FT-09).
- Returns never reduce units sold; they are reported separately.

## US-03 Acquisition spend and new members (Must)

As the **growth marketing manager**, I want spend by channel and new members by quarter and region, so that I can plan next quarter's budget.

- Given 2025 is selected, acquisition spend is 733,537,000 KRW (FT-06) and new members are 34,400 (FT-05).
- CRM costs are not included in acquisition spend.

## US-04 Blended CAC by region (Must)

As the **growth marketing manager**, I want cost per new member by region, so that I can compare regions on the same basis.

- Given 2025 and Yeongnam are selected, blended CAC shows 22,238 KRW (FT-07).
- The page states that channel-level CAC is not available in this release.

## US-05 CX service level (Must)

As the **CX manager**, I want ticket volume, SLA met % and median resolution days by category, so that I can see which case types miss the 3-day SLA.

- Given 2025 is selected, CX tickets are 10,495 (FT-11) and SLA met is 73.2% (FT-12).
- Open tickets are excluded from SLA and median days.
- Categories can be compared side by side, with SLA shown per category.

## US-06 Member health (Must)

As the **growth marketing manager**, I want active members, lapsed members and cohort retention, so that I can see whether new members keep ordering.

- Active members at 2025-W52 are 46,936 (FT-03); Seoul metro shows 25,991 (FT-04).
- Lapsed members (12+ weeks since last order) are 59,029 as of the latest week (FT-13).
- The 2024 Q1 cohort shows 46.5% retention in month 3 (FT-14).

## US-07 Channel-level CAC (Won't, this release)

As the **growth marketing manager**, I want CAC by acquisition channel.

- **Decision:** not built. Members carry no acquisition-channel tag, so any split would be an attribution guess. Logged for release 2 with two options: tag new members at registration (data engineering) or use the marketing-mix model estimates from the main BREWLY project.

## US-08 Data-quality status (Must)

As the **data governance lead**, I want to see which data checks ran and what was fixed, so that people can trust the numbers they present.

- Page 4 lists all 6 checks with rows checked, rows failing before and after the fix, and status.
- A week with late partner files is visible on the store-coverage chart.

## US-09 Definitions in the report (Should)

As the **finance business partner**, I want each KPI's definition in the report, so that everyone quotes the same number.

- Every measure has a description that appears as its tooltip and matches `02_kpi_definitions.md`.
