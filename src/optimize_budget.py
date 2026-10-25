"""
Step 3 - Budget reallocation for 2026 across all five channels.

Question: keeping each region's total budget at its 2025 level, how should spend be split across the four
acquisition channels and CRM to maximise expected gross margin?

Response curves, in one currency (KRW of gross margin, plan year):
  - acquisition channels: the calibrated MMM's posterior (new members x value of a new member)
  - CRM: the experiment-based curve from step 2b (extra orders x margin per order)
Draws are paired by index (1,000 each), so every scenario uses one MMM draw and one CRM draw.

Planning assumption: 2026 repeats 2025's weekly pattern; each channel's whole pattern is scaled by one
multiplier (for CRM: send volume, i.e. how widely the running-low journey is triggered).
Guardrails (business rules): each channel moves at most +-30% vs 2025; brand events at most +-20%
(venues are booked a year ahead).
Method: greedy marginal reallocation (0.25% of the region budget per step) on the expected margin.

Validation: the recommendation is replayed on the TRUE response, next to the truth's own best plan and the
plan an analyst would make before experiments: observational MMM + CRM valued at its attributed ROI.

Outputs: outputs/step3_*.csv, outputs/simulator_data.json
"""

import json

import numpy as np
import pandas as pd

from generate_data import geometric_adstock as true_adstock, hill
from mmm_core import (ACQ_CHANNELS, CHANNELS, LABELS, REGION_NAMES, REGIONS, ROOT, adstock_np, load_arrays,
                      load_posterior, load_truth, member_value)

OUT = ROOT / "outputs"
PLAN = slice(52, 104)
BOUNDS = {c: (0.7, 1.3) for c in CHANNELS} | {"events": (0.8, 1.2)}
STEP_SHARE = 0.0025
N_DRAWS = 1000
GRID = np.round(np.arange(0, 2.0001, 0.05), 2)
CRM = len(ACQ_CHANNELS)  # index of CRM in CHANNELS


def stacked(idata, var, idx):
    return idata.posterior[var].stack(sample=("chain", "draw")).transpose("sample", ...).values[idx]


class PlanResponse:
    """Plan-year margin (KRW) per channel at a spend multiplier, for each draw: MMM for acquisition, a curve for CRM.

    Adstock is linear, so adstock(history + s * plan) = adstock(history) + s * adstock(plan): both parts are
    computed once and any multiplier is then a cheap Hill evaluation.
    """

    def __init__(self, idata, d, crm_curves, rng):
        idx = rng.choice(idata.posterior.sizes["chain"] * idata.posterior.sizes["draw"], N_DRAWS, replace=False)
        self.decay, self.half_sat, self.shape = (stacked(idata, v, idx) for v in ("adstock_decay", "half_sat", "hill_shape"))
        self.beta = stacked(idata, "beta", idx)
        self.unit = d["y_scale"] * member_value()                  # (R,) KRW per normalised unit of new members
        self.crm = crm_curves                                       # (S, R, grid) KRW
        S, R, C = self.beta.shape
        x = d["spend"] / d["spend_scale"][None]
        hist, plan = x.copy(), x.copy()
        hist[PLAN], plan[: PLAN.start] = 0, 0
        self.a_hist, self.a_plan = np.zeros((S, R, C, 52)), np.zeros((S, R, C, 52))
        for s in range(S):
            for j in range(R):
                for k in range(C):
                    self.a_hist[s, j, k] = adstock_np(hist[:, j, k], self.decay[s, k])[PLAN]
                    self.a_plan[s, j, k] = adstock_np(plan[:, j, k], self.decay[s, k])[PLAN]

    def margin(self, j, k, mult):
        if k == CRM:
            return np.array([np.interp(mult, GRID, c) for c in self.crm[:, j]])
        ad = self.a_hist[:, j, k] + mult * self.a_plan[:, j, k] + 1e-9
        return (self.beta[:, j, k, None] * hill(ad, self.half_sat[:, k, None], self.shape[:, k, None])).sum(-1) * self.unit[j]


class TrueResponse:
    """Same question answered with the hidden truth: true acquisition response and the counterfactual CRM curve."""

    def __init__(self, truth, d):
        self.truth, self.spend = truth, d["spend"]

    def margin(self, j, k, mult):
        t = self.truth["regions"][REGIONS[j]]
        if k == CRM:
            return np.atleast_1d(np.interp(mult, GRID, t["channels"]["crm"]["plan_year_curve_orders"]) * self.truth["margin_per_order"])
        p = t["channels"][ACQ_CHANNELS[k]]
        x = self.spend[:, j, k].copy()
        x[PLAN] *= mult
        units = (p["beta"] * hill(true_adstock(x, p["decay"]) / p["scale"], p["half_sat"], p["shape"]))[PLAN].sum()
        return np.atleast_1d(units * t["value_per_new_member"])


def optimise(resp, j, base):
    mult = np.ones(len(CHANNELS))
    step = STEP_SHARE * base.sum()
    gain = lambda k, m: resp.margin(j, k, m).mean()
    for _ in range(5000):
        up = [gain(k, mult[k] + step / base[k]) - gain(k, mult[k]) if mult[k] + step / base[k] <= BOUNDS[c][1] + 1e-9 else -np.inf
              for k, c in enumerate(CHANNELS)]
        down = [gain(k, mult[k]) - gain(k, mult[k] - step / base[k]) if mult[k] - step / base[k] >= BOUNDS[c][0] - 1e-9 else np.inf
                for k, c in enumerate(CHANNELS)]
        to, frm = int(np.argmax(up)), int(np.argmin(down))
        if to == frm or up[to] - down[frm] <= 1e-6:
            break
        mult[to] += step / base[to]
        mult[frm] -= step / base[frm]
    return mult


