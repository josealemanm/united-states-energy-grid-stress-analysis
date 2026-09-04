"""
08_build_powerbi_report.py
Writes powerbi/grid_stress.Report: the six report pages, their layout and the
theme file they all read from.

Run:  python src/08_build_powerbi_report.py      (or: make powerbi)

    WARNING -- this OVERWRITES powerbi/grid_stress.Report. If you have moved
    visuals around inside Power BI Desktop and saved, running this throws that
    away. Pick one place to edit and stay there: either the numbers in this
    file, or Desktop. See docs/POWERBI_WINDOWS_GUIDE.md, "Changing the layout".

The semantic model (powerbi/grid_stress.SemanticModel) is NOT touched by this
script. Measures and relationships are edited there, or in Desktop.
"""
import json
import pathlib
import shutil
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from powerbi_theme import (build_theme, NAVY, INK, SLATE, LINE, PAGEBG, CARD,
                           STRIPBG, HEADER_SUB, RED, FONT, FONT_BOLD,
                           PT_VISUAL_TITLE, PT_KPI_LABEL, PT_KPI_VALUE,
                           PT_BODY, PT_HEADER_TITLE, PT_HEADER_EYEBROW, PT_FOOTER)

# ===========================================================================
# EDIT THE LAYOUT HERE
# ===========================================================================
CANVAS_W, CANVAS_H = 1280, 720

MARGIN = 20        # page edge to the first visual
GUTTER = 12        # gap between visuals, across and down
HEADER_H = 64      # navy band at the top
STRIP_H = 52       # slicer row; pages with no slicers skip it entirely
FOOTER_H = 28      # grey band at the bottom

# Row heights for each page, top to bottom. Exactly one row per page may be
# "auto", which takes whatever height is left. The script checks the sums and
# tells you which page is wrong if they do not fit.
ROW_HEIGHTS = {
    "summary":     [96, "auto", 168],
    "anatomy":     ["auto", 268],
    "skill":       [96, "auto", 168],
    "deepdive":    [96, "auto", 214],
    "twolenses":   ["auto", 268],
    "methodology": [268, "auto"],
}

# How each row is divided across the width, as relative weights.
# [3, 2] means the first visual takes three fifths and the second two fifths.
COLUMN_WEIGHTS = {
    "summary":     [[1, 1, 1, 1, 1], [3, 2], [2, 3]],
    "anatomy":     [[1, 1], [1, 1, 1]],
    "skill":       [[1, 1, 1, 1], [3, 2], [1, 1]],
    "deepdive":    [[1, 1, 1, 1], [2, 1], [2, 1]],
    "twolenses":   [[1, 1], [2, 1]],
    "methodology": [[1, 1, 1], [2, 1]],
}

# Which pages carry a slicer strip. Pages that do not start their content
# higher up rather than leaving a 52px gap.
PAGES_WITH_SLICERS = {"summary", "anatomy", "skill", "deepdive"}

# ===========================================================================

NS = uuid.UUID("6f2a1c30-9d44-4d55-9d0b-1f4c2a7b8e02")
def gid(s): return uuid.uuid5(NS, s).hex

ROOT = pathlib.Path("powerbi/grid_stress.Report")
DEF = ROOT / "definition"
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
THEME_FILE = "gridStressTheme.json"
MEAS = "_Measures"

FOOTER_Y = CANVAS_H - FOOTER_H
STRIP_Y = HEADER_H + 8


def content_top(page):
    return (STRIP_Y + STRIP_H + GUTTER) if page in PAGES_WITH_SLICERS else STRIP_Y


