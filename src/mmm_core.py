"""Shared pieces for steps 2-4: data arrays and a numpy copy of the model's channel response."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGIONS = ["SEL", "YNG", "ROK"]
REGION_NAMES = {"SEL": "Seoul metro", "YNG": "Yeongnam", "ROK": "Rest of Korea"}
ACQ_CHANNELS = ["referral", "store_trial", "retail_partner", "events"]   # in the MMM (new members)
CHANNELS = ACQ_CHANNELS + ["crm"]                                        # in the budget plan
LABELS = {"referral": "Member referrals", "store_trial": "Store trials", "retail_partner": "Retail partners",
          "events": "Brand events", "crm": "CRM messages"}
ACQ_CONTROLS = ["log_interest", "event_promo", "holiday_lny", "holiday_chuseok", "sin52", "cos52", "trend"]
L_MAX = 12  # weeks of carry-over kept in the adstock convolution


def ltv_inputs():
    return json.loads((ROOT / "outputs" / "step1_ltv.json").read_text())


def member_value():
    """KRW 12-month gross margin of a new member (step 1c)."""
    return ltv_inputs()["value_per_new_member"]


def load_weekly():
    return pd.read_csv(ROOT / "data" / "marts" / "weekly_region.csv", parse_dates=["week_start"]).sort_values(["region", "week"])


def load_arrays(n_train=None):
    """Weekly data from the SQL mart as (time, region, ...) arrays. Scales use the training window only."""
    df = load_weekly()
    t = df["week"]
    df["log_interest"] = np.log(df["category_interest"] / 100)
    df["sin52"], df["cos52"] = np.sin(2 * np.pi * t / 52), np.cos(2 * np.pi * t / 52)
    df["trend"] = t / 104
    wide = {r: df[df["region"] == r].reset_index(drop=True) for r in REGIONS}
    dates = wide[REGIONS[0]]["week_start"].values
    n_train = n_train or len(dates)
    stack = lambda cols: np.stack([wide[r][cols].values for r in REGIONS], axis=1).astype(float)
    spend, y = stack([f"spend_{c}" for c in ACQ_CHANNELS]), stack("new_members")
    return {
        "dates": dates, "n_train": n_train,
        "spend": spend,                                   # (T, R, C) KRW, acquisition channels
        "spend_scale": spend[:n_train].mean(axis=0),      # (R, C)
        "crm_spend": stack("spend_crm"),                  # (T, R) KRW
        "y": y, "y_scale": y[:n_train].mean(axis=0),      # (T, R) new members
        "controls": stack(ACQ_CONTROLS),                  # (T, R, K)
    }


def experiment_series(x, test, spend_scale):
    """Normalised spend series for a geo test: (business-as-usual series, treated series, treated share).
    readout = share x [response(treated) - response(business as usual)]; business as usual is the planned
    weekly spend in the window (cf_value, KRW), treated is the observed series (channel off)."""
    window = slice(test.start_week, test.start_week + test.n_weeks)
    bau = x.copy()
    bau[window] = test.cf_value / spend_scale
    return bau, x.copy(), float(test.share)


def adstock_np(x, decay, l_max=L_MAX):
    """Normalised geometric adstock along axis 0, the same as fit_mmm.geometric_adstock."""
    w = decay ** np.arange(l_max)
    w = w / w.sum()
    out = np.zeros_like(x, dtype=float)
    for lag in range(l_max):
        out[lag:] += w[lag] * x[: len(x) - lag]
    return out


def hill_np(x, half_sat, shape):
    return x**shape / (x**shape + half_sat**shape)


def channel_units(spend_rc, scale, decay, half_sat, shape, beta, y_scale):
    """Weekly new members from one acquisition channel in one region, for one posterior draw."""
    return beta * hill_np(adstock_np(spend_rc / scale, decay) + 1e-9, half_sat, shape) * y_scale


def load_posterior(tag):
    import xarray as xr
    return xr.open_datatree(ROOT / "models" / f"mmm_{tag}.zarr", engine="zarr")


def load_truth():
    return json.loads((ROOT / "data" / "truth" / "ground_truth.json").read_text())