def total(resp, j, mult):
    return sum(resp.margin(j, k, mult[k]) for k in range(len(CHANNELS)))


def main():
    rng = np.random.default_rng(11)
    d = load_arrays()
    truth = load_truth()
    crm_draws = np.load(OUT / "crm_curve_draws.npy")
    crm_info = json.loads((OUT / "step2b_crm.json").read_text())["regions"]
    # Before experiments: CRM valued at its attributed ROI, as a straight line through the 2025 point
    naive_crm = np.stack([np.outer(np.ones(N_DRAWS), GRID) * crm_info[r]["attributed_roi"] * crm_info[r]["plan_year_spend"]
                          for r in REGIONS], 1)
    cal = PlanResponse(load_posterior("full"), d, crm_draws, rng)
    obs = PlanResponse(load_posterior("full_nolift"), d, naive_crm, rng)
    true = TrueResponse(truth, d)
    base = np.concatenate([d["spend"][PLAN].sum(0), d["crm_spend"][PLAN].sum(0)[:, None]], axis=1)  # (R, 5)
    ones = np.ones(len(CHANNELS))

    alloc_rows, uplift_rows, recs = [], [], {}
    for j, r in enumerate(REGIONS):
        rec, rec_obs, rec_true = optimise(cal, j, base[j]), optimise(obs, j, base[j]), optimise(true, j, base[j])
        recs[r] = rec
        for k, c in enumerate(CHANNELS):
            eps = 0.01
            mroi = lambda resp, m: (resp.margin(j, k, m + eps) - resp.margin(j, k, m)).mean() / (eps * base[j, k])
            alloc_rows.append({"region": r, "channel": c, "spend_2025": base[j, k], "recommended_spend": rec[k] * base[j, k],
                               "change_pct": rec[k] - 1, "before_experiments_change_pct": rec_obs[k] - 1,
                               "truth_optimal_change_pct": rec_true[k] - 1, "mroi_now": mroi(cal, 1.0), "mroi_after": mroi(cal, rec[k]),
                               "true_mroi_now": mroi(true, 1.0)})
        draws = total(cal, j, rec) - total(cal, j, ones)
        tg = lambda m: (total(true, j, m) - total(true, j, ones))[0]
        u = {"region": r, "budget_2025": base[j].sum(), "expected_uplift_margin": draws.mean(),
             "uplift_p10": np.percentile(draws, 10), "uplift_p90": np.percentile(draws, 90), "prob_uplift_positive": (draws > 0).mean(),
             "true_uplift_margin": tg(rec), "true_uplift_before_experiments": tg(rec_obs), "true_best_possible_margin": tg(rec_true)}
        u["share_of_best_captured"] = u["true_uplift_margin"] / u["true_best_possible_margin"]
        u["before_experiments_share_of_best"] = u["true_uplift_before_experiments"] / u["true_best_possible_margin"]
        uplift_rows.append(u)

    alloc, uplift = pd.DataFrame(alloc_rows), pd.DataFrame(uplift_rows)
    alloc.round(3).to_csv(OUT / "step3_recommended_allocation.csv", index=False)
    uplift.round(3).to_csv(OUT / "step3_uplift.csv", index=False)
    export_simulator(cal, d, base, recs)
    pd.set_option("display.width", 250)
    show = alloc.assign(**{c: alloc[c].map("{:+.0%}".format) for c in ["change_pct", "before_experiments_change_pct", "truth_optimal_change_pct"]})
    print(show[["region", "channel", "spend_2025", "change_pct", "truth_optimal_change_pct", "before_experiments_change_pct",
                "mroi_now", "mroi_after", "true_mroi_now"]].round(2).to_string(index=False))
    shares = ["region", "prob_uplift_positive", "share_of_best_captured", "before_experiments_share_of_best"]
    print("\nKRW M except shares\n", uplift.assign(**{c: uplift[c] / 1e6 for c in uplift.columns if c not in shares}).round(3).to_string(index=False))


def export_simulator(cal, d, base, recs):
    """Per-draw response curves on a spend-multiplier grid; channels add up, so the page can sum them."""
    n_export = 200
    ltv = json.loads((OUT / "step1_ltv.json").read_text())
    data = {"brand": "BREWLY (fictional capsule-coffee brand)", "plan_year": 2026, "template_year": 2025,
            "regions": REGIONS, "region_names": REGION_NAMES, "channels": CHANNELS,
            "channel_labels": [LABELS[c] for c in CHANNELS], "is_crm": [c == "crm" for c in CHANNELS],
            "unit_value": [ltv["margin_per_order"] if c == "crm" else ltv["value_per_new_member"] for c in CHANNELS],
            "grid": GRID.tolist(), "bounds": {c: list(BOUNDS[c]) for c in CHANNELS}, "n_draws": n_export, "region_data": {}}
    for j, r in enumerate(REGIONS):
        curves = np.stack([np.stack([cal.margin(j, k, g)[:n_export] for g in GRID], -1) for k in range(len(CHANNELS))], 1)
        data["region_data"][r] = {"spend_2025": base[j].round(-3).tolist(), "recommended_multiplier": recs[r].round(4).tolist(),
                                  "curves": (curves / 1e6).round(3).tolist()}  # [draw][channel][grid] plan-year margin, KRW M
    (OUT / "simulator_data.json").write_text(json.dumps(data))


if __name__ == "__main__":
    main()
