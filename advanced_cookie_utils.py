from __future__ import annotations

from pathlib import Path


COOKIE_OPTION_DESCRIPTIONS = {
    "none": (
        "适合场景\n\n"
        "推荐用于 YouTube / 普通公开视频。\n"
        "如果视频不需要登录，优先选择此项，最稳定。\n\n"
        "说明\n\n"
        "本模式不会读取浏览器 Cookie，也不会使用 cookies.txt 文件。\n"
        "如果 Bilibili 提示 412 或登录资源无法访问，再尝试使用 cookies.txt。"
    ),
    "file": (
        "如何获取 cookies.txt\n\n"
        "1. 在浏览器中登录 Bilibili；\n"
        "2. 打开需要提取字幕的视频页面；\n"
        "3. 使用支持导出 Netscape cookies.txt 格式的浏览器扩展；\n"
        "4. 选择“导出当前网站 Cookie”，保存为 cookies.txt；\n"
        "5. 回到本软件，点击“选择”，选择该文件。\n\n"
        "提示：\n"
        "可使用 Get cookies.txt LOCALLY、Cookie-Editor 等扩展导出。\n"
        "请确认导出格式为 Netscape cookies.txt，不要选择 JSON。\n"
        "cookies.txt 相当于登录凭证，请勿分享给别人。"
    ),
    "browser": (
        "适合场景\n\n"
        "适合想快速使用浏览器登录状态的情况。\n\n"
        "注意\n\n"
        "此方式比较方便，但可能失败。\n"
        "Chrome / Edge 在部分 Windows 环境可能因为数据库占用或 DPAPI 解密失败而无法读取。\n"
        "Firefox 可能更容易成功，但不保证每台电脑都有。\n\n"
        "如果读取失败，建议改用 cookies.txt 文件方式。"
    ),
}


def cookie_option_description(mode: str) -> str:
    return COOKIE_OPTION_DESCRIPTIONS.get(mode, COOKIE_OPTION_DESCRIPTIONS["none"])


def cookie_option_frame_style(selected: bool) -> str:
    return f"""
                QFrame#cookieOption {{
                    background: {'#eef6ff' if selected else '#f9fbfd'};
                    border: 1px solid {'#60a5fa' if selected else '#e1e7ef'};
                    border-radius: 7px;
                }}
            """


def cookie_option_radio_style(selected: bool) -> str:
    return f"""
                    QRadioButton {{
                        color: {'#1d4ed8' if selected else '#172033'};
                        font-weight: 600;
                        spacing: 8px;
                    }}
                """


def cookie_file_status(mode: str, path: str, browser: str | None = None) -> str:
    if mode == "none":
        return "当前不会向下载流程传递 Cookies。推荐用于 YouTube / 普通公开视频。"
    if mode == "browser":
        browser_name = str(browser or "浏览器").title()
        return (
            f"将尝试从 {browser_name} 读取登录状态；只有读取成功后本次请求才会使用 Cookies。"
            "Chrome / Edge 可能因数据库占用或 DPAPI 解密失败而无法读取。"
        )
    if not path:
        return "请选择 cookies.txt 文件；推荐用于 Bilibili、登录资源、受限视频。软件只保存路径，不读取或展示 Cookies 内容。"
    if Path(path).exists():
        return "将使用所选 cookies.txt 文件路径；软件不会读取或展示 Cookies 内容，请不要上传、分享或提交该文件。"
    return "当前路径不存在，请确认 cookies.txt 文件位置；软件只保存路径，不读取或展示内容。"