class Grid:
    """Turns the tables above into pixel boxes, and complains if they do not fit."""

    def __init__(self, page):
        self.page = page
        top = content_top(page)
        avail = (FOOTER_Y - GUTTER) - top
        heights = list(ROW_HEIGHTS[page])
        fixed = sum(h for h in heights if h != "auto")
        autos = [i for i, h in enumerate(heights) if h == "auto"]
        if len(autos) > 1:
            raise SystemExit(f"page '{page}': only one row may be \"auto\"")
        spare = avail - fixed - GUTTER * (len(heights) - 1)
        if autos:
            if spare < 60:
                raise SystemExit(
                    f"page '{page}': fixed rows total {fixed}px, leaving {spare}px "
                    f"for the auto row. Reduce a height in ROW_HEIGHTS.")
            heights[autos[0]] = spare
        elif spare != 0:
            raise SystemExit(
                f"page '{page}': rows total {fixed}px but {avail - GUTTER * (len(heights) - 1)}px "
                f"is available. Change a height in ROW_HEIGHTS, or make one row \"auto\".")
        self.rows = []
        y = top
        for h in heights:
            self.rows.append((y, h))
            y += h + GUTTER

    def box(self, r, c):
        y, h = self.rows[r]
        weights = COLUMN_WEIGHTS[self.page][r]
        total = CANVAS_W - 2 * MARGIN
        avail = total - GUTTER * (len(weights) - 1)
        x = MARGIN
        for i, wt in enumerate(weights):
            w = round(avail * wt / sum(weights)) if i < len(weights) - 1 else (MARGIN + total) - x
            if i == c:
                return (x, y, w, h)
            x += w + GUTTER
        raise IndexError(f"page '{self.page}' row {r} has no column {c}")


# ---------------------------------------------------------- expressions ----
def col(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}

def measure(prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MEAS}}, "Property": prop}}

AGG = {"Sum": 0, "Avg": 1, "Min": 2, "Max": 3, "Count": 4}

def proj(field, ref, native=None, display=None):
    p = {"field": field, "queryRef": ref}
    if native: p["nativeQueryRef"] = native
    if display: p["displayName"] = display
    return p

def C(entity, prop, display=None):
    return proj(col(entity, prop), f"{entity}.{prop}", prop, display)

def Mm(prop, display=None):
    return proj(measure(prop), f"{MEAS}.{prop}", prop, display)

def A(entity, prop, func="Avg", display=None):
    return proj({"Aggregation": {"Expression": col(entity, prop), "Function": AGG[func]}},
                f"{func}({entity}.{prop})", f"{func} of {prop}", display)


# ---------------------------------------------------------- formatting -----
def lit(v): return {"expr": {"Literal": {"Value": v}}}
def slit(s): return lit("'" + str(s).replace("'", "''") + "'")
def num(v): return lit(f"{v}D")
def fill(c): return {"solid": {"color": slit(c)}}


def chrome(title=None, bg=CARD, border=True, pad=None, title_pt=PT_VISUAL_TITLE,
           title_colour=NAVY, radius=4, alt=None):
    o = {"background": [{"properties": {"show": lit("true"), "color": fill(bg),
                                        "transparency": num(0)}}],
         "border": [{"properties": {"show": lit("true" if border else "false"),
                                    "color": fill(LINE), "radius": num(radius)}}]}
    if pad:
        t, r, b, l = pad
        o["padding"] = [{"properties": {"top": num(t), "right": num(r),
                                        "bottom": num(b), "left": num(l)}}]
    if alt or title:
        o["general"] = [{"properties": {"altText": slit(alt or title)}}]
    if title is not None:
        o["title"] = [{"properties": {
            "show": lit("true"), "text": slit(title), "fontSize": num(title_pt),
            "fontColor": fill(title_colour), "fontFamily": slit(FONT_BOLD),
            "alignment": slit("left"), "titleWrap": lit("true"),
            "heading": slit("None")}}]
    return o


def para(text, pt, color=INK, bold=False, align="left"):
    style = {"fontSize": f"{pt}pt", "fontFamily": FONT, "color": color}
    if bold:
        style["fontWeight"] = "bold"
    return {"horizontalTextAlignment": align,
            "textRuns": [{"value": text, "textStyle": style}]}


# ---------------------------------------------------------- containers -----
def visual(name, box, vtype, query=None, objects=None, vcobjects=None,
           filter_config=None, z=0, sort=None):
    x, y, w, h = box
    v = {"visualType": vtype}
    if query is not None:
        v["query"] = {"queryState": query}
        if sort:
            v["query"]["sortDefinition"] = sort
    if objects: v["objects"] = objects
    if vcobjects: v["visualContainerObjects"] = vcobjects
    v["drillFilterOtherVisuals"] = True
    c = {"$schema": f"{SCH}/visualContainer/1.0.0/schema.json", "name": name,
         "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
         "visual": v}
    if filter_config:
        c["filterConfig"] = filter_config
    return c


