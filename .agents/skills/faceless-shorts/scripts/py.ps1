# PowerShell launcher for Faceless Shorts virtualenv Python
$FH = if ($env:FACELESS_HOME) { $env:FACELESS_HOME } else { Join-Path $HOME ".faceless-shorts" }
$venvPy = Join-Path $FH "venv\Scripts\python.exe"

if (Test-Path $venvPy) {
    & $venvPy $args
    exit $LASTEXITCODE
}

$sysPy = Get-Command python -ErrorAction SilentlyContinue
if ($sysPy) {
    & python $args
    exit $LASTEXITCODE
}

Write-Error "[ERROR] Python not found. Run scripts\setup.py first."
exit 1

