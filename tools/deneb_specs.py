"""Vega-Lite specs for the Deneb visuals. Each spec reads the visual's fields from the 'dataset' data source."""
import json

GUID = "deneb7E15AEF80B9E4D4F8E12924291ECE89A"
VEGA_LITE_VERSION = "6.4.3"

TEXT, TEXT2, TEXT3, GRID, CARD = "#F2F2F2", "#A5A5A5", "#6E6E6E", "#1F1F1F", "#141414"
GOLD, EMERALD, PURPLE, CORAL, TEAL = "#D6AC58", "#65C99A", "#956BC4", "#E77D67", "#58A6A6"

CONFIG = {
    "background": "transparent",
    "font": "Segoe UI",
    "padding": 4,
    "autosize": {"type": "fit", "contains": "padding"},
    "view": {"stroke": "transparent"},
    "axis": {"labelColor": TEXT2, "labelFontSize": 10, "titleColor": TEXT3, "titleFontSize": 10, "titleFontWeight": "normal",
             "domain": False, "ticks": False, "grid": False, "labelPadding": 6},
    "text": {"color": TEXT, "fontSize": 10},
    "legend": {"disable": True},
}

def inr(expr):
    """Vega expression that shows a rupee amount in M or K."""
    return f"'₹' + (abs({expr}) >= 1e6 ? format({expr} / 1e6, '.1f') + 'M' : abs({expr}) >= 1e3 ? format({expr} / 1e3, '.0f') + 'K' : format({expr}, ',.0f'))"

def base(**spec):
    return {"$schema": "https://vega.github.io/schema/vega-lite/v6.json", "data": {"name": "dataset"}, "width": "container", "height": "container", **spec}

def ranked_bars(category, value, color=GOLD, money=True):
    """Ranked bars. Fits any height, so Top 10 charts never scroll."""
    label = inr(f"datum['{value}']") if money else f"format(datum['{value}'], ',.0f')"
    return base(
        transform=[
            {"calculate": label, "as": "Label"},
            {"joinaggregate": [{"op": "max", "field": value, "as": "peak"}]},
            {"calculate": f"datum['{value}'] > 0.35 * datum.peak", "as": "Inside"},
        ],
        encoding={
            "y": {"field": category, "type": "nominal", "sort": {"field": value, "op": "max", "order": "descending"}, "title": None, "axis": {"labelLimit": 110}},
            "x": {"field": value, "type": "quantitative", "title": None, "axis": None, "scale": {"nice": False}},
            "tooltip": [{"field": category, "title": category}, {"field": "Label", "title": "Sales" if money else "Units"}],
        },
        layer=[
            {"mark": {"type": "bar", "color": color, "cornerRadiusEnd": 2, "height": {"band": 0.62}}},
            {"mark": {"type": "text", "align": "right", "dx": -5, "color": "#111111", "fontWeight": 600}, "encoding": {"text": {"field": "Label"}, "opacity": {"condition": {"test": "datum.Inside", "value": 1}, "value": 0}}},
            {"mark": {"type": "text", "align": "left", "dx": 5, "color": TEXT2}, "encoding": {"text": {"field": "Label"}, "opacity": {"condition": {"test": "datum.Inside", "value": 0}, "value": 1}}},
        ],
    )

def calendar():
    """Daily Amazon sales by week and weekday. A row exists only for days with recognised sales."""
    v = "Amazon Revenue"
    return base(
        transform=[{"calculate": inr(f"datum['{v}']"), "as": "Sales"}, {"calculate": "timeFormat(toDate(datum['Date']), '%a %d %b %Y')", "as": "Day"}],
        mark={"type": "rect", "cornerRadius": 3, "stroke": CARD, "strokeWidth": 2},
        encoding={
            "x": {"field": "Date", "timeUnit": "yearweek", "type": "ordinal", "title": None, "axis": {"format": "%d %b", "labelAngle": 0, "labelOverlap": "greedy", "labelSeparation": 8, "orient": "top"}},
            "y": {"field": "Date", "timeUnit": "day", "type": "ordinal", "title": None, "axis": {"format": "%a"}},
            "color": {"field": v, "type": "quantitative", "scale": {"range": ["#2B2416", GOLD]}},
            "tooltip": [{"field": "Day", "title": "Day"}, {"field": "Sales", "title": "Recorded sales"}],
        },
    )

