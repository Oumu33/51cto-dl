#!/usr/bin/env python3
"""下载构建依赖：Chromium 和 N_m3u8DL-RE"""
import json
import urllib.request
import zipfile
import subprocess
import sys
from pathlib import Path

def main():
    # 安装 Chromium
    print("[1/2] 安装 Chromium...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    
    # 下载 N_m3u8DL-RE
    print("[2/2] 下载 N_m3u8DL-RE...")
    api = "https://api.github.com/repos/nilaoda/N_m3u8DL-RE/releases/latest"
    req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    
    asset = next((a for a in data["assets"] if "win-x64" in a["name"] and a["name"].endswith(".zip")), None)
    if not asset:
        print("未找到 Windows x64 资产")
        sys.exit(1)
    
    print(f"下载 {asset['name']}...")
    urllib.request.urlretrieve(asset["browser_download_url"], "N_m3u8DL-RE.zip")
    
    print("解压...")
    with zipfile.ZipFile("N_m3u8DL-RE.zip") as z:
        for name in z.namelist():
            if name.endswith(".exe") and "N_m3u8DL-RE" in name:
                Path("N_m3u8DL-RE.exe").write_bytes(z.read(name))
                break
    
    Path("N_m3u8DL-RE.zip").unlink()
    print("完成!")

if __name__ == "__main__":
    main()