def textpanel(name, box, blocks, z=0, bg=CARD, border=True,
              pad=(12, 14, 12, 14), radius=4):
    t, r, b, l = pad
    alt = " ".join(run["value"] for blk in blocks for run in blk["textRuns"])[:300]
    vc = {"background": [{"properties": {"show": lit("true"), "color": fill(bg),
                                         "transparency": num(0)}}],
          "border": [{"properties": {"show": lit("true" if border else "false"),
                                     "color": fill(LINE), "radius": num(radius)}}],
          "padding": [{"properties": {"top": num(t), "right": num(r),
                                      "bottom": num(b), "left": num(l)}}],
          "general": [{"properties": {"altText": slit(alt)}}]}
    return visual(name, box, "textbox",
                  objects={"general": [{"properties": {"paragraphs": blocks}}]},
                  vcobjects=vc, z=z)


def card(name, box, measure_name, label, unit, z=0):
    """Label above, number, unit underneath. The unit rides on the field's
    display name because that is what renders below the value."""
    objs = {"labels": [{"properties": {"fontSize": num(PT_KPI_VALUE), "color": fill(NAVY)}}],
            "categoryLabels": [{"properties": {"show": lit("true"), "fontSize": num(8),
                                               "color": fill(SLATE)}}]}
    return visual(name, box, "card",
                  query={"Values": {"projections": [Mm(measure_name, unit)]}},
                  objects=objs,
                  vcobjects=chrome(title=label, title_pt=PT_KPI_LABEL,
                                   title_colour=SLATE, pad=(8, 12, 8, 12),
                                   alt=f"{label}: {measure_name}, {unit}"),
                  z=z)


def table(name, box, projections, title, z=0, sort=None):
    return visual(name, box, "tableEx",
                  query={"Values": {"projections": projections}},
                  vcobjects=chrome(title=title), z=z, sort=sort)


def chart(name, box, vtype, cat, ys, title, series=None, objects=None, z=0, sort=None):
    q = {"Category": {"projections": cat}, "Y": {"projections": ys}}
    if series:
        q["Series"] = {"projections": series}
    o = dict(objects or {})
    o.setdefault("legend", [{"properties": {
        "show": lit("true" if (len(ys) > 1 or series) else "false"),
        "position": slit("TopLeft"), "showTitle": lit("false"),
        "fontSize": num(9), "labelColor": fill(SLATE)}}])
    return visual(name, box, vtype, query=q, objects=o,
                  vcobjects=chrome(title=title), z=z, sort=sort)


def slicer(name, box, field_proj, label, mode="Dropdown", z=0):
    return visual(name, box, "slicer",
                  query={"Values": {"projections": [field_proj]}},
                  objects={"data": [{"properties": {"mode": slit(mode)}}],
                           "header": [{"properties": {"show": lit("false")}}]},
                  vcobjects=chrome(title=label, title_pt=PT_KPI_LABEL,
                                   title_colour=SLATE, pad=(5, 10, 5, 10)),
                  z=z)


def sort_by(field_proj, direction="Descending"):
    return {"sort": [{"field": field_proj["field"], "direction": direction}],
            "isDefaultSort": True}


def zero_line(label="Zero"):
    return {"y1AxisReferenceLine": [{"selector": {"id": "zeroLine"}, "properties": {
        "show": lit("true"), "value": slit("0"), "lineColor": fill(RED),
        "style": slit("dashed"), "transparency": num(25),
        "displayName": slit(label)}}]}


def axis_titles():
    return {"categoryAxis": [{"properties": {"showAxisTitle": lit("true")}}],
            "valueAxis": [{"properties": {"showAxisTitle": lit("true")}}]}


