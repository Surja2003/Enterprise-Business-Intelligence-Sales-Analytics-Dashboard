"""Applies the audited model fixes to the TMDL definition. Idempotent: reads from the pristine copy in tools/_orig."""
import re, shutil, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEF = ROOT / "EnterpriseSalesBI.SemanticModel" / "definition"
ORIG = ROOT / "tools" / "_orig"
if not ORIG.exists():
    shutil.copytree(DEF, ORIG)

read = lambda rel: (ORIG / rel).read_text(encoding="utf-8")
def write(rel, text):
    p = DEF / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")

def guid():
    return str(uuid.uuid4())

# ---------------------------------------------------------------- Power Query -------------------------------
def replace_m(tmdl, new_m):
    """Swap the M source of a table's partition, keeping everything around it."""
    start = tmdl.index("\t\tsource =")
    end = tmdl.index("\tannotation PBI_ResultType", start)
    body = "\n".join("\t\t\t\t" + l if l else "" for l in new_m.strip("\n").split("\n"))
    return tmdl[:start] + "\t\tsource = ```\n" + body + "\n\t\t\t\t```\n\n" + tmdl[end:]

INTL_M = r'''
let
    Source = Csv.Document(File.Contents("C:\Data\SalesBI\International sale Report.csv"),[Delimiter=",", Columns=10, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Typed Index" = Table.TransformColumnTypes(#"Promoted Headers",{{"index", Int64.Type}}),
    // The CSV stacks several exports. Rows 0-10195 and 15892-18634 are the true ledger.
    // 10196-15891 repeat 4500-10195 exactly (verified row by row); 18635-19675 are a stray stock list;
    // 19676 onward is a re-export with shifted columns, no Size and no Apr-May 2022.
    #"Kept Ledger Rows" = Table.SelectRows(#"Typed Index", each [index] <= 10195 or ([index] >= 15892 and [index] <= 18634)),
    #"Removed Columns" = Table.RemoveColumns(#"Kept Ledger Rows",{"index"}),
    #"Changed Type" = Table.TransformColumnTypes(#"Removed Columns",{{"DATE", type date}, {"Months", type text}, {"CUSTOMER", type text}, {"Style", type text}, {"SKU", type text}, {"Size", type text}, {"PCS", Int64.Type}, {"RATE", type number}, {"GROSS AMT", type number}}, "en-US"),
    #"Cleaned Text" = Table.TransformColumns(#"Changed Type",{{"CUSTOMER", each Text.Upper(Text.Clean(Text.Trim(_))), type text}, {"Style", each Text.Upper(Text.Clean(Text.Trim(_))), type text}, {"SKU", each Text.Upper(Text.Clean(Text.Trim(_))), type text}, {"Size", each Text.Upper(Text.Clean(Text.Trim(_))), type text}, {"Months", each Text.Clean(Text.Trim(_)), type text}}),
    ValidSizes = {"XS","S","M","L","XL","XXL","XXXL","4XL","5XL","6XL","FREE"},
    #"Added Final Size" = Table.AddColumn(#"Cleaned Text", "Final Size", each [Size], type text),
    #"Added Size Category" = Table.AddColumn(#"Added Final Size", "Size Category", each if [Size] = "" then "Blank" else if List.Contains(ValidSizes, [Size]) then "Clothing Size" else "Non-Size Entry", type text),
    #"Added Corrected Size" = Table.AddColumn(#"Added Size Category", "Corrected Size", each [Size], type text),
    #"Added SKU Size" = Table.AddColumn(#"Added Corrected Size", "SKU Size", each let last = List.Last(Text.Split([SKU], "-")) in if List.Contains(ValidSizes, last) then last else null, type nullable text),
    #"Added Final Corrected" = Table.AddColumn(#"Added SKU Size", "Final Corrected Size", each if [SKU Size] <> null then [SKU Size] else [Corrected Size], type text),
    #"Added Final Category" = Table.AddColumn(#"Added Final Corrected", "Final Size Category", each if [SKU Size] <> null then "Clothing Size" else [Size Category], type text),
    #"Added Calculated Gross" = Table.AddColumn(#"Added Final Category", "Calculated Gross", each Number.Round([PCS] * [RATE], 0), type number),
    #"Added Amount Difference" = Table.AddColumn(#"Added Calculated Gross", "Amount Difference", each [GROSS AMT] - [Calculated Gross], type number),
    #"Added Difference Pct" = Table.AddColumn(#"Added Amount Difference", "Difference %", each if [Calculated Gross] = 0 then null else Number.Round(([GROSS AMT] - [Calculated Gross]) / [Calculated Gross] * 100, 2), type nullable number),
    #"Added Implied Discount" = Table.AddColumn(#"Added Difference Pct", "Implied Discount %", each if [Calculated Gross] = 0 then null else Number.Round(([Calculated Gross] - [GROSS AMT]) / [Calculated Gross] * 100, 2), type nullable number),
    #"Added SKU_Key" = Table.AddColumn(#"Added Implied Discount", "SKU_Key", each if [SKU] = "" then null else Text.TrimEnd([SKU], "."), type nullable text)
in
    #"Added SKU_Key"
'''

def fix_international():
    t = replace_m(read("tables/International sale Report.tmdl"), INTL_M)
    # DATE becomes a true date so the DimDate relationship actually matches
    t = t.replace("\tcolumn DATE\n\t\tdataType: string\n", "\tcolumn DATE\n\t\tdataType: dateTime\n\t\tformatString: Long Date\n")
    t = t.replace("\t\tsourceColumn: DATE\n\n\t\tannotation SummarizationSetBy = Automatic\n",
                  "\t\tsourceColumn: DATE\n\n\t\tannotation SummarizationSetBy = Automatic\n\n\t\tannotation UnderlyingDateTimeDataType = Date\n", 1)
    for col in ["Calculated Gross", "Amount Difference", "Difference %", "Implied Discount %"]:
        t = re.sub(rf"(\tcolumn '{re.escape(col)}'\n\t\t)dataType: string", r"\1dataType: double", t)
    write("tables/International sale Report.tmdl", t)

STATE_MAP = {"RJ": "RAJASTHAN", "RAJSHTHAN": "RAJASTHAN", "RAJSTHAN": "RAJASTHAN", "ORISSA": "ODISHA", "NEW DELHI": "DELHI",
             "PB": "PUNJAB", "PUNJAB/MOHALI/ZIRAKPUR": "PUNJAB", "AR": "ARUNACHAL PRADESH", "NL": "NAGALAND", "PONDICHERRY": "PUDUCHERRY"}

def fix_amazon():
    t = read("tables/Amazon Sale Report.tmdl")
    start = t.index("\t\tsource =")
    end = t.index("\tannotation PBI_ResultType", start)
    m = "\n".join(l[4:] if l.startswith("\t\t\t\t") else l for l in t[start:end].split("\n")[1:])
    m = m.strip().strip("`").strip()
    m = m.replace("Encoding=1252", "Encoding=65001").replace("QuoteStyle.None", "QuoteStyle.Csv")
    state_rec = ", ".join(f'{{"{k}", "{v}"}}' for k, v in STATE_MAP.items())
    tail = (
        '    // All order statuses stay in the table; the sale policy lives in one column and the measures.\n'
        '    #"Added Status Group" = Table.AddColumn(#"Added Custom", "Status Group", each\n'
        '        if List.Contains({"Shipped", "Shipped - Delivered to Buyer"}, [Status]) then "Recognised Sale"\n'
        '        else if [Status] = "Cancelled" then "Cancelled"\n'
        '        else if List.Contains({"Shipped - Returned to Seller", "Shipped - Returning to Seller", "Shipped - Rejected by Buyer", "Shipped - Lost in Transit", "Shipped - Damaged"}, [Status]) then "Returned / Failed"\n'
        '        else "In Progress", type text),\n'
        f'    StateMap = {{{state_rec}}},\n'
        '    #"Added State Clean" = Table.AddColumn(#"Added Status Group", "State Clean", each if [#"ship-state"] = null then null else List.Accumulate(StateMap, [#"ship-state"], (s, p) => if s = p{0} then p{1} else s), type nullable text)\n'
        'in\n    #"Added State Clean"'
    )
    m = re.sub(r'    #"Filtered Rows" = Table\.SelectRows\(#"Added Custom".*', "", m, flags=re.S).rstrip().rstrip(",") + ",\n" + tail
    t = replace_m(t, m)
    cols = ""
    for c in ["Status Group", "State Clean"]:
        cols += f"\tcolumn '{c}'\n\t\tdataType: string\n\t\tlineageTag: {guid()}\n\t\tsummarizeBy: none\n\t\tsourceColumn: {c}\n\n\t\tannotation SummarizationSetBy = Automatic\n\n"
    t = t.replace("\tpartition 'Amazon Sale Report' = m", cols + "\tpartition 'Amazon Sale Report' = m")
    write("tables/Amazon Sale Report.tmdl", t)

def fix_expense():
    t = read("tables/Expense IIGF.tmdl")
    t = t.replace("QuoteStyle=QuoteStyle.None", "QuoteStyle=QuoteStyle.Csv").replace("Encoding=1252", "Encoding=65001")
    old = '\t\t\t\t    #"Removed Columns" = Table.RemoveColumns(#"Changed Type2",{"index"})\n\t\t\t\tin\n\t\t\t\t    #"Removed Columns"'
    new = ('\t\t\t\t    #"Removed Columns" = Table.RemoveColumns(#"Changed Type2",{"index"}),\n'
           '\t\t\t\t    // The sheet ends with a subtotal row (blank particular, 8095) and a "Pending Amount" balancing row (-3095). Neither is an expense.\n'
           '\t\t\t\t    #"Removed Summary Rows" = Table.SelectRows(#"Removed Columns", each [Expense Particular] <> null and Text.Trim([Expense Particular]) <> "" and Text.Trim([Expense Particular]) <> "Pending Amount")\n'
           '\t\t\t\tin\n\t\t\t\t    #"Removed Summary Rows"')
    assert old in t
    write("tables/Expense IIGF.tmdl", t.replace(old, new))

