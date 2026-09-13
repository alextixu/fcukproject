# 把「搬到另一台電腦需要的東西」複製到目的地(外接硬碟或網路磁碟),排除可重算的大檔。
# 用法:powershell -File scripts\pack_for_migration.ps1 -Dest "E:\專題進度"
#       加 -WithRegenerable 才連 features/bigmove/experiments parquet 一起搬(多約 14 GB,但省掉重算 1~2 小時)
param([Parameter(Mandatory=$true)][string]$Dest, [switch]$WithRegenerable)
$Src = Split-Path -Parent $PSScriptRoot
$common = @("/E", "/NFL", "/NDL", "/NJH", "/NJS", "/R:1", "/W:1", "/XD", "__pycache__", ".claude", "_archive")
# 1. 程式、文件、設定、結果(小)
foreach ($d in @("common", "method_xgb", "method_kline", "method_kline_v2", "method_chartgcn", "method_tomt", "backtest", "docs", "scripts")) {
    $xd = @()
    if ($d -eq "common")          { $xd = @("cache") }
    if ($d -eq "method_xgb")      { $xd = @("experiments") }
    if ($d -eq "method_chartgcn") { $xd = @("experiments_paper", "experiments_fusion", "logs", "cache", "cache_2026") }
    if ($d -eq "method_tomt")     { $xd = @("cache") }
    $args = @("$Src\$d", "$Dest\$d") + $common
    if ($xd.Count) { $args += "/XD"; $args += $xd }
    robocopy @args | Out-Null
    "copied $d"
}
Copy-Item "$Src\requirements.txt", "$Src\.gitignore" $Dest -Force
# 2. 原始資料快取(一定要,約 800 MB)
foreach ($d in @("yf", "yf_2026", "official", "yf_hist", "yf_fw", "kline_raw", "finmind", "finmind_2026")) {
    robocopy "$Src\common\cache\$d" "$Dest\common\cache\$d" /E /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null; "copied cache/$d"
}
# 3. XGB 實驗結果(json / testpred / importance,約 1 GB;特徵面板另計)
robocopy "$Src\method_xgb\experiments" "$Dest\method_xgb\experiments" *.json *.csv *_testpred.parquet /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null; "copied xgb experiments (json/testpred)"
robocopy "$Src\method_chartgcn\experiments_2026" "$Dest\method_chartgcn\experiments_2026" *.json *.png *.csv /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null; "copied chartgcn experiments_2026 (json)"
# 4. 可重算的大檔(選擇性)
if ($WithRegenerable) {
    foreach ($d in @("features", "bigmove")) { robocopy "$Src\common\cache\$d" "$Dest\common\cache\$d" /E /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null; "copied cache/$d" }
    robocopy "$Src\method_xgb\experiments" "$Dest\method_xgb\experiments" /E /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null; "copied xgb experiments (all)"
}
# 5. Claude 記憶(專題路徑相同時直接可用)
$mem = "$env:USERPROFILE\.claude\projects\c--Users-alex-Desktop-----\memory"
if (Test-Path $mem) { robocopy $mem "$Dest\_claude_memory" /E /NFL /NDL /NJH /NJS | Out-Null; "copied claude memory → _claude_memory (新機放回 %USERPROFILE%\.claude\projects\<專題路徑編碼>\memory)" }
"done → $Dest"
