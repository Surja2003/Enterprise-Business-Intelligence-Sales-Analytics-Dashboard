"""Report pages 2-8. Uses the Page class and layout constants from build_report."""

def build(g):
    Page, col, mea, col4 = g["Page"], g["col"], g["mea"], g["col4"]
    X, W, GAP, IDS = g["X"], g["W"], g["GAP"], g["IDS"]
    AMZ, INT, SALE, MAY, EXP, WH = g["AMZ"], g["INT"], g["SALE"], g["MAY"], g["EXP"], g["WH"]
    ds = g["ds"]
    GOLD, TEAL, EMERALD, CORAL, PURPLE, TEXT, TEXT2, FONT_SB, FONT = g["GOLD"], g["TEAL"], g["EMERALD"], g["CORAL"], g["PURPLE"], g["TEXT"], g["TEXT2"], g["FONT_SB"], g["FONT"]

    def amazon():
        p = Page(IDS["Amazon"], "Amazon Sales Intelligence", "Amazon")
        p.nav("Amazon"); p.header(); p.filters()
        p.kpis(["KPI Amazon Sales", "KPI Amazon Orders", "KPI Amazon Units", "KPI Amazon AOV", "KPI Amazon ASP", "KPI Amazon Cancelled", "KPI Amazon Shipped", "KPI Amazon Delivered"])
        y, h = 298, 246
        p.trend("trend", X, y, 540, h, "Recorded sales over time", value="Amazon Revenue", series=False)
        p.grain_slicer("grain", X + 540 - 312, y + 8, 300, 34)
        p.deneb("outcome", X + 552, y, 420, h, "Where order value went", [col(AMZ, "Status Group"), mea("Amazon Order Value")], ds.order_waterfall(), "7,566 cancelled lines have no Amount")
        p.deneb("calendar", X + 984, y, 400, h, "Daily sales calendar", [col("DimDate", "Date"), mea("Amazon Revenue")], ds.calendar(), "Brighter days sold more. Click a day to filter the page.", select=True)
        p.deneb("fulfil", X + 1396, y, 252, 117, "Fulfilment", [col(AMZ, "Fulfilment"), mea("Amazon Revenue")], ds.ranked_bars("Fulfilment", "Amazon Revenue"), select=True)
        p.deneb("b2b", X + 1396, y + 129, 252, 117, "Business buyer (B2B)", [col(AMZ, "B2B"), mea("Amazon Revenue")], ds.ranked_bars("B2B", "Amazon Revenue"), select=True)
        y, h = 556, 246
        x, w = col4(0); p.deneb("topRev", x, y, w, h, "Top 10 styles by sales", [col(AMZ, "Style"), mea("Top 10 Style Sales")], ds.ranked_bars("Style", "Top 10 Style Sales"), select=True)
        x, w = col4(1); p.deneb("topUnits", x, y, w, h, "Top 10 styles by units", [col(AMZ, "Style"), mea("Top 10 Style Units")], ds.ranked_bars("Style", "Top 10 Style Units", money=False), select=True)
        x, w = col4(2); p.table("low", x, y, w, h, "Lowest 10 selling styles", [(col(AMZ, "Style"), "Style"), (mea("Low 10 Style Units"), "Units"), (mea("Low 10 Style Sales"), "Sales")], sort=(mea("Low 10 Style Sales"), "Ascending"), row_pad=2)
        x, w = col4(3); p.bar("category", x, y, w, h, "Sales by category", col(AMZ, "Category"), mea("Amazon Revenue"), GOLD)
        y, h = 814, 246
        x, w = col4(0); p.deneb("state", x, y, w, h, "Top 10 states", [col(AMZ, "State Clean"), mea("Top 10 State Sales")], ds.ranked_bars("State Clean", "Top 10 State Sales"), "State spellings standardised", select=True)
        x, w = col4(1); p.deneb("city", x, y, w, h, "Top 10 cities", [col(AMZ, "ship-city"), mea("Top 10 City Sales")], ds.ranked_bars("ship-city", "Top 10 City Sales"), select=True)
        x, w = col4(2); p.bar("size", x, y, w, h, "Sales by size", col(AMZ, "Size"), mea("Amazon Revenue"), GOLD, horizontal=False)
        x, w = col4(3); p.svg("notes", x, y, w, h, "Insights Amazon")
        return p

    def international():
        p = Page(IDS["International"], "International Sales Intelligence", "International")
        p.nav("International"); p.header(); p.filters()
        p.kpis(["KPI International Sales", "KPI International Units", "KPI Intl Customers", "KPI Intl Value", "KPI Intl Rate", "KPI Intl Discount", "KPI Intl Top Customer", "KPI Intl Peak"])
        y, h = 298, 366
        p.trend("trend", X, y, 640, h, "Recorded sales over time", "Original GROSS AMT values", value="International Revenue", series=False, color=TEAL)
        p.grain_slicer("grain", X + 640 - 312, y + 8, 300, 34)
        p.deneb("concentration", X + 652, y, 460, h, "Customer concentration", [col(INT, "CUSTOMER"), mea("International Revenue")], ds.concentration(), "Cumulative share of sales. Ranks only, no names.")
        p.bar("customers", X + 1124, y, W - 1124, h, "Top 10 customers", col(INT, "CUSTOMER"), mea("Top 10 Customer Sales"), TEAL, "Names are upper-cased only. Similar names are not merged.")
        y, h = 676, 384
        cols = lambda i: col4(i, 5)
        x, w = cols(0); p.bar("topStyle", x, y, w, h, "Top 10 styles", col(INT, "Style"), mea("International Top 10 Style Sales"), TEAL)
        x, w = cols(1); p.table("lowStyle", x, y, w, h, "Lowest 10 styles", [(col(INT, "Style"), "Style"), (mea("International Low 10 Style Units"), "Units"), (mea("International Low 10 Style Sales"), "Sales")], sort=(mea("International Low 10 Style Sales"), "Ascending"))
        x, w = cols(2); p.bar("sku", x, y, w, h, "Top 10 SKUs", col("DimSKU", "SKU_Key"), mea("Top 10 Intl SKU Sales"), TEAL, "Right-click to drill. Apr to May rows have no SKU")
        x, w = cols(3); p.bar("size", x, y, w, h, "Sales by size", col(INT, "Final Size"), mea("International Revenue"), TEAL)
        x, w = cols(4); p.svg("notes", x, y, w, h, "Insights International")
        return p

    def product():
        p = Page(IDS["Product"], "Product Performance and Inventory", "Product")
        p.nav("Product"); p.header(); p.filters()
        p.kpis(["KPI Unique SKUs", "KPI Total Stock", "KPI Amazon Units Plain", "KPI Matched SKUs", "KPI Unmatched SKUs", "KPI Matched Units"])
        y, h = 298, 366
        p.multi_bar("stockVsSales", X, y, 820, h, "Recorded stock and units sold, top 8 categories", col(SALE, "Category"), ["Top 8 Category Stock", "Top 8 Category Units"], [TEAL, GOLD], "Only SKUs present in both tables. Stock is one undated snapshot.", horizontal=False, names={"Top 8 Category Stock": "Recorded stock", "Top 8 Category Units": "Units sold"}, label_units=1000)
        p.table("skus", X + 832, y, W - 832, h, "Top 15 SKUs by units sold", [(col("DimSKU", "SKU_Key"), "SKU"), (mea("Top 15 SKU Units"), "Units sold"), (mea("Top 15 SKU Sales"), "Sales"), (mea("Top 15 SKU Stock"), "Recorded stock")], "Right-click a SKU, then Drill through. Blank stock means no stock record.", sort=(mea("Top 15 SKU Units"), "Descending"))
        y, h = 676, 384
        x, w = col4(0); p.bar("category", x, y, w, h, "Amazon sales by category", col(AMZ, "Category"), mea("Amazon Revenue"), GOLD)
        x, w = col4(1); p.bar("stockSize", x, y, w, h, "Recorded stock by size", col(SALE, "Size"), mea("Total Stock"), TEAL)
        x, w = col4(2); p.bar("stockColor", x, y, w, h, "Top 10 colours by stock", col(SALE, "Color"), mea("Top 10 Color Stock"), TEAL)
        x, w = col4(3); p.svg("notes", x, y, w, h, "Insights Product")
        return p

    def pricing():
        p = Page(IDS["Pricing"], "Marketplace Pricing Intelligence", "Pricing")
        p.nav("Pricing"); p.header()
        p.kpis(["KPI MRP Amazon", "KPI MRP Flipkart", "KPI MRP Myntra", "KPI MRP Ajio", "KPI MRP Snapdeal", "KPI Priced Products", "KPI Price Variation", "KPI Avg Spread"], y=92)
        y, h = 232, 410
        p.deneb("mrp", X, y, 1020, h, "MRP range by marketplace", [col("Marketplace", "Marketplace"), mea("Marketplace Min MRP"), mea("Marketplace Avg MRP May 2022"), mea("Marketplace Max MRP")], ds.price_range(), "May 2022 lowest, average and highest. March 2021 is identical. Blank prices are excluded, not treated as zero.", select=True)
        p.bar("coverage", X + 1032, y, W - 1032, h, "Pricing coverage", col("Marketplace", "Marketplace"), mea("Marketplace Coverage %"), PURPLE, "Right-click a marketplace, then Drill through", sort_cat=True)
        y, h = 654, 406
        x, w = col4(0); p.bar("catMrp", x, y, w, h, "Average Amazon MRP by category", col(MAY, "Category"), mea("Avg Amazon MRP"), GOLD)
        x, w = col4(1); p.bar("catGap", x, y, w, h, "Price gaps by category", col(MAY, "Category"), mea("Products With Price Variation"), CORAL, "Products whose MRP differs between marketplaces", label_units=1)
        x, w = col4(2); p.table("gaps", x, y, w, h, "Largest price gaps", [(col(MAY, "Sku"), "SKU"), (mea("Top 12 Price Spread"), "Gap"), (mea("Top 12 Price Spread Amazon MRP"), "Amazon MRP")], sort=(mea("Top 12 Price Spread"), "Descending"))
        x, w = col4(3); p.svg("notes", x, y, w, h, "Insights Pricing")
        return p

    def expense():
        p = Page(IDS["Expense"], "Expense and Cash Movement", "Expense")
        p.nav("Expense"); p.header()
        p.kpis(["KPI Receipts", "KPI Expense Total", "KPI Balance", "KPI Largest Expense"], y=92)
        y = 232
        p.bar("expenses", X, y, 820, 828, "Expense ranking by particular", col(EXP, "Expense Particular"), mea("Total Recorded Expenses"), PURPLE, "All 13 line items on the sheet", label_units=1)
        p.bar("receipts", X + 832, y, W - 832, 420, "Receipt timeline", col(EXP, "Received Date"), mea("Total Received Amount"), TEAL, "Receipts are the only dated values on the sheet", horizontal=False, sort_cat=True, label_units=1)
        p.svg("notes", X + 832, y + 432, W - 832, 396, "Insights Expense")
        return p

    def logistics():
        p = Page(IDS["Logistics"], "Logistics and Warehouse Comparison", "Logistics")
        p.nav("Logistics"); p.header()
        y, h = 92, 340
        p.multi_bar("rates", X, y, 1000, h, "Service rates compared", col(WH, "Service / Process"), ["Shiprocket Rate", "Increff Rate"], [GOLD, TEAL], "Only services quoted as a plain rate by both providers", horizontal=False, names={"Shiprocket Rate": "Shiprocket", "Increff Rate": "INCREFF"}, label_units=1)
        p.svg("notes", X + 1012, y, W - 1012, h, "Insights Logistics")
        no_rates = [{"name": "noRates", "field": col(WH, "Section"), "type": "Categorical", "filter": {"Version": 2, "From": [{"Name": "t", "Entity": WH, "Type": 0}],
            "Where": [{"Condition": {"Not": {"Expression": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": "Section"}}], "Values": [[{"Literal": {"Value": "'Rates'"}}]]}}}}}]}}]
        p.table("detail", X, y + h + GAP, W, 1060 - (y + h + GAP), "Scope of work and service terms", [(col(WH, "Row"), "#"), (col(WH, "Section"), "Section"), (col(WH, "Item"), "Item"), (col(WH, "Detail"), "Detail")], "As listed in the source chart, which does not say which provider each term applies to. Not realised costs.", sort=(col(WH, "Row"), "Ascending"), row_pad=4, filters=no_rates, widths=[44, 190, 430, 930])
        return p

    def sku_detail():
        p = Page(IDS["SkuDetail"], "SKU Detail", "SkuDetail", drill=col("DimSKU", "SKU_Key"))
        p.nav("Product"); p.header(); p.back(); p.filters()
        p.kpis(["KPI SKU Sales", "KPI SKU Units", "KPI SKU Orders", "KPI SKU Cancelled", "KPI SKU Returned", "KPI SKU Stock", "KPI SKU Intl Sales", "KPI SKU Intl Units"])
        y, h = 298, 366
        # fixed monthly axis: a time grain chosen on the source page flows through the drill-through and would lock a slicer here
        p.trend("trend", X, y, 640, h, "Recorded sales by month", "Amazon and International stay separate", grain=False)
        p.deneb("outcome", X + 652, y, 500, h, "Where order value went", [col(AMZ, "Status Group"), mea("Amazon Order Value")], ds.order_waterfall(), "Cancelled lines can have no Amount, so value may be understated")
        p.deneb("calendar", X + 1164, y, W - 1164, h, "Daily Amazon sales", [col("DimDate", "Date"), mea("Amazon Revenue")], ds.calendar(), "Brighter days sold more", select=True)
        y, h = 676, 384
        x, w = col4(0); p.deneb("state", x, y, w, h, "Top 10 states", [col(AMZ, "State Clean"), mea("Top 10 State Sales")], ds.ranked_bars("State Clean", "Top 10 State Sales"), "Amazon recorded sales", select=True)
        x, w = col4(1); p.deneb("city", x, y, w, h, "Top 10 cities", [col(AMZ, "ship-city"), mea("Top 10 City Sales")], ds.ranked_bars("ship-city", "Top 10 City Sales"), "Amazon recorded sales", select=True)
        x, w = col4(2); p.table("monthly", x, y, w, h, "Sales by month", [(col("DimDate", "Month Year"), "Month"), (mea("Amazon Revenue"), "Amazon"), (mea("International Revenue"), "International")], "Months with no sale are left out", sort=(col("DimDate", "Month Year"), "Ascending"))
        x, w = col4(3); p.svg("notes", x, y, w, h, "Insights SkuDetail")
        return p

    def marketplace_detail():
        p = Page(IDS["MarketplaceDetail"], "Marketplace Detail", "MarketplaceDetail", drill=col("Marketplace", "Marketplace"))
        p.nav("Pricing"); p.header(); p.back()
        p.kpis(["KPI MP Avg", "KPI MP Vs All", "KPI MP Rank", "KPI MP Range", "KPI MP Priced", "KPI MP Highest", "KPI MP Lowest"], y=92)
        y, h = 232, 410
        p.multi_bar("category", X, y, 820, h, "Average MRP by category", col(MAY, "Category"), ["Marketplace Avg MRP May 2022", "All Marketplaces Avg MRP"], [GOLD, TEXT2], "This marketplace against all eight", horizontal=False, names={"Marketplace Avg MRP May 2022": "This marketplace", "All Marketplaces Avg MRP": "All marketplaces"}, label_units=1)
        p.deneb("distribution", X + 832, y, W - 832, h, "How products are priced", [col(MAY, "Sku"), mea("Marketplace Avg MRP May 2022")], ds.price_histogram("Marketplace Avg MRP May 2022"), "Products in each MRP band. Blank prices are excluded.")
        y, h = 654, 406
        x, w = col4(0); p.table("gaps", x, y, w * 2 + GAP, h, "Largest gaps above the lowest listing", [(col(MAY, "Sku"), "SKU"), (mea("Top 15 Marketplace MRP"), "This MRP"), (mea("Top 15 Marketplace Lowest MRP"), "Lowest MRP anywhere"), (mea("Top 15 Marketplace Gap"), "Gap")], "Top 15 products where this marketplace lists above the lowest marketplace", sort=(mea("Top 15 Marketplace Gap"), "Descending"))
        x, w = col4(2); p.multi_bar("position", x, y, w, h, "Highest and lowest MRP by category", col(MAY, "Category"), ["Marketplace Highest MRP Products", "Marketplace Lowest MRP Products"], [CORAL, EMERALD], "Products where marketplaces differ", names={"Marketplace Highest MRP Products": "At highest", "Marketplace Lowest MRP Products": "At lowest"}, label_units=1)
        x, w = col4(3); p.svg("notes", x, y, w, h, "Insights MarketplaceDetail")
        return p

    def notes():
        p = Page(IDS["Notes"], "Data Definitions and Limitations", "Notes")
        p.nav("Notes"); p.header()
        def para(rows):
            out = []
            for kind, t in rows:
                if kind == "h": s = {"fontFamily": FONT_SB, "fontSize": "16pt", "color": GOLD}
                elif kind == "b": s = {"fontFamily": FONT_SB, "fontSize": "13pt", "color": TEXT}
                else: s = {"fontFamily": FONT, "fontSize": "12.5pt", "color": TEXT2}
                out.append({"textRuns": [{"value": t, "textStyle": s}]})
            return out
        left = [
            ("h", "Sales definitions"),
            ("b", "Amazon recorded sales"), ("t", "Sum of Amount where Status is Shipped or Shipped - Delivered to Buyer. Source: Amazon Sale Report."),
            ("t", "Cancelled, returned, rejected, lost, damaged and pending orders stay in the table but are excluded from sales. Each has its own count."),
            ("b", "International recorded sales"), ("t", "Sum of the original GROSS AMT. PCS x RATE is kept separately, and the gap is shown as a discount rather than overwriting the source value."),
            ("b", "Total recorded sales"), ("t", "Amazon plus International. The two cover different periods and overlap only in April to May 2022, so a combined figure is not a like-for-like comparison."),
            ("b", "Currency"), ("t", "Amazon is recorded in INR. International has no currency field. It is shown in rupees because its rates sit in the same range as Amazon prices. This is an assumption, not a fact in the data."),
            ("h", ""),
            ("h", "Metrics deliberately not shown"),
            ("b", "Net profit, gross profit and COGS"), ("t", "No product cost data exists. Expense IIGF is one event's cash sheet, not business costs. Sales minus expenses would be misleading."),
            ("b", "Year-over-year growth"), ("t", "No period exists in both years for the same segment, so YoY measures correctly return blank."),
            ("b", "Stock turnover and remaining stock"), ("t", "Stock is a single undated snapshot with no history."),
        ]
        right = [
            ("h", "Corrections applied to the source files"),
            ("b", "International sale Report.csv"), ("t", "The file stacks several exports. Only 12,939 of its 37,432 rows are the true ledger."),
            ("t", "Removed: 5,696 rows repeating earlier rows exactly (index 10196-15891), 1,041 rows of a stray stock list, and 17,756 rows of a re-export with shifted columns."),
            ("t", "That re-export also holds 229 distinct shipping and label charge lines worth about 1.3M. They are not product sales and are excluded."),
            ("b", "Amazon Sale Report.csv"), ("t", "All 128,975 rows are now loaded. Previously non-shipped orders were filtered out, which made cancellations appear to be zero. State spelling variants are standardised in State Clean. The original column is kept."),
            ("t", "7,566 of the 18,332 cancelled lines have no Amount, so the cancelled value shown is lower than the true value of those orders."),
            ("b", "Expense IIGF.csv"), ("t", "A subtotal row (8,095) and a Pending Amount row (-3,095) were being added as expenses, overstating the total as 13,095. The true total is 8,095."),
            ("t", "Expense lines have no dates of their own, so they are not filtered by the date slicers."),
            ("h", ""),
            ("h", "Dataset boundaries"),
            ("b", "Pricing snapshots"), ("t", "May-2022 and P L March 2021 list the same 1,330 products with identical MRPs, so no price movement can be shown. Their SKU codes match no sales or stock table."),
            ("b", "SKU matching"), ("t", "92% of Amazon SKUs match a stock record. Unmatched SKUs are reported, never forced to match."),
            ("b", "ER Wait Time"), ("t", "An unrelated healthcare dataset. It is not loaded into this model."),
        ]
        p.text("left", X, 92, 818, 968, para(left))
        p.text("right", X + 830, 92, 818, 968, para(right))
        return p

    return [amazon(), international(), product(), pricing(), expense(), logistics(), notes(), sku_detail(), marketplace_detail()]
