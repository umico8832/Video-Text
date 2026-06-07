$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Test-Python312 {
    param(
        [string]$Exe,
        [string[]]$Args = @()
    )

    try {
        $version = & $Exe @Args -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        return $LASTEXITCODE -eq 0 -and $version.Trim() -eq "3.12"
    } catch {
        return $false
    }
}

$pythonExe = $null
$pythonArgs = @()
if (Test-Python312 -Exe "py" -Args @("-3.12")) {
    $pythonExe = "py"
    $pythonArgs = @("-3.12")
} elseif (Test-Python312 -Exe "python") {
    $pythonExe = "python"
}

if (-not $pythonExe) {
    throw "Python 3.12 was not found. Install Python 3.12 and enable PATH."
}

$buildPython = Join-Path $root ".launcher-build\Scripts\python.exe"
if (-not (Test-Path $buildPython)) {
    & $pythonExe @pythonArgs -m venv ".launcher-build"
}

& $buildPython -m pip install --upgrade pip pyinstaller
& $buildPython -m PyInstaller --onefile --windowed --name "VideoTextLauncher" launcher.py

$sourceExe = Join-Path $root "dist\VideoTextLauncher.exe"
$targetName = [string]::Concat(
    [char]0x89C6,
    [char]0x9891,
    [char]0x5B57,
    [char]0x5E55,
    [char]0x63D0,
    [char]0x53D6,
    ".exe"
)
$targetExe = Join-Path $root ("dist\" + $targetName)
if (-not (Test-Path $sourceExe)) {
    throw "Build finished but launcher exe was not found: $sourceExe"
}
Move-Item -Force -LiteralPath $sourceExe -Destination $targetExe
Copy-Item -Force -LiteralPath $targetExe -Destination (Join-Path $root $targetName)

Write-Host ""
Write-Host ("Done: dist\" + $targetName)
Write-Host ("Copied to project root: " + $targetName)