def fix_warehouse():
    t = read("tables/Cloud Warehouse Compersion Chart.tmdl").replace("QuoteStyle=QuoteStyle.None", "QuoteStyle=QuoteStyle.Csv")
    old = '\t\t\t\t    #"Removed Top Rows" = Table.Skip(#"Renamed Columns",1)\n\t\t\t\tin\n\t\t\t\t    #"Removed Top Rows"'
    assert old in t
    lines = [
        '#"Removed Top Rows" = Table.Skip(#"Renamed Columns",1),',
        '// The source mixes a rate table with an indented scope-of-work list. Keep the raw columns, add a readable shape.',
        'Clean = (v) => if v = null then "" else Text.Combine(List.Select(Text.Split(Text.Trim(v), " "), each _ <> ""), " "),',
        '#"Added Row" = Table.AddIndexColumn(#"Removed Top Rows", "Row", 1, 1, Int64.Type),',
        '#"Added Section" = Table.AddColumn(#"Added Row", "Section", each if [Row] <= 4 then "Rates" else if Clean([#"Service / Process"]) = "" then null else Clean([#"Service / Process"]), type nullable text),',
        '#"Filled Section" = Table.FillDown(#"Added Section", {"Section"}),',
        '#"Added Item" = Table.AddColumn(#"Filled Section", "Item", each Clean([#"Shiprocket Price / Details"]), type text),',
        '#"Added Detail" = Table.AddColumn(#"Added Item", "Detail", each Clean([#"INCREFF Price / Details"]), type text),',
        '#"Removed Blank Rows" = Table.SelectRows(#"Added Detail", each [Item] <> "" or [Detail] <> "")',
    ]
    new = "\n".join("\t\t\t\t    " + l for l in lines) + '\n\t\t\t\tin\n\t\t\t\t    #"Removed Blank Rows"'
    t = t.replace(old, new)
    cols = f"\tcolumn Row\n\t\tdataType: int64\n\t\tformatString: 0\n\t\tlineageTag: {guid()}\n\t\tsummarizeBy: none\n\t\tsourceColumn: Row\n\n\t\tannotation SummarizationSetBy = Automatic\n\n"
    for c in ["Section", "Item", "Detail"]:
        cols += f"\tcolumn {c}\n\t\tdataType: string\n\t\tlineageTag: {guid()}\n\t\tsummarizeBy: none\n\t\tsourceColumn: {c}\n\n\t\tannotation SummarizationSetBy = Automatic\n\n"
    t = t.replace("\tpartition 'Cloud Warehouse Compersion Chart' = m", cols + "\tpartition 'Cloud Warehouse Compersion Chart' = m")
    write("tables/Cloud Warehouse Compersion Chart.tmdl", t)

def fix_dimdate():
    t = read("tables/DimDate.tmdl")
    t = t.replace("DATE(2020, 1, 1)", "DATE(2021, 1, 1)").replace("DATE(2026, 12, 31)", "DATE(2022, 12, 31)")
    t = t.replace('"Year Month Sort", YEAR([Date]) * 100 + MONTH([Date])', '"Year Month Sort", YEAR([Date]) * 100 + MONTH([Date]),\n\t\t\t\t    "Day Of Week", WEEKDAY([Date], 2)')
    t = t.replace("formatString: General Date", "formatString: dd mmm yyyy")
    t = t.replace("\tcolumn Month\n\t\tlineageTag: 0a9c3f92-13e5-4d15-a615-7f68f78a9ff7\n\t\tsummarizeBy: none\n\t\tisNameInferred\n\t\tsourceColumn: [Month]\n",
                  "\tcolumn Month\n\t\tlineageTag: 0a9c3f92-13e5-4d15-a615-7f68f78a9ff7\n\t\tsummarizeBy: none\n\t\tisNameInferred\n\t\tsourceColumn: [Month]\n\t\tsortByColumn: 'Month Number'\n")
    t = t.replace("\t\tsourceColumn: [Day Name]\n", "\t\tsourceColumn: [Day Name]\n\t\tsortByColumn: 'Day Of Week'\n")
    for c in ["Year", "Month Number", "Week Number", "Day", "Year Month Sort"]:   # keys are not additive
        t = re.sub(rf"(sourceColumn: \[{c}\])", r"\1", t)
    t = t.replace("summarizeBy: sum", "summarizeBy: none")
    add = f"\tcolumn 'Day Of Week'\n\t\tformatString: 0\n\t\tisHidden\n\t\tlineageTag: {guid()}\n\t\tsummarizeBy: none\n\t\tisNameInferred\n\t\tsourceColumn: [Day Of Week]\n\n\t\tannotation SummarizationSetBy = Automatic\n\n"
    t = t.replace("\tpartition DimDate = calculated", add + "\tpartition DimDate = calculated")
    write("tables/DimDate.tmdl", t)

def calc_table(name, cols, source):
    q = f"'{name}'" if re.search(r"\W", name) else name
    s = f"table {q}\n\tlineageTag: {guid()}\n\n"
    for c in cols:
        s += f"\tcolumn '{c['name']}'\n"
        if c.get("fmt"): s += f"\t\tformatString: {c['fmt']}\n"
        if c.get("hidden"): s += "\t\tisHidden\n"
        s += f"\t\tlineageTag: {guid()}\n\t\tsummarizeBy: none\n"
        s += "\t\tisNameInferred\n" if c.get("inferred", True) else ""
        s += f"\t\tsourceColumn: [{c.get('src', c['name'])}]\n"
        if c.get("sort"): s += f"\t\tsortByColumn: '{c['sort']}'\n"
        if c.get("group"): s += f"\n\t\trelatedColumnDetails\n\t\t\tgroupByColumn: '{c['group']}'\n"
        if c.get("ext"): s += f"\n\t\textendedProperty ParameterMetadata = {c['ext']}\n"
        s += "\n\t\tannotation SummarizationSetBy = Automatic\n\n"
    body = "\n".join("\t\t\t\t" + l for l in source.strip().split("\n"))
    s += f"\tpartition {q} = calculated\n\t\tmode: import\n\t\tsource = ```\n{body}\n\t\t\t\t```\n\n\tannotation PBI_Id = {uuid.uuid4().hex}\n"
    write(f"tables/{name}.tmdl", s)

def fix_dimsku():
    # DAX TRIM also collapses inner double spaces, so one Amazon SKU key stopped matching. The source columns are already trimmed.
    path = "tables/DimSKU.tmdl"
    t = (ORIG / path).read_text(encoding="utf-8")
    assert t.count("UPPER(TRIM(") == 5
    t = t.replace("UPPER(TRIM(", "UPPER(").replace(' & ""))', ' & "")')
    write(path, t)

def helper_tables():
    calc_table("Segment", [dict(name="Segment", sort="Segment Order"), dict(name="Segment Order", fmt="0", hidden=True)],
               'DATATABLE("Segment", STRING, "Segment Order", INTEGER, {{"Amazon", 1}, {"International", 2}})')
    calc_table("Marketplace", [dict(name="Marketplace", sort="Marketplace Order"), dict(name="Marketplace Order", fmt="0", hidden=True)],
               'DATATABLE("Marketplace", STRING, "Marketplace Order", INTEGER, {{"Amazon", 1}, {"Amazon FBA", 2}, {"Flipkart", 3}, {"Myntra", 4}, {"Ajio", 5}, {"Snapdeal", 6}, {"Paytm", 7}, {"Limeroad", 8}})')
    calc_table("Trend Grain", [
        dict(name="Trend Grain", src="Value1", inferred=False, sort="Trend Grain Order", group="Trend Grain Fields"),
        dict(name="Trend Grain Fields", src="Value2", inferred=False, hidden=True, sort="Trend Grain Order", ext='{"version":3,"kind":2}'),
        dict(name="Trend Grain Order", src="Value3", inferred=False, hidden=True, fmt="0"),
    ], '{\n    ("Month", NAMEOF(\'DimDate\'[Month Year]), 0),\n    ("Quarter", NAMEOF(\'DimDate\'[Year Quarter]), 1),\n    ("Year", NAMEOF(\'DimDate\'[Year]), 2),\n    ("Day", NAMEOF(\'DimDate\'[Date]), 3)\n}')
    m = read("model.tmdl").replace("ref table _Measures\n", "ref table _Measures\nref table Segment\nref table Marketplace\nref table 'Trend Grain'\n")
    write("model.tmdl", m)

# ---------------------------------------------------------------- Measures ----------------------------------
AMZ = "'Amazon Sale Report'"
INT = "'International sale Report'"
SALE = "'Sale Report'"
MAY = "'May-2022'"
PL = "'PL_March_2021'"
EXP = "'Expense IIGF'"
INR = r"\₹#,0"
INR2 = r"\₹#,0.00"
PCT = "0.0%;-0.0%;0.0%"
INTF = "#,0"
M = {}  # name -> (expr, folder, format, category)

def add(name, expr, folder, fmt=None, cat=None):
    M[name] = (expr.strip(), folder, fmt, cat)

def big(v):
    return (f'IF(ISBLANK({v}), "—", IF(ABS({v}) >= 1000000, FORMAT({v} / 1000000, "0.0") & "M", '
            f'IF(ABS({v}) >= 1000, FORMAT({v} / 1000, "0.0") & "K", FORMAT({v}, "#,0"))))')

def status(cond):
    return f"{AMZ}[Status Group] = \"{cond}\""

