param([switch]$SkipSmokeTest)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create .venv and install .[windows] first.' }
Push-Location -LiteralPath $taskRoot
try {
    & $taskPython scripts/build_provenance.py
    if ($LASTEXITCODE -ne 0) { throw 'Build provenance failed.' }
    $taskManifest = Join-Path $taskRoot 'build\source_manifest.json'
    $taskVersionInfo = Join-Path $taskRoot 'build\windows_version_info.txt'
    & $taskPython -m PyInstaller --noconfirm --onedir --name BikeEnergyLab --version-file $taskVersionInfo --paths src --collect-data matplotlib --collect-data scipy.stats --hidden-import matplotlib.backends.backend_svg --hidden-import matplotlib.backends.backend_pdf --recursive-copy-metadata bikeenergylab --add-data "${taskManifest};bikeenergylab" --exclude-module IPython --exclude-module notebook --exclude-module pytest --exclude-module numba --exclude-module llvmlite --exclude-module pyarrow --exclude-module torch --exclude-module tensorflow --distpath dist --workpath build --specpath build scripts/windows_entry.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    if (-not $SkipSmokeTest) {
        & '.\dist\BikeEnergyLab\BikeEnergyLab.exe' --version
        if ($LASTEXITCODE -ne 0) { throw 'Executable version check failed.' }
        & '.\dist\BikeEnergyLab\BikeEnergyLab.exe' simulate configs/flat.yaml --output results/windows-smoke --no-figures
        if ($LASTEXITCODE -ne 0) { throw 'Executable simulation failed.' }
        & '.\dist\BikeEnergyLab\BikeEnergyLab.exe' gui --smoke-test
        if ($LASTEXITCODE -ne 0) { throw 'Executable GUI smoke check failed.' }
    }
    & $taskPython scripts/package_windows.py
    if ($LASTEXITCODE -ne 0) { throw 'Portable packaging failed.' }
} finally { Pop-Location }
