# 项目交接报告

## 1. 项目基本信息

- **项目名称**：视频字幕提取（Video-Text）
- **项目类型**：Windows 桌面应用（Python GUI 工具）
- **当前开发阶段**：早期可用阶段，核心功能已实现，具备基本 GUI 和完整提取流程
- **主要功能目标**：从 B 站 / YouTube 视频链接中提取中文字幕文本，支持直接下载字幕或通过 Whisper AI 语音识别生成字幕
- **当前已实现功能**：
  - ✅ PySide6 GUI 界面，支持输入视频链接、选择 Whisper 模型、选择设备（auto/cuda/cpu）
  - ✅ 自动检测并优先下载视频自带的中文字幕（人工字幕优先，自动字幕次之）
  - ✅ 无中文字幕时，下载音频并通过 faster-whisper 进行中文语音识别
  - ✅ 支持多种字幕格式解析（SRT、VTT、ASS/SSA、JSON/JSON3）
  - ✅ 环境检查功能（FFmpeg、yt-dlp、faster-whisper、CUDA/GPU）
  - ✅ 一键环境准备（自动安装缺失依赖）
  - ✅ GPU 加速支持（CUDA），包含 GPU 失败自动回退 CPU 的机制
  - ✅ Cookie 支持（不使用 / 从浏览器读取 / cookies.txt 文件）
  - ✅ yt-dlp 更新功能
  - ✅ GPU 加速组件安装功能（nvidia-cublas-cu12、nvidia-cudnn-cu12）
  - ✅ 轻量级启动器（launcher.py），自动创建 .venv 并安装依赖
  - ✅ PyInstaller 打包启动器 exe（视频字幕提取.exe）
  - ✅ 设置持久化（settings.json）
  - ✅ 输出文件保存到 outputs/ 目录
  - ✅ 支持从浏览器读取 Cookies（Chrome/Edge/Firefox）
- **当前未实现功能**：
  - ❌ 批量处理（一次处理多个视频）
  - ❌ 进度条精确显示（当前进度条为不确定模式）
  - ❌ 字幕时间轴保留（输出为纯文本，丢弃时间信息）
  - ❌ 多语言字幕支持（当前硬编码为中文 zh）
  - ❌ 字幕翻译功能
  - ❌ 视频下载功能（只下载音频）
  - ❌ 历史记录功能
  - ❌ 输出格式选择（当前只输出 .txt）
  - ❌ 取消正在进行的任务
  - ❌ 自动更新检查

## 2. 技术栈

- **前端技术栈**：PySide6（Qt for Python），纯代码构建 UI（无 .ui 文件）
- **后端技术栈**：Python 3.12，纯 Python 实现
- **数据库/存储**：无数据库，使用 JSON 文件（settings.json）存储配置
- **构建工具**：PyInstaller（用于打包启动器 exe）
- **主要依赖**：
  - `PySide6` — GUI 框架
  - `yt-dlp` — 视频信息获取和音频下载
  - `faster-whisper` — Whisper 语音识别引擎
  - `imageio-ffmpeg` — FFmpeg 二进制文件提供
  - `ctranslate2` — GPU 推理加速（faster-whisper 的底层依赖）
  - `nvidia-cublas-cu12`、`nvidia-cudnn-cu12` — 可选的 CUDA GPU 加速库
- **运行环境要求**：
  - Windows 10/11（主要目标平台，代码有跨平台兼容但以 Windows 为主）
  - Python 3.12
  - FFmpeg（通过 imageio-ffmpeg 自带或系统安装）
  - 可选：NVIDIA GPU + CUDA 支持

## 3. 项目目录结构分析

```
Video-Text/
├── video_text_gui.py          # 主 GUI 应用程序（PySide6 窗口、环境检查、任务调度）
├── extract_subtitle.py        # 核心业务逻辑（字幕提取、音频下载、语音识别）
├── launcher.py                # 启动器（自动创建 venv、安装依赖、启动 GUI）
├── requirements.txt           # Python 依赖清单（4 个包）
├── settings.json              # 用户配置持久化（URL、路径、模型、Cookie 设置等）
├── WINDOWS_SETUP.md           # 用户使用说明和开发者构建指南
├── 启动软件.bat                # Windows 批处理启动入口（调用 launcher.py）
├── launch_test.bat            # 开发测试启动脚本（直接用 .venv python 运行 GUI）
├── build_launcher.bat         # 构建启动器 exe 的批处理入口
├── build_launcher.ps1         # 构建启动器 exe 的 PowerShell 脚本（核心构建逻辑）
├── VideoTextLauncher.spec     # PyInstaller 打包配置文件
├── 视频字幕提取.exe             # 已构建的启动器 exe（分发给用户）
├── gui.err.log                # GUI 错误日志（当前为空）
├── gui.out.log                # GUI 输出日志（当前为空）
├── launch_err.log             # 测试启动错误日志（当前为空）
├── launch_out.log             # 测试启动输出日志（当前为空）
├── launcher.log               # 启动器运行日志
├── outputs/                   # 字幕提取结果输出目录（当前为空）
├── build/                     # PyInstaller 构建中间产物目录
│   └── VideoTextLauncher/     # 启动器构建临时文件
└── video-text-ahespcn3/       # 临时工作目录（音频下载临时文件，可清理）
    └── audio.mp3
```