# Amazon -------------------------------------------------------------------------------------------------------
F = "1. Amazon"
add("Amazon Revenue", f'CALCULATE(SUM({AMZ}[Amount]), {status("Recognised Sale")})', F, INR)
add("Amazon Units Sold", f'CALCULATE(SUM({AMZ}[Qty]), {status("Recognised Sale")})', F, INTF)
add("Amazon Orders", f'CALCULATE(DISTINCTCOUNT({AMZ}[Order ID]), {status("Recognised Sale")})', F, INTF)
add("Amazon All Orders", f"DISTINCTCOUNT({AMZ}[Order ID])", F, INTF)
add("Amazon Cancelled Orders", f'CALCULATE(DISTINCTCOUNT({AMZ}[Order ID]), {status("Cancelled")})', F, INTF)
add("Amazon Returned Orders", f'CALCULATE(DISTINCTCOUNT({AMZ}[Order ID]), {status("Returned / Failed")})', F, INTF)
add("Amazon In Progress Orders", f'CALCULATE(DISTINCTCOUNT({AMZ}[Order ID]), {status("In Progress")})', F, INTF)
add("Amazon Delivered Orders", f'CALCULATE(DISTINCTCOUNT({AMZ}[Order ID]), {AMZ}[Status] = "Shipped - Delivered to Buyer")', F, INTF)
add("Amazon Shipped Orders", f'CALCULATE(DISTINCTCOUNT({AMZ}[Order ID]), {AMZ}[Status] = "Shipped")', F, INTF)
add("Amazon Cancellation Rate %", "DIVIDE([Amazon Cancelled Orders], [Amazon All Orders])", F, PCT)
add("Amazon Return Rate %", "DIVIDE([Amazon Returned Orders], [Amazon All Orders])", F, PCT)
add("Amazon Cancelled Value", f'CALCULATE(SUM({AMZ}[Amount]), {status("Cancelled")})', F, INR)
add("Amazon Order Value", f"SUM({AMZ}[Amount])", F, INR)
add("Amazon Average Order Value", "DIVIDE([Amazon Revenue], [Amazon Orders])", F, INR)
add("Amazon Average Selling Price", "DIVIDE([Amazon Revenue], [Amazon Units Sold])", F, INR)
add("Amazon Revenue Previous Month", "CALCULATE([Amazon Revenue], DATEADD(DimDate[Date], -1, MONTH))", F, INR)
add("Amazon Trading Days", f'CALCULATE(DISTINCTCOUNT({AMZ}[Date]), {status("Recognised Sale")})', F, INTF)
add("Amazon Revenue MoM %", """
VAR PrevDays = CALCULATE([Amazon Trading Days], DATEADD(DimDate[Date], -1, MONTH))
RETURN
    IF(
        HASONEVALUE(DimDate[Year Month Sort]) && PrevDays >= 20 && NOT ISBLANK([Amazon Revenue]),
        DIVIDE([Amazon Revenue] - [Amazon Revenue Previous Month], [Amazon Revenue Previous Month])
    )
""", F, PCT)
add("Amazon Latest Month MoM %", f"""
VAR LatestDay = CALCULATE(MAX({AMZ}[Date]), {status("Recognised Sale")})
VAR CurrentSales = CALCULATE([Amazon Revenue], DATESBETWEEN(DimDate[Date], EOMONTH(LatestDay, -1) + 1, EOMONTH(LatestDay, 0)))
VAR PriorSales = CALCULATE([Amazon Revenue], DATESBETWEEN(DimDate[Date], EOMONTH(LatestDay, -2) + 1, EOMONTH(LatestDay, -1)))
VAR PriorDays = CALCULATE([Amazon Trading Days], DATESBETWEEN(DimDate[Date], EOMONTH(LatestDay, -2) + 1, EOMONTH(LatestDay, -1)))
RETURN IF(PriorDays >= 20, DIVIDE(CurrentSales - PriorSales, PriorSales))
""", F, PCT)
add("Amazon Latest Month Per Day MoM %", f"""
VAR LatestDay = CALCULATE(MAX({AMZ}[Date]), {status("Recognised Sale")})
VAR CurrentRange = DATESBETWEEN(DimDate[Date], EOMONTH(LatestDay, -1) + 1, EOMONTH(LatestDay, 0))
VAR PriorRange = DATESBETWEEN(DimDate[Date], EOMONTH(LatestDay, -2) + 1, EOMONTH(LatestDay, -1))
VAR CurrentRate = DIVIDE(CALCULATE([Amazon Revenue], CurrentRange), CALCULATE([Amazon Trading Days], CurrentRange))
VAR PriorRate = DIVIDE(CALCULATE([Amazon Revenue], PriorRange), CALCULATE([Amazon Trading Days], PriorRange))
RETURN IF(NOT ISBLANK([Amazon Latest Month MoM %]), DIVIDE(CurrentRate - PriorRate, PriorRate))
""", F, "+0.0%;-0.0%;0.0%")
add("Amazon Latest Month Label", f"""
VAR LatestDay = CALCULATE(MAX({AMZ}[Date]), {status("Recognised Sale")})
RETURN FORMAT(LatestDay, "MMM yy") & " vs " & FORMAT(EOMONTH(LatestDay, -1), "MMM yy")
""", F)
add("Amazon Previous Year Sales", "CALCULATE([Amazon Revenue], DATEADD(DimDate[Date], -1, YEAR))", F, INR)
add("Amazon YoY Growth %", "DIVIDE([Amazon Revenue] - [Amazon Previous Year Sales], [Amazon Previous Year Sales])", F, PCT)
add("Amazon Sales Contribution %", 'DIVIDE([Amazon Revenue], [Amazon Revenue] + [International Revenue])', F, PCT)

# International ------------------------------------------------------------------------------------------------
F = "2. International"
add("International Revenue", f"SUM({INT}[GROSS AMT])", F, INR)
add("International Units", f"SUM({INT}[PCS])", F, INTF)
add("International Customers", f"DISTINCTCOUNT({INT}[CUSTOMER])", F, INTF)
add("International Average Rate", f"AVERAGE({INT}[RATE])", F, INR)
add("International Realised Value per Piece", "DIVIDE([International Revenue], [International Units])", F, INR)
add("International Listed Value", f"SUMX({INT}, {INT}[PCS] * {INT}[RATE])", F, INR)
add("International Discount vs Listed %", "DIVIDE([International Listed Value] - [International Revenue], [International Listed Value])", F, PCT)
add("International Revenue Previous Month", "CALCULATE([International Revenue], DATEADD(DimDate[Date], -1, MONTH))", F, INR)
add("International Revenue MoM %", """
IF(
    HASONEVALUE(DimDate[Year Month Sort]) && NOT ISBLANK([International Revenue]),
    DIVIDE([International Revenue] - [International Revenue Previous Month], [International Revenue Previous Month])
)
""", F, PCT)
add("International Peak Month Label", f"""
VAR Months = ADDCOLUMNS(VALUES(DimDate[Month Year]), "@v", [International Revenue])
RETURN MAXX(TOPN(1, FILTER(Months, NOT ISBLANK([@v])), [@v], DESC), DimDate[Month Year])
""", F)
add("International Previous Year Sales", "CALCULATE([International Revenue], DATEADD(DimDate[Date], -1, YEAR))", F, INR)
add("International YoY Growth %", "DIVIDE([International Revenue] - [International Previous Year Sales], [International Previous Year Sales])", F, PCT)
add("International Top Customer Share %", f"""
VAR Ranked = ADDCOLUMNS(VALUES({INT}[CUSTOMER]), "@v", [International Revenue])
RETURN DIVIDE(MAXX(Ranked, [@v]), [International Revenue])
""", F, PCT)
add("International Top Customer", f"""
VAR Ranked = ADDCOLUMNS(VALUES({INT}[CUSTOMER]), "@v", [International Revenue])
RETURN MAXX(TOPN(1, Ranked, [@v], DESC), {INT}[CUSTOMER])
""", F)

# Combined -----------------------------------------------------------------------------------------------------
F = "3. Combined"
add("Total Recorded Sales", """
VAR A = IF("Amazon" IN VALUES(Segment[Segment]), [Amazon Revenue])
VAR I = IF("International" IN VALUES(Segment[Segment]), [International Revenue])
RETURN A + I
""", F, INR)
add("Total Recorded Units", """
VAR A = IF("Amazon" IN VALUES(Segment[Segment]), [Amazon Units Sold])
VAR I = IF("International" IN VALUES(Segment[Segment]), [International Units])
RETURN A + I
""", F, INTF)
add("Segment Sales", """
SWITCH(
    SELECTEDVALUE(Segment[Segment]),
    "Amazon", [Amazon Revenue],
    "International", [International Revenue],
    [Total Recorded Sales]
)
""", F, INR)
add("Amazon Sales Share %", "DIVIDE([Amazon Revenue], [Amazon Revenue] + [International Revenue])", F, PCT)
add("International Sales Share %", "DIVIDE([International Revenue], [Amazon Revenue] + [International Revenue])", F, PCT)
add("Net Profit Status", '"Not Available - COGS Data Required"', F)
add("Period Label", f"""
VAR A1 = CALCULATE(MIN({AMZ}[Date]))
VAR I1 = CALCULATE(MIN({INT}[DATE]))
VAR A2 = CALCULATE(MAX({AMZ}[Date]))
VAR I2 = CALCULATE(MAX({INT}[DATE]))
VAR Seg = IF(HASONEVALUE(Segment[Segment]), VALUES(Segment[Segment]), "Amazon + International")
VAR D1 = SWITCH(Seg, "Amazon", A1, "International", I1, IF(ISBLANK(A1), I1, IF(ISBLANK(I1), A1, MIN(A1, I1))))
VAR D2 = SWITCH(Seg, "Amazon", A2, "International", I2, IF(ISBLANK(A2), I2, IF(ISBLANK(I2), A2, MAX(A2, I2))))
RETURN IF(ISBLANK(D1), "No data in selection", Seg & "  ·  " & FORMAT(D1, "d MMM yyyy") & " to " & FORMAT(D2, "d MMM yyyy"))
""", F)

# Time intelligence --------------------------------------------------------------------------------------------
F = "4. Time Intelligence"
add("Total Sales Previous Month", "CALCULATE([Total Recorded Sales], DATEADD(DimDate[Date], -1, MONTH))", F, INR)
add("Total Sales MoM %", "IF(HASONEVALUE(DimDate[Year Month Sort]) && NOT ISBLANK([Total Recorded Sales]), DIVIDE([Total Recorded Sales] - [Total Sales Previous Month], [Total Sales Previous Month]))", F, PCT)
add("Total Sales Previous Year", "CALCULATE([Total Recorded Sales], DATEADD(DimDate[Date], -1, YEAR))", F, INR)
add("Total Sales YoY %", "DIVIDE([Total Recorded Sales] - [Total Sales Previous Year], [Total Sales Previous Year])", F, PCT)
add("Total Sales YTD", "TOTALYTD([Total Recorded Sales], DimDate[Date])", F, INR)
add("Total Sales QTD", "TOTALQTD([Total Recorded Sales], DimDate[Date])", F, INR)
add("Total Sales MTD", "TOTALMTD([Total Recorded Sales], DimDate[Date])", F, INR)
add("Total Sales Running Total", """
VAR LastVisible = MAX(DimDate[Date])
RETURN CALCULATE([Total Recorded Sales], FILTER(ALLSELECTED(DimDate[Date]), DimDate[Date] <= LastVisible))
""", F, INR)

