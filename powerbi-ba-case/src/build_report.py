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


def mea(name: str, label: str | None = None) -> dict:
    p = {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": M}}, "Property": name}},
         "queryRef": f"{M}.{name}", "nativeQueryRef": name}
    if label:
        p["displayName"] = label
    return p


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
    v = visual(name, "slicer", x, y, w, 75, {"Values": [col(table, column)]},
               objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]})
    v["visual"]["syncGroup"] = {"groupName": title, "fieldChanges": True, "filterChanges": True}  # same choice on every page
    return v


FULL = lit("1D")  # display units: none (full numbers, no locale suffixes such as "천" or "십억")


def axis_full(secondary: bool = False) -> dict:
    props = {"labelDisplayUnits": FULL}
    if secondary:
        props["secLabelDisplayUnits"] = FULL
    return {"valueAxis": [{"properties": props}]}


def bar_labels() -> dict:
    """Data labels with full numbers and no value axis (bar charts)."""
    return {"labels": [{"properties": {"show": lit("true"), "labelDisplayUnits": FULL}}],
            "valueAxis": [{"properties": {"show": lit("false")}}]}


def gradient(measure: str, low: str, high: str) -> dict:
    """Background colour scale on a table or matrix value column."""
    rule = {"linearGradient2": {"min": {"color": {"Literal": {"Value": f"'{low}'"}}},
                                "max": {"color": {"Literal": {"Value": f"'{high}'"}}},
                                "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}
    fill = {"FillRule": {"Input": mea(measure)["field"], "FillRule": rule}}
    return {"values": [{"properties": {"backColor": {"solid": {"color": {"expr": fill}}}},
                        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"{M}.{measure}"}}]}


def card(name, x, y, w, h, measure, label=None):
    # classic card: full numbers with thousand separators instead of auto units
    return visual(name, "card", x, y, w, h, {"Values": [mea(measure, label)]},
                  objects={"labels": [{"properties": {"labelDisplayUnits": lit("1D"), "fontSize": lit("20D")}}]})


def slicers(prefix, with_quarter=True):
    out = [slicer(f"{prefix}s1", 10, 5, 200, "Dim Week", "iso_year", "Year")]
    if with_quarter:
        out.append(slicer(f"{prefix}s2", 220, 5, 200, "Dim Week", "quarter", "Quarter"))
    out.append(slicer(f"{prefix}s3", 430 if with_quarter else 220, 5, 260, "Dim Region", "region_name", "Region"))
    return out


pages = {
    ("p1overview", "1 Overview"): slicers("p1") + [
        card("p1c1", 10, 85, 307, 105, "Refill Revenue (KRW)", "Refill revenue (KRW), selected period"),
        card("p1c2", 327, 85, 307, 105, "Active Members (8w)", "Active members at end of period"),
        card("p1c3", 644, 85, 307, 105, "New Members", "New members, selected period"),
        card("p1c4", 961, 85, 309, 105, "Retail Net Revenue (KRW)", "Retail net revenue (KRW), selected period"),
        visual("p1v1", "lineChart", 10, 200, 820, 510,
               {"Category": [col("Dim Week", "week_start")], "Y": [mea("Refill Orders")], "Series": [col("Dim Region", "region_name")]},
               "Weekly refill orders by region", objects=axis_full()),
        visual("p1v2", "clusteredBarChart", 840, 200, 430, 360,
               {"Category": [col("Dim Store", "partner")], "Y": [mea("Retail Net Revenue (KRW)", "Net sell-out (KRW)")]},
               "Partner net sell-out, KRW (complete weeks only)", objects=bar_labels()),
        visual("p1v3", "multiRowCard", 840, 570, 430, 140,
               {"Values": [mea("Refill Revenue YoY %", "Refill revenue"), mea("Active Members YoY %", "Active members"),
                           mea("New Members YoY %", "New members"), mea("Retail Net Revenue YoY %", "Retail revenue")]},
               "Year over year (latest year selected vs prior year)"),
    ],
    ("p2acquisition", "2 Acquisition"): slicers("p2", with_quarter=False) + [
        visual("p2v1", "columnChart", 10, 85, 625, 385,
               {"Category": [col("Dim Week", "quarter")], "Y": [mea("Acquisition Spend (KRW)")], "Series": [col("Dim Channel", "channel_name")]},
               "Acquisition spend by channel (KRW)", objects=axis_full()),
        visual("p2v2", "lineClusteredColumnComboChart", 645, 85, 625, 385,
               {"Category": [col("Dim Week", "quarter")], "Y": [mea("New Members")], "Y2": [mea("Blended CAC (KRW)")]},
               "New members (columns) and blended CAC in KRW (line)", objects=axis_full(secondary=True)),
        visual("p2v3", "tableEx", 10, 480, 1260, 230,
               {"Values": [col("Dim Region", "region_name"), mea("Acquisition Spend (KRW)"), mea("New Members"), mea("Blended CAC (KRW)")]},
               "Blended CAC by region (channel CAC is out of scope: US-07)"),
    ],
    ("p3retention", "3 Retention and CX"): slicers("p3", with_quarter=False) + [
        card("p3c1", 10, 85, 244, 105, "Lapsed Members (12w+)"),
        card("p3c2", 264, 85, 244, 105, "CX SLA Met %"),
        card("p3c5", 518, 85, 244, 105, "CX SLA Gap vs Target"),
        card("p3c3", 772, 85, 244, 105, "Median Resolution Days"),
        card("p3c4", 1026, 85, 244, 105, "Tickets per 1,000 Active Members"),
        visual("p3v1", "pivotTable", 10, 200, 640, 510,
               {"Rows": [col("Fact Cohort Retention", "join_cohort")], "Columns": [col("Fact Cohort Retention", "months_since_join")],
                "Values": [mea("Retention %")]},
               "Cohort retention: share ordering n months after joining", objects=gradient("Retention %", "#F7F1E8", "#8FC5AF")),
        visual("p3v2", "clusteredBarChart", 660, 200, 610, 245,
               {"Category": [col("Fact CX Tickets", "category")], "Y": [mea("CX Tickets")]}, "CX tickets by category", objects=bar_labels()),
        visual("p3v3", "tableEx", 660, 455, 610, 255,
               {"Values": [col("Fact CX Tickets", "category"), mea("CX Tickets"), mea("CX SLA Met %"), mea("Median Resolution Days")]},
               "Service level by category (SLA = resolved within 3 days, target 85%)", objects=gradient("CX SLA Met %", "#EBA79D", "#A9D6C3")),
    ],
    ("p4quality", "4 Data quality"): [
        card("p4c1", 10, 10, 300, 105, "DQ Checks Passed"),
        card("p4c2", 320, 10, 300, 105, "DQ Rows Fixed"),
        visual("p4v1", "tableEx", 10, 125, 1260, 330,
               {"Values": [col("DQ Checks", c) for c in ["check_id", "source_table", "rows_failed_before", "rows_failed_after", "status",
                                                          "rows_checked", "rule", "fix_applied"]]},
               "Data-quality checks run before this refresh"),
        visual("p4v2", "lineChart", 10, 465, 1260, 245,
               {"Category": [col("Dim Week", "week_start")], "Y": [mea("Sell-out Store Coverage")]},
               "Share of partner stores reported each week (below 95% = incomplete)", objects=axis_full()),
    ],
    ("p5tests", "5 Test sheet (QA)"): [
        visual("p5v1", "tableEx", 10, 10, 1260, 200,
               {"Values": [col("Dim Week", "iso_year")] + [mea(n) for n in [
                   "Refill Orders", "Refill Revenue (KRW)", "Active Members (8w)", "New Members", "Acquisition Spend (KRW)"]]},
               "FT-01, FT-02, FT-03, FT-05, FT-06 (compare the 2025 row with tests/expected_values.csv)"),
        visual("p5v2", "tableEx", 10, 215, 1260, 200,
               {"Values": [col("Dim Week", "iso_year")] + [mea(n) for n in [
                   "Retail Net Revenue (KRW)", "Device Return Rate", "CRM Messages Sent", "CX Tickets", "CX SLA Met %"]]},
               "FT-08 to FT-12"),
        visual("p5v3", "tableEx", 10, 420, 620, 290,
               {"Values": [col("Dim Week", "iso_year"), col("Dim Region", "region_name"), mea("Active Members (8w)", "Active members"),
                           mea("New Members", "New members"), mea("Blended CAC (KRW)", "Blended CAC")]},
               "FT-04 (2025, Seoul metro) and FT-07 (2025, Yeongnam)"),
        visual("p5v4", "tableEx", 640, 420, 630, 190,
               {"Values": [col("Dim Week", "iso_year"), mea("Refill Revenue YoY %", "Revenue YoY"), mea("Active Members YoY %", "Active YoY"),
                           mea("New Members YoY %", "New YoY"), mea("Retail Net Revenue YoY %", "Retail YoY"), mea("CX SLA Gap vs Target", "SLA gap")]},
               "FT-15 to FT-19 (2025 row; 2024 is blank: no 2023 data)"),
        card("p5c1", 640, 615, 300, 95, "Lapsed Members (12w+)"),
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

# BREWLY theme on top of the base theme (registered resource, as Power BI Desktop stores an imported theme)
REPORT = PAGES.parent / "report.json"
THEME_SRC = CASE / "powerbi" / "brewly_theme.json"
res = PAGES.parents[1] / "StaticResources" / "RegisteredResources"
res.mkdir(parents=True, exist_ok=True)
shutil.copyfile(THEME_SRC, res / "brewly_theme.json")
rj = json.loads(REPORT.read_text(encoding="utf-8"))
base = rj["themeCollection"]["baseTheme"]
rj["themeCollection"]["customTheme"] = {"name": "brewly_theme.json", "reportVersionAtImport": base["reportVersionAtImport"], "type": "RegisteredResources"}
rj["resourcePackages"] = [r for r in rj.get("resourcePackages", []) if r["type"] != "RegisteredResources"] + [
    {"name": "RegisteredResources", "type": "RegisteredResources",
     "items": [{"name": "brewly_theme.json", "path": "brewly_theme.json", "type": "CustomTheme"}]}]
REPORT.write_text(json.dumps(rj, indent=2), encoding="utf-8")
(PAGES / "pages.json").write_text(json.dumps({"$schema": S_PAGES, "pageOrder": order, "activePageName": order[0]}, indent=2), encoding="utf-8")
print(f"{len(order)} pages, {sum(len(v) for v in pages.values())} visuals written to {PAGES}")