## 4. 核心代码模块

### 4.1 GUI 主窗口 — `video_text_gui.py`

- **文件位置**：`video_text_gui.py`（767 行）
- **当前作用**：整个 GUI 应用的入口和主界面，包含：
  - `MainWindow` 类：主窗口，包含输入区（URL、模型选择、设备选择）、环境配置区（FFmpeg/yt-dlp 路径、Cookie 配置）、操作按钮区、日志区、结果展示区
  - `EnvWorker` 类：环境检查/安装的工作线程（QThread + QObject 模式）
  - `ExtractWorker` 类：字幕提取的工作线程
  - 辅助函数：`read_settings()`/`write_settings()` 配置读写、`ensure_ffmpeg_link()` FFmpeg 链接创建、`configure_app_font()` 中文字体配置、`install_command()` 智能选择 pip/uv 安装
- **与其他模块的关系**：
  - 导入并调用 `extract_subtitle` 模块的核心 `extract()` 函数
  - 读写 `settings.json` 持久化配置
  - 通过 `QThread` + `moveToThread` 模式在后台线程执行耗时操作
- **是否存在明显问题**：
  - ⚠️ `run_command_with_log` 函数使用了 `assert process.stdout is not None`，在优化模式（-O）下会被跳过
  - ⚠️ `save_settings()` 在每次文本变化时都会触发（通过 `textChanged` 信号连接），频繁磁盘写入
  - ⚠️ `install_command` 函数逻辑有些冗余：`shutil.which("uv")` 检查了两次
  - ⚠️ 没有任务取消机制，用户无法中途停止正在进行的提取任务
  - ⚠️ 线程管理使用实例变量 `self.thread`/`self.worker`，如果快速连续触发可能导致旧线程引用丢失

### 4.2 字幕提取核心 — `extract_subtitle.py`

- **文件位置**：`extract_subtitle.py`（545 行）
- **当前作用**：核心业务逻辑模块，包含完整的字幕提取流程：
  - `extract()` — 主入口函数，协调整个流程：获取视频信息 → 查找中文字幕 → 下载字幕或音频 → 语音识别 → 输出文本
  - `get_info()` — 通过 yt-dlp 获取视频元信息
  - `choose_subtitle()` — 智能选择最佳中文字幕（优先级：人工字幕 > 自动字幕，格式优先级：SRT > VTT > JSON3 > JSON > ASS）
  - `download_subtitle()` — 下载字幕文件
  - `subtitle_to_text()` — 字幕格式解析和纯文本转换（支持 VTT/SRT/ASS/SSA/JSON/JSON3）
  - `download_audio()` — 通过 yt-dlp 下载音频并转码为 MP3
  - `transcribe_audio()` — 使用 faster-whisper 进行中文语音识别
  - `detect_device()` — 自动检测 CUDA 可用性
  - `resolve_ffmpeg_path()` / `resolve_yt_dlp_path()` — 工具路径解析（用户指定 > .venv 本地 > 系统 PATH > imageio-ffmpeg）
  - `ensure_nvidia_library_path()` — NVIDIA CUDA 库路径自动配置（模块级执行）
  - CLI 入口：`main()` + `parse_args()` 支持命令行直接使用
- **与其他模块的关系**：
  - 被 `video_text_gui.py` 导入和调用
  - 依赖 `yt-dlp`、`faster-whisper`、`ctranslate2`、`imageio_ffmpeg`
  - 输出文件保存到 `ROOT/outputs/` 目录
- **是否存在明显问题**：
  - ⚠️ `ensure_nvidia_library_path()` 在模块导入时无条件执行（第 105 行），且在 Linux 下使用 `os.execv` 重新执行进程，可能产生副作用
  - ⚠️ `import ctranslate2`、`import yt_dlp` 等在模块顶层无条件导入（第 107-110 行），如果这些包未安装会导致导入失败，GUI 层无法优雅处理
  - ⚠️ 语言检测硬编码为中文（`language="zh"`），不支持其他语言
  - ⚠️ `parse_vtt_or_srt` 中对纯字母数字行的过滤（第 269 行）可能误删有效的英文字幕行
  - ⚠️ 临时目录使用 `tempfile.TemporaryDirectory` 但指定 `dir=str(ROOT)`，临时文件创建在项目根目录下