# Product ------------------------------------------------------------------------------------------------------
F = "5. Product"
def style_rank(tbl, measure, direction):
    return f"""
IF(
    ISINSCOPE({tbl}[Style]) && {measure} > 0,
    ROWNUMBER(
        FILTER(ALLSELECTED({tbl}[Style]), {measure} > 0),
        ORDERBY({measure}, {direction}, {tbl}[Style], ASC)
    )
)
"""
add("Amazon Style Rank", style_rank(AMZ, "[Amazon Revenue]", "DESC"), F, "0")
add("Amazon Style Units Rank", style_rank(AMZ, "[Amazon Units Sold]", "DESC"), F, "0")
add("Amazon Style Low Rank", style_rank(AMZ, "[Amazon Revenue]", "ASC"), F, "0")
add("International Style Rank", style_rank(INT, "[International Revenue]", "DESC"), F, "0")
add("International Style Low Rank", style_rank(INT, "[International Revenue]", "ASC"), F, "0")
add("Top 10 Style Sales", "VAR R = [Amazon Style Rank] RETURN IF(NOT ISBLANK(R) && R <= 10, [Amazon Revenue])", F, INR)
add("Top 10 Style Units", "VAR R = [Amazon Style Units Rank] RETURN IF(NOT ISBLANK(R) && R <= 10, [Amazon Units Sold])", F, INTF)
add("Low 10 Style Sales", "VAR R = [Amazon Style Low Rank] RETURN IF(NOT ISBLANK(R) && R <= 10, [Amazon Revenue])", F, INR)
add("Low 10 Style Units", "VAR R = [Amazon Style Low Rank] RETURN IF(NOT ISBLANK(R) && R <= 10, [Amazon Units Sold])", F, INTF)
add("International Top 10 Style Sales", "VAR R = [International Style Rank] RETURN IF(NOT ISBLANK(R) && R <= 10, [International Revenue])", F, INR)
add("International Low 10 Style Sales", "VAR R = [International Style Low Rank] RETURN IF(NOT ISBLANK(R) && R <= 10, [International Revenue])", F, INR)
add("International Low 10 Style Units", "VAR R = [International Style Low Rank] RETURN IF(NOT ISBLANK(R) && R <= 10, [International Units])", F, INTF)
add("Amazon Styles With Sales", f"COUNTROWS(FILTER(VALUES({AMZ}[Style]), [Amazon Revenue] > 0))", F, INTF)
add("Top 10 Style Share %", f"""
VAR Top10 = TOPN(10, VALUES({AMZ}[Style]), [Amazon Revenue], DESC)
RETURN DIVIDE(CALCULATE([Amazon Revenue], Top10), [Amazon Revenue])
""", F, PCT)
add("Top Style Name", f"""
VAR Top1 = TOPN(1, VALUES({AMZ}[Style]), [Amazon Revenue], DESC, {AMZ}[Style], ASC)
RETURN MAXX(Top1, {AMZ}[Style])
""", F)
add("Top Product Revenue", f"MAXX(VALUES({AMZ}[Style]), [Amazon Revenue])", F, INR)
add("Top Product Units", f"MAXX(VALUES({AMZ}[Style]), [Amazon Units Sold])", F, INTF)
add("Top State Name", f"""
VAR Top1 = TOPN(1, FILTER(VALUES({AMZ}[State Clean]), NOT ISBLANK({AMZ}[State Clean])), [Amazon Revenue], DESC)
RETURN MAXX(Top1, {AMZ}[State Clean])
""", F)
add("Top State Share %", f"""
VAR Top1 = TOPN(1, FILTER(VALUES({AMZ}[State Clean]), NOT ISBLANK({AMZ}[State Clean])), [Amazon Revenue], DESC)
RETURN DIVIDE(CALCULATE([Amazon Revenue], Top1), [Amazon Revenue])
""", F, PCT)
add("Top 10 State Sales", f"""
VAR R = IF(ISINSCOPE({AMZ}[State Clean]) && [Amazon Revenue] > 0,
    ROWNUMBER(FILTER(ALLSELECTED({AMZ}[State Clean]), [Amazon Revenue] > 0 && NOT ISBLANK({AMZ}[State Clean])), ORDERBY([Amazon Revenue], DESC, {AMZ}[State Clean], ASC)))
RETURN IF(NOT ISBLANK(R) && R <= 10, [Amazon Revenue])
""", F, INR)
add("Top 10 City Sales", f"""
VAR R = IF(ISINSCOPE({AMZ}[ship-city]) && [Amazon Revenue] > 0,
    ROWNUMBER(FILTER(ALLSELECTED({AMZ}[ship-city]), [Amazon Revenue] > 0 && NOT ISBLANK({AMZ}[ship-city])), ORDERBY([Amazon Revenue], DESC, {AMZ}[ship-city], ASC)))
RETURN IF(NOT ISBLANK(R) && R <= 10, [Amazon Revenue])
""", F, INR)
add("Top 10 Customer Sales", f"""
VAR R = IF(ISINSCOPE({INT}[CUSTOMER]) && [International Revenue] > 0,
    ROWNUMBER(FILTER(ALLSELECTED({INT}[CUSTOMER]), [International Revenue] > 0), ORDERBY([International Revenue], DESC, {INT}[CUSTOMER], ASC)))
RETURN IF(NOT ISBLANK(R) && R <= 10, [International Revenue])
""", F, INR)
add("Top 10 Intl SKU Sales", f"""
VAR R = IF(ISINSCOPE(DimSKU[SKU_Key]) && [International Revenue] > 0,
    ROWNUMBER(FILTER(ALLSELECTED(DimSKU[SKU_Key]), [International Revenue] > 0 && DimSKU[SKU_Key] <> ""), ORDERBY([International Revenue], DESC, DimSKU[SKU_Key], ASC)))
RETURN IF(NOT ISBLANK(R) && R <= 10, [International Revenue])
""", F, INR)

# Inventory ----------------------------------------------------------------------------------------------------
F = "6. Inventory"
add("Selected SKU", 'IF(HASONEVALUE(DimSKU[SKU_Key]), VALUES(DimSKU[SKU_Key]), "All SKUs. Right-click a SKU to drill through")', F)
add("SKU Amazon Sales Share %", "DIVIDE([Amazon Revenue], CALCULATE([Amazon Revenue], REMOVEFILTERS(DimSKU)))", F, "0.00%")
def first_text(*cols):
    expr = '""'
    for c in reversed(cols):
        expr = f'VAR _V = MAX({c}) RETURN IF(LEN(_V) > 0, _V, {expr})'
    return expr
add("SKU Category", first_text(f"{AMZ}[Category]", f"{SALE}[Category]"), F)
add("SKU Style", first_text(f"{AMZ}[Style]", f"{INT}[Style]"), F)
add("SKU Size", first_text(f"{AMZ}[Size]", f"{SALE}[Size]", f"{INT}[Final Size]"), F)
add("SKU Colour", first_text(f"{SALE}[Color]"), F)
add("SKU Attributes", """
IF(HASONEVALUE(DimSKU[SKU_Key]),
    "SKU DETAIL" &
    IF(LEN([SKU Category]) > 0, "  ·  " & UPPER([SKU Category])) &
    IF(LEN([SKU Style]) > 0, "  ·  STYLE " & [SKU Style]) &
    IF(LEN([SKU Size]) > 0, "  ·  SIZE " & [SKU Size]) &
    IF(LEN([SKU Colour]) > 0, "  ·  " & UPPER([SKU Colour])),
    "SKU DETAIL")
""", F)
add("Unique Catalog SKUs", f"DISTINCTCOUNT({SALE}[SKU_Key])", F, INTF)
add("Unique Amazon SKUs", f"DISTINCTCOUNT({AMZ}[SKU_Key])", F, INTF)
add("Total Stock", f"SUM({SALE}[Stock])", F, INTF)
add("Matched Amazon SKUs", f"COUNTROWS(INTERSECT(VALUES({AMZ}[SKU_Key]), VALUES({SALE}[SKU_Key])))", F, INTF)
add("Unmatched Amazon SKUs", "[Unique Amazon SKUs] - [Matched Amazon SKUs]", F, INTF)
add("SKU Match Coverage %", "DIVIDE([Matched Amazon SKUs], [Unique Amazon SKUs])", F, PCT)
add("Units Sold on Matched SKUs", f"CALCULATE([Amazon Units Sold], TREATAS(VALUES({SALE}[SKU_Key]), {AMZ}[SKU_Key]))", F, INTF)
add("Stock Category Rank", f"""
IF(
    ISINSCOPE({SALE}[Category]) && [Total Stock] > 0,
    ROWNUMBER(FILTER(ALLSELECTED({SALE}[Category]), [Total Stock] > 0 && NOT ISBLANK({SALE}[Category])), ORDERBY([Total Stock], DESC, {SALE}[Category], ASC))
)
""", F, "0")
add("Top 8 Category Stock", "VAR R = [Stock Category Rank] RETURN IF(NOT ISBLANK(R) && R <= 8, [Total Stock])", F, INTF)
add("Top 8 Category Units", "VAR R = [Stock Category Rank] RETURN IF(NOT ISBLANK(R) && R <= 8, [Units Sold on Matched SKUs])", F, INTF)
add("Top 15 SKU Units", """
VAR R = IF(ISINSCOPE(DimSKU[SKU_Key]) && [Amazon Units Sold] > 0,
    ROWNUMBER(FILTER(ALLSELECTED(DimSKU[SKU_Key]), [Amazon Units Sold] > 0), ORDERBY([Amazon Units Sold], DESC, DimSKU[SKU_Key], ASC)))
RETURN IF(NOT ISBLANK(R) && R <= 15, [Amazon Units Sold])
""", F, INTF)

add("Top 15 SKU Sales", "IF(NOT ISBLANK([Top 15 SKU Units]), [Amazon Revenue])", F, INR)
add("Top 15 SKU Stock", "IF(NOT ISBLANK([Top 15 SKU Units]), [Total Stock])", F, INTF)
add("Top 10 Color Stock", f"""
VAR R = IF(ISINSCOPE({SALE}[Color]) && [Total Stock] > 0,
    ROWNUMBER(FILTER(ALLSELECTED({SALE}[Color]), [Total Stock] > 0 && NOT ISBLANK({SALE}[Color])), ORDERBY([Total Stock], DESC, {SALE}[Color], ASC)))
RETURN IF(NOT ISBLANK(R) && R <= 10, [Total Stock])
""", F, INTF)

# Pricing ------------------------------------------------------------------------------------------------------
F = "7. Pricing"
MP = {"Amazon": "Amazon MRP", "Amazon FBA": "Amazon FBA MRP", "Flipkart": "Flipkart MRP", "Myntra": "Myntra MRP",
      "Ajio": "Ajio MRP", "Snapdeal": "Snapdeal MRP", "Paytm": "Paytm MRP", "Limeroad": "Limeroad MRP"}
for mk in ["Amazon", "Flipkart", "Myntra", "Ajio", "Snapdeal", "Paytm"]:
    add(f"Avg {mk} MRP", f"AVERAGE({MAY}[{MP[mk]}])", F, INR)
