"""Build the Power BI star schema for the BREWLY commercial dashboard (BA case).

Reads the BREWLY member-level data (../data/raw), adds two synthetic source extracts
(retail partner sell-out and CX tickets), plants six realistic data-quality issues in the
raw extracts, runs the checks, fixes them, and writes:

  data/raw_extract/  source extracts as received (with the issues)
  data/model/        clean star-schema tables loaded by Power BI
  tests/expected_values.csv   reconciliation targets computed in SQL (DuckDB)
  tests/summary.json          headline numbers quoted in the docs

All data is synthetic. Run from the repository root:
  python powerbi-ba-case/src/build_model.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "powerbi-ba-case"
SRC = ROOT / "data" / "raw"
OUT_RAW = CASE / "data" / "raw_extract"
OUT = CASE / "data" / "model"
TESTS = CASE / "tests"
for p in (OUT_RAW, OUT, TESTS):
    p.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(20261109)
W0 = pd.Timestamp("2024-01-01")
N_WEEKS = 104
LAST = N_WEEKS - 1

REGIONS = pd.DataFrame(
    {
        "region_code": ["SEL", "YNG", "ROK"],
        "region_name": ["Seoul metro", "Yeongnam", "Rest of Korea"],
        "sort_order": [1, 2, 3],
    }
)
REFILL_PRICE = {"basic": 28000, "premium": 34000}  # assumption: one capsule refill box per order

# --------------------------------------------------------------------------- dim_week
wk = pd.DataFrame({"week_id": np.arange(N_WEEKS)})
wk["week_start"] = W0 + pd.to_timedelta(wk.week_id * 7, unit="D")
iso = wk.week_start.dt.isocalendar()
wk["iso_year"] = iso.year.astype(int)
wk["iso_week"] = iso.week.astype(int)
wk["quarter"] = wk.iso_year.astype(str) + " Q" + np.minimum((wk.iso_week - 1) // 13 + 1, 4).astype(str)
wk["week_label"] = wk.iso_year.astype(str) + "-W" + wk.iso_week.astype(str).str.zfill(2)
wk["month_start"] = wk.week_start.dt.to_period("M").dt.to_timestamp()

# --------------------------------------------------------------------------- source tables
members = pd.read_parquet(SRC / "members.parquet")
orders_src = pd.read_parquet(SRC / "orders.parquet")
crm = pd.read_parquet(SRC / "crm_sends.parquet")
spend_src = pd.read_csv(SRC / "marketing_spend.csv", parse_dates=["week_start"])
members["region"] = members["region"].astype(str)
members["device_model"] = members["device_model"].astype(str)

dq_rows: list[dict] = []


def dq(check_id, table, rule, checked, failed_before, fix, failed_after):
    dq_rows.append(
        {
            "check_id": check_id,
            "source_table": table,
            "rule": rule,
            "rows_checked": int(checked),
            "rows_failed_before": int(failed_before),
            "fix_applied": fix,
            "rows_failed_after": int(failed_after),
            "status": "Pass" if failed_after == 0 else "Open",
        }
    )


# --------------------------------------------------------------------------- DQ1 orders: batch loaded twice
reg_of = members.set_index("member_id")["region"]
dup_mask = (orders_src.week == 61) & (orders_src.member_id.map(reg_of) == "YNG")
orders_raw = pd.concat([orders_src, orders_src[dup_mask]], ignore_index=True)
n_dup = int(orders_raw.duplicated(["member_id", "week"]).sum())
orders = orders_raw.drop_duplicates(["member_id", "week"]).reset_index(drop=True)
dq(
    "DQ-01", "orders", "One refill order per member per week (member_id, week unique)",
    len(orders_raw), n_dup,
    "Removed rows from the Yeongnam week-61 batch that was loaded twice", orders.duplicated(["member_id", "week"]).sum(),
)
fact_orders = orders.rename(columns={"week": "week_id"})[["member_id", "week_id"]]

# --------------------------------------------------------------------------- dim_member
first_last = fact_orders.groupby("member_id").week_id.agg(first_order_week_id="min", last_order_week_id="max")
dim_member = members.rename(columns={"region": "region_code", "join_week": "join_week_id"}).merge(
    first_last, on="member_id", how="left"
)
dim_member["join_date"] = W0 + pd.to_timedelta(dim_member.join_week_id * 7, unit="D")
q_of_week = wk.set_index("week_id")["quarter"]
dim_member["join_cohort"] = np.where(
    dim_member.join_week_id < 0, "Before 2024", dim_member.join_week_id.map(q_of_week).fillna("Before 2024")
)
dim_member["refill_price_krw"] = dim_member.device_model.map(REFILL_PRICE).fillna(28000).astype(int)
dim_member["first_order_week_id"] = dim_member.first_order_week_id.astype("Int64")
dim_member["last_order_week_id"] = dim_member.last_order_week_id.astype("Int64")
dim_member = dim_member[
    [
        "member_id", "region_code", "join_week_id", "join_date", "join_cohort", "age_band", "device_model",
        "refill_price_krw", "first_order_week_id", "last_order_week_id",
    ]
]

# active-member matrix (ordered in the last 8 weeks, inclusive)
idx = pd.Series(np.arange(len(dim_member)), index=dim_member.member_id)
M = np.zeros((len(dim_member), N_WEEKS), dtype=np.int16)
M[idx[fact_orders.member_id].values, fact_orders.week_id.values] = 1
cs = np.concatenate([np.zeros((len(M), 1), dtype=np.int32), M.cumsum(axis=1, dtype=np.int32)], axis=1)
active = np.zeros_like(M, dtype=bool)
for w in range(N_WEEKS):
    active[:, w] = (cs[:, w + 1] - cs[:, max(0, w - 7)]) > 0

# --------------------------------------------------------------------------- DQ2 marketing spend: unit mismatch
spend_src["week_id"] = ((spend_src.week_start - W0).dt.days // 7).astype(int)
spend_raw = spend_src.copy()
bad = (spend_raw.region == "ROK") & (spend_raw.channel == "events") & spend_raw.week_id.between(40, 47) & (spend_raw.spend > 0)
spend_raw.loc[bad, "spend"] = (spend_raw.loc[bad, "spend"] / 1000).round(1)  # entered in thousand KRW
spend_raw[["week_start", "region", "channel", "spend"]].to_csv(OUT_RAW / "marketing_spend_extract.csv", index=False)
med = spend_raw[spend_raw.spend > 0].groupby(["region", "channel"]).spend.transform("median")
flag = (spend_raw.spend > 0) & (spend_raw.spend < 0.01 * med.reindex(spend_raw.index).fillna(np.inf))
n_unit = int(flag.sum())
spend_clean = spend_raw.copy()
spend_clean.loc[flag, "spend"] = spend_clean.loc[flag, "spend"] * 1000
med2 = spend_clean[spend_clean.spend > 0].groupby(["region", "channel"]).spend.transform("median")
flag2 = (spend_clean.spend > 0) & (spend_clean.spend < 0.01 * med2.reindex(spend_clean.index).fillna(np.inf))
dq(
    "DQ-02", "marketing_spend", "Weekly spend within 1%-10,000% of the channel-region median (unit check)",
    len(spend_raw), n_unit, "Multiplied rows entered in thousand KRW by 1,000 (Rest of Korea brand events, weeks 40-47)",
    flag2.sum(),
)
fact_spend = spend_clean.rename(columns={"region": "region_code", "channel": "channel_code", "spend": "spend_krw"})[
    ["week_id", "region_code", "channel_code", "spend_krw"]
]
fact_spend["spend_krw"] = fact_spend.spend_krw.round(0).astype(np.int64)

dim_channel = pd.DataFrame(
    {
        "channel_code": ["referral", "store_trial", "retail_partner", "events", "crm"],
        "channel_name": ["Member referral", "Store trial", "Retail partner incentive", "Brand event", "CRM messages"],
        "channel_group": ["Owned", "Retail", "Retail", "Event", "Owned"],
        "is_acquisition": [True, True, True, True, False],
        "sort_order": [1, 2, 3, 4, 5],
    }
)

# --------------------------------------------------------------------------- CRM sends (aggregated)
crm["region_code"] = crm.member_id.map(reg_of)
crm["send_type"] = crm.send_type.astype(str)
fact_crm = (
    crm.groupby(["week", "region_code", "send_type"]).size().rename("messages").reset_index()
    .rename(columns={"week": "week_id"})
)

# --------------------------------------------------------------------------- retail sell-out (synthetic)
partners = [("Partner A", "Department store"), ("Partner B", "Hypermarket"), ("Partner C", "Electronics retailer")]
store_rows = []
counts = {"SEL": 14, "YNG": 8, "ROK": 8}
sid = 1
for reg, n in counts.items():
    for i in range(n):
        pname, fmt = partners[i % 3]
        store_rows.append(
            {
                "store_id": f"ST-{sid:03d}",
                "store_name": f"{pname} {REGIONS.set_index('region_code').region_name[reg]} #{i // 3 + 1}",
                "partner": pname,
                "store_format": fmt,
                "region_code": reg,
                "size_index": round(float(rng.uniform(0.6, 1.5)), 2),
            }
        )
        sid += 1
dim_store = pd.DataFrame(store_rows)

dim_product = pd.DataFrame(
    {
        "sku": ["DEV-BASIC", "DEV-PREMIUM", "CAP-CLASSIC", "CAP-SIGNATURE"],
        "product_name": ["BREWLY Basic machine", "BREWLY Premium machine", "Classic capsules (10)", "Signature capsules (10)"],
        "product_type": ["Device", "Device", "Capsules", "Capsules"],
        "unit_price_krw": [149000, 249000, 7900, 9900],
    }
)

rp = fact_spend[fact_spend.channel_code == "retail_partner"].set_index(["region_code", "week_id"]).spend_krw
rp_idx = rp / rp.groupby(level=0).transform("mean")
season = 1 + 0.25 * np.sin(2 * np.pi * (np.arange(N_WEEKS) - 40) / 52)
sell = []
for s in dim_store.itertuples():
    for w in range(N_WEEKS):
        k = float(rp_idx.get((s.region_code, w), 1.0))
        trend = 1 + 0.004 * w
        lam_dev = 3.2 * s.size_index * (0.55 + 0.45 * k) * season[w]
        lam_cap = 46 * s.size_index * trend * season[w]
        units = {
            "DEV-BASIC": rng.poisson(lam_dev * 0.68),
            "DEV-PREMIUM": rng.poisson(lam_dev * 0.32),
            "CAP-CLASSIC": rng.poisson(lam_cap * 0.6),
            "CAP-SIGNATURE": rng.poisson(lam_cap * 0.4),
        }
        for sku, u in units.items():
            if u > 0:
                sell.append((w, s.store_id, sku, int(u)))
            if sku.startswith("DEV") and u > 0:
                r = rng.binomial(u, 0.035)
                if r > 0:
                    sell.append((w, s.store_id, sku, -int(r)))  # returns arrive as negative rows
sell_raw = pd.DataFrame(sell, columns=["week_id", "store_id", "sku", "units"])

# DQ3 store codes in mixed formats (Partner B sends its own codes, Partner A drops zero padding)
partner_of = dim_store.set_index("store_id").partner
code = sell_raw.store_id.copy()
pb = sell_raw.store_id.map(partner_of).eq("Partner B") & (rng.random(len(sell_raw)) < 0.6)
code[pb] = "st" + sell_raw.store_id[pb].str[3:]
pa = sell_raw.store_id.map(partner_of).eq("Partner A") & (rng.random(len(sell_raw)) < 0.25)
code[pa] = "ST-" + sell_raw.store_id[pa].str[3:].astype(int).astype(str) + " "
sell_raw["store_code"] = code

# DQ6 late-arriving file: Partner C reported only part of its stores for the last week
pc_stores = dim_store[dim_store.partner == "Partner C"].store_id.tolist()
missing_last = rng.choice(pc_stores, size=int(round(len(pc_stores) * 0.6)), replace=False)
sell_raw = sell_raw[~((sell_raw.week_id == LAST) & sell_raw.store_id.isin(missing_last))]
sell_raw["week_start"] = (W0 + pd.to_timedelta(sell_raw.week_id * 7, unit="D")).dt.date
sell_raw[["week_start", "store_code", "sku", "units"]].to_csv(OUT_RAW / "retail_sellout_extract.csv", index=False)

valid = set(dim_store.store_id)
n_bad_codes = int((~sell_raw.store_code.isin(valid)).sum())


def normalise(c: str) -> str:
    m = re.search(r"(\d+)", str(c))
    return f"ST-{int(m.group(1)):03d}" if m else str(c)


sell_raw["store_id_clean"] = sell_raw.store_code.map(normalise)
dq(
    "DQ-03", "retail_sellout", "Every store code matches the store master (ST-000 format)",
    len(sell_raw), n_bad_codes, "Normalised partner codes (st012, 'ST-12 ') to ST-012 via the store master",
    (~sell_raw.store_id_clean.isin(valid)).sum(),
)
n_neg = int((sell_raw.units < 0).sum())
sell_raw["units_sold"] = sell_raw.units.clip(lower=0)
sell_raw["units_returned"] = (-sell_raw.units).clip(lower=0)
fact_sellout = (
    sell_raw.groupby(["week_id", "store_id_clean", "sku"])[["units_sold", "units_returned"]].sum().reset_index()
    .rename(columns={"store_id_clean": "store_id"})
)
price = dim_product.set_index("sku").unit_price_krw
fact_sellout["gross_revenue_krw"] = fact_sellout.units_sold * fact_sellout.sku.map(price)
fact_sellout["returns_value_krw"] = fact_sellout.units_returned * fact_sellout.sku.map(price)
fact_sellout["net_revenue_krw"] = fact_sellout.gross_revenue_krw - fact_sellout.returns_value_krw
dq(
    "DQ-04", "retail_sellout", "Units are non-negative; returns are reported separately",
    len(sell_raw), n_neg, "Split negative rows into units_returned; net revenue = gross - returns", 0,
)
rep = sell_raw.groupby("week_id").store_id_clean.nunique().reindex(range(N_WEEKS), fill_value=0)
completeness = rep / len(dim_store)
incomplete_weeks = completeness[completeness < 0.95].index.tolist()
wk["sellout_stores_reported"] = rep.values
wk["sellout_complete"] = (completeness >= 0.95).astype(int).values
dq(
    "DQ-06", "retail_sellout", "At least 95% of stores reported for the week (late files)",
    N_WEEKS, len(incomplete_weeks),
    "Flagged incomplete weeks in dim_week (sellout_complete = 0); default views exclude them until the file lands",
    0,
)

# --------------------------------------------------------------------------- CX tickets (synthetic)
cats = ["Refill delivery", "Device issue", "Billing and payment", "Subscription change or cancel", "Product question"]
cat_p = [0.34, 0.2, 0.15, 0.14, 0.17]
res_med = {"Refill delivery": 2.0, "Device issue": 5.0, "Billing and payment": 1.5, "Subscription change or cancel": 1.0, "Product question": 0.6}
member_ids = dim_member.member_id.values
last_week = dim_member.last_order_week_id.fillna(-99).astype(int).values
tickets = []
tid = 1
for w in range(N_WEEKS):
    act = np.flatnonzero(active[:, w])
    n = rng.poisson(0.0045 * len(act))
    chosen_cat = rng.choice(len(cats), size=n, p=cat_p)
    for c in chosen_cat:
        cat = cats[c]
        if cat.startswith("Subscription"):
            near = np.flatnonzero((last_week >= w - 1) & (last_week <= w + 2) & (last_week < LAST - 12))
            pool = near if len(near) and rng.random() < 0.7 else act
        else:
            pool = act
        m = member_ids[rng.choice(pool)]
        days = int(np.ceil(rng.gamma(2.0, res_med[cat] / 1.68)))
        resolved = w + days / 7 <= LAST
        tickets.append(
            {
                "ticket_id": f"T{tid:06d}",
                "member_id": int(m),
                "created_week_id": w,
                "category": cat,
                "contact_channel": rng.choice(["App chat", "Phone", "Email"], p=[0.55, 0.3, 0.15]),
                "resolution_days": days if resolved else None,
                "status": "Resolved" if resolved else "Open",
            }
        )
        tid += 1
cx = pd.DataFrame(tickets)
cx["region_code"] = cx.member_id.map(reg_of)
miss = rng.random(len(cx)) < 0.03
cx_raw = cx.copy()
cx_raw.loc[miss, "region_code"] = None
cx_raw.to_csv(OUT_RAW / "cx_tickets_extract.csv", index=False)
n_miss = int(cx_raw.region_code.isna().sum())
cx_clean = cx_raw.copy()
cx_clean["region_code"] = cx_clean.region_code.fillna(cx_clean.member_id.map(reg_of))
dq(
    "DQ-05", "cx_tickets", "Every ticket has a region code",
    len(cx_raw), n_miss, "Filled missing region from the member master (member_id)", cx_clean.region_code.isna().sum(),
)
fact_cx = cx_clean[
    ["ticket_id", "member_id", "region_code", "created_week_id", "category", "contact_channel", "resolution_days", "status"]
].copy()
fact_cx["resolution_days"] = fact_cx.resolution_days.astype("Int64")

# --------------------------------------------------------------------------- cohort retention (4-week periods)
coh = dim_member[dim_member.join_week_id >= 0][["member_id", "join_week_id", "join_cohort"]]
o = fact_orders.merge(coh, on="member_id")
o["period"] = (o.week_id - o.join_week_id) // 4
o = o[o.period >= 0]
ret = o.groupby(["join_cohort", "period"]).member_id.nunique().rename("retained_members").reset_index()
size = coh.groupby("join_cohort").agg(cohort_size=("member_id", "size"), max_join=("join_week_id", "max")).reset_index()
ret = ret.merge(size, on="join_cohort")
ret = ret[ret.max_join + 4 * ret.period + 3 <= LAST]  # keep fully observed periods only
fact_cohort = ret[["join_cohort", "period", "cohort_size", "retained_members"]].rename(columns={"period": "months_since_join"})
fact_cohort = fact_cohort[fact_cohort.months_since_join <= 12]

# --------------------------------------------------------------------------- write model
dq_df = pd.DataFrame(dq_rows).sort_values("check_id")
tables = {
    "dim_week": wk,
    "dim_region": REGIONS,
    "dim_member": dim_member,
    "dim_channel": dim_channel,
    "dim_store": dim_store,
    "dim_product": dim_product,
    "fact_orders": fact_orders,
    "fact_spend": fact_spend,
    "fact_crm_messages": fact_crm,
    "fact_sellout": fact_sellout,
    "fact_cx_tickets": fact_cx,
    "fact_cohort_retention": fact_cohort,
    "dq_checks": dq_df,
}
for name, df in tables.items():
    df.to_csv(OUT / f"{name}.csv", index=False, date_format="%Y-%m-%d")

# --------------------------------------------------------------------------- reconciliation targets (SQL)
con = duckdb.connect()
for name in tables:
    con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_csv_auto('{(OUT / (name + '.csv')).as_posix()}', header=true)")

tests = []


def t(test_id, measure, filt, sql):
    val = con.execute(sql).fetchone()[0]
    tests.append({"test_id": test_id, "measure": measure, "filter": filt, "expected_value": val, "sql": " ".join(sql.split())})


Y25 = "w.iso_year = 2025"
t("FT-01", "Refill Orders", "ISO year 2025, all regions",
  f"SELECT COUNT(*) FROM fact_orders o JOIN dim_week w USING(week_id) WHERE {Y25}")
t("FT-02", "Refill Revenue (KRW)", "ISO year 2025, all regions",
  f"SELECT SUM(m.refill_price_krw) FROM fact_orders o JOIN dim_week w USING(week_id) JOIN dim_member m USING(member_id) WHERE {Y25}")
t("FT-03", "Active Members (8w)", f"Week {wk.week_label[LAST]}, all regions",
  f"SELECT COUNT(DISTINCT member_id) FROM fact_orders WHERE week_id BETWEEN {LAST - 7} AND {LAST}")
t("FT-04", "Active Members (8w)", f"Week {wk.week_label[LAST]}, Seoul metro",
  f"SELECT COUNT(DISTINCT o.member_id) FROM fact_orders o JOIN dim_member m USING(member_id) WHERE m.region_code='SEL' AND o.week_id BETWEEN {LAST - 7} AND {LAST}")
t("FT-05", "New Members", "ISO year 2025, all regions",
  f"SELECT COUNT(*) FROM dim_member m JOIN dim_week w ON m.join_week_id = w.week_id WHERE {Y25}")
t("FT-06", "Acquisition Spend (KRW)", "ISO year 2025, all regions",
  f"SELECT SUM(s.spend_krw) FROM fact_spend s JOIN dim_week w USING(week_id) JOIN dim_channel c USING(channel_code) WHERE {Y25} AND c.is_acquisition")
t("FT-07", "Blended CAC (KRW)", "ISO year 2025, Yeongnam",
  f"""SELECT (SELECT SUM(s.spend_krw) FROM fact_spend s JOIN dim_week w USING(week_id) WHERE {Y25} AND s.region_code='YNG')
      / (SELECT COUNT(*) FROM dim_member m JOIN dim_week w ON m.join_week_id = w.week_id WHERE {Y25} AND m.region_code='YNG')""")
t("FT-08", "Retail Net Revenue (KRW)", "ISO year 2025, complete weeks only",
  f"SELECT SUM(f.net_revenue_krw) FROM fact_sellout f JOIN dim_week w USING(week_id) WHERE {Y25} AND w.sellout_complete = 1")
t("FT-09", "Device Return Rate", "ISO year 2025, complete weeks only",
  f"""SELECT SUM(units_returned)::DOUBLE / SUM(units_sold) FROM fact_sellout f JOIN dim_week w USING(week_id)
      JOIN dim_product p USING(sku) WHERE {Y25} AND w.sellout_complete = 1 AND p.product_type='Device'""")
t("FT-10", "CRM Messages Sent", "ISO year 2025 (excludes holdout-suppressed records)",
  f"SELECT SUM(messages) FROM fact_crm_messages c JOIN dim_week w USING(week_id) WHERE {Y25} AND c.send_type <> 'suppressed'")
t("FT-11", "CX Tickets", "ISO year 2025",
  f"SELECT COUNT(*) FROM fact_cx_tickets x JOIN dim_week w ON x.created_week_id = w.week_id WHERE {Y25}")
t("FT-12", "CX SLA Met % (resolved within 3 days)", "ISO year 2025, resolved tickets",
  f"""SELECT AVG(CASE WHEN resolution_days <= 3 THEN 1.0 ELSE 0 END) FROM fact_cx_tickets x
      JOIN dim_week w ON x.created_week_id = w.week_id WHERE {Y25} AND status='Resolved'""")
t("FT-13", "Lapsed Members (12w+)", f"As of {wk.week_label[LAST]}, all regions",
  f"SELECT COUNT(*) FROM dim_member WHERE last_order_week_id IS NOT NULL AND last_order_week_id <= {LAST - 12}")
t("FT-14", "Month-3 Retention", "Cohort 2024 Q1",
  "SELECT SUM(retained_members)::DOUBLE / MAX(cohort_size) FROM fact_cohort_retention WHERE join_cohort='2024 Q1' AND months_since_join=3")
REV = "SELECT SUM(m.refill_price_krw) FROM fact_orders o JOIN dim_week w USING(week_id) JOIN dim_member m USING(member_id) WHERE w.iso_year = {y}"
t("FT-15", "Refill Revenue YoY %", "ISO year 2025 vs 2024", f"SELECT ({REV.format(y=2025)}) / ({REV.format(y=2024)}) - 1")
ACT = "SELECT COUNT(DISTINCT member_id) FROM fact_orders WHERE week_id BETWEEN {a} AND {b}"
t("FT-16", "Active Members YoY %", f"Week {wk.week_label[LAST]} vs {wk.week_label[LAST - 52]}",
  f"SELECT ({ACT.format(a=LAST - 7, b=LAST)})::DOUBLE / ({ACT.format(a=LAST - 59, b=LAST - 52)}) - 1")
NEW = "SELECT COUNT(*) FROM dim_member m JOIN dim_week w ON m.join_week_id = w.week_id WHERE w.iso_year = {y}"
t("FT-17", "New Members YoY %", "ISO year 2025 vs 2024", f"SELECT ({NEW.format(y=2025)})::DOUBLE / ({NEW.format(y=2024)}) - 1")
RET = "SELECT SUM(f.net_revenue_krw) FROM fact_sellout f JOIN dim_week w USING(week_id) WHERE w.iso_year = {y} AND w.sellout_complete = 1"
t("FT-18", "Retail Net Revenue YoY %", "ISO year 2025 vs 2024, complete weeks", f"SELECT ({RET.format(y=2025)})::DOUBLE / ({RET.format(y=2024)}) - 1")
t("FT-19", "CX SLA Gap vs Target (pp)", "ISO year 2025, target 85%",
  f"""SELECT AVG(CASE WHEN resolution_days <= 3 THEN 1.0 ELSE 0 END) - 0.85 FROM fact_cx_tickets x
      JOIN dim_week w ON x.created_week_id = w.week_id WHERE {Y25} AND status='Resolved'""")
pd.DataFrame(tests).to_csv(TESTS / "expected_values.csv", index=False)

# --------------------------------------------------------------------------- headline numbers for the docs
cancel = fact_cx[fact_cx.category.str.startswith("Subscription")].merge(dim_member[["member_id", "last_order_week_id"]], on="member_id")
lag = (cancel.last_order_week_id - cancel.created_week_id).dropna()
summary = {
    "rows": {k: int(len(v)) for k, v in tables.items()},
    "dq": dq_df[["check_id", "rows_failed_before"]].set_index("check_id").rows_failed_before.to_dict(),
    "incomplete_weeks": [wk.week_label[i] for i in incomplete_weeks],
    "cancel_tickets_share_within_2w_of_last_order": round(float((lag.abs() <= 2).mean()), 3),
    "tests": {r["test_id"]: r["expected_value"] for r in tests},
}
(TESTS / "summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
print(json.dumps(summary, indent=2, default=float))
