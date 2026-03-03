"""
Playwright 浏览器生命周期管理（上下文管理器）
"""
from __future__ import annotations

import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from cto51.config import USER_AGENT
from cto51.utils import load_cookies


class BrowserSession:
    """
    使用方式：
        with BrowserSession(headless=True, cookie_file=Path(...)) as sess:
            sess.page.goto(...)
    """

    def __init__(self, headless: bool = True, cookie_file: Path | None = None):
        self.headless = headless
        self.cookie_file = cookie_file
        self._pw = None
        self._browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def __enter__(self) -> "BrowserSession":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080",
                "--start-maximized",
            ],
        )
        self.context = self._browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            # 添加更多浏览器特征
            color_scheme="light",
            has_touch=False,
            is_mobile=False,
            java_script_enabled=True,
        )
        # 注入脚本隐藏自动化特征
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)

        if self.cookie_file and self.cookie_file.exists():
            cookies = load_cookies(self.cookie_file)
            self.context.add_cookies(cookies)

        self.page = self.context.new_page()
        return self

    def __exit__(self, *_):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    def is_logged_in(self) -> bool:
        """
        检测当前页面是否处于已登录状态。
        用多个可能的选择器探测用户元素。
        带重试以兼容 Windows 上页面跳转时序问题。
        """
        selectors = [
            ".user-info",
            ".user-name",
            ".logout-btn",
            "[class*='avatar']",
            "[class*='user-head']",
            "a[href*='logout']",
        ]
        for attempt in range(3):
            try:
                return any(self.page.query_selector(s) for s in selectors)
            except Exception:
                if attempt < 2:
                    time.sleep(1)
        return False
