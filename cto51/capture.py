"""
m3u8 嗅探（网络请求拦截）
"""
from __future__ import annotations

import time
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from cto51.config import WAIT_FOR_M3U8

_PLAY_SELECTORS = [
    ".play-btn",
    ".vjs-big-play-button",
    "[class*='play-button']",
    "[class*='big-play']",
]


def capture_m3u8(page, lesson_url: str) -> tuple[str | None, dict]:
    """
    打开课时页 → 触发播放 → 拦截 m3u8 请求。
    返回 (m3u8_url, request_headers)，未捕获时 url 为 None。
    """
    captured: dict = {"url": None, "headers": {}}

    def on_response(response):
        if captured["url"]:
            return
        if ".m3u8" in response.url and response.request.method == "GET":
            captured["url"] = response.url
            captured["headers"] = dict(response.request.headers)

    # 先注册监听，再导航（避免漏请求）
    page.on("response", on_response)
    try:
        page.goto(lesson_url, wait_until="domcontentloaded")
        time.sleep(2)

        # 尝试点击播放按钮
        for sel in _PLAY_SELECTORS:
            btn = page.query_selector(sel)
            if btn:
                try:
                    btn.click()
                    break
                except Exception:
                    pass

        # 等待 m3u8 出现
        deadline = time.time() + WAIT_FOR_M3U8
        while time.time() < deadline and not captured["url"]:
            time.sleep(0.5)

    except PlaywrightTimeout:
        pass
    finally:
        page.remove_listener("response", on_response)

    return captured["url"], captured["headers"]
