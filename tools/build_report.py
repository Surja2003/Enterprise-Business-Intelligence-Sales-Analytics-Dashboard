"""Generates the PBIR report definition (theme, pages, visuals) from one layout system."""
import json, shutil
from pathlib import Path
import deneb_specs as ds

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "EnterpriseSalesBI.Report"
PAGES_DIR = REPORT / "definition" / "pages"
THEME_NAME = "Executive_Noir9066407090753045.json"
VIS_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

BG, PANEL, CARD, BORDER = "#080808", "#0E0E0E", "#141414", "#262626"
TEXT, TEXT2, TEXT3 = "#F2F2F2", "#A5A5A5", "#6E6E6E"
GOLD, EMERALD, PURPLE, CORAL, TEAL = "#D6AC58", "#65C99A", "#956BC4", "#E77D67", "#58A6A6"
FONT = "Segoe UI"
FONT_SB = "Segoe UI Semibold"

# ------------------------------------------------------------------ JSON helpers ---------------------------
def L(v):
    if isinstance(v, bool): return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)): return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}
def C(hex_): return {"solid": {"color": L(hex_)}}
def col(entity, prop): return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
def mea(prop, entity="_Measures"): return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
def proj(field, active=False, name=None):
    kind = "Column" if "Column" in field else "Measure"
    e, p = field[kind]["Expression"]["SourceRef"]["Entity"], field[kind]["Property"]
    d = {"field": field, "queryRef": f"{e}.{p}", "nativeQueryRef": p}
    if active: d["active"] = True
    if name: d["displayName"] = name
    return d
def obj(**props): return [{"properties": props}]
CLEAR_FILL = [{"properties": {"show": L(True), "fillColor": C("#FFFFFF"), "transparency": L(t)}, "selector": {"id": state}} for state, t in (("default", 100), ("hover", 95), ("press", 90))]

def container_objects(title=None, subtitle=None, bg=CARD, border=True, padding=None):
    o = {"visualHeader": obj(show=L(False)), "dropShadow": obj(show=L(False))}
    if title:
        o["title"] = obj(show=L(True), text=L(title), fontColor=C(TEXT), fontSize=L(13), fontFamily=L(FONT_SB), alignment=L("left"))
    else:
        o["title"] = obj(show=L(False))
    if subtitle:
        o["subTitle"] = obj(show=L(True), text=L(subtitle), fontColor=C(TEXT3), fontSize=L(10), fontFamily=L(FONT), alignment=L("left"))
    else:
        o["subTitle"] = obj(show=L(False))
    if bg:
        o["background"] = obj(show=L(True), color=C(bg), transparency=L(0))
    else:
        o["background"] = obj(show=L(False))
    o["border"] = obj(show=L(bool(border)), color=C(BORDER), radius=L(10), width=L(1)) if border else obj(show=L(False))
    if padding is not None:
        o["padding"] = obj(top=L(padding), bottom=L(padding), left=L(padding), right=L(padding))
    return o