def order_waterfall():
    """All recorded order value, what left it by outcome, and what was recognised. Rows are the outcome groups."""
    v, g = "Amazon Order Value", "Status Group"
    order = "['Cancelled', 'Returned / Failed', 'In Progress', 'Recognised Sale']"
    return base(
        transform=[
            {"calculate": f"indexof({order}, datum['{g}'])", "as": "k"},
            {"joinaggregate": [{"op": "sum", "field": v, "as": "total"}, {"op": "min", "field": "k", "as": "firstK"}]},
            {"calculate": "datum.k === datum.firstK ? [0, 1] : [1]", "as": "copy"},
            {"flatten": ["copy"]},
            {"calculate": "datum.copy === 0 ? -1 : datum.k", "as": "pos"},
            {"calculate": f"datum.copy === 0 ? 0 : datum['{v}']", "as": "step"},
            {"window": [{"op": "sum", "field": "step", "as": "run"}], "sort": [{"field": "pos", "order": "ascending"}]},
            {"calculate": "datum.copy === 0 ? 0 : datum.total - datum.run", "as": "low"},
            {"calculate": "datum.copy === 0 ? datum.total : datum.low + datum.step", "as": "high"},
            {"calculate": "datum.copy === 0 ? 'All recorded value' : datum['" + g + "']", "as": "Outcome"},
            {"calculate": "datum.high - datum.low", "as": "size"},
            {"calculate": inr("datum.size") + " + '  ' + format(datum.size / datum.total, '.1%')", "as": "Label"},
        ],
        encoding={
            "y": {"field": "Outcome", "type": "nominal", "sort": {"field": "pos", "order": "ascending"}, "title": None, "axis": {"labelLimit": 110}},
            "tooltip": [{"field": "Outcome", "title": "Outcome"}, {"field": "Label", "title": "Value and share"}],
        },
        layer=[
            {"mark": {"type": "bar", "cornerRadius": 2, "height": {"band": 0.58}},
             "encoding": {
                 "x": {"field": "low", "type": "quantitative", "title": None, "axis": None, "scale": {"nice": False}},
                 "x2": {"field": "high"},
                 "color": {"field": "Outcome", "type": "nominal", "scale": {
                     "domain": ["All recorded value", "Cancelled", "Returned / Failed", "In Progress", "Recognised Sale"],
                     "range": [TEXT3, CORAL, CORAL, TEXT2, GOLD]}}}},
            {"mark": {"type": "text", "baseline": "middle", "align": "right", "dx": -6, "color": "#111111", "fontWeight": 600},
             "transform": [{"filter": "datum.size / datum.total >= 0.45"}],
             "encoding": {"x": {"field": "high", "type": "quantitative"}, "text": {"field": "Label"}}},
            {"mark": {"type": "text", "baseline": "middle", "align": "right", "dx": -6, "color": TEXT2},
             "transform": [{"filter": "datum.size / datum.total < 0.45"}],
             "encoding": {"x": {"field": "low", "type": "quantitative"}, "text": {"field": "Label"}}},
        ],
    )

def concentration():
    """Cumulative share of International sales by customer rank. Shows ranks only, so no customer is named."""
    v = "International Revenue"
    return base(
        transform=[
            {"window": [{"op": "row_number", "as": "Rank"}, {"op": "sum", "field": v, "as": "run"}], "sort": [{"field": v, "order": "descending"}]},
            {"joinaggregate": [{"op": "sum", "field": v, "as": "total"}]},
            {"calculate": "datum.run / datum.total", "as": "Cumulative share"},
            {"calculate": "format(datum['Cumulative share'], '.1%')", "as": "Share"},
        ],
        encoding={
            "x": {"field": "Rank", "type": "quantitative", "title": "Customers, largest first", "axis": {"tickCount": 6, "format": "d"}, "scale": {"nice": False, "domainMin": 1}},
            "y": {"field": "Cumulative share", "type": "quantitative", "title": None, "scale": {"domain": [0, 1]}, "axis": {"format": ".0%", "tickCount": 5, "grid": True, "gridColor": GRID}},
        },
        layer=[
            {"mark": {"type": "area", "color": TEAL, "opacity": 0.14, "interpolate": "monotone"}},
            {"mark": {"type": "line", "color": TEAL, "strokeWidth": 2, "interpolate": "monotone"}},
            {"mark": {"type": "point", "filled": True, "color": TEAL, "size": 26, "opacity": 0},
             "encoding": {"tooltip": [{"field": "Rank", "title": "Customers"}, {"field": "Share", "title": "Share of sales"}]}},
            {"transform": [{"filter": "datum.Rank === 1 || datum.Rank === 10"}],
             "mark": {"type": "point", "filled": True, "color": GOLD, "size": 56}},
            {"transform": [{"filter": "datum.Rank === 1 || datum.Rank === 10"}, {"calculate": "'Top ' + datum.Rank + ': ' + datum.Share", "as": "Note"}],
             "mark": {"type": "text", "align": "left", "dx": 9, "dy": 10, "color": TEXT, "fontWeight": 600},
             "encoding": {"text": {"field": "Note"}}},
        ],
    )