add("Avg Amazon MRP Mar2021", f"AVERAGE({PL}[Amazon MRP])", F, INR)
def mp_switch(tbl, fn):
    arms = ",\n    ".join(f'"{k}", {fn}({tbl}[{v}])' for k, v in MP.items())
    return f"SWITCH(\n    SELECTEDVALUE(Marketplace[Marketplace]),\n    {arms}\n)"
add("Marketplace Avg MRP May 2022", mp_switch(MAY, "AVERAGE"), F, INR)
add("Marketplace Avg MRP Mar 2021", mp_switch(PL, "AVERAGE"), F, INR)
add("Marketplace Min MRP", mp_switch(MAY, "MIN"), F, INR)
add("Marketplace Max MRP", mp_switch(MAY, "MAX"), F, INR)
add("Marketplace Priced Products", mp_switch(MAY, "COUNT"), F, INTF)
add("Marketplace Coverage %", f"DIVIDE([Marketplace Priced Products], COUNTROWS({MAY}))", F, PCT)
LIST8 = ", ".join(f"{MAY}[{v}]" for v in MP.values())
SPREAD = "VAR Prices = {" + LIST8 + "} VAR Valid = FILTER(Prices, NOT ISBLANK([Value])) RETURN MAXX(Valid, [Value]) - MINX(Valid, [Value])"
add("Marketplace Selected", 'IF(HASONEVALUE(Marketplace[Marketplace]), VALUES(Marketplace[Marketplace]), "All marketplaces")', F)
MP_ROW = "SWITCH(SELECTEDVALUE(Marketplace[Marketplace]), " + ", ".join(f'"{k}", {MAY}[{v}]' for k, v in MP.items()) + ")"
PRICE_VARS = "VAR P = " + MP_ROW + " VAR Prices = {" + LIST8 + "} VAR Valid = FILTER(Prices, NOT ISBLANK([Value])) VAR Hi = MAXX(Valid, [Value]) VAR Lo = MINX(Valid, [Value])"
add("Marketplace Highest MRP Products", f"0 + COUNTROWS(FILTER({MAY}, {PRICE_VARS} RETURN NOT ISBLANK(P) && Hi > Lo && P = Hi))", F, INTF)
add("Marketplace Lowest MRP Products", f"0 + COUNTROWS(FILTER({MAY}, {PRICE_VARS} RETURN NOT ISBLANK(P) && Hi > Lo && P = Lo))", F, INTF)
add("Product Lowest MRP", f"IF(HASONEVALUE({MAY}[Sku]), MAXX({MAY}, {PRICE_VARS} RETURN Lo))", F, INR)
add("Marketplace Product Gap", f"IF(HASONEVALUE({MAY}[Sku]), MAXX({MAY}, {PRICE_VARS} RETURN IF(NOT ISBLANK(P), P - Lo)))", F, INR)
add("Top 15 Marketplace Gap", f"""
VAR R = IF(ISINSCOPE({MAY}[Sku]) && [Marketplace Product Gap] > 0,
    ROWNUMBER(FILTER(ALLSELECTED({MAY}[Sku]), [Marketplace Product Gap] > 0), ORDERBY([Marketplace Product Gap], DESC, {MAY}[Sku], ASC)))
RETURN IF(NOT ISBLANK(R) && R <= 15, [Marketplace Product Gap])
""", F, INR)
add("Top 15 Marketplace MRP", "IF(NOT ISBLANK([Top 15 Marketplace Gap]), [Marketplace Avg MRP May 2022])", F, INR)
add("Top 15 Marketplace Lowest MRP", "IF(NOT ISBLANK([Top 15 Marketplace Gap]), [Product Lowest MRP])", F, INR)
add("All Marketplaces Avg MRP", "DIVIDE(" + " + ".join(f"SUM({MAY}[{v}])" for v in MP.values()) + ", " + " + ".join(f"COUNT({MAY}[{v}])" for v in MP.values()) + ")", F, INR)
add("Marketplace Avg vs All %", "DIVIDE([Marketplace Avg MRP May 2022] - [All Marketplaces Avg MRP], [All Marketplaces Avg MRP])", F, "+0.0%;-0.0%;0.0%")
add("Marketplace MRP Rank", "IF(HASONEVALUE(Marketplace[Marketplace]), RANKX(ALL(Marketplace[Marketplace]), [Marketplace Avg MRP May 2022], , DESC))", F, "0")
add("Products With Prices", f"CALCULATE(COUNTROWS({MAY}), NOT ISBLANK({MAY}[Amazon MRP]))", F, INTF)
add("Products With Price Variation", f"COUNTROWS(FILTER({MAY}, {SPREAD} > 0))", F, INTF)
add("Avg Price Spread", f"AVERAGEX(FILTER({MAY}, {SPREAD} > 0), {SPREAD})", F, INR)
add("Max Price Spread", f"MAXX({MAY}, {SPREAD})", F, INR)
add("Product Price Spread", f"""
IF(
    HASONEVALUE({MAY}[Sku]),
    MAXX({MAY}, {SPREAD})
)
""", F, INR)
add("Top 12 Price Spread", f"""
VAR R = IF(ISINSCOPE({MAY}[Sku]) && [Product Price Spread] > 0,
    ROWNUMBER(FILTER(ALLSELECTED({MAY}[Sku]), [Product Price Spread] > 0), ORDERBY([Product Price Spread], DESC, {MAY}[Sku], ASC)))
RETURN IF(NOT ISBLANK(R) && R <= 12, [Product Price Spread])
""", F, INR)
add("Top 12 Price Spread Amazon MRP", "IF(NOT ISBLANK([Top 12 Price Spread]), [Avg Amazon MRP])", F, INR)
add("Snapshot Price Changes", f"""
0 + COUNTROWS(
    FILTER(
        {MAY},
        VAR K = {MAY}[SKU_Key]
        VAR P = CALCULATE(MAX({PL}[Amazon MRP]), REMOVEFILTERS({PL}), {PL}[SKU_Key] = K)
        RETURN NOT ISBLANK({MAY}[Amazon MRP]) && NOT ISBLANK(P) && {MAY}[Amazon MRP] <> P
    )
)
""", F, INTF)

# Expense ------------------------------------------------------------------------------------------------------
F = "8. Cash and Expense"
add("Total Received Amount", f"SUM({EXP}[Received Amount])", F, INR)
add("Total Recorded Expenses", f"CALCULATE(SUM({EXP}[Expense Amount]), REMOVEFILTERS(DimDate))", F, INR)
add("Recorded Net Cash Position", "CALCULATE([Total Received Amount], REMOVEFILTERS(DimDate)) - [Total Recorded Expenses]", F, INR)
add("Largest Expense Name", f"""
VAR Top1 = TOPN(1, CALCULATETABLE(VALUES({EXP}[Expense Particular]), REMOVEFILTERS(DimDate)), [Total Recorded Expenses], DESC)
RETURN MAXX(Top1, {EXP}[Expense Particular])
""", F)

# Logistics ----------------------------------------------------------------------------------------------------
F = "9. Logistics"
WH = "'Cloud Warehouse Compersion Chart'"
PARSE = lambda col: f'IFERROR(VALUE(SUBSTITUTE(SELECTEDVALUE({WH}[{col}]), "₹", "")), BLANK())'
add("Shiprocket Rate", f"""
VAR S = {PARSE("Shiprocket Price / Details")}
VAR I = {PARSE("INCREFF Price / Details")}
RETURN IF(NOT ISBLANK(S) && NOT ISBLANK(I), S)
""", F, INR2)
add("Increff Rate", f"""
VAR S = {PARSE("Shiprocket Price / Details")}
VAR I = {PARSE("INCREFF Price / Details")}
RETURN IF(NOT ISBLANK(S) && NOT ISBLANK(I), I)
""", F, INR2)

# SVG visuals --------------------------------------------------------------------------------------------------
F = "SVG"
GOLD, TEAL, EMERALD, CORAL, PURPLE, GREY = "#D6AC58", "#58A6A6", "#65C99A", "#E77D67", "#956BC4", "#8A8A8A"
FONT = "font-family='Segoe UI, sans-serif'"

def encode(svg_var):
    return f'"data:image/svg+xml;utf8," & SUBSTITUTE(SUBSTITUTE({svg_var}, "%", "%25"), "#", "%23")'

def esc(v):
    return f'SUBSTITUTE({v}, "&", "and")'

def card(name, label, value, sub, color, spark=None, grain="DimDate[Year Month Sort]", sub_color=None, w=195, h=128, guard=None):
    """A KPI tile: label, value, context line, optional sparkline driven by the same filter context."""
    spark_vars, spark_svg = "", ""
    if spark:
        top, bottom, pad = h - 42, h - 12, 14
        spark_vars = f"""
VAR _Base = FILTER(VALUES({grain}), NOT ISBLANK({spark}))
VAR _Vals = ADDCOLUMNS(_Base, "@v", {spark}, "@i", RANKX(_Base, {grain}, , ASC))
VAR _N = COUNTROWS(_Vals)
VAR _Min = MINX(_Vals, [@v])
VAR _Max = MAXX(_Vals, [@v])
VAR _Pts = CONCATENATEX(
    _Vals,
    FORMAT({pad} + DIVIDE([@i] - 1, MAX(_N - 1, 1)) * {w - 2 * pad}, "0.0") & "," & FORMAT({bottom} - DIVIDE([@v] - _Min, MAX(_Max - _Min, 1)) * {bottom - top}, "0.0"),
    " ", [@i], ASC
)
VAR _Spark = IF(_N >= 2,
    "<polygon points='{pad},{bottom} " & _Pts & " {w - pad},{bottom}' fill='{color}' fill-opacity='0.12'/>" &
    "<polyline points='" & _Pts & "' fill='none' stroke='{color}' stroke-width='1.6' stroke-linejoin='round'/>")
"""
        spark_svg = ' & _Spark'
    sc = sub_color or "'" + GREY + "'"
    if sub_color is None:
        sc = f'"{GREY}"'
    return f"""
VAR _Raw = {value}
VAR _Value = IF(_Raw = "" || _Raw = "₹" || _Raw = "₹—", "—", _Raw)
VAR _Sub = {f'IF(ISBLANK({guard}), "No data in selection", {sub})' if guard else sub}
VAR _SubColor = {sc}{spark_vars}
VAR _Svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>" &
    "<rect x='0.5' y='0.5' width='{w - 1}' height='{h - 1}' rx='10' fill='#141414' stroke='#262626'/>" &
    "<rect x='14' y='0' width='26' height='2' fill='{color}'/>" &
    "<text x='14' y='24' {FONT} font-size='11' fill='#A5A5A5'>{label}</text>" &
    "<text x='14' y='56' {FONT} font-size='27' font-weight='600' fill='#F2F2F2'>" & _Value & "</text>" &
    "<text x='14' y='74' {FONT} font-size='10.5' fill='" & _SubColor & "'>" & {esc("_Sub")} & "</text>"{spark_svg} &
    "</svg>"
RETURN {encode("_Svg")}
"""

