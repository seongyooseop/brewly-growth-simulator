"""
Step 1b - Build analysis tables from the raw member events with SQL (DuckDB).

Runs sql/marts.sql over data/raw/ and writes each table to data/marts/ as CSV.
The marketing-mix model, the dashboard and the experiment readouts all read from these marts,
never from the raw files directly.
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW, MARTS = ROOT / "data" / "raw", ROOT / "data" / "marts"
COST_PER_SEND = 120   # finance input: KRW per CRM message incl. average coupon redeemed
TABLES = ["weekly_region", "cohort_monthly", "lifecycle_funnel", "experiment_members", "uplift_training"]


def main():
    MARTS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET VARIABLE cost_per_send = {COST_PER_SEND}")
    for name in ["members", "orders", "crm_sends", "experiment_groups"]:
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{(RAW / f'{name}.parquet').as_posix()}')")
    for name in ["marketing_spend", "calendar"]:
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_csv_auto('{(RAW / f'{name}.csv').as_posix()}')")
    con.execute((ROOT / "sql" / "marts.sql").read_text(encoding="utf-8"))
    for t in TABLES:
        con.execute(f"COPY {t} TO '{(MARTS / f'{t}.csv').as_posix()}' (HEADER)")
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"{t:20s} {n:>9,} rows")
    print(con.execute("SELECT region, avg(new_members), avg(capsule_orders), avg(active_members), avg(crm_sends), "
                      "sum(spend_crm) / 1e6 FROM weekly_region GROUP BY 1 ORDER BY 1").df().round(0).to_string(index=False))


if __name__ == "__main__":
    main()
