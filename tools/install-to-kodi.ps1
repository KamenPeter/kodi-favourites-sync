# Quick install script for v1.0.68
# Copies the addon to Kodi's addons folder

$source = "C:\Users\stein\GitHub\kodi-favourites-sync\dist\plugin.service.favourites-sync-1.0.68.zip"
$kodiAddons = "C:\Users\stein\AppData\Roaming\Kodi\addons"
$addonFolder = "$kodiAddons\plugin.service.favourites-sync"

Write-Host "Installing v1.0.68 to Kodi..." -ForegroundColor Cyan

# Backup existing if present
if (Test-Path $addonFolder) {
    Write-Host "Backing up existing addon..." -ForegroundColor Yellow
    $backupPath = "$kodiAddons\plugin.service.favourites-sync.backup"
    if (Test-Path $backupPath) {
        Remove-Item $backupPath -Recurse -Force
    }
    Copy-Item $addonFolder $backupPath -Recurse
}

# Remove old version
if (Test-Path $addonFolder) {
    Write-Host "Removing old version..." -ForegroundColor Yellow
    Remove-Item $addonFolder -Recurse -Force
}

# Extract new version
Write-Host "Extracting v1.0.68..." -ForegroundColor Cyan
Expand-Archive -Path $source -DestinationPath $kodiAddons -Force

Write-Host "✓ Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Restart Kodi to load the new version"
Write-Host "2. Check Settings -> Profiles (Multi-Device) -> Manage Profiles..."
Write-Host "3. Review kodi.log for any errors"
Write-Host ""
Write-Host "Backup location: $backupPath" -ForegroundColor Gray
