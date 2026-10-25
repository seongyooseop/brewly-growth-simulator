"""
Step 2c validation - is the acquisition MMM trustworthy enough to move budget?

  1. Convergence: R-hat, effective sample size, divergences.
  2. Out-of-sample: the 12-week holdout fit predicts new members in weeks it never saw.
  3. Truth recovery: average and marginal ROI vs the hidden truth, for the observational-only
     model and the geo-test-calibrated model.
  4. Decision check: does each model rank channels for the next won, and call break-even, like the truth?
CRM is scored in step 2b (attribution vs experiments vs truth).
"""

import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fit_mmm import acquisition_tests
from mmm_core import (ACQ_CHANNELS, LABELS, REGION_NAMES, REGIONS, ROOT, channel_units, load_arrays, load_posterior,
                      load_truth, member_value)

OUT = ROOT / "outputs"
CORE_VARS = ["adstock_decay", "half_sat", "hill_shape", "roi", "log_roi_tau", "baseline_level", "control_coef", "nb_alpha"]
MODELS = {"nolift": "Observational MMM", "cal": "MMM + geo tests"}
BLUE, GREY = "#8a4b24", "#a0a0a0"


def stacked(idata, var):
    return idata.posterior[var].stack(sample=("chain", "draw")).transpose("sample", ...).values


def convergence(fits):
    rows = []
    for tag, idata in fits.items():
        s = az.summary(idata, var_names=CORE_VARS)
        rows.append({"fit": tag, "max_r_hat": s["r_hat"].max(), "min_ess_bulk": s["ess_bulk"].min(),
                     "min_ess_tail": s["ess_tail"].min(), "divergences": int(idata.sample_stats["diverging"].sum()),
                     "draws": idata.posterior.sizes["chain"] * idata.posterior.sizes["draw"]})
    out = pd.DataFrame(rows)
    out.round(3).to_csv(OUT / "step2_convergence.csv", index=False)
    return out


