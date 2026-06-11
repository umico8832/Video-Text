[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$directories = @(
    "build",
    "dist",
    ".launcher-build"
)

$files = @(
    "*.log",
    "*.spec.bak"
)

$excludedSearchDirectories = @(
    ".git",
    ".venv",
    ".launcher-build",
    "build",
    "dist",
    "models",
    "outputs",
    "__pycache__",
    "Video-Text记录"
)

foreach ($directory in $directories) {
    $path = Join-Path $root $directory
    if (Test-Path -LiteralPath $path) {
        if ($PSCmdlet.ShouldProcess($path, "Remove directory")) {
            Remove-Item -LiteralPath $path -Recurse -Force
        }
    }
}

$searchRoots = Get-ChildItem -Path $root -Directory -Force | Where-Object {
    $_.Name -notin $excludedSearchDirectories
}

$rootCache = Join-Path $root "__pycache__"
if (Test-Path -LiteralPath $rootCache) {
    if ($PSCmdlet.ShouldProcess($rootCache, "Remove directory")) {
        Remove-Item -LiteralPath $rootCache -Recurse -Force
    }
}

$searchRoots | ForEach-Object {
    Get-ChildItem -Path $_.FullName -Recurse -Directory -Filter "__pycache__"
} | ForEach-Object {
    if ($PSCmdlet.ShouldProcess($_.FullName, "Remove directory")) {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }
}

$searchRoots | ForEach-Object {
    Get-ChildItem -Path $_.FullName -Recurse -File -Include "*.pyc", "*.pyo"
} | ForEach-Object {
    if ($PSCmdlet.ShouldProcess($_.FullName, "Remove file")) {
        Remove-Item -LiteralPath $_.FullName -Force
    }
}

foreach ($pattern in $files) {
    Get-ChildItem -Path $root -File -Filter $pattern | ForEach-Object {
        if ($PSCmdlet.ShouldProcess($_.FullName, "Remove file")) {
            Remove-Item -LiteralPath $_.FullName -Force
        }
    }
}

Write-Host "Clean complete."
