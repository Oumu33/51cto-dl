# build.spec
# PyInstaller 6.x 打包配置 —— 含 Chromium，双击即用

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH)

# ── 收集 playwright 全部模块 + 数据文件 ──────────────────────────
pw_datas, pw_binaries, pw_hidden = collect_all("playwright")

# ── 找到 Chromium 路径 ────────────────────────────────────────────
# 优先使用环境变量指定的路径
_browsers_src = None

env_path = os.environ.get("CHROMIUM_PATH", "")
if env_path and Path(env_path).exists():
    _browsers_src = Path(env_path)
    print(f"[*] 使用环境变量 CHROMIUM_PATH: {_browsers_src}")
else:
    # 尝试在 playwright 包目录中搜索
    import playwright as _pw
    _pw_dir = Path(_pw.__file__).parent
    
    # 递归搜索 chromium 目录
    for chromium_dir in _pw_dir.rglob("chromium*"):
        if chromium_dir.is_dir():
            _browsers_src = chromium_dir.parent
            print(f"[*] 搜索到 Chromium 路径: {_browsers_src}")
            break

if not _browsers_src:
    raise SystemExit(
        "\n[错误] 未找到 Chromium！\n"
        "请设置 CHROMIUM_PATH 环境变量或确保 Chromium 已安装到 playwright 包目录"
    )

print(f"[*] 打包 Chromium：{_browsers_src}")

# ── N_m3u8DL-RE.exe ───────────────────────────────────────────────
_n_exe = ROOT / "N_m3u8DL-RE.exe"
if not _n_exe.exists():
    raise SystemExit(
        "\n[错误] 未找到 N_m3u8DL-RE.exe！\n"
        f"预期路径：{_n_exe}"
    )
print(f"[*] 打包 N_m3u8DL-RE：{_n_exe}")

# ── 收集 customtkinter 资源 ───────────────────────────────────────
ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")

# ── 所有 datas ────────────────────────────────────────────────────
all_datas = (
    pw_datas
    + ctk_datas
    + [
        (str(ROOT / "cto51"), "cto51"),
        (str(_browsers_src), "pw-browsers"),
    ]
)

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=pw_binaries + ctk_binaries + [
        (str(_n_exe), "."),
    ],
    datas=all_datas,
    hiddenimports=pw_hidden + ctk_hidden + [
        "cto51",
        "cto51.config",
        "cto51.utils",
        "cto51.browser",
        "cto51.auth",
        "cto51.courses",
        "cto51.capture",
        "cto51.download",
        "customtkinter",
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        "tkinter",
        "tkinter.filedialog",
        "tkinter.messagebox",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "scipy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
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
    runtime_tmpdir=None,
)
