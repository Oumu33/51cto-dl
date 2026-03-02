import json
import os
import platform
import re
import subprocess
from pathlib import Path


def sanitize(name: str) -> str:
    """去掉文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()


# ── Cookie I/O ────────────────────────────────────────────────────

def save_cookies(context, path: Path) -> None:
    """把 Playwright context 的 cookie 序列化保存"""
    cookies = context.cookies()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"[*] Cookie 已保存到 {path}")


def load_cookies(path: Path) -> list[dict]:
    """
    读取 cookie 文件，兼容两种格式：
    - 本脚本保存的 Playwright 原生格式（含 sameSite 字段）
    - EditThisCookie 扩展导出格式
    """
    with open(path, encoding="utf-8") as f:
        raw: list[dict] = json.load(f)
    if not raw:
        return []
    # Playwright 原生格式直接返回
    if "sameSite" in raw[0]:
        return raw
    # EditThisCookie 格式转换
    result = []
    for c in raw:
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".51cto.com"),
            "path": c.get("path", "/"),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
        }
        if "expirationDate" in c:
            cookie["expires"] = int(c["expirationDate"])
        result.append(cookie)
    return result


# ── 二维码显示 ─────────────────────────────────────────────────────

def _open_with_system(path: Path) -> None:
    """用系统默认图片程序打开文件"""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", str(path)])
        elif system == "Windows":
            os.startfile(str(path))
        else:
            subprocess.run(["xdg-open", str(path)])
    except Exception:
        pass


def show_qr(img_path: Path) -> None:
    """
    在终端内渲染二维码（需要 pillow）；
    失败时用系统图片查看器打开。
    """
    try:
        from PIL import Image
        img = Image.open(img_path).convert("1")
        w, h = img.size
        scale = max(1, w // 58)
        img = img.resize((w // scale, h // (scale * 2)))
        w2, h2 = img.size
        px = img.load()
        border = "─" * (w2 * 2 + 2)
        print(f"\n{border}")
        for y in range(h2):
            row = "│"
            for x in range(w2):
                row += "  " if px[x, y] == 255 else "██"
            print(row + "│")
        print(f"{border}\n")
        return
    except ImportError:
        pass

    # fallback
    print(f"[*] 二维码图片：{img_path.resolve()}")
    _open_with_system(img_path)


# ── 终端交互工具 ───────────────────────────────────────────────────

def parse_selection(raw: str, total: int) -> list[int]:
    """
    把用户输入解析为 0-based 索引列表。
    支持：all / 1 / 1,3,5 / 1-5 / 1-3,7
    """
    raw = raw.strip().lower()
    if raw in ("all", "a", ""):
        return list(range(total))

    indices: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            a, _, b = part.partition("-")
            lo, hi = int(a) - 1, int(b) - 1
            indices.update(range(max(0, lo), min(total - 1, hi) + 1))
        else:
            idx = int(part) - 1
            if 0 <= idx < total:
                indices.add(idx)
    return sorted(indices)
