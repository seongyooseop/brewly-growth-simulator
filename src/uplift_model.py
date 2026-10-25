"""
Step 4 - Who should get the message? A CRM uplift model trained on the randomised holdout.

The budget plan says CRM should send about 30% fewer messages. This step decides which 30%.
Ranking members by how likely they are to buy (what a running-low journey does) is not the same as
ranking them by how much a message changes what they do. Loyal members buy anyway ("sure things");
the message matters for members who buy now and then ("persuadables").

Data: data/marts/uplift_training.csv, members the journey triggered during the 8-week holdout test.
The holdout was random, so within this group messaged and held-out members are comparable.
Model: T-learner. Two gradient-boosting models predict 8-week orders with and without a message;
predicted uplift = the difference. Trained on 60% of members, evaluated on the other 40%.

Evaluation on the held-out 40%:
  - Qini-style curve: messaging the top x% by predicted uplift, how many extra orders (treated minus
    control rate, times members targeted), vs random and vs ranking by likelihood to buy.
  - Truth check: hidden true uplift by predicted-uplift decile.

Output: outputs/step4_uplift.json
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
NUM = ["recency_weeks", "orders_12w", "orders_26w", "tenure_weeks", "sends_8w"]
CAT = ["age_band", "device_model", "region"]
SHARES = np.round(np.arange(0, 1.0001, 0.05), 2)


def features(df):
    return pd.concat([df[NUM].astype(float), pd.get_dummies(df[CAT], dtype=float)], axis=1)


def incremental_curve(y, t, score):
    """Extra orders from messaging the top share by score: (treated rate - control rate) in the top x members targeted."""
    order = np.argsort(-score)
    y, t = y[order], t[order]
    out = []
    for s in SHARES:
        n = int(round(s * len(y)))
        if n < 50:
            out.append(0.0)
            continue
        yt, yc = y[:n][t[:n] == 1], y[:n][t[:n] == 0]
        out.append((yt.mean() - yc.mean()) * n)
    return np.array(out)


def main():
    df = pd.read_csv(ROOT / "data" / "marts" / "uplift_training.csv")
    truth = pd.read_parquet(ROOT / "data" / "truth" / "member_truth.parquet")[["member_id", "crm_uplift", "order_rate"]]
    df = df.merge(truth, on="member_id")
    X, y, t = features(df), df["orders_8w"].to_numpy(float), df["treated"].to_numpy()
    tr, te = train_test_split(np.arange(len(df)), test_size=0.4, random_state=7, stratify=t)

    params = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0, random_state=7)
    m1 = HistGradientBoostingRegressor(**params).fit(X.iloc[tr][t[tr] == 1], y[tr][t[tr] == 1])
    m0 = HistGradientBoostingRegressor(**params).fit(X.iloc[tr][t[tr] == 0], y[tr][t[tr] == 0])
    uplift = m1.predict(X) - m0.predict(X)
    propensity = m0.predict(X)   # expected orders without a message: who buys anyway

    yte, tte = y[te], t[te]
    curves = {"uplift_model": incremental_curve(yte, tte, uplift[te]),
              "likely_to_buy": incremental_curve(yte, tte, propensity[te]),
              "random": SHARES * incremental_curve(yte, tte, np.zeros(len(te)))[-1]}
    total = curves["uplift_model"][-1]
    area = {k: float(np.trapezoid(v - curves["random"], SHARES) / max(abs(total), 1e-9)) for k, v in curves.items()}

    test = df.iloc[te].assign(pred_uplift=uplift[te], decile=lambda d: pd.qcut(d["pred_uplift"].rank(method="first"), 10, labels=False))
    dec = test.groupby("decile").apply(lambda g: pd.Series({
        "members": len(g), "pred_uplift": g["pred_uplift"].mean(), "true_uplift_per_message": g["crm_uplift"].mean(),
        "observed_uplift": g.loc[g["treated"] == 1, "orders_8w"].mean() - g.loc[g["treated"] == 0, "orders_8w"].mean(),
        "orders_12w": g["orders_12w"].mean(), "share_young": g["age_band"].isin(["20s", "30s"]).mean(),
        "recency_weeks": g["recency_weeks"].mean()}), include_groups=False)
    rho = stats.spearmanr(test["pred_uplift"], test["crm_uplift"]).statistic

    # Plan check: message 70% of today's members (the budget plan's CRM cut), chosen by each ranking
    keep = 0.70
    at = lambda name: float(np.interp(keep, SHARES, curves[name]))
    summary = {
        "n_members": len(df), "n_test": len(te), "treated_share": float(t.mean()),
        "spearman_pred_vs_true_uplift": float(rho), "qini_area_vs_random": area,
        "keep_share": keep, "extra_orders_all_messaged": float(total),
        "extra_orders_keep_by_uplift": at("uplift_model"), "extra_orders_keep_by_likely_to_buy": at("likely_to_buy"),
        "extra_orders_keep_random": at("random"),
    }
    out = {"summary": summary, "shares": SHARES.tolist(), "curves": {k: v.round(1).tolist() for k, v in curves.items()},
           "deciles": dec.reset_index().round(4).to_dict(orient="records")}
    OUT.mkdir(exist_ok=True)
    (OUT / "step4_uplift.json").write_text(json.dumps(out, indent=2, default=float))
    pd.set_option("display.width", 200)
    print(json.dumps(summary, indent=2, default=float))
    print(dec.round(3).to_string())


if __name__ == "__main__":
    main()
