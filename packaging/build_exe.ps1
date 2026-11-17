# Build dist\GraphMTG.exe (Windows).
#
#   .\packaging\build_exe.ps1                   # uses .venv if present, else `python`
#
# Steps: build the web UI (npm ci + npm run build), install PyInstaller, run the spec.
# Each native step is checked via $LASTEXITCODE. (Not $ErrorActionPreference = 'Stop': in Windows
# PowerShell 5.1 that turns harmless stderr warnings from pip/npm into fatal errors.)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = if (Test-Path "$root\.venv\Scripts\python.exe") { "$root\.venv\Scripts\python.exe" } else { "python" }

Write-Host "==> Building web UI"
Push-Location web
npm ci --no-fund --no-audit
if ($LASTEXITCODE) { throw "npm ci failed" }
npm run build
if ($LASTEXITCODE) { throw "npm run build failed" }
Pop-Location

Write-Host "==> Installing build dependencies"
& $python -m pip install --quiet "pyinstaller==6.22.3" "httpx>=0.27" "fastapi>=0.115" "uvicorn>=0.30"
if ($LASTEXITCODE) { throw "pip install failed" }

Write-Host "==> Running PyInstaller"
& $python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller packaging\GraphMTG.spec
if ($LASTEXITCODE) { throw "PyInstaller failed" }

$exe = Get-Item dist\GraphMTG.exe
Write-Host ("==> Built {0} ({1:N1} MB)" -f $exe.FullName, ($exe.Length / 1MB))
