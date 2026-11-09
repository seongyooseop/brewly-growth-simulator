# 09 Insight brief: what the R1 dashboard shows (2025, synthetic data)

**For:** retail, growth and CX leads · **From:** Business Analyst · **Basis:** the R1 report and the SQL behind its tests.

The data is synthetic, and the patterns below were generated on purpose so the dashboard has something to find. The brief shows how findings would be written up for the people who act on them.

## Summary

| Area | 2025 | Year over year | Read |
|---|---|---|---|
| Refill revenue | 15.80B KRW | +0.9% | Flat: growth comes from new members, not more orders per member |
| Active members (year end) | 46,936 | +2.1% | Slow growth |
| New members | 34,400 | +2.9% | Q4 drives the year |
| Retail net sell-out | 1.89B KRW | +9.7% | Fastest-growing line |
| CX SLA (resolved within 3 days) | 73.2% | +0.1 pt | 11.8 points below the 85% target |

## Finding 1 — One ticket type keeps CX below target

- Device issues are 20% of resolved tickets (2,025 of 10,269), but only 26.7% of them close within 3 days (median 6 days).
- Without device issues the SLA is 84.6%, almost on target. The device rate stayed between 24% and 30% in all eight quarters, so this is a process limit, not a bad month.
- To reach 85% overall with today's other categories, device cases would need to close within 3 days 86% of the time.

**Recommendation:** set a separate SLA for device issues (for example 5 days) and keep 3 days for the rest; pilot a replace-first rule for devices under warranty. **Owner:** CX manager. **Next data:** ticket hand-off steps, to see where device cases wait.

## Finding 2 — Q4 acquisition spend buys members at a higher price

- Q4 2025 spend was 47.7% above Q3 (229.7M vs 155.5M KRW), but new members rose only 22.6% (9,820 vs 8,011).
- Cost per new member rose from 19,409 to 23,388 KRW (+20.5%). Q4 2024 showed the same pattern (+7.3% vs Q3).
- By region the cost is similar (20,800 to 22,200 KRW in 2025), so region is not the lever; channel mix and timing are.

**Recommendation:** before next Q4, run a holdout on the extra Q4 spend in one region, and read channel returns from the marketing-mix model in the main BREWLY project (channel CAC is out of scope here, D-03). **Owner:** growth marketing manager.

## Finding 3 — Cancel requests are an early warning, and retention is not improving

- Month-3 retention has stayed between 46% and 50% for every join cohort from 2024 Q1 to 2025 Q2.
- 72% of subscription change or cancel tickets arrive within two weeks of the member's last order (tickets before week 90, so later orders could still be seen).

**Recommendation:** route cancel tickets to a save offer (refill discount or plan change) before closing them, and track saves as a new KPI in R2. **Owner:** CX with growth.

## Finding 4 — One partner returns more machines

- Partner C's device return rate is 3.9%, against 3.6% for Partner B and 3.2% for Partner A (2025, complete weeks).

**Recommendation:** review return reasons with Partner C (demo units, setup issues). **Owner:** retail sales lead.

## What this data cannot tell

- Why device cases take longer: the CX extract has no hand-off or wait-time fields.
- Which acquisition channel brought each member (D-03).
- Whether a save offer would work: that needs a test, not this dashboard.