# ------------------------------------------------------------- filters -----
def cat_filter(fname, entity, prop, values, source="s"):
    return {"name": fname, "field": col(entity, prop), "type": "Categorical",
            "filter": {"Version": 2,
                       "From": [{"Name": source, "Entity": entity, "Type": 0}],
                       "Where": [{"Condition": {"In": {
                           "Expressions": [{"Column": {
                               "Expression": {"SourceRef": {"Source": source}},
                               "Property": prop}}],
                           "Values": [[{"Literal": {"Value": "'" + v + "'"}}]
                                      for v in values]}}}]},
            "howCreated": "User"}


def date_between_filter(fname, entity, prop, lo, hi, source="d"):
    ref = {"Column": {"Expression": {"SourceRef": {"Source": source}}, "Property": prop}}
    def dl(s): return {"Literal": {"Value": f"datetime'{s}'"}}
    return {"name": fname, "field": col(entity, prop), "type": "Advanced",
            "filter": {"Version": 2,
                       "From": [{"Name": source, "Entity": entity, "Type": 0}],
                       "Where": [{"Condition": {"And": {
                           "Left": {"Comparison": {"ComparisonKind": 2, "Left": ref, "Right": dl(lo)}},
                           "Right": {"Comparison": {"ComparisonKind": 4, "Left": ref, "Right": dl(hi)}}}}}]},
            "howCreated": "User"}


# --------------------------------------------------------------- chrome ----
META = "EIA-930  ·  8 balancing authorities  ·  Sep 2024 – Sep 2026  ·  139,055 BA-hours"
SOURCE = "Source: U.S. EIA, Form EIA-930 API v2, pulled 2 September 2026."


def header(page_title):
    return [
        textpanel("hdrL", (0, 0, 880, HEADER_H), [
            para("GRID STRESS DASHBOARD", PT_HEADER_EYEBROW, HEADER_SUB, bold=True),
            para(page_title, PT_HEADER_TITLE, "#FFFFFF", bold=True),
        ], z=90, bg=NAVY, border=False, pad=(9, 12, 8, 32), radius=0),
        textpanel("hdrR", (880, 0, 400, HEADER_H), [
            para(META, 8.0, HEADER_SUB, align="right"),
        ], z=90, bg=NAVY, border=False, pad=(24, 32, 8, 10), radius=0),
    ]


def footer(page_no):
    return [
        textpanel("ftrL", (0, FOOTER_Y, 940, FOOTER_H), [para(SOURCE, PT_FOOTER, SLATE)],
                  z=90, bg=STRIPBG, border=False, pad=(7, 8, 6, 32), radius=0),
        textpanel("ftrR", (940, FOOTER_Y, 340, FOOTER_H),
                  [para(f"Page {page_no} of 6", PT_FOOTER, SLATE, align="right")],
                  z=90, bg=STRIPBG, border=False, pad=(7, 32, 6, 8), radius=0),
    ]


def slicer_row(specs):
    """specs: list of (name, projection, label, weight)."""
    total = CANVAS_W - 2 * MARGIN
    weights = [s[3] for s in specs]
    avail = total - GUTTER * (len(weights) - 1)
    out, x = [], MARGIN
    for i, (name, pr, label, wt) in enumerate(specs):
        # Last one absorbs the rounding so the row ends exactly on the margin.
        w = (round(avail * wt / sum(weights)) if i < len(specs) - 1
             else (MARGIN + total) - x)
        out.append(slicer(name, (x, STRIP_Y, w, STRIP_H), pr, label, z=6 + i))
        x += w + GUTTER
    return out


# ================================================================ PAGES ====
pages = []

# --------------------------------------------------------------- PAGE 1 ----
g = Grid("summary")
p1 = header("Forecast error at stress hours, by region") + footer(1)
p1 += slicer_row([
    ("p1sRegion", C("dim_ba", "ba_name", "Region"), "REGION", 1),
    ("p1sSeason", C("dim_date", "season", "Season"), "SEASON", 1),
    ("p1sPrice", C("Price per MWh", "Price per MWh", "Price"), "PRICE ($/MWh)", 1),
])
kpis = [("MAPE Normal (%)", "ERROR, NORMAL HOURS", "Mean absolute % error"),
        ("MAPE Stress (%)", "ERROR, STRESS HOURS", "Mean absolute % error"),
        ("Stress Penalty (pp)", "STRESS PENALTY", "Percentage points"),
        ("Skill Normal", "SKILL VS PERSISTENCE", "Share of baseline error removed"),
        ("Stress Shortfall Upper Bound ($M)", "SHORTFALL UPPER BOUND", "$m at the slider price")]
