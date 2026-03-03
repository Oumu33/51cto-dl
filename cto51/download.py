"""
调用 N_m3u8DL-RE 或 wget 执行实际下载
支持 m3u8 和 mp4 两种格式
"""
from __future__ import annotations

import shutil
import subprocess
import urllib.request
from pathlib import Path

from cto51.config import N_M3U8DL, SAVE_DIR
from cto51.utils import sanitize

# 只向 N_m3u8DL-RE 传递这些关键 header，避免命令行过长
_KEY_HEADERS = {"cookie", "referer", "user-agent", "origin", "authorization"}


def check_tool() -> tuple[bool, str]:
    """
    检测下载工具是否可用。
    返回 (可用, 错误信息)。
    """
    # MP4 可以直接用 wget/curl 下载
    if shutil.which("wget") or shutil.which("curl"):
        return True, "wget/curl"
    
    # m3u8 需要 N_m3u8DL-RE
    p = Path(N_M3U8DL)
    if p.is_file() or shutil.which(N_M3U8DL):
        return True, N_M3U8DL
    return False, (
        f"找不到下载工具。\n\n"
        f"MP4 下载需要 wget 或 curl\n"
        f"m3u8 下载需要 N_m3u8DL-RE：{p}\n\n"
        f"或从以下地址手动下载后放到程序同目录：\n"
        f"https://github.com/nilaoda/N_m3u8DL-RE/releases"
    )


def download(video_url: str, headers: dict, save_name: str,
             save_dir: Path | None = None) -> bool:
    """
    下载视频（支持 m3u8 和 mp4）。
    save_dir 为 None 时使用 config.SAVE_DIR。
    返回 True 表示成功。
    """
    out_dir = save_dir or SAVE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # MP4 直接下载
    if ".mp4" in video_url:
        return download_mp4(video_url, headers, save_name, out_dir)
    
    # m3u8 使用 N_m3u8DL-RE
    return download_m3u8(video_url, headers, save_name, out_dir)


def download_mp4(url: str, headers: dict, save_name: str, out_dir: Path) -> bool:
    """直接下载 MP4 文件"""
    output_path = out_dir / f"{sanitize(save_name)}.mp4"
    
    # 构建请求
    req = urllib.request.Request(url)
    for k, v in headers.items():
        req.add_header(k, v)
    
    try:
        # 检查是否已有文件
        if output_path.exists() and output_path.stat().st_size > 1000:
            print(f"    [跳过] 文件已存在: {output_path.name}")
            return True
        
        # 下载文件
        print(f"    下载 MP4: {url[:60]}...")
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(output_path, 'wb') as f:
                # 分块下载
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
        
        # 验证文件
        if output_path.exists() and output_path.stat().st_size > 1000:
            return True
        return False
    except Exception as e:
        print(f"    [错误] MP4 下载失败: {e}")
        # 尝试用 wget
        return download_with_wget(url, headers, output_path)


def download_with_wget(url: str, headers: dict, output_path: Path) -> bool:
    """使用 wget 下载"""
    if not shutil.which("wget"):
        return False
    
    cmd = ["wget", "-q", "-O", str(output_path), url]
    for k, v in headers.items():
        cmd.extend(["--header", f"{k}: {v}"])
    
    try:
        result = subprocess.run(cmd, timeout=300)
        return result.returncode == 0 and output_path.exists()
    except Exception:
        return False


def download_m3u8(url: str, headers: dict, save_name: str, out_dir: Path) -> bool:
    """调用 N_m3u8DL-RE 下载 m3u8"""
    # 检查工具是否存在
    p = Path(N_M3U8DL)
    if not (p.is_file() or shutil.which(N_M3U8DL)):
        print(f"    [错误] 找不到 N_m3u8DL-RE，无法下载 m3u8")
        return False

    header_args: list[str] = []
    for k, v in headers.items():
        if k.lower() in _KEY_HEADERS:
            header_args += ["--header", f"{k}: {v}"]

    cmd = [
        N_M3U8DL,
        url,
        *header_args,
        "--save-dir", str(out_dir),
        "--save-name", sanitize(save_name),
        "--auto-select",
        "--check-segments-count",
        "--no-date-info",
    ]

    result = subprocess.run(cmd)
    return result.returncode == 0
