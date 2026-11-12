"""
Step 5 - Build the interactive page: one self-contained HTML file with six tabs.

Injects the SQL marts, experiment readouts, model checks, budget curves and uplift results into
simulator/template.html and writes simulator/index.html (no server or library needed).
"""

import json

import numpy as np
import pandas as pd

from mmm_core import ACQ_CHANNELS, REGIONS, ROOT

OUT, MARTS = ROOT / "outputs", ROOT / "data" / "marts"


def dashboard_data():
    w = pd.read_csv(MARTS / "weekly_region.csv")
    cols = ["week", "week_start", "region", "new_members", "capsule_orders", "active_members", "crm_sends", "event_promo",
            "spend_referral", "spend_store_trial", "spend_retail_partner", "spend_events", "spend_crm"]
    weekly = {r: {c: g[c].tolist() for c in cols if c != "region"} for r, g in w[cols].groupby("region")}
    coh = pd.read_csv(MARTS / "cohort_monthly.csv")
    heat = (coh.assign(share=coh["ordering_members"] / coh["cohort_size"])
            .pivot(index="cohort_month", columns="period", values="share").round(3))
    fun = pd.read_csv(MARTS / "lifecycle_funnel.csv")
    tot = fun[["registered", "first_order_4w", "three_orders_13w", "ordering_month_6"]].sum()
    return {"weekly": weekly, "cohort": {"months": heat.columns.tolist(), "cohorts": heat.index.tolist(),
                                         "share": heat.fillna(-1).values.tolist(),
                                         "size": coh.groupby("cohort_month")["cohort_size"].first().tolist()},
            "funnel": {k: int(v) for k, v in tot.items()},
            "funnel_by_quarter": fun.to_dict(orient="records")}


def validation_data():
    rec = pd.read_csv(OUT / "step2_roi_recovery.csv")
    hold = pd.read_csv(OUT / "step2_holdout_metrics.csv")
    conv = pd.read_csv(OUT / "step2_convergence.csv").set_index("fit")
    upl = pd.read_csv(OUT / "step3_uplift.csv").set_index("region")
    lift = pd.read_csv(OUT / "step2_lift_tests.csv")
    crm = json.loads((OUT / "step2b_crm.json").read_text())["regions"]
    cohort = pd.read_csv(OUT / "step1_cohort_curve.csv")
    ltv = json.loads((OUT / "step1_ltv.json").read_text())
    regions = {}
    for r in REGIONS:
        g = rec[rec["region"] == r].set_index("channel").loc[ACQ_CHANNELS]
        regions[r] = {
            "channels": [{k: round(float(g.loc[c, k]), 3) for k in
                          ["true_mroi", "nolift_mroi", "nolift_mroi_lo90", "nolift_mroi_hi90", "cal_mroi", "cal_mroi_lo90",
                           "cal_mroi_hi90"]} for c in ACQ_CHANNELS],
            "crm": {k: (np.round(v, 3).tolist() if isinstance(v, list) else round(float(v), 3)) for k, v in crm[r].items()},
            "holdout_mape": round(float(hold[(hold["region"] == r) & (hold["period"] == "test")]["mape"].iloc[0]), 3),
            "uplift": {k: round(float(upl.loc[r, k]), 3) for k in upl.columns if k != "region"},
        }
    return {
        "regions": regions,
        "coverage_mroi": {"cal": int(rec["cal_mroi_covered"].sum()), "nolift": int(rec["nolift_mroi_covered"].sum()), "n": len(rec)},
        "convergence": {"divergences": int(conv.loc["cal", "divergences"]), "max_r_hat": round(float(conv.loc["cal", "max_r_hat"]), 3),
                        "draws": int(conv.loc["cal", "draws"])},
        "geo_tests": lift[["region", "channel", "start_week", "n_weeks", "observed_lift", "se", "model_implied"]].to_dict(orient="records"),
        "cohort": {"orders_per_member": cohort["orders_per_member"].round(3).tolist(),
                   "active_share": cohort["active_share"].round(3).tolist(), **ltv},
    }


def main():
    blocks = {
        "/*__SIM_DATA__*/": json.loads((OUT / "simulator_data.json").read_text()),
        "/*__VALIDATION__*/": validation_data(),
        "/*__DASHBOARD__*/": dashboard_data(),
        "/*__EXPERIMENTS__*/": json.loads((OUT / "step2a_experiments.json").read_text()),
        "/*__UPLIFT__*/": json.loads((OUT / "step4_uplift.json").read_text()),
    }
    payload = {key: json.dumps(data, separators=(",", ":"), default=float) for key, data in blocks.items()}

    def render(template):
        html = (ROOT / "simulator" / template).read_text(encoding="utf-8")
        for key, data in payload.items():
            assert key in html, key
            html = html.replace(key, data)
        return html

    def standalone(html, lang):
        return (f'<!doctype html>\n<html lang="{lang}">\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                "<style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>\n"
                + html + "\n</html>\n")

    # artifact.html: page body for the Artifact host, which adds its own document skeleton.
    # index.html: the same page as a standalone document for GitHub Pages or a local browser.
    # ko/index.html: the Korean edition (template_ko.html), same data and logic.
    html = render("template.html")
    (ROOT / "simulator" / "artifact.html").write_text(html, encoding="utf-8")
    (ROOT / "simulator" / "index.html").write_text(standalone(html, "en"), encoding="utf-8")
    (ROOT / "simulator" / "ko").mkdir(exist_ok=True)
    (ROOT / "simulator" / "ko" / "index.html").write_text(standalone(render("template_ko.html"), "ko"), encoding="utf-8")
    print(f"simulator/index.html, ko/index.html and artifact.html  {len(html) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
