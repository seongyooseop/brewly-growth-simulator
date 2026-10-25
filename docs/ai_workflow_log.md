# AI workflow log

How this project was built with an AI coding agent, what went wrong, and how each problem was caught.
Written for reviewers who want to see how AI was used, not only the result.

- **Agent:** Claude Code (Claude Opus 5.5), running locally on Windows with a Python virtual environment.
- **Dates:** 2026-10-24 to 2026-10-25, two working sessions. The model structure comes from an earlier pharma
  project ([mmm-budget-simulator](https://github.com/seongyooseop/mmm-budget-simulator)).
- **Split of work:**
  - *Me:* set the business questions and the scenario, asked for a review against a target job description,
    required a check against the hidden truth at every stage, and decided what to keep.
  - *The agent:* wrote and ran the code, ran the diagnostics, and drafted the explanations.

## Scope

The first draft used weekly aggregate data and paid media channels. A review against the target role (digital
performance analytics in a regulated consumer business) found it strong on experiments, modelling and optimisation,
but weak on member-level CRM analysis, monitoring dashboards, significance testing and SQL, and built around paid
channels a regulated brand could not use. The final build adds those.

## Working method

1. **Every stage is checked against something independent:** the hidden truth, never the agent's own claim.
2. **Known truth stays out of fitting.** `data/truth/` is used only for scoring.
3. **Fixes must be things a real analyst could do:** a better control, an experiment, a stated assumption,
   or a different method, not a prior nudged toward the known answer.

## Issues log

| # | Stage | What went wrong | How it surfaced | Fix | Lesson |
| --- | --- | --- | --- | --- | --- |
| 1 | Data | CRM's marginal return came out higher than its average | Truth table | Real reminders only work when a member is close to running out; uplift now depends on readiness and fades with recent messages | Check that a simulated mechanism behaves like the real one before modelling it |
| 2 | Data | At first, CRM still paid back at the margin, against the over-messaging scenario | Truth curve was S-shaped with today's volume on the rising side | Message volume relative to the base was too low for the scenario; doubled it via cost per message | Make the synthetic world match the business story you want to test |
| 3 | Readout | Sign of the holdout effect flipped when passed to the model | Reading the calibration table against the readout table | Defined every readout as observed minus counterfactual | Write the sign convention down once and use it everywhere |
| 4 | MMM | **CRM did not work inside the weekly model.** Average ROI about 30, then no convergence (R-hat 1.5) | Truth recovery and convergence table | Six specifications: experiment form by design, carry-over priors, per-member intensity, a journey-eligibility control. Each either contradicted the experiments or did not converge | Triggered CRM moves with baseline demand; weekly aggregates cannot separate them. Measure it with member-level holdouts, as CRM teams do |
| 5 | MMM | A "members due to reorder" control built in SQL did not track message volume at all (correlation about 0) | Correlation check before refitting | Dropped it. The SQL used `LEAD ... PARTITION BY member_id` so each member's next order was their own | A control is only useful if it measures the confounder; check before using it |
| 6 | Truth | Holdout said CRM averaged about half of the "true" ROI | Comparing readout and truth | The first truth summed instant uplift. Re-ran the member simulation with and without CRM (same random numbers): reminders that only move a purchase earlier add little. The holdout was closer than the truth | Define the truth as the counterfactual you care about, not the easiest sum |
| 7 | Plan | The CRM curve cannot fall below zero, so it reads the next message at 0.1-0.25 instead of -0.25 | Truth comparison | Kept and disclosed; the call (cut CRM to the guardrail) is the same | Know which way a model's simplification biases the answer |
| 8 | Plan | Brand events underrated by both models (0.4 vs 0.8-0.9) | Truth recovery | Reported; the memo proposes an events geo test and caps the cut at 20% | No experiment, no confidence |
| 9 | Page | Cohort chart and heatmap zigzagged; the funnel grew at its last stage | Visual check of every tab | Four-week periods instead of uneven months; funnel stages nested in SQL | Look at the page; a data artefact can look like a finding |
| 10 | Page | Experiment table columns were cut off; KPI cards wrapped 5 + 1 | Full-page screenshots of all six tabs | Full-width table with the chart below; 3-column card grid | Check every tab, at desktop and phone width, light and dark |

## Issues from the first draft (weekly aggregate data)

| # | What went wrong | Fix |
| --- | --- | --- |
| 1 | Cohort table counted 5 weeks per month, value of a new member 10% too high | 52 weeks split into 12 months explicitly |
| 2 | An unobserved demand shock kept search at 3-4x its true ROI after a geo test | Made category demand observable through a search-trend index |
| 3 | A steep S-curve let a demand-following channel slip past its geo test | Hill-slope prior set to a gentle S, written down |
| 4 | Without experiments CRM looked like the best channel | Member holdout and frequency test |
| 5 | Full-length fit did not converge (R-hat 1.53) | Search spend was collinear with the demand control; added quarterly budget resets |

An earlier lesson that shaped this workflow comes from my doctoral research: an LLM built seller-level lag
variables without `PARTITION BY seller_id`, mixing sellers' values. Odd descriptive statistics and a comparison
with the raw data exposed it. Since then every AI-written transformation gets an independent check.

## Demo script (5 minutes)

1. **Weekly dashboard:** KPIs from the SQL marts, lifecycle funnel, cohort heatmap.
2. **Experiments:** the 30% holdout (significant nationally, p < 0.001; not in the two small regions, and why),
   the frequency test (no gain from twice the messages), sample-ratio and delivery checks.
3. **Model check:** CRM attribution about 20 vs holdout about 1 vs truth; why CRM is measured by experiments,
   not the MMM; geo tests fixing retail partners.
4. **Budget simulator:** push CRM back up and watch the gain fall.
5. **CRM targeting:** uplift vs "likely to buy" at the plan's 70% volume (86% vs 51%).
6. **Decision memo:** the plan, the range, the next tests.