def header(name, title, eyebrow, period="[Period Label]"):
    return f"""
VAR _Period = {period}
VAR _Svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='1648' height='64' viewBox='0 0 1648 64'>" &
    "<text x='0' y='17' {FONT} font-size='12' letter-spacing='1.6' fill='{GOLD}'>{eyebrow}</text>" &
    "<text x='0' y='50' {FONT} font-size='30' font-weight='600' fill='#F2F2F2'>{title}</text>" &
    "<text x='1648' y='50' text-anchor='end' {FONT} font-size='13' fill='#A5A5A5'>" & _Period & "</text>" &
    "</svg>"
RETURN {encode("_Svg")}
"""

def seg(name, expr):
    return f'IF("{name}" IN VALUES(Segment[Segment]), {expr}, "—")'
def seg_sub(name, expr):
    return f'IF("{name}" IN VALUES(Segment[Segment]), {expr}, "Segment not selected")'

CARDS = {
    # Executive
    "KPI Total Sales": dict(label="Total Recorded Sales", value=f'"₹" & {big("[Total Recorded Sales]")}', sub='"Periods differ by segment"', color=GOLD, spark="[Total Recorded Sales]"),
    "KPI Amazon Sales": dict(label="Amazon Recorded Sales", value=f'IF("Amazon" IN VALUES(Segment[Segment]), "₹" & {big("[Amazon Revenue]")}, "—")', sub=seg_sub("Amazon", 'FORMAT([Amazon Sales Share %], "0.0%") & " of recorded sales"'), color=GOLD, spark="[Amazon Revenue]", grain="DimDate[Date]"),
    "KPI International Sales": dict(label="International Recorded Sales", value=f'IF("International" IN VALUES(Segment[Segment]), "₹" & {big("[International Revenue]")}, "—")', sub=seg_sub("International", 'FORMAT([International Sales Share %], "0.0%") & " of recorded sales"'), color=TEAL, spark="[International Revenue]"),
    "KPI Amazon Orders": dict(label="Amazon Orders", value=seg("Amazon", big("[Amazon Orders]")), sub=seg_sub("Amazon", '"Avg order ₹" & FORMAT([Amazon Average Order Value], "#,0")'), color=GOLD, spark="[Amazon Orders]", grain="DimDate[Date]"),
    "KPI Amazon Units": dict(label="Amazon Units Sold", value=seg("Amazon", big("[Amazon Units Sold]")), sub=seg_sub("Amazon", '"Avg price ₹" & FORMAT([Amazon Average Selling Price], "#,0")'), color=GOLD, spark="[Amazon Units Sold]", grain="DimDate[Date]"),
    "KPI International Units": dict(label="International Units", value=seg("International", big("[International Units]")), sub=seg_sub("International", 'FORMAT([International Customers], "#,0") & " customers"'), color=TEAL, spark="[International Units]"),
    "KPI Growth": dict(label="Amazon Sales Growth MoM", guard="[Amazon Revenue]", value=seg("Amazon", 'IF(ISBLANK([Amazon Revenue]), "—", IF(ISBLANK([Amazon Latest Month MoM %]), "n/a", IF([Amazon Latest Month MoM %] >= 0, "▲ ", "▼ ") & FORMAT(ABS([Amazon Latest Month MoM %]), "0.0%")))'),
                       sub=seg_sub("Amazon", 'IF(ISBLANK([Amazon Latest Month MoM %]), "Needs two full months", [Amazon Latest Month Label] & ". " & FORMAT([Amazon Latest Month Per Day MoM %], "+0.0%;-0.0%") & " per day")'),
                       color=EMERALD, spark="[Amazon Revenue]", sub_color=f'IF([Amazon Latest Month MoM %] < 0, "{CORAL}", "{EMERALD}")'),
    "KPI Expenses": dict(label="Recorded Expenses", value='"₹" & ' + big("[Total Recorded Expenses]"), sub='"IIGF event sheet only"', color=PURPLE),
    # Amazon
    "KPI Amazon AOV": dict(label="Average Order Value", value='"₹" & FORMAT([Amazon Average Order Value], "#,0")', sub='"Recognised sales ÷ orders"', color=GOLD),
    "KPI Amazon ASP": dict(label="Average Selling Price", value='"₹" & FORMAT([Amazon Average Selling Price], "#,0")', sub='"Recognised sales ÷ units"', color=GOLD),
    "KPI Amazon Cancelled": dict(label="Cancelled Orders", value=big("[Amazon Cancelled Orders]"), sub='FORMAT([Amazon Cancellation Rate %], "0.0%") & " of all orders"', color=CORAL, spark="[Amazon Cancelled Orders]", grain="DimDate[Date]"),
    "KPI Amazon Returned": dict(label="Returned / Failed Orders", value=big("[Amazon Returned Orders]"), sub='FORMAT([Amazon Return Rate %], "0.0%") & " of all orders"', color=CORAL, spark="[Amazon Returned Orders]", grain="DimDate[Date]"),
    "KPI Amazon Shipped": dict(label="Shipped Orders", value=big("[Amazon Shipped Orders]"), sub='"Status: Shipped"', color=EMERALD, spark="[Amazon Shipped Orders]", grain="DimDate[Date]"),
    "KPI Amazon Delivered": dict(label="Delivered to Buyer", value=big("[Amazon Delivered Orders]"), sub='"Status: Delivered"', color=EMERALD, spark="[Amazon Delivered Orders]", grain="DimDate[Date]"),
    # International
    "KPI Intl Rate": dict(label="Average Listed Rate", value='"₹" & FORMAT([International Average Rate], "#,0")', sub='"Mean of RATE per line"', color=TEAL),
    "KPI Intl Value": dict(label="Realised Value per Piece", value='"₹" & FORMAT([International Realised Value per Piece], "#,0")', sub='"GROSS AMT ÷ PCS"', color=TEAL),
    "KPI Intl Discount": dict(label="Discount vs Listed", value='FORMAT([International Discount vs Listed %], "0.0%")', sub='"GROSS AMT vs PCS × RATE"', color=PURPLE),
    "KPI Intl Top Customer": dict(label="Top Customer Share", value='FORMAT([International Top Customer Share %], "0.0%")', sub="LEFT([International Top Customer], 24)", color=PURPLE),
    "KPI Intl Peak": dict(label="Peak Month", value='[International Peak Month Label]', sub='"Highest recorded sales"', color=TEAL),
    "KPI Intl Customers": dict(label="Customers", value='FORMAT([International Customers], "#,0")', sub='"Distinct billed names"', color=TEAL),
    # Product
    "KPI Amazon Units Plain": dict(label="Amazon Units Sold", value=big("[Amazon Units Sold]"), sub='"Recognised orders only"', color=GOLD, spark="[Amazon Units Sold]", grain="DimDate[Date]", w=265),
    "KPI Unique SKUs": dict(label="Amazon SKUs Sold or Listed", value=big("[Unique Amazon SKUs]"), sub='FORMAT([Unique Catalog SKUs], "#,0") & " in stock catalogue"', color=GOLD, w=265),
    "KPI Total Stock": dict(label="Recorded Stock (Units)", value=big("[Total Stock]"), sub='"A snapshot, not units sold"', color=TEAL, w=265),
    "KPI Matched SKUs": dict(label="SKUs Matched to Stock", value=big("[Matched Amazon SKUs]"), sub='FORMAT([SKU Match Coverage %], "0.0%") & " coverage"', color=EMERALD, w=265),
    "KPI Unmatched SKUs": dict(label="SKUs Without Stock Record", value=big("[Unmatched Amazon SKUs]"), sub='"Not forced to match"', color=CORAL, w=265),
    "KPI Matched Units": dict(label="Units on Matched SKUs", value=big("[Units Sold on Matched SKUs]"), sub='FORMAT(DIVIDE([Units Sold on Matched SKUs], [Amazon Units Sold]), "0.0%") & " of Amazon units"', color=GOLD, w=265),
    # Pricing
    "KPI MRP Amazon": dict(label="Average Amazon MRP", value='"₹" & FORMAT([Avg Amazon MRP], "#,0")', sub='"May 2022 snapshot"', color=GOLD),
    "KPI MRP Flipkart": dict(label="Average Flipkart MRP", value='"₹" & FORMAT([Avg Flipkart MRP], "#,0")', sub='"May 2022 snapshot"', color=TEAL),
    "KPI MRP Myntra": dict(label="Average Myntra MRP", value='"₹" & FORMAT([Avg Myntra MRP], "#,0")', sub='"May 2022 snapshot"', color=TEAL),
    "KPI MRP Ajio": dict(label="Average Ajio MRP", value='"₹" & FORMAT([Avg Ajio MRP], "#,0")', sub='"May 2022 snapshot"', color=TEAL),
    "KPI MRP Snapdeal": dict(label="Average Snapdeal MRP", value='"₹" & FORMAT([Avg Snapdeal MRP], "#,0")', sub='"May 2022 snapshot"', color=TEAL),
    "KPI Priced Products": dict(label="Products With Prices", value=big("[Products With Prices]"), sub='FORMAT(COUNTROWS(\'May-2022\'), "#,0") & " products listed"', color=PURPLE),
    "KPI Price Variation": dict(label="Products With Price Gaps", value=big("[Products With Price Variation]"), sub='"MRP differs by marketplace"', color=CORAL),
    "KPI Avg Spread": dict(label="Average Price Gap", value='"₹" & FORMAT([Avg Price Spread], "#,0")', sub='"Where a gap exists"', color=CORAL),
    # Expense
    "KPI Receipts": dict(label="Recorded Receipts", value='"₹" & FORMAT([Total Received Amount], "#,0")', sub='"Four dated receipts"', color=TEAL, w=400),
    "KPI Expense Total": dict(label="Recorded Expenses", value='"₹" & FORMAT([Total Recorded Expenses], "#,0")', sub='"13 undated line items"', color=PURPLE, w=400),
    "KPI Balance": dict(label="Recorded Balance Difference", value='"₹" & FORMAT([Recorded Net Cash Position], "#,0")', sub='"Source sheet: Pending Amount. Not profit"', color=CORAL, w=400),
    "KPI Largest Expense": dict(label="Largest Expense", value="LEFT([Largest Expense Name], 22)", sub='"By recorded amount"', color=PURPLE, w=400),
    # SKU detail
    "KPI SKU Sales": dict(label="Amazon Recorded Sales", value='IF(ISBLANK([Amazon Revenue]), "—", "₹" & ' + big("[Amazon Revenue]") + ')', sub='IF(ISBLANK([Amazon Revenue]), "No recognised Amazon sale", FORMAT([SKU Amazon Sales Share %], "0.00%") & " of Amazon sales")', color=GOLD, spark="[Amazon Revenue]", grain="DimDate[Date]"),
    "KPI SKU Units": dict(label="Amazon Units Sold", value=big("[Amazon Units Sold]"), sub='IF(ISBLANK([Amazon Units Sold]), "Recognised orders only", "Avg price ₹" & FORMAT([Amazon Average Selling Price], "#,0"))', color=GOLD, spark="[Amazon Units Sold]", grain="DimDate[Date]"),
    "KPI SKU Orders": dict(label="Amazon Orders", value=big("[Amazon Orders]"), sub='FORMAT(0 + [Amazon All Orders], "#,0") & " including all outcomes"', color=GOLD),
    "KPI SKU Cancelled": dict(label="Cancelled Orders", value=big("[Amazon Cancelled Orders]"), sub='IF(ISBLANK([Amazon All Orders]), "No Amazon orders", FORMAT(0 + [Amazon Cancellation Rate %], "0.0%") & " of all orders")', color=CORAL),
    "KPI SKU Returned": dict(label="Returned / Failed Orders", value=big("[Amazon Returned Orders]"), sub='IF(ISBLANK([Amazon All Orders]), "No Amazon orders", FORMAT(0 + [Amazon Return Rate %], "0.0%") & " of all orders")', color=CORAL),
    "KPI SKU Stock": dict(label="Recorded Stock (Units)", value=big("[Total Stock]"), sub='IF(ISBLANK([Total Stock]), "No stock record for this SKU", "Undated snapshot")', color=TEAL),
    "KPI SKU Intl Sales": dict(label="International Sales", value='IF(ISBLANK([International Revenue]), "—", "₹" & ' + big("[International Revenue]") + ')', sub='IF(ISBLANK([International Revenue]), "No International line", FORMAT([International Customers], "#,0") & " customers")', color=TEAL, spark="[International Revenue]"),
    "KPI SKU Intl Units": dict(label="International Units", value=big("[International Units]"), sub='"Apr to May 2022 lines carry no SKU"', color=TEAL),
    # Marketplace detail
    "KPI MP Avg": dict(label="Average MRP", value='"₹" & FORMAT([Marketplace Avg MRP May 2022], "#,0")', sub='"All marketplaces ₹" & FORMAT([All Marketplaces Avg MRP], "#,0")', color=GOLD, w=225),
    "KPI MP Vs All": dict(label="Against All Marketplaces", value='FORMAT([Marketplace Avg vs All %], "+0.0%;-0.0%;0.0%")', sub='"Difference in average MRP"', color=GOLD, w=225),
    "KPI MP Rank": dict(label="Rank by Average MRP", value='IF(ISBLANK([Marketplace MRP Rank]), "—", "#" & [Marketplace MRP Rank])', sub='"Of 8. Ties share a rank"', color=PURPLE, w=225),
    "KPI MP Range": dict(label="MRP Range", value='"₹" & FORMAT([Marketplace Min MRP], "#,0") & " – ₹" & FORMAT([Marketplace Max MRP], "#,0")', sub='"Lowest to highest listed"', color=PURPLE, w=225),
    "KPI MP Priced": dict(label="Products Priced", value='FORMAT([Marketplace Priced Products], "#,0")', sub='FORMAT([Marketplace Coverage %], "0.0%") & " of listed products"', color=TEAL, w=225),
    "KPI MP Highest": dict(label="Products at Highest MRP", value='FORMAT([Marketplace Highest MRP Products], "#,0")', sub='"Only where marketplaces differ"', color=CORAL, w=225),
    "KPI MP Lowest": dict(label="Products at Lowest MRP", value='FORMAT([Marketplace Lowest MRP Products], "#,0")', sub='"Only where marketplaces differ"', color=EMERALD, w=225),
}
GUARDS = {
    "[Amazon All Orders]": ["KPI Amazon Sales", "KPI Amazon Orders", "KPI Amazon Units", "KPI Amazon AOV", "KPI Amazon ASP", "KPI Amazon Cancelled", "KPI Amazon Returned",
                            "KPI Amazon Shipped", "KPI Amazon Delivered", "KPI Amazon Units Plain", "KPI Unique SKUs", "KPI Matched SKUs", "KPI Unmatched SKUs", "KPI Matched Units"],
    "[International Revenue]": ["KPI International Sales", "KPI International Units", "KPI Intl Rate", "KPI Intl Value", "KPI Intl Discount", "KPI Intl Top Customer", "KPI Intl Peak", "KPI Intl Customers"],
}
for measure, names in GUARDS.items():
    for nm in names:
        CARDS[nm]["guard"] = measure
