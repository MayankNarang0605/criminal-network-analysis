# =============================================================================
# NCRB Criminal Network Analysis System — one-command launcher (Windows)
#
# Creates the virtual environment if needed, installs dependencies, builds the
# dashboard, and starts the server. Everything runs in one process against a
# single SQLite file; no Docker, database server or search cluster is required.
#
#   .\run.ps1              start the platform (builds the UI if missing)
#   .\run.ps1 -Dev         run backend + Vite dev server with hot reload
#   .\run.ps1 -Test        run the test suite
#   .\run.ps1 -Reset       discard the database and re-ingest from scratch
# =============================================================================
[CmdletBinding()]
param(
    [switch]$Dev,
    [switch]$Test,
    [switch]$Reset,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$env:PYTHONHASHSEED = "0"
$Root = $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"

function Info($msg) { Write-Host "  $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  NCRB Criminal Network Analysis System" -ForegroundColor White
Write-Host "  National Crime Records Bureau | Women Safety Division | MHA" -ForegroundColor DarkGray
Write-Host ""

# --- 1. Python environment -----------------------------------------------
if (-not (Test-Path -LiteralPath $Py)) {
    Info "Creating virtual environment..."
    python -m venv $Venv
    if (-not (Test-Path -LiteralPath $Py)) { throw "Failed to create venv. Is Python 3.11+ installed and on PATH?" }
}

$stamp = Join-Path $Venv ".deps-installed"
$reqs = Join-Path $Root "backend\requirements.txt"
$needsInstall = -not (Test-Path -LiteralPath $stamp)
if (-not $needsInstall) {
    $needsInstall = (Get-Item $reqs).LastWriteTime -gt (Get-Item $stamp).LastWriteTime
}
if ($needsInstall) {
    Info "Installing Python dependencies..."
    & $Py -m pip install --quiet --disable-pip-version-check --upgrade pip
    & $Py -m pip install --quiet --disable-pip-version-check -r $reqs
    Set-Content -LiteralPath $stamp -Value (Get-Date -Format o)
    Ok "Dependencies ready."
}

# --- 2. Optional reset ----------------------------------------------------
if ($Reset) {
    Warn "Removing existing database; the corpus will be rebuilt on next start."
    Get-ChildItem -LiteralPath (Join-Path $Root "runtime") -Filter "ncrb.db*" -ErrorAction SilentlyContinue |
        Remove-Item -Force
}

# --- 3. Tests -------------------------------------------------------------
if ($Test) {
    Info "Running test suite..."
    Push-Location (Join-Path $Root "backend")
    try { & $Py -m pytest tests/ -v --tb=short }
    finally { Pop-Location }
    exit $LASTEXITCODE
}

# --- 4. Frontend ----------------------------------------------------------
$frontend = Join-Path $Root "frontend"
$dist = Join-Path $frontend "dist"
$nodeModules = Join-Path $frontend "node_modules"
$npm = Get-Command npm -ErrorAction SilentlyContinue

if ($npm) {
    if (-not (Test-Path -LiteralPath $nodeModules)) {
        Info "Installing frontend dependencies (first run only)..."
        Push-Location $frontend
        try { npm install --no-audit --no-fund --silent }
        finally { Pop-Location }
    }
    if (-not $Dev -and -not (Test-Path -LiteralPath (Join-Path $dist "index.html"))) {
        Info "Building dashboard..."
        Push-Location $frontend
        try { npm run build }
        finally { Pop-Location }
        Ok "Dashboard built."
    }
} else {
    Warn "npm not found. The API will run, but the dashboard will not be available."
}

# --- 5. Launch ------------------------------------------------------------
Write-Host ""
if ($Dev) {
    Ok "Starting in development mode."
    Write-Host "    Dashboard : http://localhost:5173" -ForegroundColor White
    Write-Host "    API docs  : http://localhost:$Port/docs" -ForegroundColor White
    Write-Host ""
    Info "Launching backend in a separate window..."
    Start-Process -FilePath $Py `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "$Port" `
        -WorkingDirectory (Join-Path $Root "backend")
    Start-Sleep -Seconds 3
    Push-Location $frontend
    try { npm run dev }
    finally { Pop-Location }
} else {
    Ok "Starting the platform."
    Write-Host "    Dashboard : http://localhost:$Port/app" -ForegroundColor White
    Write-Host "    API docs  : http://localhost:$Port/docs" -ForegroundColor White
    Write-Host "    Health    : http://localhost:$Port/health" -ForegroundColor White
    Write-Host ""
    Write-Host "    Sign in as investigator / invest123!  (or admin / admin123!)" -ForegroundColor DarkGray
    Write-Host "    First start ingests the corpus and runs full analytics (~15s)." -ForegroundColor DarkGray
    Write-Host ""
    Push-Location (Join-Path $Root "backend")
    try { & $Py -m uvicorn app.main:app --host 0.0.0.0 --port $Port }
    finally { Pop-Location }
}
