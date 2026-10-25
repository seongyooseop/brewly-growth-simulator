"""
Step 1 - Synthetic member-level data for a fictional capsule-coffee brand ("BREWLY") in Korea.

Setting: a device-plus-refills membership sold to adults, in a market where paid brand advertising
is assumed to be unavailable (as in regulated categories). Growth runs through owned channels:
member referrals, in-store trials, retail partners, brand events and CRM messages.

  new members      weekly device registrations per region, driven by four acquisition channels
  capsule orders   orders placed by each member, lifted by CRM messages

What is generated, from a KNOWN process so later steps can score themselves against the truth:
  data/raw/members.parquet             one row per member (region, join week, age band, device)
  data/raw/orders.parquet              one row per capsule order (member, week)
  data/raw/crm_sends.parquet           one row per CRM message, plus messages suppressed by the holdout test
  data/raw/experiment_groups.parquet   random assignment for the CRM holdout and frequency tests
  data/raw/marketing_spend.csv         weekly spend of the four acquisition channels (CRM spend comes from sends)
  data/raw/calendar.csv                weeks, promotions, holidays, category search-trend index per region
  data/raw/geo_test_plan.csv           geo test design: which channel was switched off where, and its planned spend
  data/truth/ground_truth.json         hidden true parameters, ROI and marginal ROI, CRM response curve
  data/truth/member_truth.parquet      hidden member traits (order rate, churn, CRM uplift)

Planted traps:
  1. Retail-partner incentives follow demand. They are paid per device sold, so spend rises when
     category demand rises, and that same demand brings in members.
  2. Referrals and store trials run on one seasonal calendar, so the data can barely tell them apart.
  3. CRM is triggered for members who are about to reorder ("running low" journeys), so orders
     those members would have placed anyway look like CRM's doing. Message volume also rises
     and falls with how many members are due, which links CRM spend to baseline orders.
Two experiments run inside the member data and are analysed in step 2a:
  - weeks 80-87: a random 30% of members are held out from CRM (their triggers are logged as suppressed)
  - weeks 92-97: a random 50% of members get roughly twice the messages (frequency test)
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, TRUTH = ROOT / "data" / "raw", ROOT / "data" / "truth"
SEED = 20261025

N_WEEKS = 104
START = "2024-01-01"  # Monday
PLAN = slice(52, 104)

ACQ_CHANNELS = ["referral", "store_trial", "retail_partner", "events"]
CHANNELS = ACQ_CHANNELS + ["crm"]

DEVICE_MARGIN = 35_000      # KRW per machine
MARGIN_PER_ORDER = 11_000   # KRW per capsule order
COST_PER_SEND = 120         # KRW per CRM message, incl. the average coupon redeemed
LTV_FOR_CALIBRATION = 105_000  # used only to size acquisition effects before members exist

REGIONS = {
    # annual budget incl. CRM (KRW), weekly baseline registrations, active members at start
    "SEL": {"budget": 480_000_000, "base_acq": 225, "active0": 30_000},
    "YNG": {"budget": 220_000_000, "base_acq": 96, "active0": 12_800},
    "ROK": {"budget": 180_000_000, "base_acq": 82, "active0": 11_000},
}
MIX = {"referral": 0.24, "store_trial": 0.20, "retail_partner": 0.24, "events": 0.14, "crm": 0.18}

# Acquisition channels: geometric adstock + Hill saturation, effect sized to a target average ROI
TRUE_CHANNEL = {
    "referral":       {"decay": 0.35, "half_sat": 1.30, "shape": 1.3, "roi": 2.2},
    "store_trial":    {"decay": 0.45, "half_sat": 1.20, "shape": 1.4, "roi": 1.8},
    "retail_partner": {"decay": 0.10, "half_sat": 0.50, "shape": 1.2, "roi": 0.9},
    "events":         {"decay": 0.55, "half_sat": 0.90, "shape": 1.5, "roi": 1.2},
}
REGION_ROI_MULT = {"SEL": 1.00, "YNG": 0.90, "ROK": 1.10}

# CRM at member level: a message raises that week's order probability by the member's uplift.
# Uplift is highest for members who buy now and then, lowest for loyal members who buy anyway
# ("sure things"). It also needs timing: a reminder works when the member is close to running out,
# and fades with recent messages (fatigue). So sending to more members reaches less-ready ones.
U_SCALE = 0.20
DUE_MID, DUE_WIDTH = 0.90, 0.12   # reminder response = logistic in (weeks since last order / reorder cycle)
FATIGUE = 0.70        # each message in the previous 3 weeks multiplies the next message's uplift by this
SCORE_NOISE = 0.15    # the "running low" score is a noisy view of how due a member is

PROMO_WEEKS = ["2024-05-13", "2024-11-25", "2024-12-16", "2024-12-23",
               "2025-05-12", "2025-11-24", "2025-12-15", "2025-12-22"]
LNY_WEEKS = ["2024-02-05", "2025-01-27"]
CHUSEOK_WEEKS = ["2024-09-16", "2025-10-06"]
HOLDOUT = {"start": 80, "weeks": 8, "share": 0.30}
FREQ = {"start": 92, "weeks": 6, "share": 0.50}
GEO_TESTS = [{"region": "YNG", "channel": "store_trial", "start": 62, "weeks": 6},
             {"region": "ROK", "channel": "retail_partner", "start": 70, "weeks": 4}]
GRID = np.round(np.arange(0, 2.0001, 0.05), 2)


def geometric_adstock(x, decay):
    """Normalised geometric adstock (keeps the spend scale), warm-started at steady state."""
    out = np.empty_like(x, dtype=float)
    carry = x[0]
    for t, v in enumerate(x):
        carry = (1 - decay) * v + decay * carry
        out[t] = carry
    return out


def hill(x, half_sat, shape):
    return x**shape / (x**shape + half_sat**shape)


def ar1(rng, n, rho, sd):
    z = np.zeros(n)
    for i in range(1, n):
        z[i] = rho * z[i - 1] + rng.normal(0, sd)
    return z


def calendar():
    weeks = pd.date_range(START, periods=N_WEEKS, freq="7D")
    return weeks, {"promo": weeks.isin(pd.to_datetime(PROMO_WEEKS)).astype(int),
                   "lny": weeks.isin(pd.to_datetime(LNY_WEEKS)).astype(int),
                   "chuseok": weeks.isin(pd.to_datetime(CHUSEOK_WEEKS)).astype(int)}


# ---------------------------------------------------------------- acquisition (region level)

def acquisition(name, cfg, rng, cal, shared):
    t = np.arange(N_WEEKS)
    interest = 100 * np.exp(ar1(rng, N_WEEKS, 0.8, 0.03) + 0.10 * np.cos(2 * np.pi * (t - 48) / 52) + 0.0015 * t)
    interest = interest * np.exp(ar1(rng, N_WEEKS, 0.6, 0.04))  # short demand shocks, visible in the trend index
    season = (1 - 0.15 * cal["lny"]) * (1 - 0.12 * cal["chuseok"])
    base_acq = cfg["base_acq"] * (interest / 100) * (1 + 0.55 * cal["promo"]) * season

    weekly = {c: cfg["budget"] * MIX[c] / 52 for c in CHANNELS}
    raw = {
        "referral": shared["season"] * rng.lognormal(0, 0.08, N_WEEKS),
        "store_trial": shared["season"] * rng.lognormal(0, 0.08, N_WEEKS),
        # incentives paid per device sold: they follow demand (trap 1), on top of quarterly budget resets
        "retail_partner": (interest / 100) ** 3 * np.repeat(rng.lognormal(0, 0.18, N_WEEKS // 13 + 1), 13)[:N_WEEKS]
                          * rng.lognormal(0, 0.08, N_WEEKS),
    }
    events = np.full(N_WEEKS, 0.3)
    events[rng.choice(N_WEEKS, 18, replace=False)] += 2.4
    raw["events"] = events * rng.lognormal(0, 0.10, N_WEEKS)

    planned = {}
    for c in ACQ_CHANNELS:
        s = raw[c] * (1 + 0.6 * cal["promo"])
        planned[c] = s / s.mean() * weekly[c]
    spend = {c: planned[c].copy() for c in ACQ_CHANNELS}
    for g in GEO_TESTS:  # geo tests switch a channel off in one region
        if g["region"] == name:
            spend[g["channel"]][g["start"]: g["start"] + g["weeks"]] = 0.0

    params, contrib = {}, {}
    for c in ACQ_CHANNELS:
        p = TRUE_CHANNEL[c]
        decay = float(np.clip(p["decay"] + rng.uniform(-0.05, 0.05), 0.05, 0.9))
        half_sat = p["half_sat"] * rng.uniform(0.9, 1.1)
        roi = p["roi"] * REGION_ROI_MULT[name] * rng.uniform(0.9, 1.1)
        scale = geometric_adstock(planned[c], decay).mean()
        h_plan = hill(geometric_adstock(planned[c], decay) / scale, half_sat, p["shape"])
        beta = roi * planned[c].sum() / (LTV_FOR_CALIBRATION * h_plan.sum())  # max weekly members from channel
        contrib[c] = beta * hill(geometric_adstock(spend[c], decay) / scale, half_sat, p["shape"])
        params[c] = {"decay": decay, "half_sat": half_sat, "shape": p["shape"], "scale": scale, "beta": beta}
    mu = base_acq + sum(contrib.values())
    new_members = rng.poisson(mu * rng.lognormal(0, 0.03, N_WEEKS))
    return {"interest": interest, "planned": planned, "spend": spend, "params": params, "contrib": contrib,
            "base_acq": base_acq, "new_members": new_members}


# ---------------------------------------------------------------- members and orders

def traits(rng, n):
    device = np.where(rng.random(n) < 0.40, "premium", "basic")
    age = rng.choice(["20s", "30s", "40s", "50s+"], n, p=[0.22, 0.33, 0.28, 0.17])
    rate = np.clip(rng.gamma(4.0, 0.17 / 4.0, n) * np.where(device == "premium", 1.15, 0.92), 0.03, 0.6)
    churn = 0.012 * rng.lognormal(0, 0.3, n)
    young = np.isin(age, ["20s", "30s"])
    uplift = U_SCALE * np.exp(-(((rate - 0.10) / 0.07) ** 2)) * np.where(young, 1.25, 0.85) * rng.lognormal(0, 0.3, n)
    return device, age, rate, churn, np.clip(uplift, 0, 0.30)


def simulate_members(name, cfg, new_counts, cal, tau, seed, record, experiments=True):
    """Run the member base week by week. Returns weekly totals, and event logs when record=True."""
    rng = np.random.default_rng(seed)
    n0, n_max = cfg["active0"], cfg["active0"] + int(new_counts.sum())
    device, age, rate, churn, uplift = traits(rng, n_max)
    cycle = 1 / rate
    join = np.empty(n_max, int)
    join[:n0] = -rng.integers(1, 150, n0)
    join[n0:] = np.repeat(np.arange(N_WEEKS), new_counts)
    since = rng.uniform(0, 1, n_max) * cycle          # weeks since the member's last order
    alive = np.ones(n_max, bool)
    hold = rng.random(n_max) < HOLDOUT["share"]
    boost = rng.random(n_max) < FREQ["share"]
    recent = np.zeros((3, n_max), np.int8)             # messages received in each of the last 3 weeks
    t_idx = np.arange(N_WEEKS)
    order_season = 1 + 0.06 * np.cos(2 * np.pi * (t_idx - 48) / 52)

    weekly = {k: np.zeros(N_WEEKS) for k in ["orders", "sends", "boost_sends", "suppressed", "incr", "active"]}
    curve = np.zeros((len(GRID), N_WEEKS))   # expected incremental orders if trigger volume were scaled by GRID
    incr_plus1 = np.zeros(N_WEEKS)
    logs = {"orders": [], "sends": []}
    for t in range(N_WEEKS):
        act = alive & (join <= t)
        idx = np.flatnonzero(act)
        promo = cal["promo"][t]
        score = since[idx] / cycle[idx] + rng.normal(0, SCORE_NOISE, idx.size)
        trig = score >= tau - 0.35 * promo       # running-low journeys, widened in promotion weeks
        ready = 1 / (1 + np.exp(-(since[idx] / cycle[idx] - DUE_MID) / DUE_WIDTH))
        u_eff = uplift[idx] * FATIGUE ** recent[:, idx].sum(0) * ready

        in_hold = experiments and HOLDOUT["start"] <= t < HOLDOUT["start"] + HOLDOUT["weeks"]
        in_freq = experiments and FREQ["start"] <= t < FREQ["start"] + FREQ["weeks"]
        suppressed = trig & hold[idx] if in_hold else np.zeros(idx.size, bool)
        sent = trig & ~suppressed
        extra = np.zeros(idx.size, bool)
        if in_freq:  # boost group: as many extra messages as their triggered ones, to the next most-due members
            cand = np.flatnonzero(boost[idx] & ~trig)
            k = int((trig & boost[idx]).sum())
            extra[cand[np.argsort(-score[cand])[:k]]] = True
            sent = sent | extra

        # True CRM response for the trigger volume scaled by m: the next most-due members are added first
        order_by = np.argsort(-score)
        cum = np.concatenate([[0], np.cumsum(u_eff[order_by])])
        n_trig = int(trig.sum())
        curve[:, t] = cum[np.minimum(np.round(GRID * n_trig).astype(int), idx.size)]
        incr_plus1[t] = cum[min(int(round(1.01 * n_trig)), idx.size)]

        due = since[idx] >= 0.8 * cycle[idx]
        p0 = rate[idx] * order_season[t] * (1 + 0.25 * promo) * (1 - 0.10 * cal["lny"][t]) * (1 - 0.10 * cal["chuseok"][t]) \
            * np.where(due, 1.35, 0.85)
        p = np.clip(p0 + sent * u_eff, 0, 0.95)
        ordered = rng.random(idx.size) < p

        weekly["orders"][t], weekly["sends"][t] = ordered.sum(), sent.sum()
        weekly["boost_sends"][t], weekly["suppressed"][t] = extra.sum(), suppressed.sum()
        weekly["incr"][t], weekly["active"][t] = (sent * u_eff).sum(), idx.size
        if record:
            logs["orders"].append(np.column_stack([idx[ordered], np.full(ordered.sum(), t)]))
            typ = np.where(extra, 1, 0)
            logs["sends"].append(np.column_stack([idx[sent], np.full(sent.sum(), t), typ[sent]]))
            logs["sends"].append(np.column_stack([idx[suppressed], np.full(suppressed.sum(), t), np.full(suppressed.sum(), 2)]))

        since[idx] = np.where(ordered, 0, since[idx] + 1)
        recent = np.roll(recent, 1, axis=0)
        recent[0] = 0
        recent[0, idx[sent]] = 1
        alive[idx[rng.random(idx.size) < churn[idx]]] = False

    out = {"weekly": weekly, "curve": curve, "incr_plus1": incr_plus1}
    if record:
        out["members"] = pd.DataFrame({"member_local": np.arange(n_max), "join_week": join, "age_band": age,
                                       "device_model": device})
        out["truth"] = pd.DataFrame({"member_local": np.arange(n_max), "order_rate": rate, "weekly_churn": churn,
                                     "crm_uplift": uplift, "holdout_group": hold, "boost_group": boost})
        out["orders"] = np.concatenate(logs["orders"])
        out["sends"] = np.concatenate(logs["sends"])
    return out


def crm_truth(name, cfg, new_counts, cal, seed, tau):
    """True CRM effect by re-running the member base with the same random numbers (the random stream does
    not depend on who is messaged): plan-year orders at trigger volume m x 2025, minus orders with no CRM.
    This counts timing: a reminder that only moves a purchase earlier adds little. No experiments in these runs."""
    run = lambda t: simulate_members(name, cfg, new_counts, cal, t, seed, record=False, experiments=False)["weekly"]
    base = run(tau)
    s1, o1 = base["sends"][PLAN].sum(), base["orders"][PLAN].sum()
    o0 = run(99.0)["orders"][PLAN].sum()
    grid = np.round(np.arange(0, 2.0001, 0.25), 2)
    incr = []
    for m in grid:
        if m == 0:
            incr.append(0.0)
            continue
        lo, hi = -3.0, 4.0           # threshold whose plan-year sends equal m x 2025
        for _ in range(12):
            mid = (lo + hi) / 2
            w = run(mid)
            lo, hi = (mid, hi) if w["sends"][PLAN].sum() > m * s1 else (lo, mid)
        incr.append(float(run((lo + hi) / 2)["orders"][PLAN].sum() - o0))
    curve = np.interp(GRID, grid, incr)
    return {"plan_year_sends": float(s1), "plan_year_incr_orders": float(o1 - o0), "curve_grid": grid.tolist(),
            "curve_orders": incr, "plan_year_curve_orders": curve.round(1).tolist()}


def calibrate_tau(name, cfg, new_counts, cal, seed):
    """Trigger threshold that makes two-year CRM spend match the CRM budget (bisection on a fixed random stream)."""
    target = cfg["budget"] * MIX["crm"] * 2 / COST_PER_SEND
    lo, hi = 0.2, 2.5
    for _ in range(14):
        mid = (lo + hi) / 2
        sends = simulate_members(name, cfg, new_counts, cal, mid, seed, record=False)["weekly"]["sends"].sum()
        lo, hi = (mid, hi) if sends > target else (lo, mid)
    return (lo + hi) / 2


def main():
    rng = np.random.default_rng(SEED)
    weeks, cal = calendar()
    shared = {"season": np.where((np.arange(N_WEEKS) % 9) < 6, 1.35, 0.45) * rng.lognormal(0, 0.05, N_WEEKS)}
    RAW.mkdir(parents=True, exist_ok=True)
    TRUTH.mkdir(parents=True, exist_ok=True)
    truth = {"seed": SEED, "note": "Hidden ground truth. Do not use for model fitting.", "margin_per_order": MARGIN_PER_ORDER,
             "device_margin": DEVICE_MARGIN, "cost_per_send": COST_PER_SEND, "grid": GRID.tolist(), "regions": {}}
    members, orders, sends, groups, mtruth, spend_rows, cal_rows, geo_plan = [], [], [], [], [], [], [], []
    offset = 0
    for k, (name, cfg) in enumerate(REGIONS.items()):
        acq = acquisition(name, cfg, rng, cal, shared)
        seed = SEED + 101 * (k + 1)
        tau = calibrate_tau(name, cfg, acq["new_members"], cal, seed)
        sim = simulate_members(name, cfg, acq["new_members"], cal, tau, seed, record=True)
        m = sim["members"].assign(member_id=lambda d: d["member_local"] + offset, region=name)
        members.append(m[["member_id", "region", "join_week", "age_band", "device_model"]])
        mtruth.append(sim["truth"].assign(member_id=lambda d: d["member_local"] + offset)
                      .drop(columns="member_local"))
        orders.append(pd.DataFrame({"member_id": sim["orders"][:, 0] + offset, "week": sim["orders"][:, 1]}))
        sends.append(pd.DataFrame({"member_id": sim["sends"][:, 0] + offset, "week": sim["sends"][:, 1],
                                   "send_type": np.array(["trigger", "boost", "suppressed"])[sim["sends"][:, 2]]}))
        t = sim["truth"]
        for exp, col, label in (("crm_holdout_w80", "holdout_group", "holdout"),
                                ("crm_frequency_w92", "boost_group", "more_messages")):
            groups.append(pd.DataFrame({"member_id": t["member_local"] + offset, "experiment": exp,
                                        "group": np.where(t[col], label, "business_as_usual")}))
        for g in GEO_TESTS:
            if g["region"] == name:
                geo_plan.append({**g, "planned_weekly_spend": round(float(acq["planned"][g["channel"]][g["start"]: g["start"] + g["weeks"]].mean()), -3)})
        offset += len(m)
        for c in ACQ_CHANNELS:
            spend_rows.append(pd.DataFrame({"week_start": weeks.date, "region": name, "channel": c,
                                            "spend": np.round(acq["spend"][c], -3)}))
        cal_rows.append(pd.DataFrame({"week_start": weeks.date, "region": name,
                                      "category_interest": np.round(acq["interest"] * rng.lognormal(0, 0.01, N_WEEKS), 1),
                                      "event_promo": cal["promo"], "holiday_lny": cal["lny"], "holiday_chuseok": cal["chuseok"]}))

        # ---- truth: value of a new member, acquisition ROI, CRM ROI and response curve ----
        mt = sim["truth"]
        o = pd.DataFrame(sim["orders"], columns=["m", "w"])
        joined = sim["members"].query("0 <= join_week < 52")
        first_year = o.merge(joined[["member_local", "join_week"]], left_on="m", right_on="member_local")
        first_year = first_year[(first_year["w"] >= first_year["join_week"]) & (first_year["w"] < first_year["join_week"] + 52)]
        ltv = DEVICE_MARGIN + MARGIN_PER_ORDER * len(first_year) / len(joined)
        ch = {}
        for c in ACQ_CHANNELS:
            p = acq["params"][c]
            total = acq["contrib"][c].sum()
            up = hill(geometric_adstock(acq["spend"][c] * 1.01, p["decay"]) / p["scale"], p["half_sat"], p["shape"])
            ch[c] = {**p, "true_roi": total * ltv / acq["spend"][c].sum(),
                     "true_marginal_roi": (p["beta"] * up - acq["contrib"][c]).sum() * ltv / (0.01 * acq["spend"][c].sum()),
                     "total_spend": acq["spend"][c].sum(), "total_contribution": total,
                     "planned_spend": acq["planned"][c].round(0).tolist()}
        w = sim["weekly"]
        ct = crm_truth(name, cfg, acq["new_members"], cal, seed, tau)
        spend_plan = ct["plan_year_sends"] * COST_PER_SEND
        g = GRID.tolist()
        ch["crm"] = {"true_roi": ct["plan_year_incr_orders"] * MARGIN_PER_ORDER / spend_plan,
                     "true_marginal_roi": (ct["plan_year_curve_orders"][g.index(1.05)] - ct["plan_year_curve_orders"][g.index(0.95)])
                                          * MARGIN_PER_ORDER / (0.1 * spend_plan),
                     "instant_uplift_roi": w["incr"].sum() * MARGIN_PER_ORDER / (w["sends"] * COST_PER_SEND).sum(),
                     "total_spend": (w["sends"] * COST_PER_SEND).sum(), "trigger_threshold": tau,
                     "note": "true ROI and marginal ROI are for the 2025 plan year, from counterfactual re-runs", **ct}
        truth["regions"][name] = {
            "value_per_new_member": ltv, "channels": ch,
            "media_share_of_new_members": float(sum(acq["contrib"].values()).sum() / (acq["base_acq"] + sum(acq["contrib"].values())).sum()),
            "crm_share_of_orders": float(ct["plan_year_incr_orders"] / w["orders"][PLAN].sum()),
            "avg_uplift_per_send": float(w["incr"].sum() / w["sends"].sum()),
            "mean_member_uplift": float(mt["crm_uplift"].mean()),
        }

    pd.concat(members).to_parquet(RAW / "members.parquet", index=False)
    pd.concat(orders).to_parquet(RAW / "orders.parquet", index=False)
    pd.concat(sends).to_parquet(RAW / "crm_sends.parquet", index=False)
    pd.concat(groups).to_parquet(RAW / "experiment_groups.parquet", index=False)
    pd.concat(spend_rows).to_csv(RAW / "marketing_spend.csv", index=False)
    pd.concat(cal_rows).to_csv(RAW / "calendar.csv", index=False)
    pd.DataFrame(geo_plan).to_csv(RAW / "geo_test_plan.csv", index=False)  # the test design the analyst receives
    pd.concat(mtruth).to_parquet(TRUTH / "member_truth.parquet", index=False)
    (TRUTH / "ground_truth.json").write_text(json.dumps(truth, indent=2, default=float))

    print(f"members {offset:,}  orders {sum(len(o) for o in orders):,}  CRM rows {sum(len(s) for s in sends):,}")
    for r in REGIONS:
        g = truth["regions"][r]
        print(f"\n{r}  member value KRW {g['value_per_new_member']:,.0f}  acquisition share {g['media_share_of_new_members']:.1%}  "
              f"CRM share of orders {g['crm_share_of_orders']:.1%}  uplift/send {g['avg_uplift_per_send']:.3f}")
        for c in CHANNELS:
            p = g["channels"][c]
            print(f"  {c:15s} spend KRW {p['total_spend'] / 1e6:6,.0f}M  ROI {p['true_roi']:.2f}  mROI {p['true_marginal_roi']:.2f}")


if __name__ == "__main__":
    main()