for i, (m, label, unit) in enumerate(kpis):
    p1.append(card(f"p1k{i+1}", g.box(0, i), m, label, unit, z=10 + i))
p1 += [
    chart("p1hero", g.box(1, 0), "clusteredColumnChart", [C("dim_ba", "ba_code")],
          [Mm("MAPE Normal (%)"), Mm("MAPE Stress (%)")],
          "Mean absolute % error by region, normal and stress hours", z=20),
    table("p1table", g.box(1, 1),
          [C("dim_ba", "ba_name", "Region"),
           Mm("Penalty With Interval", "Penalty (95% CI)"),
           Mm("Is Significant", "Verdict")],
          "Stress penalty by region, with 95% interval", z=21,
          sort=sort_by(Mm("Stress Penalty (pp)"))),
    chart("p1scatter", g.box(2, 0), "scatterChart", [C("dim_ba", "ba_code")],
          [Mm("Stress Penalty (pp)")],
          "Stress penalty against net imports at peak",
          objects={**zero_line("No effect"), **axis_titles()}, z=22),
    table("p1table2", g.box(2, 1),
          [C("dim_ba", "ba_name", "Region"),
           Mm("MAPE Normal (%)", "Normal (%)"),
           Mm("MAPE Stress (%)", "Stress (%)"),
           Mm("Stress Multiple", "Multiple"),
           Mm("Net Import at Stress (MW)", "Net imports at peak (MW)"),
           Mm("Stress Shortfall (MWh)", "Stress shortfall (MWh)")],
          "Error, multiple, imports and shortfall by region", z=23,
          sort=sort_by(Mm("Stress Penalty (pp)"))),
]
p1[-2]["visual"]["query"]["queryState"]["X"] = {
    "projections": [Mm("Net Import at Stress (MW)")]}
pages.append(("summary", "1 Summary", p1, None))

# --------------------------------------------------------------- PAGE 2 ----
g = Grid("anatomy")
p2 = header("Anatomy of the forecast error") + footer(2)
p2 += slicer_row([
    ("p2sRegion", C("dim_ba", "ba_name", "Region"), "REGION", 1),
    ("p2sSeason", C("dim_date", "season", "Season"), "SEASON", 1),
    ("p2sFuel", C("dim_date", "year", "Year"), "YEAR", 1),
])
p2 += [
    chart("p2hour", g.box(0, 0), "lineChart", [C("fact_grid_hourly", "hour_local")],
          [Mm("MAPE Normal (%)"), Mm("MAPE Stress (%)")],
          "Mean absolute % error by hour of the local day", z=10),
    chart("p2month", g.box(0, 1), "columnChart", [C("dim_date", "year_month")],
          [Mm("MAPE (%)")], "Mean absolute % error by month", z=11),
    chart("p2hist", g.box(1, 0), "columnChart", [C("fact_grid_hourly", "pct_error_bin")],
          [Mm("Hours Analyzed")],
          "Hours by signed error, one percentage point per bucket", z=12),
    chart("p2bias", g.box(1, 1), "clusteredColumnChart", [C("dim_ba", "ba_code")],
          [Mm("Forecast Bias (%)")], "Mean signed error by region",
          objects=zero_line("Unbiased"), z=13,
          sort=sort_by(Mm("Forecast Bias (%)"))),
    table("p2biastable", g.box(1, 2),
          [C("dim_ba", "ba_code", "Region"),
           Mm("Forecast Bias (%)", "Bias (pp)"),
           Mm("Bias Share of Error", "Share one-directional"),
           Mm("Hours Forecast Ran High (%)", "Hours running high")],
          "Forecast bias by region", z=14,
          sort=sort_by(Mm("Bias Share of Error"))),
]
pages.append(("anatomy", "2 Anatomy", p2, None))

