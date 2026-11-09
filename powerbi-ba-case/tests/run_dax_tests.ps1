# Run the functional tests against the model open in Power BI Desktop.
# Usage: powershell -File tests/run_dax_tests.ps1   (Power BI Desktop must have the project open)
# Writes tests/dax_results.csv with the value each DAX measure returns.
$ErrorActionPreference = "Stop"
$proc = Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'" | Select-Object -First 1
if (-not $proc) { throw "Power BI Desktop is not running with a model open." }
$dataDir = [regex]::Match($proc.CommandLine, '-s "([^"]+)"').Groups[1].Value
$port = ((Get-Content (Join-Path $dataDir "msmdsrv.port.txt") -Encoding Unicode) -join '').Trim()
$pkg = (Get-AppxPackage *PowerBIDesktop*).InstallLocation
if (-not $pkg) { $pkg = "C:\Program Files\Microsoft Power BI Desktop" }
Add-Type -Path (Join-Path $pkg "bin\Microsoft.PowerBI.AdomdClient.dll")
$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
$conn.Open()

function Invoke-Dax([string]$query) {
    $cmd = $conn.CreateCommand(); $cmd.CommandText = $query
    $r = $cmd.ExecuteReader(); $rows = @()
    while ($r.Read()) { $row = [ordered]@{}; for ($i = 0; $i -lt $r.FieldCount; $i++) { $row[$r.GetName($i)] = $r.GetValue($i) }; $rows += [pscustomobject]$row }
    $r.Close(); return $rows
}

$tests = [ordered]@{
    "FT-01" = "CALCULATE ( [Refill Orders], 'Dim Week'[iso_year] = 2025 )"
    "FT-02" = "CALCULATE ( [Refill Revenue (KRW)], 'Dim Week'[iso_year] = 2025 )"
    "FT-03" = "CALCULATE ( [Active Members (8w)], 'Dim Week'[week_label] = ""2025-W52"" )"
    "FT-04" = "CALCULATE ( [Active Members (8w)], 'Dim Week'[week_label] = ""2025-W52"", 'Dim Region'[region_code] = ""SEL"" )"
    "FT-05" = "CALCULATE ( [New Members], 'Dim Week'[iso_year] = 2025 )"
    "FT-06" = "CALCULATE ( [Acquisition Spend (KRW)], 'Dim Week'[iso_year] = 2025 )"
    "FT-07" = "CALCULATE ( [Blended CAC (KRW)], 'Dim Week'[iso_year] = 2025, 'Dim Region'[region_code] = ""YNG"" )"
    "FT-08" = "CALCULATE ( [Retail Net Revenue (KRW)], 'Dim Week'[iso_year] = 2025 )"
    "FT-09" = "CALCULATE ( [Device Return Rate], 'Dim Week'[iso_year] = 2025 )"
    "FT-10" = "CALCULATE ( [CRM Messages Sent], 'Dim Week'[iso_year] = 2025 )"
    "FT-11" = "CALCULATE ( [CX Tickets], 'Dim Week'[iso_year] = 2025 )"
    "FT-12" = "CALCULATE ( [CX SLA Met %], 'Dim Week'[iso_year] = 2025 )"
    "FT-13" = "[Lapsed Members (12w+)]"
    "FT-14" = "CALCULATE ( [Retention %], 'Fact Cohort Retention'[join_cohort] = ""2024 Q1"", 'Fact Cohort Retention'[months_since_join] = 3 )"
    "BT-01 quarter" = "CALCULATE ( [Active Members (8w)], 'Dim Week'[quarter] = ""2025 Q4"" )"
    "BT-03 W52 retail (complete only)" = "CALCULATE ( [Retail Net Revenue (KRW)], 'Dim Week'[week_label] = ""2025-W52"" )"
    "BT-03 W52 retail (incl. incomplete)" = "CALCULATE ( [Retail Net Revenue incl. Incomplete (KRW)], 'Dim Week'[week_label] = ""2025-W52"" )"
}
$cols = ($tests.GetEnumerator() | ForEach-Object { """$($_.Key)"", $($_.Value)" }) -join ",`n  "
$row = Invoke-Dax "EVALUATE ROW (`n  $cols`n)"
$out = foreach ($p in $row[0].PSObject.Properties) { [pscustomobject]@{ test_id = ($p.Name -replace '^\[|\]$', ''); dax_value = $p.Value } }
$blank = Invoke-Dax "EVALUATE FILTER ( SUMMARIZECOLUMNS ( 'Dim Week'[iso_year], ""am"", [Active Members (8w)] ), ISBLANK ( 'Dim Week'[iso_year] ) )"
$out += [pscustomobject]@{ test_id = "DEF-01 blank-week rows with Active Members"; dax_value = @($blank).Count }
# BT-02: for each fact, the sum over the three regions equals the unfiltered total
$bt2 = Invoke-Dax @"
EVALUATE
ROW (
  "orders", SUMX ( VALUES ( 'Dim Region'[region_code] ), [Refill Orders] ) - [Refill Orders],
  "spend", SUMX ( VALUES ( 'Dim Region'[region_code] ), [Acquisition Spend (KRW)] ) - [Acquisition Spend (KRW)],
  "sellout", SUMX ( VALUES ( 'Dim Region'[region_code] ), [Retail Net Revenue (KRW)] ) - [Retail Net Revenue (KRW)],
  "crm", SUMX ( VALUES ( 'Dim Region'[region_code] ), [CRM Messages Sent] ) - [CRM Messages Sent],
  "cx", SUMX ( VALUES ( 'Dim Region'[region_code] ), [CX Tickets] ) - [CX Tickets]
)
"@
$gap = ($bt2[0].PSObject.Properties | ForEach-Object { [math]::Abs([double]$_.Value) } | Measure-Object -Sum).Sum
$out += [pscustomobject]@{ test_id = "BT-02 region sum minus total (all facts)"; dax_value = $gap }
# BT-04: every measure has a description
$m = Invoke-Dax "EVALUATE SELECTCOLUMNS ( INFO.MEASURES (), ""name"", [Name], ""description"", [Description] )"
$missing = @($m | Where-Object { [string]::IsNullOrWhiteSpace($_.'[description]') }).Count
$out += [pscustomobject]@{ test_id = "BT-04 measures without description"; dax_value = "$missing of $(@($m).Count)" }
$conn.Close()
$csv = Join-Path $PSScriptRoot "dax_results.csv"
$out | Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8
$out | Format-Table -AutoSize
