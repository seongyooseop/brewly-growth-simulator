"""
Step 2 - Hierarchical Bayesian MMM for BREWLY's acquisition channels, fitted with PyMC (nutpie sampler).

  new_members[t, r] ~ NegBinomial(scale[r] * (baseline[t, r] + sum_c media[t, r, c]))

  baseline = level[r] * exp(controls . gamma[r])        category interest, promo, holidays, season, trend
  media    = beta[r, c] * Hill(adstock(spend[t, r, c] / scale[r, c]; decay[c]); half_sat[c], shape[c])

  - Channels: member referrals, store trials, retail partners, brand events. Data: the weekly region
    mart built in SQL from member events (data/marts/weekly_region.csv).
  - Response shape (decay, half_sat, shape) is shared across regions.
  - Effect size is parameterised by ROI over the training window (as in Google Meridian): beta is
    solved so that the channel's contribution x value of a new member / spend equals roi[r, c], so
    ROI reads in KRW of gross margin per KRW spent. ROI is partially pooled across regions on the log
    scale; priors read in business terms (median ROI 1.5, regions differ by roughly +-15%).
  - Calibration: the two geo tests (data/lift_tests.csv, step 2a) enter as extra observations of the
    model's own counterfactual: observed weeks (channel off) vs the planned spend.

  CRM is measured outside this model, from member-level experiments (step 2b). Earlier attempts put
  CRM in a second likelihood for weekly orders; across six specifications it did not converge to
  one answer. Running-low messages go to members who are about to reorder, so weekly message volume
  moves with baseline demand, and carry-over, saturation and baseline traded off freely. Randomised
  member holdouts measure triggered CRM directly; that is what CRM teams use, and what step 2b does.

Usage:
  python src/fit_mmm.py --holdout 12   # fit on the first 92 weeks, keep the last 12 for testing
  python src/fit_mmm.py                # fit on all 104 weeks (used for ROI and the simulator)
  python src/fit_mmm.py --no-lift      # observational-only fit, for comparison
"""

import argparse
import json

import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt

from mmm_core import ACQ_CHANNELS, ACQ_CONTROLS, L_MAX, REGIONS, ROOT, experiment_series, load_arrays, member_value


def lagged(x, l_max=L_MAX):
    """Stack x shifted by 0..l_max-1 weeks along a new first axis, zero-padded at the start."""
    out = np.zeros((l_max,) + x.shape)
    for lag in range(l_max):
        out[lag, lag:] = x[: len(x) - lag]
    return out


def geometric_adstock(x_lagged, decay):
    """Normalised geometric adstock (same as pymc_marketing's, normalize=True); decay has shape (C,)."""
    w = decay[None, :] ** np.arange(x_lagged.shape[0])[:, None]  # (L, C)
    w = w / w.sum(axis=0)
    return (w[:, None, None, :] * x_lagged).sum(axis=0)