for nm, c in CARDS.items():
    add(nm, card(nm, **c), F, None, "ImageUrl")

PAGES = {
    "Executive": ("Executive Overview", "SALES AND BUSINESS PERFORMANCE"),
    "Amazon": ("Amazon Sales Intelligence", "MARKETPLACE PERFORMANCE"),
    "International": ("International Sales Intelligence", "MULTI-CHANNEL EXPORT LEDGER"),
    "Product": ("Product Performance and Inventory", "AMAZON SALES AGAINST RECORDED STOCK"),
    "Pricing": ("Marketplace Pricing Intelligence", "MRP SNAPSHOTS, NOT REVENUE"),
    "Expense": ("Expense and Cash Movement", "IIGF EVENT CASH SHEET"),
    "Logistics": ("Logistics and Warehouse Comparison", "SHIPROCKET AND INCREFF"),
    "Notes": ("Data Definitions and Limitations", "HOW EVERY NUMBER IS BUILT"),
}
def span(tbl, col, label):
    return (f'VAR _D1 = CALCULATE(MIN({tbl}[{col}])) VAR _D2 = CALCULATE(MAX({tbl}[{col}])) '
            f'RETURN IF(ISBLANK(_D1), "No data in selection", "{label}  ·  " & FORMAT(_D1, "d MMM yyyy") & " to " & FORMAT(_D2, "d MMM yyyy"))')
add("Period Amazon", span(AMZ, "Date", "Amazon"), "3. Combined")
add("Period International", span(INT, "DATE", "International"), "3. Combined")
PERIODS = {"Amazon": "[Period Amazon]", "International": "[Period International]", "Product": "[Period Amazon]",
           "Pricing": '"Snapshots: March 2021 and May 2022"', "Expense": '"Receipts dated 19 to 23 June 2022"', "Logistics": '"Undated reference chart"', "Notes": '"Applies to every page"'}
for key, (t, e) in PAGES.items():
    add(f"Header {key}", header(key, t, e, PERIODS.get(key, "[Period Label]")), F, None, "ImageUrl")

def dynamic_header(title, eyebrow, period):
    return f"""
VAR _Title = {title}
VAR _Eyebrow = {eyebrow}
VAR _Period = {period}
VAR _Svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='1648' height='64' viewBox='0 0 1648 64'>" &
    "<text x='0' y='17' {FONT} font-size='12' letter-spacing='1.6' fill='{GOLD}'>" & {esc("_Eyebrow")} & "</text>" &
    "<text x='0' y='50' {FONT} font-size='30' font-weight='600' fill='#F2F2F2'>" & {esc("_Title")} & "</text>" &
    "<text x='1648' y='50' text-anchor='end' {FONT} font-size='13' fill='#A5A5A5'>" & _Period & "</text>" &
    "<rect x='1498.5' y='0.5' width='149' height='29' rx='8' fill='#141414' stroke='#262626'/>" &
    "<text x='1573' y='19' text-anchor='middle' {FONT} font-size='12' fill='#A5A5A5'>Back to previous page</text>" &
    "</svg>"
RETURN {encode("_Svg")}
"""
add("Header SkuDetail", dynamic_header("[Selected SKU]", "[SKU Attributes]", "[Period Label]"), F, None, "ImageUrl")
add("Header MarketplaceDetail", dynamic_header("[Marketplace Selected]", '"MARKETPLACE DETAIL  ·  MRP, NOT REVENUE"', '"May 2022 snapshot"'), F, None, "ImageUrl")

NAV_ITEMS = [("Executive", "Executive Overview"), ("Amazon", "Amazon Sales"), ("International", "International Sales"), ("Product", "Products and Stock"),
             ("Pricing", "Marketplace Pricing"), ("Expense", "Expenses and Cash"), ("Logistics", "Logistics"), ("Notes", "Data Notes")]

def rail(active):
    """The navigation rail is one image; transparent buttons sit on top of each row."""
    rows, y = "", 104
    for key, label in NAV_ITEMS:
        if key == active:
            rows += f"<rect x='12' y='{y}' width='192' height='42' rx='8' fill='#1B1810'/><rect x='12' y='{y + 10}' width='3' height='22' rx='1.5' fill='{GOLD}'/>"
            rows += f"<text x='28' y='{y + 26}' {FONT} font-size='13.5' font-weight='600' fill='{GOLD}'>{label}</text>"
        else:
            rows += f"<text x='28' y='{y + 26}' {FONT} font-size='13.5' fill='#A5A5A5'>{label}</text>"
        y += 46
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='216' height='1080' viewBox='0 0 216 1080'>"
           "<rect width='216' height='1080' fill='#0E0E0E'/><rect x='215' width='1' height='1080' fill='#1F1F1F'/>"
           f"<text x='28' y='48' {FONT} font-size='19' font-weight='600' letter-spacing='1' fill='{GOLD}'>SALES</text>"
           f"<text x='28' y='68' {FONT} font-size='11' letter-spacing='1.6' fill='#A5A5A5'>INTELLIGENCE</text>"
           + rows +
           f"<text x='28' y='982' {FONT} font-size='10' fill='#6E6E6E'>In Desktop, Ctrl + click to navigate</text></svg>")
    return f'VAR _Svg = "{svg}" RETURN {encode("_Svg")}'

