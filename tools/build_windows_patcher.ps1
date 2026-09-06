param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $RepoRoot ".build-tools-venv"
$PatchDir = Join-Path $RepoRoot "patch"
$DistDir = Join-Path $RepoRoot "release\windows-patcher"
$WorkDir = Join-Path $RepoRoot ".pyinstaller-work"

if (-not (Test-Path -LiteralPath $Venv)) {
    & $Python -m venv $Venv
}

$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install --disable-pip-version-check "pyinstaller==6.16.0"

& $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "Langrisser-FX-KR-Auto-Patcher" `
    --distpath $DistDir `
    --workpath $WorkDir `
    --specpath $WorkDir `
    --paths $PatchDir `
    --add-data "$(Join-Path $PatchDir 'Langrisser-FX-KR-v0.8.lfxpatch');." `
    (Join-Path $PatchDir "langrisser_fx_auto_patcher.py")

Write-Host "Built: $(Join-Path $DistDir 'Langrisser-FX-KR-Auto-Patcher.exe')"
