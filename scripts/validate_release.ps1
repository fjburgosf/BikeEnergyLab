$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
Push-Location -LiteralPath $taskRoot
try {
    & $taskPython scripts/validate_release.py
    if ($LASTEXITCODE -ne 0) { throw 'Acceptance checks failed.' }
    & $taskPython scripts/build_package.py
    if ($LASTEXITCODE -ne 0) { throw 'Package build failed.' }
} finally { Pop-Location }
