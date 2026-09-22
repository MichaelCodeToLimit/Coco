Write-Host "Packaging Lapis VS Code Extension..." -ForegroundColor Cyan
if (Get-Command npx -ErrorAction SilentlyContinue) {
    Set-Location "$PSScriptRoot\lapis-extension"
    npx @vscode/vsce package --out "$PSScriptRoot\lapis-support.vsix"
    Set-Location $PSScriptRoot
    Write-Host "lapis-support.vsix generated successfully." -ForegroundColor Green
} else {
    Write-Host "Node.js / npx not found. Retaining placeholder VSIX." -ForegroundColor Yellow
}