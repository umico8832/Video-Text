param(
    [string]$Version = "v0.1.0"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$releaseRoot = Join-Path $root "release"
$packageName = "Video-Text-$Version"
$packageDir = Join-Path $releaseRoot $packageName
$appDir = Join-Path $packageDir "app"
$exeName = [string]::Concat(
    [char]0x89C6,
    [char]0x9891,
    [char]0x5B57,
    [char]0x5E55,
    [char]0x63D0,
    [char]0x53D6,
    ".exe"
)
$distExe = Join-Path $root ("dist\" + $exeName)
$rootExe = Join-Path $packageDir $exeName
$zipPath = Join-Path $releaseRoot "$packageName.zip"

if (-not (Test-Path -LiteralPath $distExe)) {
    throw "Launcher exe not found. Run .\build_launcher.ps1 first: $distExe"
}

if (Test-Path -LiteralPath $packageDir) {
    Remove-Item -Recurse -Force -LiteralPath $packageDir
}
New-Item -ItemType Directory -Force -Path $appDir | Out-Null

Copy-Item -Force -LiteralPath $distExe -Destination $rootExe

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
    "WINDOWS_SETUP.md"
)

foreach ($file in $runtimeFiles) {
    $source = Join-Path $root $file
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Runtime file not found: $source"
    }
    Copy-Item -Force -LiteralPath $source -Destination (Join-Path $appDir $file)
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -Force -LiteralPath $zipPath
}
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Done: $zipPath"
Write-Host "Package layout:"
Write-Host ("  " + $packageName + "\" + $exeName)
Write-Host "  $packageName\app\"
