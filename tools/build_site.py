"""Turns the model export in tools/_site_raw into docs/data.json for the web dashboard. Customer names are masked here."""
import csv, json, re
from collections import defaultdict
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "tools" / "_site_raw"
OUT = ROOT / "docs" / "data.json"
PERSON_LINE = re.compile(r"^\w+ (Hotel|Cash)$")  # expense lines that start with a person's name
def clean_expense(name):
    m = PERSON_LINE.match(name)
    return f"{m.group(1)} (name removed)" if m and not name.startswith("Delhi") else name

def load(name):
    with open(RAW / f"{name}.tsv", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
    head = [h.split("[")[-1].rstrip("]") for h in rows[0]]
    return [dict(zip(head, r)) for r in rows[1:]]

def num(v):
    if v in ("", None): return 0
    x = float(v)
    return int(x) if x == int(x) else round(x, 2)

months_raw = sorted(load("months"), key=lambda r: int(r["ym"]))
int_month = load("int_month")
amz_day = sorted(load("amz_day"), key=lambda r: r["Date"])
int_day = sorted(load("int_day"), key=lambda r: r["Date"])
active = {int(r["Year Month Sort"]) for r in int_month} |{int(r["Date"][:4] + r["Date"][5:7]) for r in amz_day}
months = [r for r in months_raw if r["ym"] and int(r["ym"]) in active]
mi = {int(r["ym"]): i for i, r in enumerate(months)}
ymi = lambda ym: mi.get(int(ym)) if ym else None
date_mi = lambda d: mi[int(d[:4] + d[5:7])]

def dim(name, key, *measures, rename=None):
    keys, rows = {}, []
    for r in load(name):
        m, k = ymi(r["Year Month Sort"]), r[key]
        if m is None or k == "": continue
        k = rename(k) if rename else k
        rows.append([m, keys.setdefault(k, len(keys))] + [num(r[x]) for x in measures])
    return {"k": list(keys), "r": rows}

# Customers become "Customer 001" in order of total sales, so names never leave this script
cust_rows = load("int_customer")
cust_total = defaultdict(float)
for r in cust_rows:
    if r["CUSTOMER"]: cust_total[r["CUSTOMER"]] += num(r["s"])
ranked = sorted(cust_total, key=lambda c: (-cust_total[c], c))
masked = {c: f"Customer {i + 1:03d}" for i, c in enumerate(ranked)}

# SKU table and which SKUs can be opened from a Top N list under any filter combination
sku_rows = [r for r in load("sku_month") if r["SKU_Key"] and ymi(r["Year Month Sort"]) is not None]
sku_keys = {}
sku_month = []
for r in sku_rows:
    k = sku_keys.setdefault(r["SKU_Key"], len(sku_keys))
    sku_month.append([ymi(r["Year Month Sort"]), k] + [num(r[x]) for x in ("s", "u", "o", "a", "c", "r", "is", "iu")])
stock = {r["SKU_Key"]: num(r["stock"]) for r in load("sku_stock") if r["stock"] != ""}

def period_sets():
    ys = sorted({r["y"] for r in months})
    qs = sorted({r["q"] for r in months})
    ms = sorted({r["m"] for r in months})
    seen = set()
    for y, q, m in product([None] + ys, [None] + qs, [None] + ms):
        s = frozenset(i for i, r in enumerate(months) if (not y or r["y"] == y) and (not q or r["q"] == q) and (not m or r["m"] == m))
        if s and s not in seen:
            seen.add(s)
            yield s

reach = set()
names = list(sku_keys)
for period in period_sets():
    units, intl = defaultdict(float), defaultdict(float)
    for row in sku_month:
        if row[0] in period:
            units[row[1]] += row[3]
            intl[row[1]] += row[8]
    reach |= {names[k] for k in sorted((k for k in units if units[k] > 0), key=lambda k: (-units[k], names[k]))[:15]}
    reach |= {names[k] for k in sorted((k for k in intl if intl[k] > 0), key=lambda k: (-intl[k], names[k]))[:10]}

detail = {s: {"attr": {}, "day": [], "status": [], "state": [], "city": []} for s in reach}
for r in load("sku_attr_st"):
    if r["SKU_Key"] in detail: detail[r["SKU_Key"]]["attr"].update(cat=r["cat"], size=r["size"], colour=r["colour"])
for r in load("sku_attr_int"):
    if r["SKU_Key"] in detail: detail[r["SKU_Key"]]["attr"].update({k: v for k, v in dict(style=r["style"], size=r["size"]).items() if v})
for r in load("sku_attr_amz"):
    if r["SKU_Key"] in detail: detail[r["SKU_Key"]]["attr"].update({k: v for k, v in dict(cat=r["cat"], style=r["style"], size=r["size"]).items() if v})
for r in load("sku_day"):
    if r["SKU_Key"] in detail and r["s"]: detail[r["SKU_Key"]]["day"].append([r["Date"], num(r["s"])])
for r in load("sku_status"):
    m = ymi(r["Year Month Sort"])
    if r["SKU_Key"] in detail and m is not None and r["v"]: detail[r["SKU_Key"]]["status"].append([m, r["Status Group"], num(r["v"])])
for src, col, field in (("sku_state", "State Clean", "state"), ("sku_city", "ship-city", "city")):
    for r in load(src):
        m = ymi(r["Year Month Sort"])
        if r["SKU_Key"] in detail and m is not None and r["s"] and r[col]: detail[r["SKU_Key"]][field].append([m, r[col], num(r["s"])])
for d in detail.values(): d["day"].sort()

prices = load("prices")
MK = ["Amazon", "Amazon FBA", "Flipkart", "Myntra", "Ajio", "Snapdeal", "Paytm", "Limeroad"]

data = {
    "months": [dict(ym=int(r["ym"]), y=r["y"], q=r["q"], m=r["m"], label=r["label"]) for r in months],
    "amzDay": [[r["Date"]] + [num(r[x]) for x in ("s", "u", "o", "a", "c", "r", "p", "sh", "d")] for r in amz_day],
    "intDay": [[r["Date"], num(r["s"]), num(r["u"])] for r in int_day if r["s"] or r["u"]],
    "amzStatus": [[ymi(r["Year Month Sort"]), r["Status Group"], num(r["v"])] for r in load("amz_status") if ymi(r["Year Month Sort"]) is not None],
    "dims": {
        "style": dim("amz_style", "Style", "s", "u"), "state": dim("amz_state", "State Clean", "s", "u"), "city": dim("amz_city", "ship-city", "s", "u"),
        "category": dim("amz_category", "Category", "s", "u"), "size": dim("amz_size", "Size", "s", "u"), "fulfil": dim("amz_fulfil", "Fulfilment", "s", "u"), "b2b": dim("amz_b2b", "B2B", "s", "u"),
    },
    "int": {
        "month": [[ymi(r["Year Month Sort"])] + [num(r[x]) for x in ("s", "u", "l", "rs", "rc")] for r in int_month if ymi(r["Year Month Sort"]) is not None],
        "customer": dim("int_customer", "CUSTOMER", "s", "u", rename=lambda c: masked[c]),
        "style": dim("int_style", "Style", "s", "u"), "size": dim("int_size", "Final Size", "s"),
    },
    "sku": {"k": names, "stock": [stock.get(n) for n in names], "r": sku_month},
    "detail": detail,
    "stock": {
        "cat": [[r["Category"], num(r["stock"])] for r in load("stock_cat") if r["Category"]],
        "size": [[r["Size"], num(r["stock"])] for r in load("stock_size") if r["Size"]],
        "colour": [[r["Color"], num(r["stock"])] for r in load("stock_colour") if r["Color"]],
        "units": [[ymi(r["Year Month Sort"]), r["Category"], num(r["u"])] for r in load("stock_units") if ymi(r["Year Month Sort"]) is not None and r["Category"]],
        "total": sum(stock.values()), "catalogue": len(load("sku_attr_st")),
    },
    "prices": {"mk": MK, "r": [[r["sku"], r["cat"]] + [num(r[m]) if r[m] != "" else None for m in MK] for r in prices]},
    "expenses": sorted(([clean_expense(r["Expense Particular"]), num(r["v"])] for r in load("expenses")), key=lambda x: -x[1]),
    "receipts": sorted([r["Received Date"], num(r["v"])] for r in load("receipts") if r["Received Date"]),
    "wh": {
        "rates": [[r["Service / Process"], num(r["ship"]), num(r["incr"])] for r in load("wh_rates") if r["ship"] and r["incr"]],
        "terms": sorted(([num(r["row"]), r["section"], r["item"], r["detail"]] for r in load("wh_terms")), key=lambda x: x[0]),
    },
    "totals": {k: num(v) if k != "x" else v for k, v in load("totals")[0].items()},
}

# Keep only cities that can reach a Top 10 under some filter choice, so the first download stays small
city = data["dims"]["city"]
keep = set()
for period in period_sets():
    totals = defaultdict(float)
    for m, k, s, _ in city["r"]:
        if m in period: totals[k] += s
    keep |= set(sorted((k for k in totals if totals[k] > 0), key=lambda k: (-totals[k], city["k"][k]))[:10])
remap = {old: new for new, old in enumerate(sorted(keep))}
data["dims"]["city"] = {"k": [city["k"][old] for old in sorted(keep)], "r": [[m, remap[k], s, u] for m, k, s, u in city["r"] if k in remap]}

# SKU tables load only on the pages that use them
sku_file = {"sku": data.pop("sku"), "detail": data.pop("detail")}
OUT.parent.mkdir(exist_ok=True)
leaks = []
for path, payload in ((OUT, data), (OUT.with_name("sku.json"), sku_file)):
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    upper = text.upper()
    leaks += [c for c in ranked if len(c) >= 5 and f'"{c}"' in upper or (len(c) >= 8 and c in upper)]
    print(f"{path.name} {len(text) // 1024} KB")
print(f"months {len(months)}, SKUs {len(names)}, SKU detail pages {len(detail)}, cities kept {len(keep)}, customers masked {len(masked)}")
print("names found:", leaks[:10] if leaks else "none")
