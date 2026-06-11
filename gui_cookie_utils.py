from __future__ import annotations


def selected_cookie_browser(combo, browsers: list[str] | tuple[str, ...]) -> str:
    browser = combo.currentData()
    if browser:
        return str(browser).lower()
    index = combo.currentIndex()
    if 0 <= index < len(browsers):
        return browsers[index]
    return "chrome"