def build_model(d, lift_tests=None):
    T = len(d["dates"])
    coords = {"date": np.arange(T), "region": REGIONS, "channel": ACQ_CHANNELS, "control": ACQ_CONTROLS}
    with pm.Model(coords=coords) as model:
        x = d["spend"] / d["spend_scale"][None]  # (T, R, C), mean 1 in the training window

        decay = pm.Beta("adstock_decay", 3, 3, dims="channel")
        half_sat = pm.Gamma("half_sat", mu=1.0, sigma=0.5, dims="channel")
        # A steep S-curve let a demand-following channel take credit only in its high-spend weeks, which are
        # the demand-shock weeks, and slip past the geo test. Assumption: at weekly spend levels the curve is a gentle S.
        shape = pm.Gamma("hill_shape", mu=1.3, sigma=0.25, dims="channel")
        log_roi_mu = pm.Normal("log_roi_mu", np.log(1.5), 0.7, dims="channel")
        # Three regions barely identify the pooling scale; a stated assumption: regions differ by about +-15%.
        log_roi_tau = pm.Gamma("log_roi_tau", mu=0.15, sigma=0.05)
        log_roi_z = pm.Normal("log_roi_z", 0, 1, dims=("region", "channel"))
        roi = pm.Deterministic("roi", pt.exp(log_roi_mu + log_roi_tau * log_roi_z), dims=("region", "channel"))
        ad = geometric_adstock(lagged(x), decay) + 1e-9
        sat = ad**shape / (ad**shape + half_sat**shape)  # (T, R, C)
        n = d["n_train"]
        unit = member_value() * d["y_scale"][:, None]  # KRW of one normalised unit of new members, per region
        beta = pm.Deterministic("beta", roi * d["spend"][:n].sum(0) / (unit * sat[:n].sum(0)), dims=("region", "channel"))
        media = pm.Deterministic("media", beta * sat, dims=("date", "region", "channel"))

        level = pm.Normal("baseline_level", 0.7, 0.3, dims="region")
        gamma = pm.Normal("control_coef", 0, 0.5, dims=("region", "control"))
        baseline = pm.Deterministic("baseline", level * pt.exp((d["controls"] * gamma[None]).sum(-1)), dims=("date", "region"))
        mu = pm.Deterministic("mu", d["y_scale"] * (baseline + media.sum(-1)), dims=("date", "region"))
        alpha = pm.LogNormal("nb_alpha", np.log(300), 1)
        pm.NegativeBinomial("new_members", mu=mu[:n], alpha=alpha, observed=d["y"][:n])

        # Geo-test calibration: the model's own counterfactual for each test must match the readout
        if lift_tests is not None:
            implied = []
            for test in lift_tests.itertuples():
                j, k = REGIONS.index(test.region), ACQ_CHANNELS.index(test.channel)
                bau, treated, share = experiment_series(x[:, j, k], test, d["spend_scale"][j, k])
                w = decay[k] ** np.arange(L_MAX)
                resp = []
                for series in (treated, bau):
                    ad_s = (w[:, None] / w.sum() * lagged(series)).sum(axis=0) + 1e-9
                    resp.append(ad_s ** shape[k] / (ad_s ** shape[k] + half_sat[k] ** shape[k]))
                implied.append(share * (beta[j, k] * (resp[0] - resp[1])).sum() * d["y_scale"][j])
            pm.Deterministic("lift_implied", pt.stack(implied))
            pm.Normal("lift_obs", mu=pt.stack(implied), sigma=lift_tests["se"].values,
                      observed=lift_tests["observed_lift"].values)
    return model


def acquisition_tests():
    lift = pd.read_csv(ROOT / "data" / "lift_tests.csv")
    return lift[lift["channel"].isin(ACQ_CHANNELS)].reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", type=int, default=0, help="weeks at the end kept out of fitting")
    ap.add_argument("--no-lift", action="store_true", help="fit on observational data only")
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--tune", type=int, default=1500)
    args = ap.parse_args()

    d = load_arrays(n_train=104 - args.holdout)
    lift = None if args.no_lift else acquisition_tests()
    tag = (f"holdout{args.holdout}" if args.holdout else "full") + ("_nolift" if args.no_lift else "")
    with build_model(d, lift):
        idata = pm.sample(draws=args.draws, tune=args.tune, chains=4, target_accept=0.95,
                          nuts_sampler="nutpie", random_seed=20261025)
    (ROOT / "models").mkdir(exist_ok=True)
    idata.to_zarr(ROOT / "models" / f"mmm_{tag}.zarr", mode="w")  # zarr: no HDF5, safe with non-ASCII paths
    (ROOT / "models" / f"mmm_{tag}_meta.json").write_text(json.dumps({"n_train": d["n_train"], "regions": REGIONS,
                                                                      "channels": ACQ_CHANNELS}, indent=2))
    print(f"Saved models/mmm_{tag}.zarr  divergences: {int(idata.sample_stats['diverging'].sum())}")


if __name__ == "__main__":
    main()
