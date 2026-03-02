# build.spec
# PyInstaller 6.x 打包配置 —— 含 Chromium，双击即用
#
# 执行方式：python build.py  （不要直接 pyinstaller build.spec）
# build.py 会先把 Chromium 装到正确位置再调用此 spec

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH)

# ── 收集 playwright 全部模块 + 数据文件 ──────────────────────────
pw_datas, pw_binaries, pw_hidden = collect_all("playwright")

# ── 找到 playwright 包里的 Chromium ────────────────────────────────
import playwright as _pw
_pw_dir = Path(_pw.__file__).parent

# 尝试多种可能的浏览器路径
_possible_paths = [
    _pw_dir / ".local-browsers",  # PLAYWRIGHT_BROWSERS_PATH=0 时的路径
    _pw_dir / "driver" / ".local-browsers",  # 另一种可能的路径
    Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")) if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") not in ("", "0") else None,
]

# 搜索实际的 Chromium 路径
_browsers_src = None
for p in _possible_paths:
    if p and p.exists():
        chromium_dirs = list(p.rglob("chromium*"))
        if chromium_dirs:
            _browsers_src = p
            print(f"[*] 找到 Chromium 源路径: {p}")
            break

# 如果上述路径都没找到，尝试递归搜索整个 playwright 目录
if not _browsers_src:
    print("[*] 在预设路径未找到 Chromium，正在搜索...")
    for chromium_dir in _pw_dir.rglob("chromium*"):
        if chromium_dir.is_dir() and "chromium" in chromium_dir.name.lower():
            _browsers_src = chromium_dir.parent
            print(f"[*] 搜索到 Chromium 路径: {_browsers_src}")
            break

if not _browsers_src:
    raise SystemExit(
        f"\n[错误] 未找到 Chromium！\n"
        f"已搜索的路径：\n"
        f"  - {_pw_dir / '.local-browsers'}\n"
        f"  - {_pw_dir / 'driver' / '.local-browsers'}\n"
        f"请先运行：python build.py 或确保 PLAYWRIGHT_BROWSERS_PATH 环境变量正确"
    )

print(f"[*] 打包 Chromium：{_browsers_src}")

# ── N_m3u8DL-RE.exe（由 build.py 下载到项目根目录）─────────────
_n_exe = ROOT / "N_m3u8DL-RE.exe"
if not _n_exe.exists():
    raise SystemExit(
        "\n[错误] 未找到 N_m3u8DL-RE.exe！请先运行：python build.py\n"
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
        # cto51 业务包
        (str(ROOT / "cto51"), "cto51"),
        # Chromium 浏览器文件（目标目录名 pw-browsers，与 app.py 对应）
        (str(_browsers_src), "pw-browsers"),
    ]
)

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=pw_binaries + ctk_binaries + [
        # N_m3u8DL-RE 打包到 MEIPASS 根目录，config.py 运行时直接引用
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
    console=False,       # 不弹黑色终端窗口
    runtime_tmpdir=None,
    # icon="icon.ico",   # 取消注释以自定义图标
)
