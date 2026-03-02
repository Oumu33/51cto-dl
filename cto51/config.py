import sys
from pathlib import Path

# ── 运行环境检测 ───────────────────────────────────────────────────
# getattr 防止非 CPython 环境报错
_FROZEN = getattr(sys, "frozen", False)

# EXE 所在目录（打包后）或脚本所在目录（开发时）
_HERE = Path(sys.executable).parent if _FROZEN else Path(__file__).parent.parent

# 下载目录：EXE 旁边的 videos 文件夹，开发时在项目根
SAVE_DIR = _HERE / "videos"

# 默认 cookie 存储路径（用户家目录，重装 EXE 后不丢失登录状态）
COOKIE_FILE = Path.home() / ".cto51_cookies.json"

# ── N_m3u8DL-RE 路径 ───────────────────────────────────────────────
# 打包后：PyInstaller 解压目录（sys._MEIPASS）里的 N_m3u8DL-RE.exe
# 开发时：直接用 PATH 里的命令名
if _FROZEN:
    _meipass = Path(sys._MEIPASS)       # type: ignore[attr-defined]
    N_M3U8DL = str(_meipass / "N_m3u8DL-RE.exe")
else:
    N_M3U8DL = "N_m3u8DL-RE"

# 等待 m3u8 出现的最长秒数
WAIT_FOR_M3U8 = 20

# 每课时抓取失败后的重试次数
RETRY_TIMES = 3

# 51CTO 各页面 URL
URL_HOME = "https://edu.51cto.com"
URL_LOGIN = "https://edu.51cto.com/index.php?do=login"
URL_MY_COURSES = "https://edu.51cto.com/center/user/index/type/buy"
URL_COURSE = "https://edu.51cto.com/course/{course_id}.html"

# 浏览器 User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