### 4.3 启动器 — `launcher.py`

- **文件位置**：`launcher.py`（167 行）
- **当前作用**：应用程序的启动入口，负责：
  - 自动检测系统 Python 3.12
  - 创建 `.venv` 虚拟环境
  - 安装/更新 `requirements.txt` 中的依赖（通过 SHA256 校验避免重复安装）
  - 启动 GUI 应用（优先使用 pythonw 无控制台窗口）
- **与其他模块的关系**：
  - 启动 `video_text_gui.py`
  - 被 `启动软件.bat` 或 `视频字幕提取.exe`（PyInstaller 打包）调用
- **是否存在明显问题**：
  - ⚠️ 只支持 Python 3.12，不兼容其他版本（硬编码 `PYTHON_VERSION = "3.12"`）
  - ⚠️ `start_gui()` 使用 `subprocess.Popen` 以 detached 模式启动 GUI，stdout/stderr 重定向到 DEVNULL，GUI 的错误信息会丢失

### 4.4 构建系统

- **文件位置**：`build_launcher.bat` + `build_launcher.ps1` + `VideoTextLauncher.spec`
- **当前作用**：使用 PyInstaller 将 `launcher.py` 打包为单文件 exe（`视频字幕提取.exe`）
- **与其他模块的关系**：
  - 只打包 launcher.py，不打包 GUI 和业务代码（轻量级启动器策略）
  - 构建环境使用独立的 `.launcher-build` venv
- **是否存在明显问题**：
  - 无明显问题，构建策略合理

### 4.5 启动入口

- **文件位置**：`启动软件.bat`
- **当前作用**：Windows 批处理启动入口，优先使用 `py -3.12`，回退到 `python`，调用 `launcher.py`
- **是否存在明显问题**：
  - 无明显问题

### 4.6 配置文件 — `settings.json`

- **文件位置**：`settings.json`
- **当前作用**：持久化用户配置，包括：视频 URL、FFmpeg 路径、yt-dlp 路径、Cookie 设置、Whisper 模型选择、设备选择
- **与其他模块的关系**：被 `video_text_gui.py` 读写
- **是否存在明显问题**：
  - ⚠️ 当前文件中存储了一个具体的 YouTube URL（看起来是测试数据），分发时应清理

### 4.7 工具函数

工具函数分布在 `video_text_gui.py` 和 `extract_subtitle.py` 中，没有独立的工具模块：

- `video_text_gui.py` 中：`timestamp()`、`read_settings()`/`write_settings()`、`path_exists()`、`local_bin()`、`install_command()`、`package_version()`、`clean_log_text()`、`run_command_with_log()`、`ensure_ffmpeg_link()`、`configure_app_font()`
- `extract_subtitle.py` 中：`venv_tool_path()`、`nvidia_library_dirs()`、`ensure_nvidia_library_path()`、`is_gpu_runtime_error()`、`sanitize_filename()`、`resolve_ffmpeg_path()`、`resolve_yt_dlp_path()`、`ydl_base_opts()`、`lang_score()`、`clean_lines()`、`parse_vtt_or_srt()`、`parse_ass()`、`parse_json_subtitle()`、`subtitle_to_text()`、`detect_device()`

## 5. 当前运行方式

- **安装依赖命令**：由 `launcher.py` 自动处理，或手动执行：
  ```bash
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
  ```

- **启动开发环境命令**：
  ```bash
  # 方式 1：通过启动器（自动处理 venv 和依赖）
  python launcher.py
  
  # 方式 2：直接运行 GUI（需已安装依赖）
  .venv\Scripts\python.exe video_text_gui.py
  
  # 方式 3：双击 启动软件.bat
  
  # 方式 4：双击 视频字幕提取.exe（已构建的启动器）
  ```

- **构建命令**：
  ```bash
  # 构建启动器 exe
  build_launcher.bat
  # 或直接运行 PowerShell 脚本
  powershell -NoProfile -ExecutionPolicy Bypass -File build_launcher.ps1
  ```

- **测试命令**：当前无自动化测试，`launch_test.bat` 是手动测试脚本

- **必要的环境变量名称**：
  - `HF_HUB_DISABLE_SYMLINKS_WARNING` — 代码中自动设置，禁用 HuggingFace 符号链接警告
  - `PATH` — 代码中动态添加 NVIDIA CUDA 库路径
  - `LD_LIBRARY_PATH` — Linux 下动态添加 NVIDIA CUDA 库路径
  - `VIDEO_TEXT_EXTRACTION_REEXEC` — 内部使用，防止 NVIDIA 库路径配置时重复执行进程
  - 注：无 `.env` 文件，无 API 密钥需求

## 6. 当前项目状态判断

- **是否能正常启动**：✅ 是。launcher.log 显示启动器成功创建 venv 并启动 GUI。启动器 exe 已构建完成。

