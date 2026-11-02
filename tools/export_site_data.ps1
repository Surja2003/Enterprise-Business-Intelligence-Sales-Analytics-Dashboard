# Exports summary tables from the model open in Power BI Desktop into tools/_site_raw (not published: it holds customer names).
$ErrorActionPreference = 'Stop'
$out = Join-Path $PSScriptRoot '_site_raw'
New-Item -ItemType Directory -Force $out | Out-Null
$portFile = Get-ChildItem "$env:USERPROFILE\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces\*\Data\msmdsrv.port.txt" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$port = (Get-Content $portFile.FullName -Encoding Unicode).Trim()
$bin = Split-Path (Get-Process PBIDesktop | Select-Object -First 1).Path
Add-Type -Path "$bin\Microsoft.PowerBI.AdomdClient.dll"
$c = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection "Data Source=localhost:$port"
$c.Open()

$AMZ = "'Amazon Sale Report'"; $INT = "'International sale Report'"; $SALE = "'Sale Report'"; $MAY = "'May-2022'"; $EXP = "'Expense IIGF'"; $WH = "'Cloud Warehouse Compersion Chart'"
$YM = "DimDate[Year Month Sort]"
function AmzDim($col) { "EVALUATE SUMMARIZECOLUMNS($YM, $AMZ[$col], ""s"", [Amazon Revenue], ""u"", [Amazon Units Sold])" }

