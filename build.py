#!/usr/bin/env python3
"""
一键打包脚本
安装依赖 → 下载 Chromium → 下载 N_m3u8DL-RE → 打包 EXE

在 Windows 上运行：
    python build.py

产物：dist\51CTO下载器.exe（约 300 MB，双击即用，无需任何额外文件）
"""
import json
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


def run(cmd: list, env: dict = None, desc: str = ""):
    label = desc or " ".join(str(c) for c in cmd)
    print(f"\n{'─'*56}\n  {label}\n{'─'*56}")
    result = subprocess.run(cmd, env=env or os.environ.copy())
    if result.returncode != 0:
        print(f"\n[错误] 命令失败（退出码 {result.returncode}）")
        sys.exit(result.returncode)


def download_n_m3u8dl():
    """从 GitHub Releases 下载最新版 N_m3u8DL-RE Windows x64"""
    exe = Path("N_m3u8DL-RE.exe")
    if exe.exists():
        print(f"[*] N_m3u8DL-RE.exe 已存在，跳过下载")
        return

    print("[*] 获取 N_m3u8DL-RE 最新版本信息…")
    api = "https://api.github.com/repos/nilaoda/N_m3u8DL-RE/releases/latest"
    req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)

    # 找 Windows x64 zip 资产
    asset = next(
        (a for a in data["assets"]
         if "win-x64" in a["name"] and a["name"].endswith(".zip")),
        None,
    )
    if not asset:
        print("[!] 未找到 Windows x64 资产，请手动下载放到项目根目录：")
        print("    https://github.com/nilaoda/N_m3u8DL-RE/releases")
        sys.exit(1)

    zip_path = Path("N_m3u8DL-RE.zip")
    print(f"[*] 下载 {asset['name']} ({asset['size'] // 1024 // 1024} MB)…")
    urllib.request.urlretrieve(asset["browser_download_url"], zip_path)

    print("[*] 解压…")
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.endswith(".exe") and "N_m3u8DL-RE" in name:
                data_bytes = z.read(name)
                exe.write_bytes(data_bytes)
                break
    zip_path.unlink()
    print(f"[*] N_m3u8DL-RE.exe 就绪（{exe.stat().st_size // 1024} KB）")


def main():
    print("=" * 56)
    print("  51CTO 下载器 — EXE 打包工具")
    print("=" * 56)

    # 1. Python 依赖
    print("\n[1/5] 安装 Python 依赖…")
    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        desc="pip install -r requirements.txt")

    # 2. Chromium（装到 playwright 包目录内）
    print("\n[2/5] 下载 Chromium（约 150 MB，仅首次需要）…")
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    run([sys.executable, "-m", "playwright", "install", "chromium"],
        env=env, desc="playwright install chromium")

    import playwright as _pw
    browsers_path = Path(_pw.__file__).parent / ".local-browsers"
    if not browsers_path.exists():
        print(f"[错误] Chromium 未正确安装：{browsers_path}")
        sys.exit(1)
    print(f"[*] Chromium 就绪：{list(browsers_path.glob('chromium*'))[0]}")

    # 3. N_m3u8DL-RE
    print("\n[3/5] 获取 N_m3u8DL-RE…")
    download_n_m3u8dl()

    # 4. PyInstaller 打包
    print("\n[4/5] PyInstaller 打包（可能需要几分钟）…")
    run([sys.executable, "-m", "PyInstaller", "build.spec",
         "--clean", "--noconfirm"],
        desc="pyinstaller build.spec --clean --noconfirm")

    # 5. 完成
    exe = Path("dist") / "51CTO下载器.exe"
    print("\n" + "=" * 56)
    if exe.exists():
        size_mb = exe.stat().st_size / 1024 / 1024
        print(f"  [5/5] 打包成功！")
        print(f"  文件：{exe.resolve()}")
        print(f"  大小：{size_mb:.0f} MB")
        print(f"\n  双击即用，无需任何额外文件。")
    else:
        print("  [!] 未找到输出文件，请检查上方错误")
    print("=" * 56)


if __name__ == "__main__":
    main()
