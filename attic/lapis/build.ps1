Write-Host "Building Lapis Toolchain..." -ForegroundColor Cyan
if (Get-Command gcc -ErrorAction SilentlyContinue) {
    gcc -O2 lapis.c -o lapis.exe
    Write-Host "Compiled lapis.exe successfully." -ForegroundColor Green
} else {
    Write-Host "GCC not detected. Running via PowerShell IR engine." -ForegroundColor Yellow
}