class Page:
    def __init__(self, pid, display, key, drill=None):
        self.pid, self.display, self.key, self.drill = pid, display, key, drill
        self.visuals, self.z = [], 0

    def add(self, name, x, y, w, h, visual, cobjs=None, filters=None):
        self.z += 100
        v = dict(visual)
        if cobjs: v["visualContainerObjects"] = cobjs
        v.setdefault("drillFilterOtherVisuals", True)
        c = {"$schema": VIS_SCHEMA, "name": name, "position": {"x": x, "y": y, "z": self.z, "height": h, "width": w, "tabOrder": self.z}, "visual": v}
        if filters: c["filterConfig"] = {"filters": filters}
        self.visuals.append(c)
        return c

    # ---- building blocks -----------------------------------------------------------------------------------
    def svg(self, name, x, y, w, h, measure):
        self.add(name, x, y, w, h, {
            "visualType": "image",
            "objects": {
                "image": obj(sourceType=L("imageUrl"), sourceUrl={"expr": mea(measure)}),
                "imageScaling": obj(imageScalingType=L("Fit")),
                "general": obj(altText=L(measure)),
            }}, container_objects(bg=None, border=False, padding=0))

    def text(self, name, x, y, w, h, paragraphs, bg=CARD, border=True, padding=16):
        self.add(name, x, y, w, h, {"visualType": "textbox", "objects": {"general": obj(paragraphs=paragraphs)}}, container_objects(bg=bg, border=border, padding=padding))

    def slicer(self, name, x, y, w, h, field, label, mode="Dropdown", sync=None):
        hide_blank = None
        if mode == "Dropdown" and field["Column"]["Expression"]["SourceRef"]["Entity"] == "DimDate":
            prop = field["Column"]["Property"]
            hide_blank = [{"name": f"noBlank{prop}", "field": field, "type": "Advanced", "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "DimDate", "Type": 0}],
                "Where": [{"Condition": {"Not": {"Expression": {"Comparison": {"ComparisonKind": 0, "Left": {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": prop}}, "Right": {"Literal": {"Value": "null"}}}}}}}]}}]
        v = {"visualType": "slicer", "query": {"queryState": {"Values": {"projections": [proj(field, active=True)]}}},
             "objects": {
                 "data": obj(mode=L(mode)),
                 "header": obj(show=L(True), text=L(label), fontColor=C(TEXT3), fontFamily=L(FONT), textSize=L(10), showRestatement=L(False)),
                 "items": obj(fontColor=C(TEXT), background=C(CARD), textSize=L(11), fontFamily=L(FONT)),
                 "general": obj(outlineColor=C(BORDER), outlineWeight=L(0)),
                 "date": obj(background=C(CARD), textColor=C(TEXT)) if mode == "Between" else None,
                 "numericInputStyle": obj(background=C(CARD), fontColor=C(TEXT), textSize=L(10)) if mode == "Between" else None,
                 "slider": obj(color=C(GOLD), show=L(True)) if mode == "Between" else None,
             }}
        v["objects"] = {k: o for k, o in v["objects"].items() if o}
        if sync: v["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
        self.add(name, x, y, w, h, v, container_objects(bg=CARD, border=True, padding=6), filters=hide_blank)

    def grain_slicer(self, name, x, y, w, h):
        field = col("Trend Grain", "Trend Grain")
        month = "'''DimDate''[Month Year]'"
        fields = {"Column": {"Expression": {"SourceRef": {"Entity": "Trend Grain"}}, "Property": "Trend Grain Fields"}}
        cond = {"Version": 2, "From": [{"Name": "t", "Entity": "Trend Grain", "Type": 0}],
                "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": "Trend Grain Fields"}}], "Values": [[{"Literal": {"Value": month}}]]}},
                           "Annotations": {"filterExpressionMetadata": {
                               "expressions": [field],
                               "decomposedIdentities": {"values": [[{"0": [{"Literal": {"Value": month}}]}]], "columns": [{"value": fields}]},
                               "valueMap": [{"0": "Month"}]}}}]}
        v = {"visualType": "slicer", "query": {"queryState": {"Values": {"projections": [proj(field, active=True)]}}},
             "objects": {
                 "data": obj(mode=L("Basic")),
                 "general": [{"properties": {"orientation": {"expr": {"Literal": {"Value": "1D"}}}, "filter": {"filter": cond}}}],
                 "selection": obj(singleSelect=L(True), strictSingleSelect=L(True), selectAllCheckboxEnabled=L(False)),
                 "header": obj(show=L(False)),
                 "items": obj(fontColor=C(TEXT2), background=C(BG), textSize=L(10), fontFamily=L(FONT), outlineStyle=L(0)),
             }}
        self.add(name, x, y, w, h, v, container_objects(bg=None, border=False, padding=0))

    def nav(self, active_key):
        self.svg("rail", 0, 0, 216, 1080, f"Rail {active_key}")
        y = 104
        for key, label, pid in NAV:
            self.add(f"nav{key}", 12, y, 192, 42, {
                "visualType": "actionButton",
                "objects": {
                    "icon": obj(show=L(False)),
                    "text": [{"properties": {"show": L(False)}, "selector": {"id": "default"}}],
                    "fill": CLEAR_FILL,
                    "outline": [{"properties": {"show": L(False)}, "selector": {"id": "default"}}],
                },
            }, {**container_objects(bg=None, border=False, padding=0),
                "visualTooltip": obj(show=L(False)),
                "visualLink": obj(show=L(True), type=L("PageNavigation"), navigationSection=L(pid), tooltip=L(f"Go to {label}"))})
            y += 46
        self.add("navReset", 12, 1000, 192, 40, {
            "visualType": "actionButton",
            "objects": {
                "icon": obj(show=L(False)),
                "text": [{"properties": {"show": L(True), "text": L("Clear all filters"), "fontColor": C(TEXT2), "fontSize": L(10), "fontFamily": L(FONT), "horizontalAlignment": L("center")}, "selector": {"id": "default"}}],
                "fill": [{"properties": {"show": L(True), "fillColor": C(state_color), "transparency": L(0)}, "selector": {"id": state}} for state, state_color in (("default", CARD), ("hover", BORDER), ("press", BORDER))],
                "outline": [{"properties": {"show": L(True), "lineColor": C(BORDER), "weight": L(1), "roundEdge": L(8)}, "selector": {"id": "default"}}],
            },
        }, {**container_objects(bg=None, border=False, padding=0), "visualLink": obj(show=L(True), type=L("ClearAllSlicers"))})

    def back(self):
        self.add("backButton", X + W - 150, 20, 150, 30, {
            "visualType": "actionButton",
            "objects": {
                "icon": obj(show=L(False)),
                "text": [{"properties": {"show": L(False)}, "selector": {"id": "default"}}],
                "fill": CLEAR_FILL,
                "outline": [{"properties": {"show": L(False)}, "selector": {"id": "default"}}],
            },
        }, {**container_objects(bg=None, border=False, padding=0), "visualLink": obj(show=L(True), type=L("Back"), tooltip=L("Back to the page you came from"))})

    def header(self):
        self.svg("pageHeader", X, 20, W, 64, f"Header {self.key}")

    def filters(self, segment=False, y=92, h=58):
        widths = [440, 200, 200, 200] + ([200] if segment else [])
        x = X
        specs = [("Date", col("DimDate", "Date"), "Date range", "Between", "syncDate"),
                 ("Year", col("DimDate", "Year"), "Year", "Dropdown", "syncYear"),
                 ("Quarter", col("DimDate", "Quarter"), "Quarter", "Dropdown", "syncQuarter"),
                 ("Month", col("DimDate", "Month"), "Month", "Dropdown", "syncMonth")]
        if segment: specs.append(("Segment", col("Segment", "Segment"), "Sales segment", "Dropdown", "syncSegment"))
        for (nm, f, label, mode, sync), w in zip(specs, widths):
            self.slicer(f"f{nm}", x, y, w, h, f, label, mode, sync)
            x += w + 12

    def kpis(self, measures, y=158, h=128):
        gap = 12
        w = (W - gap * (len(measures) - 1)) / len(measures)
        for i, m in enumerate(measures):
            self.svg(f"kpi{i}", round(X + i * (w + gap)), y, round(w), h, m)

    # ---- charts --------------------------------------------------------------------------------------------
    def bar(self, name, x, y, w, h, title, cat, value, color=GOLD, subtitle=None, label_units=0, horizontal=True, sort_cat=False):
        vtype = "clusteredBarChart" if horizontal else "clusteredColumnChart"
        sort_field = cat if sort_cat else value
        visual = {"visualType": vtype,
                  "query": {"queryState": {"Category": {"projections": [proj(cat, active=True)]}, "Y": {"projections": [proj(value)]}},
                            "sortDefinition": {"sort": [{"field": sort_field, "direction": "Ascending" if sort_cat else "Descending"}]}},
                  "objects": {
                      "categoryAxis": obj(show=L(True), showAxisTitle=L(False), labelColor=C(TEXT2), fontSize=L(10), fontFamily=L(FONT), gridlineShow=L(False), axisType=L("Categorical"), innerPadding=L(28), preferredCategoryWidth=L(16)),
                      "valueAxis": obj(show=L(False), showAxisTitle=L(False), gridlineShow=L(False), start=L(0)),
                      "labels": obj(show=L(True), color=C(TEXT), fontSize=L(9), fontFamily=L(FONT), labelDisplayUnits=L(label_units), labelPrecision=L(0 if label_units == 1 else 1)),
                      "dataPoint": obj(fill=C(color)),
                      "legend": obj(show=L(False)),
                  }}
        self.add(name, x, y, w, h, visual, container_objects(title, subtitle, padding=8))

    def multi_bar(self, name, x, y, w, h, title, cat, values, colors, subtitle=None, horizontal=True, labels=True, names=None, label_units=0):
        vtype = "clusteredBarChart" if horizontal else "clusteredColumnChart"
        dp = [{"properties": {"fill": C(c)}, "selector": {"metadata": f"_Measures.{m}"}} for m, c in zip(values, colors)]
        visual = {"visualType": vtype,
                  "query": {"queryState": {"Category": {"projections": [proj(cat, active=True)]}, "Y": {"projections": [proj(mea(m), name=(names or {}).get(m)) for m in values]}}},
                  "objects": {
                      "categoryAxis": obj(show=L(True), showAxisTitle=L(False), labelColor=C(TEXT2), fontSize=L(10), fontFamily=L(FONT), gridlineShow=L(False)),
                      "valueAxis": obj(show=L(not labels), showAxisTitle=L(False), gridlineShow=L(not labels), gridlineColor=C("#1F1F1F"), labelColor=C(TEXT3), fontSize=L(9), start=L(0)),
                      "labels": obj(show=L(labels), color=C(TEXT), fontSize=L(9), fontFamily=L(FONT), labelDisplayUnits=L(label_units)),
                      "legend": obj(show=L(True), position=L("Top"), labelColor=C(TEXT2), fontSize=L(10), fontFamily=L(FONT), showTitle=L(False)),
                      "dataPoint": dp,
                  }}
        self.add(name, x, y, w, h, visual, container_objects(title, subtitle, padding=8))

    def trend(self, name, x, y, w, h, title, subtitle=None, value="Segment Sales", series=True, color=GOLD, grain=True):
        param = col("Trend Grain", "Trend Grain")
        category = {"projections": [proj(col("DimDate", "Month Year"), active=True)],
                    "fieldParameters": [{"parameterExpr": param, "index": 0, "length": 1}]}
        if not grain: del category["fieldParameters"]
        state = {"Category": category, "Y": {"projections": [proj(mea(value))]}}
        if series: state["Series"] = {"projections": [proj(col("Segment", "Segment"))]}
        visual = {"visualType": "columnChart", "query": {"queryState": state},
                  "objects": {
                      "categoryAxis": obj(show=L(True), showAxisTitle=L(False), labelColor=C(TEXT2), fontSize=L(10), fontFamily=L(FONT), gridlineShow=L(False), axisType=L("Categorical")),
                      "valueAxis": obj(show=L(True), showAxisTitle=L(False), labelColor=C(TEXT3), fontSize=L(9), fontFamily=L(FONT), gridlineShow=L(True), gridlineColor=C("#1F1F1F"), gridlineThickness=L(1), labelDisplayUnits=L(1000000), start=L(0)),
                      "legend": obj(show=L(series), position=L("Top"), labelColor=C(TEXT2), fontSize=L(10), fontFamily=L(FONT), showTitle=L(False)),
                      "labels": obj(show=L(False)),
                  }}
        if not series: visual["objects"]["dataPoint"] = obj(fill=C(color))
        self.add(name, x, y, w, h, visual, container_objects(title, subtitle, padding=10))

    def donut(self, name, x, y, w, h, title, cat, value, subtitle=None):
        visual = {"visualType": "donutChart",
                  "query": {"queryState": {"Category": {"projections": [proj(cat, active=True)]}, "Y": {"projections": [proj(value)]}}},
                  "objects": {
                      "labels": obj(show=L(True), labelStyle=L("Category, percent of total"), color=C(TEXT), fontSize=L(10), fontFamily=L(FONT), percentageDecimalPlaces=L(1)),
                      "legend": obj(show=L(False)),
                  }}
        self.add(name, x, y, w, h, visual, container_objects(title, subtitle, padding=8))

    def deneb(self, name, x, y, w, h, title, fields, spec, subtitle=None, select=False):
        visual = {"visualType": ds.GUID,
                  "query": {"queryState": {"dataset": {"projections": [proj(f) for f in fields]}}},
                  "objects": {"vega": obj(jsonSpec=L(ds.dumps(spec)), jsonConfig=L(ds.dumps(ds.CONFIG)), provider=L("vegaLite"), version=L(ds.VEGA_LITE_VERSION),
                                          enableTooltips=L(True), enableContextMenu=L(True), enableSelection=L(select))}}
        self.add(name, x, y, w, h, visual, container_objects(title, subtitle, padding=8))

    def table(self, name, x, y, w, h, title, cols, subtitle=None, sort=None, row_pad=4, filters=None, widths=None):
        q = {"Values": {"projections": [proj(f, name=n) for f, n in cols]}}
        visual = {"visualType": "tableEx", "query": {"queryState": q}, "objects": {
            "grid": obj(gridVertical=L(False), gridHorizontal=L(True), gridHorizontalColor=C("#1F1F1F"), gridHorizontalWeight=L(1), rowPadding=L(row_pad), outlineColor=C(BORDER), textSize=L(10)),
            "columnHeaders": obj(fontColor=C(TEXT2), backColor=C(CARD), fontFamily=L(FONT_SB), fontSize=L(10), outline=L("None")),
            "values": obj(fontColorPrimary=C(TEXT), fontColorSecondary=C(TEXT), backColorPrimary=C(CARD), backColorSecondary=C(CARD), fontFamily=L(FONT), fontSize=L(10)),
            "total": obj(totals=L(False)),
        }}
        if widths:
            visual["objects"]["columnWidth"] = [{"properties": {"value": L(wd)}, "selector": {"metadata": proj(f)["queryRef"]}} for (f, _), wd in zip(cols, widths)]
            visual["objects"]["values"][0]["properties"]["wordWrap"] = L(True)
        if sort:
            visual["query"]["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}]}
        self.add(name, x, y, w, h, visual, container_objects(title, subtitle, padding=8), filters=filters)

    def write(self):
        d = PAGES_DIR / self.pid
        (d / "visuals").mkdir(parents=True, exist_ok=True)
        page = {"$schema": PAGE_SCHEMA, "name": self.pid, "displayName": self.display, "displayOption": "FitToPage", "height": 1080, "width": 1920,
                "objects": {"background": obj(color=C(BG), transparency=L(0)), "outspace": obj(color=C(BG), transparency=L(0))}}
        if self.drill:
            page["type"] = "Drillthrough"
            page["visibility"] = "HiddenInViewMode"
            page["filterConfig"] = {"filters": [{"name": f"drill{self.key}", "field": self.drill, "type": "Categorical", "howCreated": "Drillthrough"}]}
            page["pageBinding"] = {"name": f"binding{self.key}", "type": "Drillthrough", "parameters": [{"name": f"param{self.key}", "boundFilter": f"drill{self.key}", "fieldExpr": self.drill}]}
        (d / "page.json").write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
        for v in self.visuals:
            vd = d / "visuals" / v["name"]
            vd.mkdir(parents=True, exist_ok=True)
            (vd / "visual.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")

# ------------------------------------------------------------------ Layout ---------------------------------
X, W = 240, 1648
GAP = 12
AMZ, INT, SALE, MAY, EXP, WH = "Amazon Sale Report", "International sale Report", "Sale Report", "May-2022", "Expense IIGF", "Cloud Warehouse Compersion Chart"
IDS = dict(Executive="87f710b2c70c33630cb0", Amazon="d765c07f363e06e0174b", International="037782b40d172984cb33", Product="0b7d6366726706227643",
           Pricing="a8a35bc1b4a09d416744", Expense="c1e7a0d4b2f94a6e81d3", Logistics="d2f8b1e5c3a05b7f92e4", Notes="e3a9c2f6d4b16c8fa3f5", SkuDetail="f4b0d3a7e5c27d9ab4c6", MarketplaceDetail="a5c1e4b8f6d38eab05d7")
NAV = [("Executive", "Executive Overview", IDS["Executive"]), ("Amazon", "Amazon Sales", IDS["Amazon"]), ("International", "International Sales", IDS["International"]),
       ("Product", "Products and Stock", IDS["Product"]), ("Pricing", "Marketplace Pricing", IDS["Pricing"]), ("Expense", "Expenses and Cash", IDS["Expense"]),
       ("Logistics", "Logistics", IDS["Logistics"]), ("Notes", "Data Notes", IDS["Notes"])]

def col4(i, n=4, gap=GAP):
    w = (W - gap * (n - 1)) / n
    return round(X + i * (w + gap)), round(w)

def executive():
    p = Page(IDS["Executive"], "Executive Overview", "Executive")
    p.nav("Executive"); p.header(); p.filters(segment=True)
    p.kpis(["KPI Total Sales", "KPI Amazon Sales", "KPI International Sales", "KPI Amazon Orders", "KPI Amazon Units", "KPI International Units", "KPI Growth", "KPI Expenses"])
    y2, h2 = 298, 366
    p.trend("trend", X, y2, 1200, h2, "Recorded sales over time", "Amazon and International stay separate. Switch the time grain at top right.")
    p.grain_slicer("grain", X + 1200 - 312, y2 + 8, 300, 34)
    x3 = X + 1200 + GAP
    p.deneb("mix", x3, y2, W - 1200 - GAP, h2, "Sales contribution and coverage by segment", [col("Segment", "Segment"), col("DimDate", "Year"), col("DimDate", "Month Number"), col("DimDate", "Month Year"), mea("Segment Sales")], ds.segment_coverage(), "Share of recorded sales. Cells mark months with sales.")
    y3, h3 = 676, 384
    x, w = col4(0)
    p.deneb("top", x, y3, w, h3, "Top 10 styles", [col(AMZ, "Style"), mea("Top 10 Style Sales")], ds.ranked_bars("Style", "Top 10 Style Sales"), "Amazon recorded sales", select=True)
    x, w = col4(1)
    p.table("low", x, y3, w, h3, "Lowest 10 selling styles", [(col(AMZ, "Style"), "Style"), (mea("Low 10 Style Units"), "Units"), (mea("Low 10 Style Sales"), "Sales")], "Amazon styles with at least one recognised sale", sort=(mea("Low 10 Style Sales"), "Ascending"))
    x, w = col4(2)
    p.table("monthly", x, y3, w, h3, "Sales performance by month", [(col("DimDate", "Month Year"), "Month"), (mea("Amazon Revenue"), "Amazon"), (mea("International Revenue"), "International"), (mea("Amazon Revenue MoM %"), "Amazon MoM")], "Blank growth means no comparable prior month", sort=(col("DimDate", "Month Year"), "Ascending"), row_pad=2)
    x, w = col4(3)
    p.svg("insights", x, y3, w, h3, "Insights Executive")
    return p

def build():
    report_path = REPORT / "definition" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if ds.GUID not in report.get("publicCustomVisuals", []):
        report["publicCustomVisuals"] = report.get("publicCustomVisuals", []) + [ds.GUID]
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    theme = json.loads((ROOT / "tools" / "theme.json").read_text(encoding="utf-8"))
    (REPORT / "StaticResources" / "RegisteredResources" / THEME_NAME).write_text(json.dumps(theme, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.copy(ROOT / "tools" / "theme.json", ROOT.parent / "ExecutiveNoir-theme.json")
    pages = [executive()]
    try:
        import pages_more
        pages += pages_more.build(globals())
    except ImportError:
        pass
    keep = {p.pid for p in pages}
    for d in PAGES_DIR.iterdir():
        if d.is_dir():
            shutil.rmtree(d)
    for p in pages: p.write()
    (PAGES_DIR / "pages.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p.pid for p in pages], "activePageName": pages[0].pid, "landingPageName": pages[0].pid}, indent=2), encoding="utf-8")
    print("Pages:", [p.display for p in pages], "visuals:", sum(len(p.visuals) for p in pages))

if __name__ == "__main__":
    build()
