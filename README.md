# BREWLY Growth Analytics (synthetic data)

**Live demo:** https://seongyooseop.github.io/brewly-growth-simulator/simulator/

An end-to-end analytics portfolio project for a **fictional** device-and-refills membership brand, "BREWLY"
(capsule coffee), in three Korean regions. Paid brand advertising is assumed to be unavailable, as in regulated
categories, so growth runs through owned channels: member referrals, store trials, retail partners, brand events
and CRM messages. All data is synthetic, generated from a known process so every step can be scored against the truth.

## At a glance

- **Data:** 121,634 simulated members, about 1.02 million capsule orders and 2.7 million CRM message records,
  turned into analysis tables with SQL (DuckDB).
- **Questions:** (1) What does CRM really add? (2) How should the 2026 budget be split across five channels?
  (3) Who should get a CRM message?
- **Answers:**
  - Attribution credits CRM with about ₩20 of margin per won. A randomised 30% member holdout puts the
    average at ₩0.4-1.1, and doubling messages added nothing measurable (p = 0.76).
  - With flat budgets: cut CRM volume about 30%, add about 30% to member referrals and 16-28% to store trials,
    trim retail partners and brand events. Expected +₩38M / +₩17M / +₩13M of gross margin a year.
  - Choose who keeps getting messages by predicted uplift: keeping 70% of messages keeps about 86% of CRM's
    extra orders, versus 51% when messaging the members most likely to buy.
- **Why it can be trusted:** replayed on the hidden truth, the plan captures 78-88% of the best possible gain.
  The plan an analyst would make before experiments (attribution plus an observational model) raises CRM by 30%
  and loses margin in every region.
- **Try it:** the live demo or `simulator/index.html` (six tabs, each with a "How to read this tab" guide).
- **How AI was used:** [`docs/ai_workflow_log.md`](docs/ai_workflow_log.md).

## Pipeline

```
python src/generate_data.py        # members, orders, CRM sends, experiments, spend (data/raw) + hidden truth
python src/build_marts.py          # SQL marts (sql/marts.sql) -> data/marts
python src/estimate_ltv.py         # value of a new member from the cohort mart
python src/check_traps.py          # naive vs controlled regression against the truth
python src/analyze_experiments.py  # CRM holdout and frequency tests; geo tests -> data/lift_tests.csv
python src/fit_mmm.py --holdout 12 # acquisition MMM, out-of-sample check
python src/fit_mmm.py              # acquisition MMM calibrated with geo tests
python src/fit_mmm.py --no-lift    # observational-only fit, for comparison
python src/measure_crm.py          # attribution vs experiments; CRM response curve
python src/validate_mmm.py         # convergence, holdout, truth recovery
python src/optimize_budget.py      # five-channel budget plan, replayed on the truth
python src/uplift_model.py         # T-learner uplift model for CRM targeting
python src/build_simulator.py      # simulator/index.html
```

Setup: `python -m venv .venv`, `.venv/Scripts/pip install -r requirements.txt`, `PYTHONUTF8=1` on Windows.
Posterior samples (`models/`) are not in the repository; `src/fit_mmm.py` recreates them.

## 1. Data (member level)

| Table | Rows | Contents |
| --- | --- | --- |
| `data/raw/members.parquet` | 121,634 | region, join week, age band, device model |
| `data/raw/orders.parquet` | 1,024,802 | member, week |
| `data/raw/crm_sends.parquet` | 2,702,906 | member, week, type (trigger, boost, suppressed by the holdout) |
| `data/raw/experiment_groups.parquet` | 243,268 | random assignment for the two CRM tests |
| `data/raw/marketing_spend.csv`, `calendar.csv` | 1,248, 312 | acquisition spend; promotions, holidays, category search-trend index |

Planted traps: retail-partner incentives are paid per device sold, so they follow demand; referrals and store
trials share one seasonal calendar (weekly correlation 0.81-0.97); CRM "running low" messages go to members
who are about to reorder anyway, so message volume moves with baseline demand.

## 2. SQL marts (`sql/marts.sql`)

`weekly_region` (model input and dashboard), `cohort_monthly` (13 four-week periods per join cohort),
`lifecycle_funnel`, `experiment_members` (intention-to-treat population and outcomes) and `uplift_training`.
Active members use an observable rule (an order or a join in the last 8 weeks), since true churn is never seen.

## 3. Experiments (`src/analyze_experiments.py`)

