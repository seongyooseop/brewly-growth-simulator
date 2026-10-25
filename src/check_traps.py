"""
Step 1d - Do the planted traps actually mislead a standard analysis?

Simple linear regressions per region on the weekly mart (no adstock, no saturation):
  new members : new_members ~ 4 acquisition channels                (naive)
                + category interest, promo, holidays, season          (with every observed control)
  orders      : capsule_orders ~ CRM spend                            (naive)
                + active members, promo, holidays, season             (with every observed control)
The implied ROI (coefficient x unit value) is compared with the hidden true ROI.

What should happen: the category-demand index pulls retail partners back toward the truth, but CRM
stays inflated, because its confounder (how many members are about to reorder) is not in the data,
and referrals and store trials stay unstable because they move together. Only experiments can settle those.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
ACQ = ["referral", "store_trial", "retail_partner", "events"]
SEASON = ["sin52", "cos52"]


def implied_roi(df, y, cols, value):
    X = sm.add_constant(df[cols], has_constant="add")
    X = X.loc[:, X.std() > 0].assign(const=1.0)  # drop flags that never fire
    fit = sm.OLS(df[y], X).fit()
    return {c.removeprefix("spend_"): fit.params[c] * value for c in cols if c.startswith("spend_")}


def main():
    df = pd.read_csv(ROOT / "data" / "marts" / "weekly_region.csv")
    truth = json.loads((ROOT / "data" / "truth" / "ground_truth.json").read_text())
    df["sin52"], df["cos52"] = np.sin(2 * np.pi * df["week"] / 52), np.cos(2 * np.pi * df["week"] / 52)
    df["log_interest"] = np.log(df["category_interest"])
    acq_spend = [f"spend_{c}" for c in ACQ]
    acq_ctrl = ["log_interest", "event_promo", "holiday_lny", "holiday_chuseok"] + SEASON
    ord_ctrl = ["active_members", "event_promo", "holiday_lny", "holiday_chuseok"] + SEASON

    rows = []
    for r, g in df.groupby("region", sort=False):
        t = truth["regions"][r]
        ltv, mpo = t["value_per_new_member"], truth["margin_per_order"]
        naive = implied_roi(g, "new_members", acq_spend, ltv) | implied_roi(g, "capsule_orders", ["spend_crm"], mpo)
        ctrl = (implied_roi(g, "new_members", acq_spend + acq_ctrl, ltv)
                | implied_roi(g, "capsule_orders", ["spend_crm"] + ord_ctrl, mpo))
        for c in ACQ + ["crm"]:
            rows.append({"region": r, "channel": c, "true_roi": t["channels"][c]["true_roi"],
                         "naive_ols_roi": naive[c], "controlled_ols_roi": ctrl[c]})
    out = pd.DataFrame(rows).round(2)
    (ROOT / "outputs").mkdir(exist_ok=True)
    out.to_csv(ROOT / "outputs" / "step1_trap_check.csv", index=False)
    print(out.to_string(index=False))
    corr = df.groupby("region")[["spend_referral", "spend_store_trial"]].corr().xs("spend_referral", level=1)["spend_store_trial"]
    print("\nReferral-store trial weekly spend correlation by region:", corr.round(2).to_dict())
    crm_corr = df.groupby("region")[["spend_crm", "capsule_orders"]].corr().xs("spend_crm", level=1)["capsule_orders"]
    print("CRM spend vs orders correlation by region:", crm_corr.round(2).to_dict())


if __name__ == "__main__":
    main()
