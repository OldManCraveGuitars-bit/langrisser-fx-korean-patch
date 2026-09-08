param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $RepoRoot ".build-tools-venv"
$PatchDir = Join-Path $RepoRoot "patch"
$DistDir = Join-Path $RepoRoot "release\windows-patcher"
$WorkDir = Join-Path $RepoRoot ".pyinstaller-work"
$ExeName = "Langrisser-FX-KR-Auto-Patcher-v0.84"

if (Test-Path -LiteralPath (Join-Path $DistDir ($ExeName + '.exe'))) {
    throw "Preserve the existing versioned executable; use a new output version"
}

if (-not (Test-Path -LiteralPath $Venv)) {
    & $Python -m venv $Venv
}

$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install --disable-pip-version-check "pyinstaller==6.16.0" "pyinstaller-hooks-contrib==2026.7"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed" }

& $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $ExeName `
    --distpath $DistDir `
    --workpath $WorkDir `
    --specpath $WorkDir `
    --paths $PatchDir `
    --add-data "$(Join-Path $PatchDir 'Langrisser-FX-KR-v0.84.lfxpatch');." `
    (Join-Path $PatchDir "langrisser_fx_auto_patcher.py")
if ($LASTEXITCODE -ne 0) { throw "Automatic patcher build failed" }

Write-Host "Built: $(Join-Path $DistDir ($ExeName + '.exe'))"
