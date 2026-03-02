# build.spec
# PyInstaller 打包配置 —— 含 Chromium，双击即用
#
# 执行方式：python build.py  （不要直接 pyinstaller build.spec）
# build.py 会先把 Chromium 装到正确位置再调用此 spec

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH)

# ── 收集 playwright 全部模块 + 数据文件 ──────────────────────────
pw_datas, pw_binaries, pw_hidden = collect_all("playwright")

# ── 找到 playwright 包里的 Chromium（由 build.py 安装到此处）────
import playwright as _pw
_pw_dir = Path(_pw.__file__).parent
_browsers_src = _pw_dir / ".local-browsers"

if not _browsers_src.exists():
    raise SystemExit(
        "\n[错误] 未找到 Chromium！请先运行：python build.py\n"
        f"预期路径：{_browsers_src}"
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
ctk_datas = collect_data_files("customtkinter", include_py_files=True)

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

block_cipher = None

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=pw_binaries + [
        # N_m3u8DL-RE 打包到 MEIPASS 根目录，config.py 运行时直接引用
        (str(_n_exe), "."),
    ],
    datas=all_datas,
    hiddenimports=pw_hidden + [
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
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
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
