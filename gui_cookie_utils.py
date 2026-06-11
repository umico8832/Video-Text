from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CookieRequest:
    cookies: str
    cookies_from_browser: str | None
    log_message: str


def selected_cookie_browser(combo, browsers: list[str] | tuple[str, ...]) -> str:
    browser = combo.currentData()
    if browser:
        return str(browser).lower()
    index = combo.currentIndex()
    if 0 <= index < len(browsers):
        return browsers[index]
    return "chrome"


def cookie_mode_label(modes: list[dict] | tuple[dict, ...], mode: str | None) -> str:
    for item in modes:
        if item.get("name") == mode:
            return str(item.get("label") or mode or "未知")
    return mode or "未知"


def build_cookie_request(mode: str | None, cookies_text: str, browser: str) -> CookieRequest:
    if mode == "browser":
        return CookieRequest(
            cookies="",
            cookies_from_browser=browser,
            log_message=f"正在尝试从浏览器 {browser.title()} 读取 Cookies...",
        )
    if mode == "file":
        cookies = cookies_text
        if cookies.strip():
            filename = Path(cookies).name or "cookies.txt"
            message = f"已选择 cookies.txt 文件：{filename}，本次请求将使用该文件。"
        else:
            message = "已选择 cookies.txt 文件模式，但尚未填写文件路径。"
        return CookieRequest(cookies=cookies, cookies_from_browser=None, log_message=message)
    return CookieRequest(
        cookies="",
        cookies_from_browser=None,
        log_message="未启用 Cookies，本次请求不会使用登录态。",
    )
