"""
Step 1c - What is a new member worth? 12-month value from the join-cohort mart.

Acquisition channels bring in members; members bring margin through capsule orders for months after.
To compare a won spent on referrals with a won spent on CRM, both need the same unit: gross margin.

  value of a new member = device margin + margin per order x orders per member in weeks 0-51

Orders per member come from data/marts/cohort_monthly.csv (2024 monthly join cohorts, 13 four-week periods,
built in SQL from the order log), weighted by cohort size. The device margin and margin per order are finance inputs.

Output: outputs/step1_ltv.json, outputs/step1_cohort_curve.csv
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEVICE_MARGIN = 35_000      # finance input, KRW per machine
MARGIN_PER_ORDER = 11_000   # finance input, KRW per capsule order


def main():
    df = pd.read_csv(ROOT / "data" / "marts" / "cohort_monthly.csv")
    g = df.groupby("period")[["orders", "ordering_members", "cohort_size"]].sum()
    curve = pd.DataFrame({"orders_per_member": g["orders"] / g["cohort_size"],
                          "active_share": g["ordering_members"] / g["cohort_size"],
                          "n_cohorts": df.groupby("period").size()})
    orders_12m = curve["orders_per_member"].sum()
    ltv = DEVICE_MARGIN + MARGIN_PER_ORDER * orders_12m
    out = {"device_margin": DEVICE_MARGIN, "margin_per_order": MARGIN_PER_ORDER,
           "orders_per_member_12m": round(float(orders_12m), 3), "value_per_new_member": round(float(ltv)),
           "active_share_period_12": round(float(curve["active_share"].iloc[-1]), 3)}
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs" / "step1_ltv.json").write_text(json.dumps(out, indent=2))
    curve.round(4).to_csv(ROOT / "outputs" / "step1_cohort_curve.csv")
    truth = json.loads((ROOT / "data" / "truth" / "ground_truth.json").read_text())["regions"]
    print(curve.round(3).to_string())
    print(f"\nOrders per member in 12 months: {orders_12m:.2f}")
    print(f"Value of a new member: KRW {ltv:,.0f}  (truth by region, hidden: "
          + ", ".join(f"{r} {v['value_per_new_member']:,.0f}" for r, v in truth.items()) + ")")


if __name__ == "__main__":
    main()