# --------------------------------------------------------------- PAGE 3 ----
g = Grid("skill")
p3 = header("Forecast skill against a naive baseline") + footer(3)
p3 += slicer_row([
    ("p3sRegion", C("dim_ba", "ba_name", "Region"), "REGION", 1),
    ("p3sSeason", C("dim_date", "season", "Season"), "SEASON", 1),
])
for i, (m, label, unit) in enumerate([
        ("Skill Normal", "SKILL, NORMAL HOURS", "Share of baseline error removed"),
        ("Skill Stress", "SKILL, STRESS HOURS", "Share of baseline error removed"),
        ("MAPE (%)", "DAY-AHEAD ERROR", "Mean absolute % error"),
        ("MAPE Persistence (%)", "PERSISTENCE ERROR", "Yesterday, same hour")]):
    p3.append(card(f"p3k{i+1}", g.box(0, i), m, label, unit, z=10 + i))
p3 += [
    chart("p3hero", g.box(1, 0), "clusteredColumnChart", [C("dim_ba", "ba_code")],
          [Mm("Skill Normal"), Mm("Skill Stress")],
          "Skill against 24-hour persistence by region, normal and stress hours",
          objects=zero_line("Break-even"), z=20,
          sort=sort_by(Mm("Skill Normal"), "Ascending")),
    table("p3table", g.box(1, 1),
          [C("dim_ba", "ba_code", "Region"),
           Mm("Skill Normal", "Skill, normal"),
           Mm("Skill Stress", "Skill, stress"),
           Mm("MAPE (%)", "MAPE (%)"),
           Mm("MAPE Clean (%)", "MAPE, clean hours (%)")],
          "Skill and error by region", z=21,
          sort=sort_by(Mm("Skill Normal"), "Ascending")),
    chart("p3persist", g.box(2, 0), "clusteredColumnChart", [C("dim_ba", "ba_code")],
          [Mm("MAPE (%)"), Mm("MAPE Persistence (%)")],
          "Day-ahead error against persistence error, by region", z=22,
          sort=sort_by(Mm("MAPE (%)"))),
    chart("p3hour", g.box(2, 1), "lineChart", [C("fact_grid_hourly", "hour_local")],
          [Mm("Skill vs Persistence")],
          "Skill by hour of the local day",
          objects=zero_line("Break-even"), z=23),
]
pages.append(("skill", "3 Skill", p3, None))

# --------------------------------------------------------------- PAGE 4 ----
g = Grid("deepdive")
p4 = header("PJM, week of 20 June 2025") + footer(4)
p4 += slicer_row([
    ("p4sFuel", C("dim_fuel", "fuel_group", "Fuel group"), "FUEL GROUP", 1),
    ("p4sDay", C("dim_date", "day_name", "Day"), "DAY", 1),
])
for i, (m, label, unit) in enumerate([
        ("Peak Demand (MW)", "PEAK DEMAND", "Highest hour in view"),
        ("MAPE (%)", "AVERAGE ERROR", "Mean absolute % error"),
        ("Shortfall (MWh)", "UNDER-FORECAST", "MWh below actual"),
        ("Hours Analyzed", "HOURS", "BA-hours in view")]):
    p4.append(card(f"p4k{i+1}", g.box(0, i), m, label, unit, z=10 + i))
p4 += [
    chart("p4load", g.box(1, 0), "lineChart", [C("fact_grid_hourly", "ts_local")],
          [A("fact_grid_hourly", "demand_mw", "Avg", "Demand"),
           A("fact_grid_hourly", "forecast_mw", "Avg", "Day-ahead forecast")],
          "Demand and day-ahead forecast, MW", z=20),
    chart("p4err", g.box(1, 1), "areaChart", [C("fact_grid_hourly", "ts_local")],
          [A("fact_grid_hourly", "forecast_error_mw", "Avg", "Forecast minus actual")],
          "Forecast minus actual, MW", objects=zero_line("Exact"), z=21),
    chart("p4fuel", g.box(2, 0), "stackedAreaChart", [C("fact_fuel_hourly", "ts_local")],
          [A("fact_fuel_hourly", "generation_mw", "Sum", "Generation")],
          "Generation by fuel, MW", series=[C("dim_fuel", "fuel_name")], z=22),
    chart("p4imp", g.box(2, 1), "lineChart", [C("fact_grid_hourly", "ts_local")],
          [A("fact_grid_hourly", "net_import_mw", "Avg", "Net imports")],
          "Net imports, MW", objects=zero_line("Self-sufficient"), z=23),
]
pages.append(("deepdive", "4 Deep Dive", p4, {"filters": [
    cat_filter(gid("p4ba"), "dim_ba", "ba_code", ["PJM"]),
    date_between_filter(gid("p4daterange"), "dim_date", "date_key",
                        "2025-06-20T00:00:00", "2025-06-27T00:00:00")]}))

