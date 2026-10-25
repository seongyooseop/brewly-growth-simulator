"""
Step 2a - Read out the experiments, then turn them into calibration inputs for the MMM.

CRM tests (randomised at member level, analysed from data/marts/experiment_members.csv):
  - crm_holdout_w80:   30% of members got no CRM for 8 weeks. Effect = orders the holdout lost.
  - crm_frequency_w92: 50% of members got about twice the messages for 6 weeks.
  For each test and region:
    1. Sample-ratio check: do group sizes match the design (chi-square)? A mismatch means the
       assignment broke, and the readout should not be trusted.
    2. Delivery check: sends per member by group (the holdout must show zero sends).
    3. Effect: difference in orders per member, Welch t-test, 95% confidence interval.
    4. Power: the smallest effect the test could detect (80% power, 5% two-sided).
    5. Scale to the region: per-member difference x members in the treated group, the change in
       total orders the weekly model can see.

Geo tests (one channel switched off in one region): read out against the other regions in practice
(synthetic control). Here the readout is the true effect plus sampling noise.

Outputs: data/lift_tests.csv (MMM calibration rows), outputs/step2a_experiments.json (for the page).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from generate_data import geometric_adstock, hill

ROOT = Path(__file__).resolve().parents[1]
MARTS, OUT = ROOT / "data" / "marts", ROOT / "outputs"
DESIGN = {"crm_holdout_w80": {"treated": "holdout", "share": 0.30, "start": 80, "weeks": 8},
          "crm_frequency_w92": {"treated": "more_messages", "share": 0.50, "start": 92, "weeks": 6}}
REGIONS = ["SEL", "YNG", "ROK"]
GEO_SE_SHARE, GEO_SE_FLOOR = 0.15, 15.0


def readout(g, treated):
    t = g[g["group"] == treated]["orders_in_window"].to_numpy(float)
    c = g[g["group"] != treated]["orders_in_window"].to_numpy(float)
    diff = t.mean() - c.mean()
    se = np.sqrt(t.var(ddof=1) / len(t) + c.var(ddof=1) / len(c))
    test = stats.ttest_ind(t, c, equal_var=False)
    dof = test.df
    q = stats.t.ppf(0.975, dof)
    mde = (stats.norm.ppf(0.975) + stats.norm.ppf(0.80)) * se
    return {"n_treated": len(t), "n_control": len(c), "mean_treated": t.mean(), "mean_control": c.mean(),
            "diff_per_member": diff, "se_per_member": se, "ci_lo": diff - q * se, "ci_hi": diff + q * se,
            "p_value": float(test.pvalue), "relative_lift": diff / c.mean(), "mde_per_member": mde,
            "sends_treated": g[g["group"] == treated]["sends_in_window"].mean(),
            "sends_control": g[g["group"] != treated]["sends_in_window"].mean()}


def main():
    em = pd.read_csv(MARTS / "experiment_members.csv")
    weekly = pd.read_csv(MARTS / "weekly_region.csv")
    truth = json.loads((ROOT / "data" / "truth" / "ground_truth.json").read_text())
    geo_plan = pd.read_csv(ROOT / "data" / "raw" / "geo_test_plan.csv")
    rng = np.random.default_rng(31)
    results, lift_rows = {}, []

    for exp, d in DESIGN.items():
        e = em[em["experiment"] == exp]
        counts = e["group"].value_counts()
        n_t, n_all = counts.get(d["treated"], 0), len(e)
        srm = stats.chisquare([n_t, n_all - n_t], [n_all * d["share"], n_all * (1 - d["share"])])
        rows = {}
        for r in REGIONS + ["ALL"]:
            g = e if r == "ALL" else e[e["region"] == r]
            res = readout(g, d["treated"])
            res["total_effect_orders"] = res["diff_per_member"] * res["n_treated"]
            res["total_effect_se"] = res["se_per_member"] * res["n_treated"]
            rows[r] = res
            if r == "ALL":
                continue
            w = weekly[(weekly["region"] == r) & weekly["week"].between(d["start"], d["start"] + d["weeks"] - 1)]
            # Observed minus counterfactual, in region orders: the holdout's lost orders (negative), or the
            # extra orders from extra messages. The counterfactual send volume, relative to observed:
            if exp == "crm_holdout_w80":   # observed weeks lack the suppressed messages
                cf = float(((w["crm_sends"] + w["crm_suppressed"]) / w["crm_sends"]).mean())
            else:                           # observed weeks include the extra messages
                cf = float(((w["crm_sends"] - w["crm_boost_sends"]) / w["crm_sends"]).mean())
            effect = res["total_effect_orders"]
            lift_rows.append({"region": r, "channel": "crm", "test": exp, "start_week": d["start"], "n_weeks": d["weeks"],
                              "unit": "orders", "observed_lift": round(effect, 1), "se": round(res["total_effect_se"], 1),
                              "design": "holdout" if exp == "crm_holdout_w80" else "frequency",
                              "share": d["share"],
                              "intensity": 1.0 if exp == "crm_holdout_w80" else round(res["sends_treated"] / res["sends_control"], 3),
                              "cf_value": round(cf, 4)})
        results[exp] = {"design": d, "srm_p_value": float(srm.pvalue), "n_population": int(n_all), "regions": rows}

    # Geo tests: true effect of the switch-off (observed minus planned) plus readout noise
    for g in geo_plan.itertuples():
        p = truth["regions"][g.region]["channels"][g.channel]
        planned = np.array(p["planned_spend"])
        observed = planned.copy()
        observed[g.start: g.start + g.weeks] = 0.0
        resp = lambda s: p["beta"] * hill(geometric_adstock(s, p["decay"]) / p["scale"], p["half_sat"], p["shape"])
        true = (resp(observed) - resp(planned)).sum()
        se = max(GEO_SE_SHARE * abs(true), GEO_SE_FLOOR)
        lift_rows.append({"region": g.region, "channel": g.channel, "test": f"geo_{g.channel}_off", "start_week": g.start,
                          "n_weeks": g.weeks, "unit": "new members", "observed_lift": round(true + rng.normal(0, se), 1),
                          "se": round(se, 1), "design": "geo", "share": 1.0, "intensity": 0.0,
                          "cf_value": g.planned_weekly_spend,
                          "true_lift": round(true, 1)})

    lift = pd.DataFrame(lift_rows)
    lift.drop(columns="true_lift").to_csv(ROOT / "data" / "lift_tests.csv", index=False)
    OUT.mkdir(exist_ok=True)
    (OUT / "step2a_experiments.json").write_text(json.dumps(results, indent=2, default=float))
    pd.set_option("display.width", 220)
    for exp, res in results.items():
        print(f"\n{exp}  population {res['n_population']:,}  SRM p = {res['srm_p_value']:.3f}")
        print(pd.DataFrame(res["regions"]).T[["n_treated", "n_control", "mean_treated", "mean_control", "diff_per_member",
                                               "ci_lo", "ci_hi", "p_value", "relative_lift", "mde_per_member",
                                               "sends_treated", "sends_control", "total_effect_orders"]].round(4).to_string())
    print("\n", lift.to_string(index=False))


if __name__ == "__main__":
    main()
