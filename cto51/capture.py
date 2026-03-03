"""
视频源嗅探（网络请求拦截）
支持 m3u8 和 mp4 两种格式
"""
from __future__ import annotations

import time
import random
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from cto51.config import WAIT_FOR_M3U8

_PLAY_SELECTORS = [
    ".prism-big-play-btn",
    ".play-btn",
    ".vjs-big-play-button",
    "[class*='play-button']",
    "[class*='big-play']",
    "[class*='play']",
]


def capture_m3u8(page, lesson_url: str) -> tuple[str | None, dict]:
    """
    打开课时页 → 触发播放 → 拦截视频源请求。
    支持 m3u8 和 mp4 两种格式。
    返回 (video_url, request_headers)，未捕获时 url 为 None。
    """
    captured: dict = {"url": None, "headers": {}}

    def on_response(response):
        if captured["url"]:
            return
        url = response.url
        method = response.request.method
        # 捕获 m3u8
        if ".m3u8" in url and method == "GET":
            captured["url"] = url
            captured["headers"] = dict(response.request.headers)
            return
        # 捕获 mp4（排除页面中的静态资源）
        if ".mp4" in url and method == "GET" and "v" in url and "51cto.com" in url:
            captured["url"] = url
            captured["headers"] = dict(response.request.headers)

    # 先注册监听，再导航（避免漏请求）
    page.on("response", on_response)
    try:
        page.goto(lesson_url, wait_until="domcontentloaded")
        time.sleep(random.uniform(2.0, 3.0))

        # 尝试点击播放按钮
        for sel in _PLAY_SELECTORS:
            btn = page.query_selector(sel)
            if btn:
                try:
                    btn.click()
                    break
                except Exception:
                    pass

        # 等待视频源出现
        deadline = time.time() + WAIT_FOR_M3U8
        while time.time() < deadline and not captured["url"]:
            time.sleep(0.5)

        # 如果还没抓到，尝试从 video 元素获取
        if not captured["url"]:
            video_url = page.evaluate("""() => {
                const video = document.querySelector('video');
                return video ? (video.src || video.currentSrc) : null;
            }""")
            if video_url and (".mp4" in video_url or ".m3u8" in video_url):
                captured["url"] = video_url
                captured["headers"] = {}

    except PlaywrightTimeout:
        pass
    finally:
        page.remove_listener("response", on_response)

    return captured["url"], captured["headers"]
