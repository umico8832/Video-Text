from __future__ import annotations

from pathlib import Path


def is_bilibili_412_error(url: str, error: str) -> bool:
    text = f"{url}\n{error}".lower()
    return (
        "bilibili" in text
        and ("http error 412" in text or "precondition failed" in text)
    )


def is_browser_cookie_database_error(error: str) -> bool:
    text = error.lower()
    return (
        "could not copy chrome cookie database" in text
        or ("could not copy" in text and "cookie database" in text)
    )


def is_browser_cookie_dpapi_error(error: str) -> bool:
    return "failed to decrypt with dpapi" in error.lower()


def compact_error_detail(error: str) -> str:
    lines = [line.strip() for line in str(error).splitlines() if line.strip()]
    return "\n".join(lines[-6:])


def browser_display_name(browser: str | None) -> str:
    if not browser:
        return "浏览器"
    normalized = str(browser).strip().lower()
    names = {
        "chrome": "Chrome",
        "edge": "Edge",
        "firefox": "Firefox",
    }
    return names.get(normalized, normalized.title())


def cookie_file_display_name(cookies: str | None) -> str:
    if not cookies:
        return "cookies.txt"
    name = Path(cookies).name
    return name or "cookies.txt"


def format_download_error(
    url: str,
    exc: Exception,
    fallback: str,
    cookies_from_browser: str | None = None,
) -> str:
    detail = compact_error_detail(str(exc))
    if is_browser_cookie_database_error(detail):
        browser_name = browser_display_name(cookies_from_browser)
        return (
            f"读取 {browser_name} Cookie 失败，Cookie 未被使用。\n"
            f"原因可能是 {browser_name} 仍在后台运行，或 Cookie 数据库被占用。\n\n"
            "建议：\n"
            f"1. 完全关闭 {browser_name}；\n"
            "2. 改用 cookies.txt 文件方式。\n\n"
            f"详情：{detail}"
        )
    if is_browser_cookie_dpapi_error(detail):
        browser_name = browser_display_name(cookies_from_browser)
        return (
            f"读取 {browser_name} Cookie 失败，Cookie 未被使用。\n"
            "原因是浏览器 Cookie 解密失败。\n\n"
            "建议：\n"
            "1. 改用 cookies.txt 文件方式；\n"
            "2. 或尝试 Firefox Cookie。\n\n"
            f"详情：{detail}"
        )
    if is_bilibili_412_error(url, detail):
        return (
            "Bilibili 获取失败：B 站可能拦截了未登录或异常网络请求。\n\n"
            "建议：\n"
            "1. 优先使用 cookies.txt 文件方式；\n"
            "2. 或尝试可用的浏览器 Cookie。\n\n"
            f"详情：{detail}"
        )
    return f"{fallback}\n详情：{detail}"
