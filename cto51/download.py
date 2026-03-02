"""
调用 N_m3u8DL-RE 执行实际下载
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from cto51.config import N_M3U8DL, SAVE_DIR
from cto51.utils import sanitize

# 只向 N_m3u8DL-RE 传递这些关键 header，避免命令行过长
_KEY_HEADERS = {"cookie", "referer", "user-agent", "origin", "authorization"}


def check_tool() -> tuple[bool, str]:
    """
    检测 N_m3u8DL-RE 是否可用。
    返回 (可用, 错误信息)。
    """
    p = Path(N_M3U8DL)
    if p.is_file() or shutil.which(N_M3U8DL):
        return True, N_M3U8DL
    return False, (
        f"找不到下载工具 N_m3u8DL-RE。\n\n"
        f"预期路径：{p}\n\n"
        f"可能是 EXE 解压不完整，尝试重新运行程序，\n"
        f"或从以下地址手动下载后放到程序同目录：\n"
        f"https://github.com/nilaoda/N_m3u8DL-RE/releases"
    )


def download(m3u8_url: str, headers: dict, save_name: str,
             save_dir: Path | None = None) -> bool:
    """
    调用 N_m3u8DL-RE 下载 m3u8。
    save_dir 为 None 时使用 config.SAVE_DIR。
    返回 True 表示成功（退出码 0）。
    """
    out_dir = save_dir or SAVE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    header_args: list[str] = []
    for k, v in headers.items():
        if k.lower() in _KEY_HEADERS:
            header_args += ["--header", f"{k}: {v}"]

    cmd = [
        N_M3U8DL,
        m3u8_url,
        *header_args,
        "--save-dir", str(out_dir),
        "--save-name", sanitize(save_name),
        "--auto-select",
        "--check-segments-count",
        "--no-date-info",
    ]

    result = subprocess.run(cmd)
    return result.returncode == 0
