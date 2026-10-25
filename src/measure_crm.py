"""
Step 2b - How much does CRM really add? Three answers from the member data, and a response curve.

  1. Attribution (what a CRM dashboard usually reports): an order in the same week as a message is
     credited to the message. Computed in SQL from the send and order logs.
  2. Holdout (average effect): orders the 30% holdout lost, per message they would have received.
  3. Frequency test (effect of more messages): extra orders per extra message, the slope above today's volume.

Response curve for the budget plan, per region: plan-year incremental orders at send volume m (1 = 2025):
  f(m) = F1 * (1 - exp(-b m)) / (1 - exp(-b))
  F1 (level at today's volume) comes from the region's holdout; the curvature b from the national ratio of
  the frequency-test slope to the holdout average (pooled, because each region alone is too noisy).
  Uncertainty: 1,000 draws of both readouts from their sampling distributions.

Outputs: outputs/step2b_crm.json (summary and truth check), outputs/crm_curve_draws.npy (draws x region x grid)
"""

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "outputs"
REGIONS = ["SEL", "YNG", "ROK"]
GRID = np.round(np.arange(0, 2.0001, 0.05), 2)
N_DRAWS = 1000
PLAN = (52, 103)


def attribution():
    con = duckdb.connect()
    sql = f"""
        WITH s AS (SELECT member_id, week FROM read_parquet('{(RAW / 'crm_sends.parquet').as_posix()}')
                   WHERE send_type IN ('trigger', 'boost')),
             o AS (SELECT DISTINCT member_id, week FROM read_parquet('{(RAW / 'orders.parquet').as_posix()}')),
             m AS (SELECT member_id, region FROM read_parquet('{(RAW / 'members.parquet').as_posix()}'))
        SELECT m.region, count(*) AS sends, count(o.member_id) AS sends_followed_by_order
        FROM s JOIN m USING (member_id) LEFT JOIN o USING (member_id, week)
        GROUP BY 1 ORDER BY 1"""
    return con.execute(sql).df().set_index("region")


def curvature(rho, k):
    """b such that the average slope of g(m) = (1 - e^-bm)/(1 - e^-b) over [1, k] equals rho (0 < rho < 1)."""
    g = lambda b, m: (1 - np.exp(-b * m)) / (1 - np.exp(-b))
    return brentq(lambda b: (g(b, k) - 1) / (k - 1) - rho, 1e-6, 60)


def main():
    exp = json.loads((OUT / "step2a_experiments.json").read_text())
    weekly = pd.read_csv(ROOT / "data" / "marts" / "weekly_region.csv")
    truth = json.loads((ROOT / "data" / "truth" / "ground_truth.json").read_text())
    ltv = json.loads((OUT / "step1_ltv.json").read_text())
    margin, cost = ltv["margin_per_order"], 120
    att = attribution()
    rng = np.random.default_rng(5)

    def window(r, start, n, col):
        w = weekly[(weekly["region"] == r) & weekly["week"].between(start, start + n - 1)]
        return float(w[col].sum())

    hold, freq = exp["crm_holdout_w80"], exp["crm_frequency_w92"]
    per_send = {}
    for r in REGIONS + ["ALL"]:
        regs = REGIONS if r == "ALL" else [r]
        suppressed = sum(window(x, 80, 8, "crm_suppressed") for x in regs)
        extra = sum(window(x, 92, 6, "crm_boost_sends") for x in regs)
        h, f = hold["regions"][r], freq["regions"][r]
        per_send[r] = {"avg": -h["total_effect_orders"] / suppressed, "avg_se": h["total_effect_se"] / suppressed,
                       "marg": f["total_effect_orders"] / extra, "marg_se": f["total_effect_se"] / extra}
    k = float(np.mean([freq["regions"][r]["sends_treated"] / freq["regions"][r]["sends_control"] for r in REGIONS]))

    # National curvature draws, shared by regions
    avg_d = rng.normal(per_send["ALL"]["avg"], per_send["ALL"]["avg_se"], N_DRAWS)
    marg_d = rng.normal(per_send["ALL"]["marg"], per_send["ALL"]["marg_se"], N_DRAWS)
    rho = np.clip(marg_d / np.maximum(avg_d, 1e-6), 0.02, 0.98)
    b = np.array([curvature(x, k) for x in rho])
    g = (1 - np.exp(-np.outer(b, GRID))) / (1 - np.exp(-b))[:, None]   # (draws, grid), g(1) = 1

    summary, curves = {"k_frequency": k, "regions": {}}, np.zeros((N_DRAWS, len(REGIONS), len(GRID)))
    for j, r in enumerate(REGIONS):
        sends_plan = window(r, PLAN[0], PLAN[1] - PLAN[0] + 1, "crm_sends")
        lvl = np.maximum(rng.normal(per_send[r]["avg"], per_send[r]["avg_se"], N_DRAWS), 0) * sends_plan  # F1, orders
        curves[:, j] = lvl[:, None] * g * margin                                                           # KRW
        spend_plan = sends_plan * cost
        slope = (curves[:, j, GRID.tolist().index(1.05)] - curves[:, j, GRID.tolist().index(0.95)]) / (0.1 * spend_plan)
        t = truth["regions"][r]["channels"]["crm"]
        att_roi = att.loc[r, "sends_followed_by_order"] * margin / (att.loc[r, "sends"] * cost)
        summary["regions"][r] = {
            "attributed_roi": att_roi,
            "holdout_avg_roi": per_send[r]["avg"] * margin / cost,
            "holdout_avg_roi_ci": [(per_send[r]["avg"] + q * per_send[r]["avg_se"]) * margin / cost for q in (-1.96, 1.96)],
            "frequency_marginal_roi": per_send[r]["marg"] * margin / cost,
            "frequency_marginal_roi_ci": [(per_send[r]["marg"] + q * per_send[r]["marg_se"]) * margin / cost for q in (-1.96, 1.96)],
            "curve_mroi_mean": float(slope.mean()), "curve_mroi_90": np.percentile(slope, [5, 95]).tolist(),
            "curve_avg_roi_mean": float((curves[:, j, GRID.tolist().index(1.0)] / spend_plan).mean()),
            "true_roi": t["true_roi"], "true_marginal_roi": t["true_marginal_roi"],
            "plan_year_sends": sends_plan, "plan_year_spend": spend_plan,
        }
    OUT.mkdir(exist_ok=True)
    np.save(OUT / "crm_curve_draws.npy", curves)
    (OUT / "step2b_crm.json").write_text(json.dumps(summary, indent=2, default=float))
    print(f"frequency intensity k = {k:.2f}; national per-send: avg {per_send['ALL']['avg']:.4f} ± {per_send['ALL']['avg_se']:.4f}, "
          f"marginal {per_send['ALL']['marg']:.4f} ± {per_send['ALL']['marg_se']:.4f}")
    print(pd.DataFrame(summary["regions"]).T[["attributed_roi", "holdout_avg_roi", "frequency_marginal_roi", "curve_avg_roi_mean",
                                              "curve_mroi_mean", "true_roi", "true_marginal_roi"]].astype(float).round(2).to_string())


if __name__ == "__main__":
    main()