for key, _ in NAV_ITEMS:
    add(f"Rail {key}", rail(key), F, None, "ImageUrl")

def insight_panel(name, title, lines, w=403, h=384):
    """Each line is (DAX text expression, colour). Two-tier layout: bullet line wrapped by the author."""
    rows, y = [], 52
    for expr, colour in lines:
        if colour == "gap":
            y += 10
            continue
        rows.append(f"\"<text x='18' y='{y}' {FONT} font-size='12.5' fill='{colour}'>\" & {esc(expr)} & \"</text>\"")
        y += 19
    body = " &\n    ".join(rows)
    return f"""
VAR _Svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>" &
    "<rect x='0.5' y='0.5' width='{w - 1}' height='{h - 1}' rx='10' fill='#141414' stroke='#262626'/>" &
    "<text x='18' y='30' {FONT} font-size='14' font-weight='600' fill='#F2F2F2'>{title}</text>" &
    {body} &
    "</svg>"
RETURN {encode("_Svg")}
"""

W, S = "#E6E6E6", "#9A9A9A"
def when(measure, expr, alt='""'):
    return f'IF(ISBLANK({measure}), {alt}, {expr})'
AMZ_ORDERS, AMZ_SALES, INT_SALES = "[Amazon All Orders]", "[Amazon Revenue]", "[International Revenue]"
add("Insights Executive", insight_panel("x", "Key business insights", [
    (when(AMZ_SALES, when(INT_SALES, '"Amazon brings " & FORMAT([Amazon Sales Share %], "0%") & " of recorded sales: ₹" & ' + big("[Amazon Revenue]") + ' & " vs ₹" & ' + big("[International Revenue]"), '"All recorded sales here are Amazon: ₹" & ' + big("[Amazon Revenue]")), '"No Amazon sales in this selection"'), W),
    (when(AMZ_SALES, '"Top 10 styles earn " & FORMAT([Top 10 Style Share %], "0%") & " of Amazon sales, led by " & [Top Style Name]'), W),
    (when(AMZ_SALES, '[Top State Name] & " is the largest Amazon market at " & FORMAT([Top State Share %], "0%") & " of sales"'), W),
    (when(AMZ_ORDERS, 'FORMAT([Amazon Cancellation Rate %], "0.0%") & " of Amazon orders were cancelled"'), CORAL),
    (when(AMZ_ORDERS, '"and " & FORMAT([Amazon Return Rate %], "0.0%") & " came back or failed in delivery"'), CORAL),
    (when(INT_SALES, '"Largest International buyer: " & LEFT([International Top Customer], 26)', '"No International sales in this selection"'), W),
    (when(INT_SALES, '"at " & FORMAT([International Top Customer Share %], "0%") & " of that segment"'), W),
    ('""', "gap"),
    ('"READ THIS BEFORE COMPARING"', GOLD),
    ('"Amazon covers 31 Mar to 29 Jun 2022. International"', S),
    ('"covers 5 Jun 2021 to 11 May 2022. They overlap only"', S),
    ('"in Apr to May 2022, so totals are not like for like."', S),
    ('""', "gap"),
    ('"Net Profit: not available. COGS data is required."', CORAL),
    ('"Expenses are one event sheet, not business costs."', S),
    ('"Stock and MRP are not sales and are excluded here."', S),
]), F, None, "ImageUrl")
add("Insights Amazon", insight_panel("x", "Reading this page", [
    ('"Sales count only Shipped and Delivered orders."', W),
    (when(AMZ_ORDERS, '"Cancelled value not counted: ₹" & ' + big("[Amazon Cancelled Value]"), '"No Amazon orders in this selection"'), CORAL),
    (when(AMZ_ORDERS, '"In progress orders not counted: " & FORMAT(0 + [Amazon In Progress Orders], "#,0")'), S),
    (when(AMZ_ORDERS, '"Returned or failed orders: " & FORMAT(0 + [Amazon Returned Orders], "#,0")'), S),
    ('""', "gap"),
    ('"Nearly every order ships to India, so a country"', S),
    ('"chart would add nothing and is left out."', S),
    ('"The 29 Jun cut-off makes June slightly short."', S),
], h=246), F, None, "ImageUrl")
add("Insights International", insight_panel("x", "Limits of this data", [
    ('"Multi-channel export ledger, not Amazon only."', W),
    ('"No channel, city, state or country"', CORAL),
    ('"field exists, so none is inferred."', CORAL),
    ('""', "gap"),
    ('"Sales use original GROSS AMT."', S),
    ('"PCS x RATE is kept separately."', S),
    ('""', "gap"),
    ('"May 2022 ends on the 11th, so that"', S),
    ('"month is partial."', S),
    ('"Currency is not stated in the file."', S),
], w=320), F, None, "ImageUrl")
add("Insights Product", insight_panel("x", "Reading this page", [
    (when(AMZ_ORDERS, 'FORMAT([SKU Match Coverage %], "0%") & " of Amazon SKUs have a stock record."', '"No Amazon SKUs in this selection"'), W),
    ('"Unmatched SKUs are reported, not forced."', S),
    ('""', "gap"),
    ('"Stock is a single undated snapshot."', CORAL),
    ('"Remaining stock and turnover cannot be"', CORAL),
    ('"calculated without inventory history."', CORAL),
    ('""', "gap"),
    ('"Date filters change units and sales."', S),
    ('"They do not change recorded stock."', S),
]), F, None, "ImageUrl")
add("Insights Pricing", insight_panel("x", "Reading this page", [
    ('FORMAT([Products With Price Variation], "#,0") & " products have different MRPs across"', W),
    ('"marketplaces, with an average gap of ₹" & FORMAT([Avg Price Spread], "#,0")', W),
    ('"and a maximum of ₹" & FORMAT([Max Price Spread], "#,0")', W),
    ('""', "gap"),
    ('"NO PRICE MOVEMENT BETWEEN SNAPSHOTS"', GOLD),
    ('"Mar 2021 and May 2022 hold identical MRPs for"', S),
    ('"every product. Amazon MRP changes: " & FORMAT([Snapshot Price Changes], "0")', S),
    ('"The two files may be one price list."', S),
    ('""', "gap"),
    ('"MRP is a list price, never revenue."', CORAL),
    ('"These SKU codes match no sales table,"', S),
    ('"so price and sales are not compared."', S),
], h=406), F, None, "ImageUrl")
add("Insights Expense", insight_panel("x", "Reading this page", [
    ('"This sheet appears to record one event (IIGF, June 2022): travel, hotel, labour and sundries."', W),
    ('"It is not the cost base of the sales business, so it must not be netted against sales."', CORAL),
    ('""', "gap"),
    ('"The difference of ₹" & FORMAT([Recorded Net Cash Position], "#,0") & " matches the Pending Amount row on the sheet."', S),
    ('"It means spending exceeded receipts on this sheet. It is not a profit or loss."', S),
    ('""', "gap"),
    ('"Expense lines have no dates, so no expense timeline is possible."', S),
    ('"The date on each row belongs to the receipt beside it, not to the expense."', S),
], w=816, h=396), F, None, "ImageUrl")
add("Insights SkuDetail", insight_panel("x", "Reading this page", [
    ('"Sales count only Shipped and Delivered orders."', W),
    ('"Cancelled and returned orders are shown"', S),
    ('"but never added to sales."', S),
    ('""', "gap"),
    ('"STOCK IS NOT COMPARED OVER TIME"', GOLD),
    ('"Stock is one undated snapshot, so no turnover"', S),
    ('"or days of cover can be calculated."', S),
    ('"A blank stock card means no record, not zero."', S),
    ('""', "gap"),
    ('"International Apr to May 2022 lines have no SKU,"', CORAL),
    ('"so International sales for this SKU may be higher."', CORAL),
]), F, None, "ImageUrl")
add("Insights MarketplaceDetail", insight_panel("x", "Reading this page", [
    ('[Marketplace Selected] & " has a price for " & FORMAT([Marketplace Priced Products], "#,0") & " of 1,330 products."', W),
    ('"Average MRP is " & FORMAT([Marketplace Avg vs All %], "+0.0%;-0.0%;0.0%") & " against all marketplaces."', W),
    ('""', "gap"),
    ('"MRP IS A LIST PRICE, NEVER REVENUE"', GOLD),
    ('"These prices do not show what sold on this"', S),
    ('"marketplace. Only Amazon has sales data here,"', S),
    ('"and these SKU codes match no sales table."', S),
    ('""', "gap"),
    ('"March 2021 holds identical MRPs,"', CORAL),
    ('"so no price change can be shown."', CORAL),
]), F, None, "ImageUrl")
add("Insights Logistics", insight_panel("x", "Reading this page", [
    ('"Shiprocket is cheaper on outbound and customer returns."', W),
    ('"Inbound is the same price at both providers."', W),
    ('""', "gap"),
    ('"Storage is left out of the chart because the units differ:"', CORAL),
    ('"Shiprocket quotes 25 per cft, INCREFF 0.15 per day."', CORAL),
    ('""', "gap"),
    ('"Rates are reference prices with no stated unit of volume."', S),
    ('"They are not realised costs and are not part of any sales figure."', S),
], w=636, h=340), F, None, "ImageUrl")

# --------------------------------------------------------------- Emit _Measures -----------------------------
def emit_measures():
    orig = read("tables/_Measures.tmdl")
    tags = dict(re.findall(r"measure '?([^'=\n]+?)'? =.*?lineageTag: ([0-9a-f-]{36})", orig, flags=re.S))
    out = ["table _Measures", f"\tlineageTag: bcf78b4e-11e7-4735-9f98-1d711ec06510", ""]
    for name, (expr, folder, fmt, cat) in M.items():
        q = f"'{name}'"
        out.append(f"\tmeasure {q} = ```")
        out += ["\t\t\t" + l if l else "" for l in expr.split("\n")]
        out.append("\t\t\t```")
        if fmt: out.append(f"\t\tformatString: {fmt}")
        if cat: out.append(f"\t\tdataCategory: {cat}")
        out.append(f"\t\tdisplayFolder: {folder}")
        out.append(f"\t\tlineageTag: {tags.get(name, guid())}")
        out.append("")
    tail = orig[orig.index("\tcolumn 'Measure Group'"):]
    write("tables/_Measures.tmdl", "\n".join(out) + "\n" + tail)

fix_international(); fix_amazon(); fix_expense(); fix_warehouse(); fix_dimdate(); fix_dimsku(); helper_tables(); emit_measures()
print(f"Model written: {len(M)} measures")