def holdout(idata, rng):
    d = load_arrays(n_train=92)
    mu = stacked(idata, "mu")
    nb = stacked(idata, "nb_alpha")[:, None, None]
    pred = rng.negative_binomial(nb, nb / (nb + mu))
    lo, hi = np.percentile(pred, [5, 95], axis=0)
    mean = mu.mean(0)
    rows = []
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    for j, r in enumerate(REGIONS):
        y = d["y"][:, j]
        for part, sl in (("train", slice(0, 92)), ("test", slice(92, None))):
            rows.append({"region": r, "period": part, "mape": np.mean(np.abs(mean[sl, j] - y[sl]) / y[sl]),
                         "coverage_90": np.mean((y[sl] >= lo[sl, j]) & (y[sl] <= hi[sl, j]))})
        ax = axes[j]
        ax.axvspan(d["dates"][92], d["dates"][-1], color="#f2f2f2", zorder=0)
        ax.fill_between(d["dates"], lo[:, j], hi[:, j], color=BLUE, alpha=0.18, lw=0, label="90% predictive interval")
        ax.plot(d["dates"], mean[:, j], color=BLUE, lw=1.4, label="Model mean")
        ax.plot(d["dates"], y, "o", color="#1f1f1f", ms=2.4, label="Actual new members")
        ax.set_ylabel(f"{r}\nnew members / week")
        ax.set_ylim(0, max(hi[:, j].max(), y.max()) * 1.12)
        ax.text(d["dates"][-1], ax.get_ylim()[1] * 0.97, f"Holdout MAPE {rows[-1]['mape']:.1%}", ha="right", va="top", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(loc="upper left", fontsize=8, frameon=False, ncol=3)
    axes[0].set_title("Out-of-sample check: fitted on 92 weeks; the last 12 weeks (grey) were never seen", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "step2_holdout.png", dpi=150)
    out = pd.DataFrame(rows)
    out.round(3).to_csv(OUT / "step2_holdout_metrics.csv", index=False)
    return out


def roi_draws(idata, rng, n_mroi=400):
    d = load_arrays()
    roi = stacked(idata, "roi")
    idx = rng.choice(roi.shape[0], size=n_mroi, replace=False)
    decay, half_sat, shape = (stacked(idata, v)[idx] for v in ("adstock_decay", "half_sat", "hill_shape"))
    beta = stacked(idata, "beta")[idx]
    value = member_value()
    mroi = np.zeros((n_mroi, len(REGIONS), len(ACQ_CHANNELS)))
    for s in range(n_mroi):
        for j in range(len(REGIONS)):
            for k in range(len(ACQ_CHANNELS)):
                args = (d["spend_scale"][j, k], decay[s, k], half_sat[s, k], shape[s, k], beta[s, j, k], d["y_scale"][j])
                x = d["spend"][:, j, k]
                mroi[s, j, k] = (channel_units(x * 1.01, *args).sum() - channel_units(x, *args).sum()) * value / (0.01 * x.sum())
    return roi, mroi


def recovery_table(draws, truth):
    rows = []
    for j, r in enumerate(REGIONS):
        for k, c in enumerate(ACQ_CHANNELS):
            t = truth["regions"][r]["channels"][c]
            row = {"region": r, "channel": c, "true_roi": t["true_roi"], "true_mroi": t["true_marginal_roi"]}
            for tag, (roi, mroi) in draws.items():
                for name, arr in (("roi", roi[:, j, k]), ("mroi", mroi[:, j, k])):
                    lo, hi = np.percentile(arr, [5, 95])
                    row.update({f"{tag}_{name}": arr.mean(), f"{tag}_{name}_lo90": lo, f"{tag}_{name}_hi90": hi,
                                f"{tag}_{name}_covered": lo <= row[f"true_{name}"] <= hi})
            rows.append(row)
    out = pd.DataFrame(rows)
    out.round(3).to_csv(OUT / "step2_roi_recovery.csv", index=False)
    return out


def decision_check(df):
    rows = []
    for r, g in df.groupby("region", sort=False):
        g = g.set_index("channel")
        truth_rank = g["true_mroi"].rank(ascending=False)
        row = {"region": r, "truth_order": " > ".join(truth_rank.sort_values().index.map(LABELS))}
        for tag in MODELS:
            rank = g[f"{tag}_mroi"].rank(ascending=False)
            row[f"{tag}_order"] = " > ".join(rank.sort_values().index.map(LABELS))
            row[f"{tag}_rank_corr"] = truth_rank.corr(rank, method="spearman")
            row[f"{tag}_breakeven_calls_right"] = int(((g[f"{tag}_mroi"] > 1) == (g["true_mroi"] > 1)).sum())
        rows.append(row)
    out = pd.DataFrame(rows)
    out.round(2).to_csv(OUT / "step2_decision_check.csv", index=False)
    return out


def plot_recovery(df):
    fig, axes = plt.subplots(2, 3, figsize=(13, 6.5), sharey=True)
    ypos = np.arange(len(ACQ_CHANNELS))[::-1]
    for j, r in enumerate(REGIONS):
        g = df[df["region"] == r].set_index("channel").loc[ACQ_CHANNELS]
        for row, (name, title) in enumerate((("roi", "Average ROI"), ("mroi", "Marginal ROI (next won)"))):
            ax = axes[row, j]
            for tag, label, off, col in (("nolift", MODELS["nolift"], 0.17, GREY), ("cal", MODELS["cal"], -0.17, BLUE)):
                ax.hlines(ypos + off, g[f"{tag}_{name}_lo90"], g[f"{tag}_{name}_hi90"], color=col, lw=3, alpha=0.5)
                ax.plot(g[f"{tag}_{name}"], ypos + off, "o", color=col, ms=5.5, label=f"{label} (90% interval)")
            ax.plot(g[f"true_{name}"], ypos, "D", color="#1f1f1f", ms=6.5, mfc="white", mew=1.6, label="Truth")
            ax.axvline(1, color="#b0b0b0", lw=0.8, ls=":")
            ax.set_yticks(ypos, [LABELS[c] for c in ACQ_CHANNELS])
            ax.set_title(f"{REGION_NAMES[r]} - {title}", loc="left", fontsize=10)
            ax.spines[["top", "right"]].set_visible(False)
    axes[0, 2].legend(loc="lower right", fontsize=7.5, frameon=False)
    fig.suptitle("Acquisition channels: observational MMM vs MMM calibrated with geo tests (dotted line = break-even)",
                 x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "step2_roi_recovery.png", dpi=150)


def main():
    rng = np.random.default_rng(7)
    truth = load_truth()
    fits = {"cal": load_posterior("full"), "nolift": load_posterior("full_nolift"), "cal_holdout": load_posterior("holdout12")}
    pd.set_option("display.width", 250)
    print("Convergence\n", convergence(fits).round(3).to_string(index=False))
    print("\nHoldout (calibrated model)\n", holdout(fits["cal_holdout"], rng).round(3).to_string(index=False))
    draws = {tag: roi_draws(fits[tag], rng) for tag in MODELS}
    rec = recovery_table(draws, truth)
    plot_recovery(rec)
    cols = ["region", "channel", "true_roi", "nolift_roi", "cal_roi", "true_mroi", "nolift_mroi", "cal_mroi", "cal_mroi_lo90", "cal_mroi_hi90"]
    print("\nROI recovery\n", rec[cols].round(2).to_string(index=False))
    for tag in MODELS:
        print(f"{MODELS[tag]:20s} mROI covered {rec[f'{tag}_mroi_covered'].sum()} of {len(rec)}; "
              f"mean abs mROI error {(rec[f'{tag}_mroi'] - rec['true_mroi']).abs().mean():.2f}")
    print("\nDecision check\n", decision_check(rec).to_string(index=False))
    lift = acquisition_tests()
    lift["model_implied"] = stacked(fits["cal"], "lift_implied").mean(0).round(1)
    lift.to_csv(OUT / "step2_lift_tests.csv", index=False)
    print("\nGeo tests: readout vs calibrated model\n", lift[["region", "channel", "observed_lift", "se", "model_implied"]].to_string(index=False))


if __name__ == "__main__":
    main()
