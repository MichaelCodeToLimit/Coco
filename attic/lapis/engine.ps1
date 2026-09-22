param (
    [string]$Action = "app.lp",
    [string]$Target = ""
)

$lapisDir = "$env:LOCALAPPDATA\Lapis"

if ($Action -in @("ide", "studio")) {
    $idePath = "$lapisDir\ide.html"
    $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    Start-Process msedge -ArgumentList "--app=file:///$($idePath.Replace('\', '/'))?v=$timestamp", "--window-size=1280,820"
    exit 0
}

$File = if ($Action -in @("run", "start")) {
    if ([string]::IsNullOrWhiteSpace($Target)) { "app.lp" } else { $Target }
} else {
    $Action
}

$targetPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($File)
if (-not (Test-Path $targetPath)) {
    Write-Host "Error: Could not find file '$targetPath'" -ForegroundColor Red
    exit 1
}

$codeRaw = Get-Content -Path $targetPath -Raw -Encoding utf8
if ($null -eq $codeRaw) { $codeRaw = "" }
$fileBytes = [System.Text.Encoding]::UTF8.GetBytes($codeRaw)
$b64 = [Convert]::ToBase64String($fileBytes)

$template = Get-Content -Path "$lapisDir\template.html" -Raw -Encoding utf8
$rendered = $template.Replace("LAPIS_PAYLOAD_BASE64", $b64)

$timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$tempHtml = "$lapisDir\active_app.html"
[System.IO.File]::WriteAllText($tempHtml, $rendered, [System.Text.Encoding]::UTF8)

Get-Process msedge -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*Lapis*" -and $_.MainWindowTitle -notlike "*Studio*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Process msedge -ArgumentList "--app=file:///$($tempHtml.Replace('\', '/'))?v=$timestamp", "--window-size=480,720"