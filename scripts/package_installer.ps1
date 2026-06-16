param(
    [string]$Version = "v0.1.0"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$releaseRoot = Join-Path $root "release"
$stagingDir = Join-Path $releaseRoot "installer-staging"
$payloadBuildDir = Join-Path $stagingDir "payload-build"
$payloadZip = Join-Path $stagingDir "payload.zip"
$payloadDir = $payloadBuildDir
$appDir = Join-Path $payloadDir "app"
$installerScript = Join-Path $stagingDir "install.ps1"
$sedPath = Join-Path $stagingDir "installer.sed"
$outputExe = Join-Path $releaseRoot "Video-Text-Setup-$Version.exe"
$launcherSource = Join-Path $root "dist\VideoTextLauncher.exe"

if (-not (Test-Path -LiteralPath $launcherSource)) {
    & (Join-Path $root ".launcher-build\Scripts\python.exe") -m PyInstaller --onefile --windowed --name "VideoTextLauncher" (Join-Path $root "launcher.py")
}
if (-not (Test-Path -LiteralPath $launcherSource)) {
    throw "Launcher exe not found: $launcherSource"
}

if (Test-Path -LiteralPath $stagingDir) {
    Remove-Item -Recurse -Force -LiteralPath $stagingDir
}
New-Item -ItemType Directory -Force -Path $appDir | Out-Null

Copy-Item -Force -LiteralPath $launcherSource -Destination (Join-Path $payloadDir "VideoTextLauncher.exe")

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

$installScriptContent = @'
$ErrorActionPreference = "Stop"

$appName = [string]::Concat([char]0x89C6, [char]0x9891, [char]0x5B57, [char]0x5E55, [char]0x63D0, [char]0x53D6)
$payloadZip = Join-Path $PSScriptRoot "payload.zip"
$payloadExtractDir = Join-Path $PSScriptRoot "payload"
$installDir = Join-Path $env:LOCALAPPDATA "Programs\Video-Text"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Video-Text"
$desktop = [Environment]::GetFolderPath("DesktopDirectory")

Get-Process | Where-Object {
    $_.Path -and $_.Path.StartsWith($installDir, [System.StringComparison]::OrdinalIgnoreCase)
} | Stop-Process -Force

if (Test-Path -LiteralPath $payloadExtractDir) {
    Remove-Item -Recurse -Force -LiteralPath $payloadExtractDir
}
Expand-Archive -LiteralPath $payloadZip -DestinationPath $payloadExtractDir -Force

if (Test-Path -LiteralPath $installDir) {
    Remove-Item -Recurse -Force -LiteralPath $installDir
}
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Get-ChildItem -Force -LiteralPath $payloadExtractDir |
    Copy-Item -Recurse -Force -Destination $installDir

$appDir = Join-Path $installDir "app"
if (Test-Path -LiteralPath $appDir) {
    attrib +h $appDir
}

New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null
$target = Join-Path $installDir "VideoTextLauncher.exe"
$shell = New-Object -ComObject WScript.Shell

$desktopShortcut = $shell.CreateShortcut((Join-Path $desktop ($appName + ".lnk")))
$desktopShortcut.TargetPath = $target
$desktopShortcut.WorkingDirectory = $installDir
$desktopShortcut.Save()

$menuShortcut = $shell.CreateShortcut((Join-Path $startMenuDir ($appName + ".lnk")))
$menuShortcut.TargetPath = $target
$menuShortcut.WorkingDirectory = $installDir
$menuShortcut.Save()

Start-Process -FilePath $target -WorkingDirectory $installDir
'@
Set-Content -LiteralPath $installerScript -Value $installScriptContent -Encoding UTF8

if (Test-Path -LiteralPath $payloadZip) {
    Remove-Item -Force -LiteralPath $payloadZip
}
Compress-Archive -Path (Join-Path $payloadBuildDir "*") -DestinationPath $payloadZip -Force

$stagedFiles = @("install.ps1", "payload.zip")

$sourceFiles = New-Object System.Collections.Generic.List[string]
$fileEntries = New-Object System.Collections.Generic.List[string]
for ($i = 0; $i -lt $stagedFiles.Count; $i++) {
    $fileEntries.Add("FILE$i=$($stagedFiles[$i])")
    $sourceFiles.Add("%FILE$i%=")
}

$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$outputExe
FriendlyName=Video-Text Setup
AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -File install.ps1
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$stagingDir
[SourceFiles0]
$($sourceFiles -join "`r`n")
[Strings]
$($fileEntries -join "`r`n")
"@
Set-Content -LiteralPath $sedPath -Value $sed -Encoding ASCII

if (Test-Path -LiteralPath $outputExe) {
    Remove-Item -Force -LiteralPath $outputExe
}
$iexpress = Join-Path $env:SystemRoot "System32\iexpress.exe"
$process = Start-Process -FilePath $iexpress -ArgumentList @("/N", "/Q", $sedPath) -Wait -PassThru

if (-not (Test-Path -LiteralPath $outputExe)) {
    throw "Installer build failed: $outputExe"
}

Write-Host ""
Write-Host "Done: $outputExe"
exit 0