| Test | Design | Result (all regions) |
| --- | --- | --- |
| CRM holdout | 30% of members, no CRM for 8 weeks | -0.038 orders per member, 95% CI -0.060 to -0.016, p < 0.001; sample-ratio check p = 0.60 |
| CRM frequency | 50% of members, about 2.2x the messages for 6 weeks | -0.003, 95% CI -0.020 to +0.015, p = 0.76 |
| Geo: store trials | switched off in Yeongnam, 6 weeks | -84 ± 15 new members (model after calibration: -87) |
| Geo: retail partners | paused in Rest of Korea, 4 weeks | -23 ± 15 new members (model: -36) |

Seoul's holdout reads on its own (p = 0.002); Yeongnam and Rest of Korea do not (p = 0.36, 0.20), with
minimum detectable effects about twice the true effect. The plan uses the pooled curvature.

## 4. CRM: three answers (`src/measure_crm.py`)

| Region | Attribution ROI | Holdout average ROI [95% CI] | Frequency marginal ROI | Truth: average / marginal |
| --- | --- | --- | --- | --- |
| Seoul metro | 20.4 | 1.05 [0.38, 1.72] | -0.26 | 1.52 / -0.25 |
| Yeongnam | 19.9 | 0.44 | 0.11 | 1.36 / -0.27 |
| Rest of Korea | 20.3 | 0.70 | 0.13 | 1.47 / -0.27 |

Truth comes from re-running the member simulation with and without CRM (same random numbers), so it counts
purchases a reminder only moved earlier. CRM's true response peaks at about 75% of today's volume.

## 5. Acquisition MMM (`src/fit_mmm.py`, `src/validate_mmm.py`)

Hierarchical Bayesian MMM (PyMC, nutpie) for new members: adstock, Hill saturation, ROI parameterisation
(as in Google Meridian), partial pooling across regions, calibration with the two geo tests.

| Check | Observational | + geo tests |
| --- | --- | --- |
| Divergences / max R-hat | 0 / 1.005 | 0 / 1.006 |
| Truth inside 90% interval, marginal ROI | 5 of 12 | 9 of 12 |
| Mean absolute error, marginal ROI | 0.45 | 0.35 |
| Break-even calls right | 9 of 12 | 12 of 12 |

Out-of-sample (last 12 weeks unseen): MAPE 5.0% Seoul, 9.4% Yeongnam, 6.7% Rest of Korea.
Both models underrate brand events (about 0.4 vs 0.8-0.9); no test covers them.

Why CRM is not in the MMM: six specifications that put weekly orders and CRM in the model either contradicted
the experiments or did not converge (carry-over, saturation and baseline traded off freely), because message
volume follows baseline demand. Member-level holdouts measure it directly.

## 6. Budget plan (`src/optimize_budget.py`)

Flat budgets, guardrails +-30% per channel (brand events +-20%), greedy marginal reallocation over 1,000
paired draws (MMM for acquisition, experiment curve for CRM).

| Channel | Seoul metro | Yeongnam | Rest of Korea |
| --- | --- | --- | --- |
| Member referrals | +29% | +29% | +30% |
| Store trials | +20% | +16% | +28% |
| Retail partners | -10% | -7% | -18% |
| Brand events | -19% | -19% | -20% |
| CRM messages | -30% | -29% | -29% |

| Region | Budget | Expected extra margin / yr (80%) | P(gain) | Truth | Share of best | Before experiments, truth |
| --- | --- | --- | --- | --- | --- | --- |
| Seoul metro | ₩489M | +₩38M (22 to 55) | 99.5% | +₩62M | 87% | -21% |
| Yeongnam | ₩220M | +₩17M (10 to 24) | >99.9% | +₩23M | 78% | -31% |
| Rest of Korea | ₩184M | +₩13M (5 to 20) | 97.6% | +₩29M | 88% | -11% |

## 7. CRM targeting (`src/uplift_model.py`)

T-learner (two gradient-boosting models, with and without a message) trained on the randomised holdout,
48,673 triggered members, 40% kept for evaluation. Keeping 70% of messages: by predicted uplift 86% of extra
orders, random 70%, by likelihood to buy 51%. True uplift rises across predicted deciles (0.044 to 0.125 per
message); rank correlation with the truth 0.26, noisy for individuals but good for ordering groups.

## 8. Interactive page (`src/build_simulator.py`)

One self-contained HTML file with six tabs: weekly dashboard, experiments, model check, budget simulator,
CRM targeting and decision memo. Hand-drawn SVG, no libraries, light and dark themes, works at phone width.