# --------------------------------------------------------------- PAGE 5 ----
g = Grid("twolenses")
p5 = header("Demand stress and ramp stress compared") + footer(5)
p5 += [
    chart("p5bars", g.box(0, 0), "clusteredBarChart", [C("dim_ba", "ba_code")],
          [Mm("Stress Penalty (pp)"), Mm("Ramp Stress Penalty (pp)")],
          "Stress penalty by region, both definitions",
          objects=zero_line("No effect"), z=10,
          sort=sort_by(Mm("Ramp Stress Penalty (pp)"))),
    table("p5table", g.box(0, 1),
          [C("dim_ba", "ba_name", "Region"),
           Mm("Penalty With Interval", "Demand stress (95% CI)"),
           Mm("Ramp Penalty With Interval", "Ramp stress (95% CI)"),
           A("analysis_ramp_stress_penalty", "pct_overlap_with_demand_stress", "Avg",
             "Hours shared (%)")],
          "Stress penalty by region and definition, with 95% intervals", z=11,
          sort=sort_by(Mm("Ramp Stress Penalty (pp)"))),
    chart("p5ramp", g.box(1, 0), "clusteredColumnChart", [C("dim_ba", "ba_code")],
          [Mm("MAPE Ramp Normal (%)"), Mm("MAPE Ramp Stress (%)")],
          "Mean absolute % error by region, normal and ramp-stress hours", z=12,
          sort=sort_by(Mm("Ramp Stress Penalty (pp)"))),
    chart("p5overlap", g.box(1, 1), "columnChart", [C("dim_ba", "ba_code")],
          [A("analysis_ramp_stress_penalty", "pct_overlap_with_demand_stress", "Avg",
             "Hours shared (%)")],
          "Share of ramp-stress hours that are also demand-stress hours", z=13,
          sort=sort_by(A("analysis_ramp_stress_penalty",
                         "pct_overlap_with_demand_stress", "Avg"))),
]
pages.append(("twolenses", "5 Two Lenses", p5, None))

