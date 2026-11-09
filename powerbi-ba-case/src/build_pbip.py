"""Generate the Power BI project (PBIP, TMDL semantic model) and measures.dax.

The model reads the CSVs in data/model through one parameter, DataFolder.
Run from the repository root after build_model.py:
  python powerbi-ba-case/src/build_pbip.py
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
DATA = (CASE / "data" / "model").resolve()
PB = CASE / "powerbi"
NAME = "BREWLY_Commercial"
SM = PB / f"{NAME}.SemanticModel"
RP = PB / f"{NAME}.Report"
NS = uuid.UUID("6f1c2b8e-1d5a-4c0e-9b1f-2a7d4e9c0b11")


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "|".join(parts)))


M_TYPE = {"int64": "Int64.Type", "double": "type number", "string": "type text", "dateTime": "type date", "boolean": "type logical"}

# (column, dataType, hidden, summarize, formatString, sortBy)
T = {
    "Dim Week": ("dim_week", [
        ("week_id", "int64", False, "none", "0", None),
        ("week_start", "dateTime", False, "none", "yyyy-mm-dd", None),
        ("iso_year", "int64", False, "none", "0", None),
        ("iso_week", "int64", False, "none", "0", None),
        ("quarter", "string", False, "none", None, None),
        ("week_label", "string", False, "none", None, None),
        ("month_start", "dateTime", False, "none", "yyyy-mm", None),
        ("sellout_stores_reported", "int64", False, "none", "0", None),
        ("sellout_complete", "int64", False, "none", "0", None),
    ]),
    "Dim Region": ("dim_region", [
        ("region_code", "string", False, "none", None, None),
        ("region_name", "string", False, "none", None, "sort_order"),
        ("sort_order", "int64", True, "none", "0", None),
    ]),
    "Dim Member": ("dim_member", [
        ("member_id", "int64", False, "none", "0", None),
        ("region_code", "string", True, "none", None, None),
        ("join_week_id", "int64", True, "none", "0", None),
        ("join_date", "dateTime", False, "none", "yyyy-mm-dd", None),
        ("join_cohort", "string", False, "none", None, None),
        ("age_band", "string", False, "none", None, None),
        ("device_model", "string", False, "none", None, None),
        ("refill_price_krw", "int64", False, "none", "#,0", None),
        ("first_order_week_id", "int64", True, "none", "0", None),
        ("last_order_week_id", "int64", True, "none", "0", None),
    ]),
    "Dim Channel": ("dim_channel", [
        ("channel_code", "string", True, "none", None, None),
        ("channel_name", "string", False, "none", None, "sort_order"),
        ("channel_group", "string", False, "none", None, None),
        ("is_acquisition", "boolean", False, "none", None, None),
        ("sort_order", "int64", True, "none", "0", None),
    ]),
    "Dim Store": ("dim_store", [
        ("store_id", "string", False, "none", None, None),
        ("store_name", "string", False, "none", None, None),
        ("partner", "string", False, "none", None, None),
        ("store_format", "string", False, "none", None, None),
        ("region_code", "string", True, "none", None, None),
        ("size_index", "double", True, "none", "0.00", None),
    ]),
    "Dim Product": ("dim_product", [
        ("sku", "string", False, "none", None, None),
        ("product_name", "string", False, "none", None, None),
        ("product_type", "string", False, "none", None, None),
        ("unit_price_krw", "int64", False, "none", "#,0", None),
    ]),
    "Fact Orders": ("fact_orders", [
        ("member_id", "int64", True, "none", "0", None),
        ("week_id", "int64", True, "none", "0", None),
    ]),
    "Fact Spend": ("fact_spend", [
        ("week_id", "int64", True, "none", "0", None),
        ("region_code", "string", True, "none", None, None),
        ("channel_code", "string", True, "none", None, None),
        ("spend_krw", "int64", True, "sum", "#,0", None),
    ]),
    "Fact CRM Messages": ("fact_crm_messages", [
        ("week_id", "int64", True, "none", "0", None),
        ("region_code", "string", True, "none", None, None),
        ("send_type", "string", False, "none", None, None),
        ("messages", "int64", True, "sum", "#,0", None),
    ]),
    "Fact Sellout": ("fact_sellout", [
        ("week_id", "int64", True, "none", "0", None),
        ("store_id", "string", True, "none", None, None),
        ("sku", "string", True, "none", None, None),
        ("units_sold", "int64", True, "sum", "#,0", None),
        ("units_returned", "int64", True, "sum", "#,0", None),
        ("gross_revenue_krw", "int64", True, "sum", "#,0", None),
        ("returns_value_krw", "int64", True, "sum", "#,0", None),
        ("net_revenue_krw", "int64", True, "sum", "#,0", None),
    ]),
    "Fact CX Tickets": ("fact_cx_tickets", [
        ("ticket_id", "string", False, "none", None, None),
        ("member_id", "int64", True, "none", "0", None),
        ("region_code", "string", True, "none", None, None),
        ("created_week_id", "int64", True, "none", "0", None),
        ("category", "string", False, "none", None, None),
        ("contact_channel", "string", False, "none", None, None),
        ("resolution_days", "int64", False, "none", "0", None),
        ("status", "string", False, "none", None, None),
    ]),
    "Fact Cohort Retention": ("fact_cohort_retention", [
        ("join_cohort", "string", False, "none", None, None),
        ("months_since_join", "int64", False, "none", "0", None),
        ("cohort_size", "int64", True, "sum", "#,0", None),
        ("retained_members", "int64", True, "sum", "#,0", None),
    ]),
    "DQ Checks": ("dq_checks", [
        ("check_id", "string", False, "none", None, None),
        ("source_table", "string", False, "none", None, None),
        ("rule", "string", False, "none", None, None),
        ("rows_checked", "int64", False, "sum", "#,0", None),
        ("rows_failed_before", "int64", False, "sum", "#,0", None),
        ("fix_applied", "string", False, "none", None, None),
        ("rows_failed_after", "int64", False, "sum", "#,0", None),
        ("status", "string", False, "none", None, None),
    ]),
}

# (name, expression, formatString, folder, description)
MEASURES = [
    ("Refill Orders", "COUNTROWS ( 'Fact Orders' )", "#,0", "Members", "Capsule refill orders (one per member per week after de-duplication)."),
    ("Refill Revenue (KRW)", "SUMX ( 'Fact Orders', RELATED ( 'Dim Member'[refill_price_krw] ) )", "#,0", "Members", "Refill orders x refill box price by device model (assumption: basic 28,000, premium 34,000)."),
    ("Ordering Members", "DISTINCTCOUNT ( 'Fact Orders'[member_id] )", "#,0", "Members", "Members with at least one refill order in the selected weeks."),
    ("Active Members (8w)", "VAR LastWeek = MAX ( 'Dim Week'[week_id] ) RETURN IF ( NOT ISBLANK ( LastWeek ), CALCULATE ( DISTINCTCOUNT ( 'Fact Orders'[member_id] ), REMOVEFILTERS ( 'Dim Week' ), 'Dim Week'[week_id] > LastWeek - 8, 'Dim Week'[week_id] <= LastWeek ) )", "#,0", "Members", "Members with a refill order in the 8 weeks up to the last selected week (semi-additive: a quarter shows its last week; blank for the unmatched-week row)."),
    ("New Members", "CALCULATE ( COUNTROWS ( 'Dim Member' ), USERELATIONSHIP ( 'Dim Member'[join_week_id], 'Dim Week'[week_id] ), 'Dim Member'[join_week_id] >= 0 )", "#,0", "Members", "Members who registered a machine in the selected weeks (from 2024)."),
    ("Lapsed Members (12w+)", "VAR Cutoff = CALCULATE ( MAX ( 'Dim Week'[week_id] ), REMOVEFILTERS ( 'Dim Week' ) ) RETURN CALCULATE ( COUNTROWS ( 'Dim Member' ), NOT ISBLANK ( 'Dim Member'[last_order_week_id] ), 'Dim Member'[last_order_week_id] <= Cutoff - 12 )", "#,0", "Members", "Members whose last refill order is 12 or more weeks before the latest data week. Ignores the week filter by design."),
    ("Acquisition Spend (KRW)", "CALCULATE ( SUM ( 'Fact Spend'[spend_krw] ), 'Dim Channel'[is_acquisition] = TRUE () )", "#,0", "Acquisition", "Spend on referral, store trial, retail partner incentive and brand events."),
    ("Blended CAC (KRW)", "DIVIDE ( [Acquisition Spend (KRW)], [New Members] )", "#,0", "Acquisition", "Acquisition spend / new members. Channel-level CAC is out of scope (needs the MMM in the main project)."),
    ("Retail Net Revenue (KRW)", "CALCULATE ( SUM ( 'Fact Sellout'[net_revenue_krw] ), 'Dim Week'[sellout_complete] = 1 )", "#,0", "Retail", "Partner sell-out net of returns, complete weeks only (at least 95% of stores reported)."),
    ("Retail Net Revenue incl. Incomplete (KRW)", "SUM ( 'Fact Sellout'[net_revenue_krw] )", "#,0", "Retail", "Same as above including weeks still waiting for partner files."),
    ("Device Units Sold", "CALCULATE ( SUM ( 'Fact Sellout'[units_sold] ), 'Dim Product'[product_type] = \"Device\", 'Dim Week'[sellout_complete] = 1 )", "#,0", "Retail", "Machines sold through partners, complete weeks only."),
    ("Device Return Rate", "DIVIDE ( CALCULATE ( SUM ( 'Fact Sellout'[units_returned] ), 'Dim Product'[product_type] = \"Device\", 'Dim Week'[sellout_complete] = 1 ), [Device Units Sold] )", "0.0%", "Retail", "Machines returned / machines sold."),
    ("Sell-out Store Coverage", "DIVIDE ( MIN ( 'Dim Week'[sellout_stores_reported] ), COUNTROWS ( ALL ( 'Dim Store' ) ) )", "0%", "Retail", "Lowest share of stores that reported in the selected weeks."),
    ("CRM Messages Sent", "CALCULATE ( SUM ( 'Fact CRM Messages'[messages] ), 'Fact CRM Messages'[send_type] <> \"suppressed\" )", "#,0", "CRM and CX", "Trigger and boost messages; holdout-suppressed records are not sends."),
    ("CX Tickets", "COUNTROWS ( 'Fact CX Tickets' )", "#,0", "CRM and CX", "Customer service tickets created in the selected weeks."),
    ("CX SLA Met %", "DIVIDE ( CALCULATE ( COUNTROWS ( 'Fact CX Tickets' ), 'Fact CX Tickets'[status] = \"Resolved\", 'Fact CX Tickets'[resolution_days] <= 3 ), CALCULATE ( COUNTROWS ( 'Fact CX Tickets' ), 'Fact CX Tickets'[status] = \"Resolved\" ) )", "0.0%", "CRM and CX", "Resolved tickets closed within 3 days / resolved tickets."),
    ("Median Resolution Days", "CALCULATE ( MEDIAN ( 'Fact CX Tickets'[resolution_days] ), 'Fact CX Tickets'[status] = \"Resolved\" )", "0.0", "CRM and CX", "Median days to resolve, resolved tickets only."),
    ("Tickets per 1,000 Active Members", "DIVIDE ( [CX Tickets], [Active Members (8w)] ) * 1000", "0.0", "CRM and CX", "Tickets in the period per 1,000 members active at its end."),
    ("Retention %", "DIVIDE ( SUM ( 'Fact Cohort Retention'[retained_members] ), SUM ( 'Fact Cohort Retention'[cohort_size] ) )", "0.0%", "Members", "Share of a join cohort ordering in the n-th 4-week period after joining. Use with cohort and month on the axes."),
    ("DQ Checks Passed", "CALCULATE ( COUNTROWS ( 'DQ Checks' ), 'DQ Checks'[status] = \"Pass\" )", "0", "Data quality", "Checks with no failing rows after fixes."),
    ("DQ Rows Fixed", "SUM ( 'DQ Checks'[rows_failed_before] )", "#,0", "Data quality", "Rows that failed a check before the fix."),
]

# (from table, from column, to table, to column, active)
RELS = [
    ("Fact Orders", "member_id", "Dim Member", "member_id", True),
    ("Fact Orders", "week_id", "Dim Week", "week_id", True),
    ("Dim Member", "region_code", "Dim Region", "region_code", True),
    ("Dim Member", "join_week_id", "Dim Week", "week_id", False),
    ("Fact Spend", "week_id", "Dim Week", "week_id", True),
    ("Fact Spend", "region_code", "Dim Region", "region_code", True),
    ("Fact Spend", "channel_code", "Dim Channel", "channel_code", True),
    ("Fact CRM Messages", "week_id", "Dim Week", "week_id", True),
    ("Fact CRM Messages", "region_code", "Dim Region", "region_code", True),
    ("Fact Sellout", "week_id", "Dim Week", "week_id", True),
    ("Fact Sellout", "store_id", "Dim Store", "store_id", True),
    ("Fact Sellout", "sku", "Dim Product", "sku", True),
    ("Dim Store", "region_code", "Dim Region", "region_code", True),
    ("Fact CX Tickets", "member_id", "Dim Member", "member_id", True),
    ("Fact CX Tickets", "created_week_id", "Dim Week", "week_id", True),
]


def q(name: str) -> str:
    return f"'{name}'" if any(c in name for c in " ()%,.-") else name


def table_tmdl(tname: str, csv: str, cols) -> str:
    L = [f"table {q(tname)}", f"\tlineageTag: {tag('t', tname)}", ""]
    for c, dt, hidden, summ, fmt, sort in cols:
        L.append(f"\tcolumn {c}")
        L.append(f"\t\tdataType: {dt}")
        if hidden:
            L.append("\t\tisHidden")
        if fmt:
            L.append(f"\t\tformatString: {fmt}")
        L.append(f"\t\tlineageTag: {tag('c', tname, c)}")
        L.append(f"\t\tsummarizeBy: {summ}")
        L.append(f"\t\tsourceColumn: {c}")
        if sort:
            L.append(f"\t\tsortByColumn: {sort}")
        L.append("")
    types = ", ".join(f'{{"{c}", {M_TYPE[dt]}}}' for c, dt, *_ in cols)
    L += [
        f"\tpartition {q(tname + '-csv')} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    CsvRaw = Csv.Document(File.Contents("{DATA}\\{csv}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "\t\t\t\t    WithHeaders = Table.PromoteHeaders(CsvRaw, [PromoteAllScalars = true]),",
        f'\t\t\t\t    TypedTable = Table.TransformColumnTypes(WithHeaders, {{{types}}}, "en-US")',
        "\t\t\t\tin",
        "\t\t\t\t    TypedTable",
        "",
    ]
    return "\n".join(L)


def measures_tmdl() -> str:
    L = ["table _Measures", f"\tlineageTag: {tag('t', '_Measures')}", ""]
    for name, expr, fmt, folder, desc in MEASURES:
        L.append(f"\t/// {desc}")
        L.append(f"\tmeasure {q(name)} = {expr}")
        L.append(f"\t\tformatString: {fmt}")
        L.append(f"\t\tdisplayFolder: {folder}")
        L.append(f"\t\tlineageTag: {tag('m', name)}")
        L.append("")
    L += [
        "\tcolumn Placeholder",
        "\t\tdataType: string",
        "\t\tisHidden",
        f"\t\tlineageTag: {tag('c', '_Measures', 'Placeholder')}",
        "\t\tsummarizeBy: none",
        "\t\tsourceColumn: Placeholder",
        "",
        "\tpartition '_Measures-empty' = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        '\t\t\t\t    EmptyTable = #table(type table [Placeholder = text], {})',
        "\t\t\t\tin",
        "\t\t\t\t    EmptyTable",
        "",
    ]
    return "\n".join(L)


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


import sys

if (SM / ".pbi").exists() and "--force" not in sys.argv:
    # Power BI Desktop has saved the project: it now owns the model files (auto date tables, layout).
    sys.exit("Semantic model already saved by Power BI Desktop; rerun with --force to regenerate it.")

d = SM / "definition"
write(SM / "definition.pbism", json.dumps({"version": "4.0", "settings": {}}, indent=2))
write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
order = ["_Measures"] + list(T)
write(
    d / "model.tmdl",
    "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-US\n\n"
    + "\n".join(f"ref table {q(t)}" for t in order) + "\n",
)
(d / "expressions.tmdl").unlink(missing_ok=True)  # no parameter: each table reads its CSV by full path
for tname, (csv, cols) in T.items():
    write(d / "tables" / f"{tname}.tmdl", table_tmdl(tname, csv, cols))
write(d / "tables" / "_Measures.tmdl", measures_tmdl())
rel = []
for ft, fc, tt, tc, active in RELS:
    rel.append(f"relationship {tag('r', ft, fc, tt, tc)}")
    if not active:
        rel.append("\tisActive: false")
    rel.append(f"\tfromColumn: {q(ft)}.{fc}")
    rel.append(f"\ttoColumn: {q(tt)}.{tc}")
    rel.append("")
write(d / "relationships.tmdl", "\n".join(rel))

if (RP / "definition.pbir").exists():
    # Power BI Desktop owns the report files after the first save; never overwrite them.
    print("Report folder exists, left unchanged")
else:
    # Bootstrap only: Desktop rejects this stub on first open, then writes a valid report on save.
    write(RP / "definition.pbir", json.dumps({"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2))
    stub = {"config": json.dumps({"version": "5.59", "activeSectionIndex": 0}), "layoutOptimization": 0, "resourcePackages": [],
            "sections": [{"config": "{}", "displayName": "Page 1", "displayOption": 1, "filters": "[]", "height": 720.0,
                          "name": "Section1", "visualContainers": [], "width": 1280.0}]}
    write(RP / "report.json", json.dumps(stub, indent=2))
write(PB / f"{NAME}.pbip", json.dumps({"version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}}, indent=2))
write(PB / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")

# measures.dax for reading and manual setup
lines = ["// BREWLY commercial dashboard - DAX measures (all live in the _Measures table)", ""]
for name, expr, fmt, folder, desc in MEASURES:
    lines += [f"// [{folder}] {desc}", f"{name} =", "    " + expr, f"// format: {fmt}", ""]
write(PB / "measures.dax", "\n".join(lines))
print("PBIP written to", PB)
