param(
    [string]$Version = "v0.1.0",
    [switch]$IncludeModels,
    [switch]$SkipWheels,
    [string]$InnoSetupCompiler = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$releaseRoot = Join-Path $root "release"
$stagingDir = Join-Path $releaseRoot "installer-staging"
$payloadDir = Join-Path $stagingDir "payload"
$appDir = Join-Path $payloadDir "app"
$wheelsDir = Join-Path $appDir "wheels"
$installerDir = Join-Path $root "installer"
$installerScript = Join-Path $installerDir "VideoTextInstaller.iss"
$outputExe = Join-Path $releaseRoot "Video-Text-Setup-$Version.exe"
$launcherSource = Join-Path $root "dist\VideoTextLauncher.exe"
$launcherChineseName = [string]::Concat(
    [char]0x89C6,
    [char]0x9891,
    [char]0x5B57,
    [char]0x5E55,
    [char]0x63D0,
    [char]0x53D6,
    ".exe"
)
$launcherChineseSource = Join-Path $root ("dist\" + $launcherChineseName)

function Resolve-InnoSetupCompiler {
    param([string]$ConfiguredPath)

    if ($ConfiguredPath) {
        if (Test-Path -LiteralPath $ConfiguredPath) {
            return (Resolve-Path -LiteralPath $ConfiguredPath).Path
        }
        throw "Inno Setup compiler not found: $ConfiguredPath"
    }

    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php or pass -InnoSetupCompiler <path-to-ISCC.exe>."
}

function Copy-RuntimeFile {
    param([string]$RelativePath)

    $source = Join-Path $root $RelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Runtime file not found: $source"
    }
    Copy-Item -Force -LiteralPath $source -Destination (Join-Path $appDir $RelativePath)
}

function Resolve-Python312 {
    if (Test-Python312 -Exe "py" -Args @("-3.12")) {
        return @{ Exe = "py"; Args = @("-3.12") }
    }
    if (Test-Python312 -Exe "python") {
        return @{ Exe = "python"; Args = @() }
    }
    throw "Python 3.12 was not found. Install Python 3.12 and enable PATH."
}

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

$launcherScript = Join-Path $root "launcher.py"
$launcherOutdated = $true
if (Test-Path -LiteralPath $launcherChineseSource) {
    $launcherOutdated = (Get-Item -LiteralPath $launcherChineseSource).LastWriteTime -lt (Get-Item -LiteralPath $launcherScript).LastWriteTime
} elseif (Test-Path -LiteralPath $launcherSource) {
    $launcherOutdated = (Get-Item -LiteralPath $launcherSource).LastWriteTime -lt (Get-Item -LiteralPath $launcherScript).LastWriteTime
}

if ($launcherOutdated) {
    & (Join-Path $root "build_launcher.ps1")
}

if (Test-Path -LiteralPath $launcherChineseSource) {
    $launcherSource = $launcherChineseSource
} elseif (-not (Test-Path -LiteralPath $launcherSource)) {
    throw "Launcher exe not found. Run .\build_launcher.ps1 first."
}

if (-not (Test-Path -LiteralPath $installerScript)) {
    throw "Installer script not found: $installerScript"
}

if (Test-Path -LiteralPath $stagingDir) {
    Remove-Item -Recurse -Force -LiteralPath $stagingDir
}
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null

Copy-Item -Force -LiteralPath $launcherSource -Destination (Join-Path $payloadDir $launcherChineseName)

$runtimeFiles = @(
    "advanced_cookie_utils.py",
    "advanced_cookies_tab.py",
    "advanced_env_tab.py",
    "advanced_model_tab.py",
    "advanced_model_utils.py",
    "advanced_settings_dialog.py",
    "download_errors.py",
    "env_checker.py",
    "extract_subtitle.py",
    "gpu_runtime.py",
    "gui_app_utils.py",
    "gui_confirmations.py",
    "gui_cookie_utils.py",
    "gui_log_utils.py",
    "gui_model_utils.py",
    "gui_status_utils.py",
    "media_downloader.py",
    "model_config.py",
    "model_picker_dialog.py",
    "output_paths.py",
    "process_utils.py",
    "requirements.txt",
    "settings.example.json",
    "settings_manager.py",
    "subtitle_parser.py",
    "subtitle_selector.py",
    "transcriber.py",
    "ui_components.py",
    "video_text_gui.py",
    "workers.py",
    "WINDOWS_SETUP.md"
)

foreach ($file in $runtimeFiles) {
    Copy-RuntimeFile -RelativePath $file
}

if ($IncludeModels) {
    $modelsDir = Join-Path $root "models"
    if (Test-Path -LiteralPath $modelsDir) {
        Copy-Item -Recurse -Force -LiteralPath $modelsDir -Destination (Join-Path $appDir "models")
    } else {
        Write-Warning "Models directory not found, skipping: $modelsDir"
    }
}

if (-not $SkipWheels) {
    New-Item -ItemType Directory -Force -Path $wheelsDir | Out-Null
    $python = Resolve-Python312
    & $python.Exe @($python.Args) -m pip download `
        --only-binary=:all: `
        --dest $wheelsDir `
        -r (Join-Path $root "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to download bundled wheels."
    }
}

$iscc = Resolve-InnoSetupCompiler -ConfiguredPath $InnoSetupCompiler
if (Test-Path -LiteralPath $outputExe) {
    Remove-Item -Force -LiteralPath $outputExe
}

& $iscc "/DMyAppVersion=$Version" "/O$releaseRoot" "/FVideo-Text-Setup-$Version" $installerScript
if ($LASTEXITCODE -ne 0) {
    throw "Installer build failed with exit code $LASTEXITCODE."
}
if (-not (Test-Path -LiteralPath $outputExe)) {
    throw "Installer build finished but output was not found: $outputExe"
}

Write-Host ""
Write-Host "Done: $outputExe"
Write-Host "Install wizard includes:"
Write-Host "  - install directory selection"
Write-Host "  - optional desktop shortcut"
Write-Host "  - Start Menu shortcut"
Write-Host "  - Windows uninstall entry"
if (-not $SkipWheels) {
    Write-Host "  - bundled Python dependency wheels"
}
if ($IncludeModels) {
    Write-Host "  - bundled models directory"
}
exit 0
