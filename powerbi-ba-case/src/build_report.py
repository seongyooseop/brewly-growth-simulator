"""Write the report pages and visuals (PBIR format) for BREWLY_Commercial.

Run after the project has been opened and saved once in Power BI Desktop
(Desktop then owns report.json, the theme files and the semantic model):
  python powerbi-ba-case/src/build_report.py
Existing pages are replaced; everything else in the report folder is kept.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PAGES = CASE / "powerbi" / "BREWLY_Commercial.Report" / "definition" / "pages"
S_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
S_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
S_VIS = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"
M = "_Measures"


def lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


LABELS = {"iso_year": "Year", "quarter": "Quarter", "region_name": "Region", "week_start": "Week", "partner": "Partner",
          "channel_name": "Channel", "join_cohort": "Join cohort", "months_since_join": "Month", "category": "Category",
          "check_id": "Check", "source_table": "Source", "rule": "Rule", "rows_checked": "Rows checked",
          "rows_failed_before": "Failed before fix", "fix_applied": "Fix applied", "rows_failed_after": "Failed after fix",
          "status": "Status"}


def col(table: str, column: str) -> dict:
    p = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}},
         "queryRef": f"{table}.{column}", "nativeQueryRef": column}
    if column in LABELS:
        p["displayName"] = LABELS[column]
    return p


def mea(name: str) -> dict:
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": M}}, "Property": name}},
            "queryRef": f"{M}.{name}", "nativeQueryRef": name}


def visual(name, vtype, x, y, w, h, roles: dict, title: str | None = None, objects: dict | None = None, z=0):
    v = {"visualType": vtype, "query": {"queryState": {r: {"projections": p} for r, p in roles.items()}},
         "drillFilterOtherVisuals": True}
    if objects:
        v["objects"] = objects
    if title:
        v["visualContainerObjects"] = {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{title}'")}}],
                                       "subTitle": [{"properties": {"show": lit("false")}}]}
    return {"$schema": S_VIS, "name": name,
            "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z}, "visual": v}


def slicer(name, x, y, w, table, column, title):
    return visual(name, "slicer", x, y, w, 75, {"Values": [col(table, column)]},
                  objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]})


def card(name, x, y, w, h, measure):
    # classic card: full numbers with thousand separators instead of auto units
    return visual(name, "card", x, y, w, h, {"Values": [mea(measure)]},
                  objects={"labels": [{"properties": {"labelDisplayUnits": lit("1D"), "fontSize": lit("20D")}}]})


def slicers(prefix, with_quarter=True):
    out = [slicer(f"{prefix}s1", 10, 5, 200, "Dim Week", "iso_year", "Year")]
    if with_quarter:
        out.append(slicer(f"{prefix}s2", 220, 5, 200, "Dim Week", "quarter", "Quarter"))
    out.append(slicer(f"{prefix}s3", 430 if with_quarter else 220, 5, 260, "Dim Region", "region_name", "Region"))
    return out


pages = {
    ("p1overview", "1 Overview"): slicers("p1") + [
        card("p1c1", 10, 85, 307, 105, "Refill Revenue (KRW)"),
        card("p1c2", 327, 85, 307, 105, "Active Members (8w)"),
        card("p1c3", 644, 85, 307, 105, "New Members"),
        card("p1c4", 961, 85, 309, 105, "Retail Net Revenue (KRW)"),
        visual("p1v1", "lineChart", 10, 200, 820, 510,
               {"Category": [col("Dim Week", "week_start")], "Y": [mea("Refill Orders")], "Series": [col("Dim Region", "region_name")]},
               "Weekly refill orders by region"),
        visual("p1v2", "clusteredBarChart", 840, 200, 430, 360,
               {"Category": [col("Dim Store", "partner")], "Y": [mea("Retail Net Revenue (KRW)")]},
               "Partner net sell-out (complete weeks only)"),
        card("p1v3", 840, 570, 430, 140, "Sell-out Store Coverage"),
    ],
    ("p2acquisition", "2 Acquisition"): slicers("p2", with_quarter=False) + [
        visual("p2v1", "columnChart", 10, 85, 625, 385,
               {"Category": [col("Dim Week", "quarter")], "Y": [mea("Acquisition Spend (KRW)")], "Series": [col("Dim Channel", "channel_name")]},
               "Acquisition spend by channel"),
        visual("p2v2", "lineClusteredColumnComboChart", 645, 85, 625, 385,
               {"Category": [col("Dim Week", "quarter")], "Y": [mea("New Members")], "Y2": [mea("Blended CAC (KRW)")]},
               "New members (columns) and blended CAC (line)"),
        visual("p2v3", "tableEx", 10, 480, 1260, 230,
               {"Values": [col("Dim Region", "region_name"), mea("Acquisition Spend (KRW)"), mea("New Members"), mea("Blended CAC (KRW)")]},
               "Blended CAC by region (channel CAC is out of scope: US-07)"),
    ],
    ("p3retention", "3 Retention and CX"): slicers("p3", with_quarter=False) + [
        card("p3c1", 10, 85, 307, 105, "Lapsed Members (12w+)"),
        card("p3c2", 327, 85, 307, 105, "CX SLA Met %"),
        card("p3c3", 644, 85, 307, 105, "Median Resolution Days"),
        card("p3c4", 961, 85, 309, 105, "Tickets per 1,000 Active Members"),
        visual("p3v1", "pivotTable", 10, 200, 640, 510,
               {"Rows": [col("Fact Cohort Retention", "join_cohort")], "Columns": [col("Fact Cohort Retention", "months_since_join")],
                "Values": [mea("Retention %")]},
               "Cohort retention: share ordering n months after joining"),
        visual("p3v2", "clusteredBarChart", 660, 200, 610, 250,
               {"Category": [col("Fact CX Tickets", "category")], "Y": [mea("CX Tickets")]}, "CX tickets by category"),
        visual("p3v3", "tableEx", 660, 460, 610, 250,
               {"Values": [col("Fact CX Tickets", "category"), mea("CX Tickets"), mea("CX SLA Met %"), mea("Median Resolution Days")]},
               "Service level by category (SLA = resolved within 3 days)"),
    ],
    ("p4quality", "4 Data quality"): [
        card("p4c1", 10, 10, 300, 105, "DQ Checks Passed"),
        card("p4c2", 320, 10, 300, 105, "DQ Rows Fixed"),
        visual("p4v1", "tableEx", 10, 125, 1260, 330,
               {"Values": [col("DQ Checks", c) for c in ["check_id", "source_table", "rule", "rows_checked", "rows_failed_before",
                                                          "fix_applied", "rows_failed_after", "status"]]},
               "Data-quality checks run before this refresh"),
        visual("p4v2", "lineChart", 10, 465, 1260, 245,
               {"Category": [col("Dim Week", "week_start")], "Y": [mea("Sell-out Store Coverage")]},
               "Share of partner stores reported each week (below 95% = incomplete)"),
    ],
    ("p5tests", "5 Test sheet"): [
        visual("p5v1", "tableEx", 10, 10, 1260, 175,
               {"Values": [col("Dim Week", "iso_year")] + [mea(n) for n in [
                   "Refill Orders", "Refill Revenue (KRW)", "Active Members (8w)", "New Members", "Acquisition Spend (KRW)"]]},
               "FT-01, FT-02, FT-03, FT-05, FT-06 (compare the 2025 row with tests/expected_values.csv)"),
        visual("p5v2", "tableEx", 10, 195, 1260, 175,
               {"Values": [col("Dim Week", "iso_year")] + [mea(n) for n in [
                   "Retail Net Revenue (KRW)", "Device Return Rate", "CRM Messages Sent", "CX Tickets", "CX SLA Met %"]]},
               "FT-08 to FT-12"),
        visual("p5v3", "tableEx", 10, 380, 940, 330,
               {"Values": [col("Dim Week", "iso_year"), col("Dim Region", "region_name"), mea("Active Members (8w)"),
                           mea("New Members"), mea("Acquisition Spend (KRW)"), mea("Blended CAC (KRW)")]},
               "FT-04 (2025, Seoul metro active members) and FT-07 (2025, Yeongnam blended CAC)"),
        card("p5c1", 960, 380, 310, 160, "Lapsed Members (12w+)"),
    ],
}

if PAGES.exists():
    shutil.rmtree(PAGES)
PAGES.mkdir(parents=True)
for (pname, display), visuals in pages.items():
    pdir = PAGES / pname
    (pdir / "visuals").mkdir(parents=True)
    (pdir / "page.json").write_text(json.dumps(
        {"$schema": S_PAGE, "name": pname, "displayName": display, "displayOption": "FitToPage", "height": 720, "width": 1280},
        indent=2), encoding="utf-8")
    for i, v in enumerate(visuals):
        v["position"]["z"] = i * 1000
        v["position"]["tabOrder"] = i * 1000
        vdir = pdir / "visuals" / v["name"]
        vdir.mkdir()
        (vdir / "visual.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
order = [p for p, _ in pages]
(PAGES / "pages.json").write_text(json.dumps({"$schema": S_PAGES, "pageOrder": order, "activePageName": order[0]}, indent=2), encoding="utf-8")
print(f"{len(order)} pages, {sum(len(v) for v in pages.values())} visuals written to {PAGES}")