# --------------------------------------------------------------- PAGE 6 ----
g = Grid("methodology")
p6 = header("Method and limitations") + footer(6)
p6 += [
    textpanel("p6def", g.box(0, 0), [
        para("Stress hour", 10.5, NAVY, bold=True),
        para("Top 5% of demand for that balancing authority, within that season. "
             "Percentile within region, so a small grid is not compared to ERCOT on raw "
             "megawatts. Within season, so a summer-peaking and a winter-peaking region "
             "are not compared on climate. 6,961 stress hours across the eight regions.",
             PT_BODY, INK),
        para("Ramp stress hour", 10.5, NAVY, bold=True),
        para("Top 5% of absolute hour-over-hour change in net load, where net load is "
             "demand minus solar and wind. Overlaps demand-stress hours by 5 to 12%.",
             PT_BODY, INK),
    ], z=10),
    textpanel("p6dec", g.box(0, 1), [
        para("Excluded hours", 10.5, NAVY, bold=True),
        para("1,113 of 140,168 hours, under 1%.", PT_BODY, INK),
        para("Hours missing demand, forecast, net generation or interchange: excluded, "
             "not interpolated.", PT_BODY, INK),
        para("92 New York ISO hours reporting a day-ahead forecast of exactly zero: "
             "dropped, as the form requires a positive value.", PT_BODY, INK),
        para("Balance-identity failures and one day of implausible SWPP forecasts "
             "(16 April 2026): reported, not corrected.", PT_BODY, INK),
    ], z=11),
    textpanel("p6lim", g.box(0, 2), [
        para("Limitations", 10.5, NAVY, bold=True),
        para("MISO and SWPP each span more than one time zone and are assigned a single "
             "local zone.", PT_BODY, INK),
        para("Raw EIA series, not the adjusted series.", PT_BODY, INK),
        para("The price band is a sourced assumption. The dollar figure is an upper "
             "bound: it assumes every under-forecast megawatt is bought at that price.",
             PT_BODY, INK),
        para("24 months is a short window for weather-driven conclusions.", PT_BODY, INK),
    ], z=12),
    table("p6table", g.box(1, 0),
          [C("dim_ba", "ba_name", "Region"),
           Mm("Avg Abs Imbalance (%)", "Mean |imbalance| (%)"),
           Mm("Hours Failing Balance Check", "Hours failing"),
           Mm("MAPE (%)", "MAPE, all hours (%)"),
           Mm("MAPE Clean (%)", "MAPE, hours that balance (%)")],
          "Balance-identity check by region", z=13,
          sort=sort_by(Mm("Avg Abs Imbalance (%)"))),
    textpanel("p6ci", g.box(1, 1), [
        para("Confidence intervals", 10.5, NAVY, bold=True),
        para("95% block bootstrap, 2,000 resamples drawn by calendar day rather than by "
             "hour. Errors within a day are autocorrelated, so an hourly bootstrap would "
             "treat 24 correlated errors as 24 independent draws and report intervals "
             "that are too tight.", PT_BODY, INK),
        para("Source: U.S. Energy Information Administration, Form EIA-930, API v2. "
             "Pulled 2 September 2026. Code and data: "
             "github.com/josealemanm/grid-stress-dashboard", 8.5, SLATE),
    ], z=14),
]
pages.append(("methodology", "6 Methodology", p6, None))


# ================================================================ WRITE ====
def write_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def main():
    if ROOT.exists():
        shutil.rmtree(ROOT)

    write_json(ROOT / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "grid_stress"},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid5(NS, "logical:report"))}})

    write_json(ROOT / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../grid_stress.SemanticModel"}}})

    write_json(ROOT / "StaticResources" / "RegisteredResources" / THEME_FILE, build_theme())

    write_json(DEF / "report.json", {
        "$schema": f"{SCH}/report/1.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.61",
                          "type": "SharedResources"},
            "customTheme": {"name": THEME_FILE, "reportVersionAtImport": "5.61",
                            "type": "RegisteredResources"}},
        "layoutOptimization": "None",
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": THEME_FILE, "path": THEME_FILE,
                                         "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True,
                     "defaultFilterActionIsDataFilter": True}})

    write_json(DEF / "version.json", {
        "$schema": f"{SCH}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})

    write_json(DEF / "pages" / "pages.json", {
        "$schema": f"{SCH}/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p[0] for p in pages],
        "activePageName": pages[0][0]})

    for name, display, visuals, filter_config in pages:
        page = {"$schema": f"{SCH}/page/1.0.0/schema.json", "name": name,
                "displayName": display, "displayOption": "FitToPage",
                "height": CANVAS_H, "width": CANVAS_W}
        if filter_config:
            page["filterConfig"] = filter_config
        write_json(DEF / "pages" / name / "page.json", page)
        # Tab order follows reading order, so keyboard navigation matches the eye.
        for i, v in enumerate(sorted(visuals, key=lambda v: (v["position"]["y"],
                                                            v["position"]["x"]))):
            v["position"]["tabOrder"] = i
        for v in visuals:
            write_json(DEF / "pages" / name / "visuals" / v["name"] / "visual.json", v)

    print(f"Wrote {ROOT}")
    for name, display, visuals, fc in pages:
        rows = " + ".join(str(h) for _, h in Grid(name).rows)
        print(f"  {display:<16} {len(visuals):>2} visuals   rows {rows}"
              + ("   (page filters)" if fc else ""))


if __name__ == "__main__":
    main()
