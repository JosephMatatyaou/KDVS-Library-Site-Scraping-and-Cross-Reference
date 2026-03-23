$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

python -m PyInstaller `
  --clean `
  --noconfirm `
  --onefile `
  --windowed `
  --icon assets/icon.ico `
  --name TheCharter3000 `
  MergedKDVSApp.py

if (Test-Path "dist/TheCharter3000-Windows.zip") {
  Remove-Item "dist/TheCharter3000-Windows.zip" -Force
}

Compress-Archive -Path "dist/TheCharter3000.exe" -DestinationPath "dist/TheCharter3000-Windows.zip" -Force

Write-Host "Created $RootDir/dist/TheCharter3000-Windows.zip"