def price_range():
    """Lowest, average and highest MRP in each marketplace. Blank prices are ignored by the measures."""
    lo, av, hi = "Marketplace Min MRP", "Marketplace Avg MRP May 2022", "Marketplace Max MRP"
    tip = [{"field": "Marketplace", "title": "Marketplace"}, {"field": "Low", "title": "Lowest MRP"}, {"field": "Avg", "title": "Average MRP"}, {"field": "High", "title": "Highest MRP"}]
    axis = {"field": lo, "type": "quantitative", "title": "MRP (₹)", "axis": {"format": ",.0f", "grid": True, "gridColor": GRID, "tickCount": 8}}
    return base(
        transform=[{"calculate": f"'₹' + format(datum['{lo}'], ',.0f')", "as": "Low"}, {"calculate": f"'₹' + format(datum['{av}'], ',.0f')", "as": "Avg"}, {"calculate": f"'₹' + format(datum['{hi}'], ',.0f')", "as": "High"}],
        encoding={"y": {"field": "Marketplace", "type": "nominal", "sort": {"field": av, "order": "descending"}, "title": None}, "tooltip": tip},
        layer=[
            {"mark": {"type": "rule", "color": "#3A3A3A", "strokeWidth": 5, "strokeCap": "round"}, "encoding": {"x": axis, "x2": {"field": hi}}},
            {"mark": {"type": "tick", "color": TEXT2, "thickness": 2, "size": 16}, "encoding": {"x": {"field": lo, "type": "quantitative"}}},
            {"mark": {"type": "tick", "color": TEXT2, "thickness": 2, "size": 16}, "encoding": {"x": {"field": hi, "type": "quantitative"}}},
            {"mark": {"type": "point", "filled": True, "color": GOLD, "size": 130, "opacity": 1}, "encoding": {"x": {"field": av, "type": "quantitative"}}},
            {"mark": {"type": "text", "dy": -14, "color": GOLD, "fontWeight": 600}, "encoding": {"x": {"field": av, "type": "quantitative"}, "text": {"field": "Avg"}}},
        ],
    )

def segment_coverage():
    """Sales share in each row label, and one cell per month with sales, so the short overlap is visible."""
    v = "Segment Sales"
    return base(
        transform=[
            {"calculate": "datum['Year'] * 100 + datum['Month Number']", "as": "ym"},
            {"joinaggregate": [{"op": "sum", "field": v, "as": "all"}]},
            {"joinaggregate": [{"op": "sum", "field": v, "as": "seg"}, {"op": "max", "field": v, "as": "peak"}], "groupby": ["Segment"]},
            {"calculate": "datum.Segment + '  ' + format(datum.seg / datum.all, '.1%')", "as": "Row"},
            {"calculate": f"datum['{v}'] / datum.peak", "as": "Intensity"},
            {"calculate": inr(f"datum['{v}']"), "as": "Sales"},
        ],
        mark={"type": "rect", "cornerRadius": 3, "stroke": CARD, "strokeWidth": 2},
        encoding={
            "x": {"field": "Month Year", "type": "ordinal", "sort": {"field": "ym", "order": "ascending"}, "title": None, "axis": {"labelAngle": -55, "labelOverlap": False, "labelFontSize": 9}},
            "y": {"field": "Row", "type": "nominal", "sort": "ascending", "title": None, "axis": {"labelLimit": 130, "labelFontSize": 11, "labelColor": TEXT}},
            "color": {"field": "Segment", "type": "nominal", "scale": {"domain": ["Amazon", "International"], "range": [GOLD, TEAL]}},
            "opacity": {"field": "Intensity", "type": "quantitative", "scale": {"domain": [0, 1], "range": [0.3, 1]}},
            "tooltip": [{"field": "Segment", "title": "Segment"}, {"field": "Month Year", "title": "Month"}, {"field": "Sales", "title": "Recorded sales"}],
        },
    )

def price_histogram(value):
    """How many products sit in each MRP band. One row per product."""
    return base(
        layer=[{
            "mark": {"type": "bar", "color": PURPLE, "cornerRadiusEnd": 2, "binSpacing": 2},
            "encoding": {
                "x": {"field": value, "bin": {"maxbins": 24}, "type": "quantitative", "title": "MRP (₹)", "axis": {"format": ",.0f", "tickCount": 8}},
                "y": {"aggregate": "count", "type": "quantitative", "title": None, "axis": {"grid": True, "gridColor": GRID, "tickCount": 5}},
                "tooltip": [{"field": value, "bin": {"maxbins": 24}, "type": "quantitative", "title": "MRP band", "format": ",.0f"}, {"aggregate": "count", "type": "quantitative", "title": "Products"}],
            }}],
    )

def dumps(spec):
    return json.dumps(spec, ensure_ascii=False)
