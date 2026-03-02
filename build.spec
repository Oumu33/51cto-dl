# build.spec - PyInstaller 6.x
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)

# 收集 playwright 和 customtkinter
pw_datas, pw_binaries, pw_hidden = collect_all("playwright")
ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")

# 找 Chromium 路径
import playwright
pw_dir = Path(playwright.__file__).parent

browsers_src = None
for p in pw_dir.rglob("chromium*"):
    if p.is_dir():
        browsers_src = p.parent
        print(f"[*] Found Chromium: {p}")
        break

if not browsers_src:
    raise SystemExit(f"[ERROR] Chromium not found! Search path: {pw_dir}")

# N_m3u8DL-RE
n_exe = ROOT / "N_m3u8DL-RE.exe"
if not n_exe.exists():
    raise SystemExit(f"[ERROR] N_m3u8DL-RE.exe not found: {n_exe}")

print(f"[*] Chromium path: {browsers_src}")
print(f"[*] N_m3u8DL-RE: {n_exe}")

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=pw_binaries + ctk_binaries + [(str(n_exe), ".")],
    datas=pw_datas + ctk_datas + [
        (str(ROOT / "cto51"), "cto51"),
        (str(browsers_src), "pw-browsers"),
    ],
    hiddenimports=pw_hidden + ctk_hidden + [
        "cto51", "cto51.config", "cto51.utils", "cto51.browser",
        "cto51.auth", "cto51.courses", "cto51.capture", "cto51.download",
        "customtkinter", "PIL", "PIL.Image", "PIL.ImageTk",
        "tkinter", "tkinter.filedialog", "tkinter.messagebox",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "scipy"],
    noarchive=False,
)

exe = EXE(
    PYZ(a.pure),
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="51CTO下载器",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=["vcruntime140.dll", "python*.dll"],
    console=False,
)
