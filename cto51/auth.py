"""
扫码登录逻辑（基于 51CTO 实际页面结构）
"""
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from cto51.config import URL_LOGIN
from cto51.utils import save_cookies, show_qr

QR_TIMEOUT = 120   # 扫码等待上限（秒）

# ── 已验证的真实 selector ──────────────────────────────────────────

# 触发登录弹窗（元素不可见，必须用 JS click）
_OPEN_LOGIN_JS = "() => document.querySelector('.LoginReg')?.click()"

# 二维码图片（微信 showqrcode 接口）
_QR_IMG_SELECTORS = [
    "#login-wechat .wx_img img",
    ".code_wxbox .wx_img img",
    ".code_wxbox img",
    "img[src*='showqrcode']",
]

# 二维码过期提示层（display:none → 可见时说明已过期）
_QR_EXPIRED_SEL = ".wx_10s"

# 二维码过期后的刷新按钮
_QR_REFRESH_SELECTORS = [
    ".wx_10s a",
    "a[onclick*='getQrImg']",
]

# 登录成功后出现的用户元素
_LOGIN_SUCCESS_SELECTORS = [
    ".user-info",
    ".user-name",
    "[class*='avatar']",
    ".logout-btn",
    "a[href*='logout']",
]


def _find_first(page, selectors: list[str]):
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            return el
    return None


def _is_qr_expired(page) -> bool:
    el = page.query_selector(_QR_EXPIRED_SEL)
    if not el:
        return False
    return el.is_visible()


def qr_login(sess, save_path: Path) -> bool:
    """
    执行扫码登录。
    sess: BrowserSession（headless=True 即可，QR 图片截图后在外部显示）
    save_path: 登录成功后保存 cookie 的路径
    返回 True 表示登录成功。
    """
    page = sess.page
    # 二维码保存到固定位置，方便用户扫描
    qr_img_path = Path("/home/ubuntu/51cto_downloader/qrcode.png")

    print("[*] 打开登录页…")
    try:
        page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=60000)
    except PlaywrightTimeout:
        # 即使超时也继续，页面可能已部分加载
        print("[!] 页面加载较慢，继续尝试...")
    except Exception as e:
        print(f"[!] 页面加载异常: {e}")

    # 等待页面稳定
    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass  # 忽略 networkidle 超时
    time.sleep(2)

    # 1. 用 JS 点击触发登录弹窗（元素不可见，不能用 playwright click）
    try:
        page.evaluate(_OPEN_LOGIN_JS)
    except Exception as e:
        print(f"[!] 触发登录弹窗失败: {e}")
    time.sleep(3)   # 等弹窗动画 + 二维码加载

    # 2. 截取二维码图片（带重试）
    def snap_qr() -> bool:
        for attempt in range(5):
            try:
                time.sleep(1)  # 每次重试前等待
                el = _find_first(page, _QR_IMG_SELECTORS)
                if el:
                    try:
                        el.screenshot(path=str(qr_img_path))
                        return True
                    except Exception:
                        continue
                # 找不到精确元素，截整个登录框
                box = page.query_selector("#login-wechat, #login-base, .loginBord")
                if box:
                    box.screenshot(path=str(qr_img_path))
                    return True
                else:
                    page.screenshot(path=str(qr_img_path), clip={"x": 0, "y": 0, "width": 600, "height": 700})
                    return True
            except Exception as e:
                if attempt < 4:
                    print(f"[!] 截取二维码失败(重试 {attempt+1}/5): {e}")
                    time.sleep(2)
                else:
                    print(f"[!] 截取二维码最终失败: {e}")
        return False

    found = snap_qr()
    if not found:
        print("[!] 未能精确定位二维码图片，已截取登录区域")

    # 3. 显示二维码（终端 ASCII 或系统图片查看器）
    print("\n请用微信扫描二维码登录：")
    show_qr(qr_img_path)

    # 4. 轮询等待登录成功
    print(f"[*] 等待扫码（最长 {QR_TIMEOUT} 秒）…")
    deadline = time.time() + QR_TIMEOUT

    while time.time() < deadline:
        time.sleep(2)

        # 检测登录成功（使用 try-except 处理页面跳转导致的上下文销毁）
        try:
            if any(page.query_selector(s) for s in _LOGIN_SUCCESS_SELECTORS):
                break
            if "login" not in page.url and page.url != URL_LOGIN:
                break
        except Exception:
            # 页面可能正在跳转，等待后重试
            time.sleep(1)
            continue

        # 检测二维码过期，自动刷新
        try:
            if _is_qr_expired(page):
                refresh = _find_first(page, _QR_REFRESH_SELECTORS)
                if refresh:
                    try:
                        refresh.click()
                    except Exception:
                        page.evaluate("() => document.querySelector('.wx_10s a, a[onclick*=\"getQrImg\"]')?.click()")
                    time.sleep(2)
                    snap_qr()
                    print("\n[*] 二维码已刷新，请重新扫码：")
                    show_qr(qr_img_path)
        except Exception:
            # 页面跳转中，忽略错误
            pass

        remaining = int(deadline - time.time())
        print(f"\r[*] 等待扫码… 剩余 {remaining:3d}s", end="", flush=True)
    else:
        print("\n[!] 超时未完成登录")
        return False

    print("\n[*] 扫码成功！")

    # 等待页面稳定（关闭可能存在的弹窗）
    time.sleep(1)
    try:
        # 尝试关闭登录成功后的弹窗
        for sel in [".close", ".close-btn", "[class*='close']", ".modal-close"]:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                time.sleep(0.3)
    except Exception:
        pass

    # 登录后是局部刷新 DOM，不是页面跳转
    # 等待用户元素出现（而不是 networkidle）
    try:
        for sel in _LOGIN_SUCCESS_SELECTORS:
            try:
                page.wait_for_selector(sel, timeout=5000, state="visible")
                break
            except PlaywrightTimeout:
                continue
    except Exception:
        pass

    time.sleep(1)
    save_cookies(sess.context, save_path)

    try:
        qr_img_path.unlink()
    except Exception:
        pass

    return True