$queries = [ordered]@{
  months       = "EVALUATE SELECTCOLUMNS(SUMMARIZE(DimDate, DimDate[Year Month Sort], DimDate[Year], DimDate[Quarter], DimDate[Month], DimDate[Month Year]), ""ym"", DimDate[Year Month Sort], ""y"", DimDate[Year], ""q"", DimDate[Quarter], ""m"", DimDate[Month], ""label"", DimDate[Month Year])"
  amz_day      = "EVALUATE SUMMARIZECOLUMNS(DimDate[Date], ""s"", [Amazon Revenue], ""u"", [Amazon Units Sold], ""o"", [Amazon Orders], ""a"", [Amazon All Orders], ""c"", [Amazon Cancelled Orders], ""r"", [Amazon Returned Orders], ""p"", [Amazon In Progress Orders], ""sh"", [Amazon Shipped Orders], ""d"", [Amazon Delivered Orders])"
  amz_status   = "EVALUATE SUMMARIZECOLUMNS($YM, $AMZ[Status Group], ""v"", [Amazon Order Value])"
  amz_style    = AmzDim 'Style'
  amz_state    = AmzDim 'State Clean'
  amz_city     = AmzDim 'ship-city'
  amz_category = AmzDim 'Category'
  amz_size     = AmzDim 'Size'
  amz_fulfil   = AmzDim 'Fulfilment'
  amz_b2b      = AmzDim 'B2B'
  sku_month    = "EVALUATE SUMMARIZECOLUMNS($YM, DimSKU[SKU_Key], ""s"", [Amazon Revenue], ""u"", [Amazon Units Sold], ""o"", [Amazon Orders], ""a"", [Amazon All Orders], ""c"", [Amazon Cancelled Orders], ""r"", [Amazon Returned Orders], ""is"", [International Revenue], ""iu"", [International Units], ""ic"", [International Customers])"
  sku_stock    = "EVALUATE SUMMARIZECOLUMNS(DimSKU[SKU_Key], ""stock"", [Total Stock])"
  sku_attr_amz = "EVALUATE SUMMARIZECOLUMNS($AMZ[SKU_Key], ""cat"", MAX($AMZ[Category]), ""style"", MAX($AMZ[Style]), ""size"", MAX($AMZ[Size]))"
  sku_attr_st  = "EVALUATE SUMMARIZECOLUMNS($SALE[SKU_Key], ""cat"", MAX($SALE[Category]), ""size"", MAX($SALE[Size]), ""colour"", MAX($SALE[Color]))"
  sku_attr_int = "EVALUATE SUMMARIZECOLUMNS($INT[SKU_Key], ""style"", MAX($INT[Style]), ""size"", MAX($INT[Final Size]))"
  sku_day      = "EVALUATE SUMMARIZECOLUMNS(DimSKU[SKU_Key], DimDate[Date], ""s"", [Amazon Revenue])"
  sku_status   = "EVALUATE SUMMARIZECOLUMNS($YM, DimSKU[SKU_Key], $AMZ[Status Group], ""v"", [Amazon Order Value])"
  sku_state    = "EVALUATE SUMMARIZECOLUMNS($YM, DimSKU[SKU_Key], $AMZ[State Clean], ""s"", [Amazon Revenue])"
  sku_city     = "EVALUATE SUMMARIZECOLUMNS($YM, DimSKU[SKU_Key], $AMZ[ship-city], ""s"", [Amazon Revenue])"
  int_day      = "EVALUATE SUMMARIZECOLUMNS(DimDate[Date], ""s"", [International Revenue], ""u"", [International Units])"
  int_month    = "EVALUATE SUMMARIZECOLUMNS($YM, ""s"", [International Revenue], ""u"", [International Units], ""l"", [International Listed Value], ""rs"", SUM($INT[RATE]), ""rc"", COUNT($INT[RATE]))"
  int_customer = "EVALUATE SUMMARIZECOLUMNS($YM, $INT[CUSTOMER], ""s"", [International Revenue], ""u"", [International Units])"
  int_style    = "EVALUATE SUMMARIZECOLUMNS($YM, $INT[Style], ""s"", [International Revenue], ""u"", [International Units])"
  int_size     = "EVALUATE SUMMARIZECOLUMNS($YM, $INT[Final Size], ""s"", [International Revenue])"
  stock_cat    = "EVALUATE SUMMARIZECOLUMNS($SALE[Category], ""stock"", [Total Stock])"
  stock_size   = "EVALUATE SUMMARIZECOLUMNS($SALE[Size], ""stock"", [Total Stock])"
  stock_colour = "EVALUATE SUMMARIZECOLUMNS($SALE[Color], ""stock"", [Total Stock])"
  stock_units  = "EVALUATE SUMMARIZECOLUMNS($YM, $SALE[Category], ""u"", [Units Sold on Matched SKUs])"
  prices       = "EVALUATE SELECTCOLUMNS($MAY, ""sku"", $MAY[Sku], ""cat"", $MAY[Category], ""Amazon"", $MAY[Amazon MRP], ""Amazon FBA"", $MAY[Amazon FBA MRP], ""Flipkart"", $MAY[Flipkart MRP], ""Myntra"", $MAY[Myntra MRP], ""Ajio"", $MAY[Ajio MRP], ""Snapdeal"", $MAY[Snapdeal MRP], ""Paytm"", $MAY[Paytm MRP], ""Limeroad"", $MAY[Limeroad MRP])"
  expenses     = "EVALUATE SUMMARIZECOLUMNS($EXP[Expense Particular], ""v"", [Total Recorded Expenses])"
  receipts     = "EVALUATE SUMMARIZECOLUMNS($EXP[Received Date], ""v"", [Total Received Amount])"
  wh_rates     = "EVALUATE SUMMARIZECOLUMNS($WH[Service / Process], ""ship"", [Shiprocket Rate], ""incr"", [Increff Rate])"
  wh_terms     = "EVALUATE SELECTCOLUMNS(FILTER($WH, $WH[Section] <> ""Rates""), ""row"", $WH[Row], ""section"", $WH[Section], ""item"", $WH[Item], ""detail"", $WH[Detail])"
  totals       = "EVALUATE ROW(""total"", [Total Recorded Sales], ""amazon"", [Amazon Revenue], ""intl"", [International Revenue], ""orders"", [Amazon Orders], ""allOrders"", [Amazon All Orders], ""units"", [Amazon Units Sold], ""intlUnits"", [International Units], ""customers"", [International Customers], ""cancelled"", [Amazon Cancelled Orders], ""returned"", [Amazon Returned Orders], ""delivered"", [Amazon Delivered Orders], ""shipped"", [Amazon Shipped Orders], ""skusAmz"", [Unique Amazon SKUs], ""skusCat"", [Unique Catalog SKUs], ""matched"", [Matched Amazon SKUs], ""matchedUnits"", [Units Sold on Matched SKUs], ""stock"", [Total Stock], ""priced"", [Products With Prices], ""variation"", [Products With Price Variation], ""avgGap"", [Avg Price Spread], ""maxGap"", [Max Price Spread], ""expenses"", [Total Recorded Expenses], ""receipts"", [Total Received Amount], ""avgRate"", [International Average Rate], ""discount"", [International Discount vs Listed %], ""top10share"", [Top 10 Style Share %], ""momLatest"", [Amazon Latest Month MoM %], ""momDay"", [Amazon Latest Month Per Day MoM %])"
}

foreach ($name in $queries.Keys) {
  $cmd = $c.CreateCommand(); $cmd.CommandText = $queries[$name]; $cmd.CommandTimeout = 300
  $r = $cmd.ExecuteReader()
  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add((0..($r.FieldCount - 1) | ForEach-Object { $r.GetName($_) }) -join "`t")
  while ($r.Read()) {
    $vals = for ($i = 0; $i -lt $r.FieldCount; $i++) {
      $v = $r.GetValue($i)
      if ($v -is [DBNull] -or $null -eq $v) { '' }
      elseif ($v -is [datetime]) { $v.ToString('yyyy-MM-dd') }
      elseif ($v -is [double] -or $v -is [decimal] -or $v -is [single]) { ([double]$v).ToString('R', [Globalization.CultureInfo]::InvariantCulture) }
      else { ("$v" -replace '[\t\r\n]+', ' ') }
    }
    $lines.Add($vals -join "`t")
  }
  $r.Close()
  [IO.File]::WriteAllLines((Join-Path $out "$name.tsv"), $lines, (New-Object Text.UTF8Encoding $false))
  "{0,-14} {1,7} rows" -f $name, ($lines.Count - 1)
}
$c.Close()