- **是否有明显缺失**：
  - ⚠️ 无自动化测试（无任何 test 文件）
  - ⚠️ 无版本号管理（无 `__version__`、无 `setup.py`/`pyproject.toml`）
  - ⚠️ 无 `.gitignore` 文件（可能导致 venv、build、outputs 等被误提交）
  - ⚠️ 无错误上报或崩溃日志收集机制
  - ⚠️ 无国际化支持（UI 硬编码中文）

- **是否有明显架构问题**：
  - ⚠️ `extract_subtitle.py` 顶层无条件导入重型依赖（ctranslate2、yt_dlp、faster_whisper、imageio_ffmpeg），导致即使只想运行 GUI 检查环境也必须先安装所有依赖
  - ⚠️ 工具函数分散在两个主文件中，没有独立的 utils 模块
  - ⚠️ `ensure_nvidia_library_path()` 在模块级执行，有副作用
  - ⚠️ 没有清晰的 MVC/MVP 分离，GUI 文件承担了过多职责

- **是否有明显代码风格问题**：
  - ⚠️ 整体代码风格良好，使用了 type hints、dataclass 风格
  - ⚠️ 但部分函数较长（如 `build_ui` 约 120 行、`EnvWorker.check` 约 80 行），可考虑拆分
  - ⚠️ `assert` 语句用于运行时检查（应使用显式异常）

- **是否有明显安全风险**：
  - ✅ 无明显安全风险
  - ⚠️ `settings.json` 中可能包含用户本地路径信息，分发时需注意清理
  - ⚠️ Cookie 从浏览器读取功能涉及敏感数据，但这是用户主动操作

- **是否适合继续在当前基础上开发**：✅ 是。项目结构清晰，核心功能完整，代码质量可接受。建议优先：
  1. 添加 `.gitignore`
  2. 将 `extract_subtitle.py` 的顶层导入改为延迟导入（lazy import），降低启动门槛
  3. 添加基础的错误处理和日志记录
  4. 考虑将工具函数提取为独立模块

## 7. 给另一个 GPT 的上下文摘要

```
你正在指导开发一个名为"视频字幕提取"的 Windows 桌面 Python 工具。

【项目目标】
从 B 站 / YouTube 视频链接中提取中文字幕文本。优先下载视频自带字幕（人工 > 自动），
无字幕时下载音频并通过 Whisper AI 语音识别生成文本。

【技术栈】
- Python 3.12 + PySide6（Qt GUI）
- yt-dlp（视频信息/音频下载）
- faster-whisper + ctranslate2（语音识别，支持 CUDA GPU 加速）
- imageio-ffmpeg（FFmpeg 二进制）
- PyInstaller（打包启动器 exe）

【项目文件】
- video_text_gui.py（767行）：PySide6 GUI 主窗口，包含环境检查（EnvWorker）、字幕提取（ExtractWorker）、设置读写、UI 构建
- extract_subtitle.py（545行）：核心业务逻辑，字幕提取全流程（获取信息→选择字幕→下载→解析→语音识别→输出），也支持 CLI 独立运行
- launcher.py（167行）：启动器，自动创建 .venv、安装依赖、启动 GUI
- requirements.txt：4 个依赖（PySide6, yt-dlp, faster-whisper, imageio-ffmpeg）
- settings.json：用户配置持久化
- 启动软件.bat：Windows 启动入口
- build_launcher.bat/ps1 + VideoTextLauncher.spec：构建启动器 exe
- 视频字幕提取.exe：已构建的启动器

【当前进度】
核心功能完整可用：GUI 界面、环境检查/准备、字幕提取（直接下载+语音识别双通道）、
Cookie 支持（浏览器读取/文件）、GPU 加速（含自动回退 CPU）、设置持久化、启动器打包。

【架构特点】
- GUI 使用 QThread + moveToThread 模式处理耗时任务
- 启动器只打包 launcher.py 为 exe（轻量级），GUI 和业务代码随源码分发
- 依赖安装通过 SHA256 校验避免重复
- NVIDIA CUDA 库路径在 extract_subtitle.py 模块导入时自动配置

【已知问题】
- extract_subtitle.py 顶层无条件导入重型依赖，无法在未安装依赖时优雅降级
- ensure_nvidia_library_path() 在模块级执行有副作用
- 无自动化测试、无 .gitignore、无版本管理
- save_settings() 在每次文本变化时触发磁盘写入
- 无任务取消机制

【后续可能需求】
- 批量处理多个视频
- 多语言字幕支持（当前硬编码中文）
- 字幕翻译功能
- 更精确的进度显示
- 输出格式选择（SRT/ASS/TXT）
- 历史记录
- 自动更新检查

请基于以上上下文指导后续开发工作。