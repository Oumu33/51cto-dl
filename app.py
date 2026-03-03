"""
51CTO 课程下载器 - GUI 主程序
双击运行，无需命令行。
"""
# ══════════════════════════════════════════════════════════════════
#  【必须最先执行】冻结环境路径修复
#  PyInstaller 打包后 sys._MEIPASS 是解压目录，
#  在 import playwright 之前设好环境变量，否则找不到 Chromium。
# ══════════════════════════════════════════════════════════════════
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    _bundle = Path(sys._MEIPASS)
    # 告诉 Playwright 在哪里找浏览器
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_bundle / "pw-browsers")
    # 告诉 Playwright 在哪里找 driver（Node.js 运行时）
    os.environ.setdefault(
        "PLAYWRIGHT_DRIVER_PATH",
        str(_bundle / "playwright" / "driver"),
    )
    # 把 bundle 根目录加入 sys.path，让 cto51 包可以被找到
    sys.path.insert(0, str(_bundle))

# ── 标准库 ────────────────────────────────────────────────────────
import queue
import re
import tempfile
import threading
import time
import random
from tkinter import filedialog, messagebox
import tkinter as tk

# ── 第三方库 ──────────────────────────────────────────────────────
import customtkinter as ctk
from PIL import Image, ImageTk

# ── 本包 ──────────────────────────────────────────────────────────
from cto51.config import COOKIE_FILE
from cto51.browser import BrowserSession
from cto51.courses import fetch_purchased, fetch_lessons, Course
from cto51.capture import capture_m3u8
from cto51.download import download as dl_m3u8
from cto51.utils import sanitize, save_cookies

# ── 主题常量 ──────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT  = "#3B8ED0"
SUCCESS = "#3CB371"
WARN    = "#E5A50A"
DANGER  = "#E05252"
BG_DARK = "#1E1E2E"
BG_MID  = "#2A2A3E"
BG_CARD = "#313145"
FG_MAIN = "#CDD6F4"
FG_DIM  = "#7F849C"


# ══════════════════════════════════════════════════════════════════
#  二维码弹窗
# ══════════════════════════════════════════════════════════════════
class QRWindow(ctk.CTkToplevel):
    def __init__(self, parent, img_path: Path):
        super().__init__(parent)
        self.title("扫码登录")
        self.resizable(False, False)
        self.grab_set()

        self._photo = self._load(img_path)
        ctk.CTkLabel(self, text="使用 51CTO APP 或微信扫码登录",
                     font=("Microsoft YaHei", 13)).pack(pady=(16, 8))
        self._img_lbl = tk.Label(self, image=self._photo, bg=BG_DARK)
        self._img_lbl.pack(padx=24, pady=4)
        self._status_lbl = ctk.CTkLabel(
            self, text="等待扫码…",
            font=("Microsoft YaHei", 12), text_color=FG_DIM)
        self._status_lbl.pack(pady=(4, 16))

    @staticmethod
    def _load(path: Path):
        img = Image.open(path).resize((280, 280), Image.LANCZOS)
        return ImageTk.PhotoImage(img)

    def set_status(self, text: str, color: str = FG_DIM):
        self._status_lbl.configure(text=text, text_color=color)

    def refresh_image(self, img_path: Path):
        self._photo = self._load(img_path)
        self._img_lbl.configure(image=self._photo)


# ══════════════════════════════════════════════════════════════════
#  课程复选框行
# ══════════════════════════════════════════════════════════════════
class CourseRow(ctk.CTkFrame):
    def __init__(self, parent, course: Course, **kw):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=8, **kw)
        self.course = course
        self._var = tk.BooleanVar(value=True)

        ctk.CTkCheckBox(self, variable=self._var, text="",
                        width=24, checkbox_width=20,
                        checkbox_height=20).pack(side="left", padx=(10, 4), pady=8)

        ctk.CTkLabel(self, text=course.title,
                     font=("Microsoft YaHei", 13),
                     anchor="w").pack(side="left", fill="x", expand=True, pady=8)

        count = f"{course.lesson_count} 课时" if course.lesson_count else "? 课时"
        ctk.CTkLabel(self, text=count,
                     font=("Microsoft YaHei", 11),
                     text_color=FG_DIM, width=60).pack(side="right", padx=12)

    @property
    def selected(self) -> bool:
        return self._var.get()

    def set_selected(self, val: bool):
        self._var.set(val)


# ══════════════════════════════════════════════════════════════════
#  主窗口
# ══════════════════════════════════════════════════════════════════
class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("51CTO 课程下载器")
        self.geometry("880x680")
        self.minsize(780, 580)
        self.configure(fg_color=BG_DARK)

        self._cookie_path: Path = COOKIE_FILE
        self._save_dir: Path = Path.home() / "Videos" / "51CTO"
        self._course_rows: list[CourseRow] = []
        self._gui_queue: queue.Queue = queue.Queue()
        self._qr_window: QRWindow | None = None
        self._downloading = False

        self._build_ui()
        self._poll_queue()
        threading.Thread(target=self._check_login_task, daemon=True).start()

    # ── UI 构建 ────────────────────────────────────────────────────

    def _build_ui(self):
        # 顶部标题栏
        topbar = ctk.CTkFrame(self, fg_color=BG_MID, height=52, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="🎓  51CTO 课程下载器",
                     font=("Microsoft YaHei", 16, "bold"),
                     text_color=FG_MAIN).pack(side="left", padx=20)
        self._login_badge = ctk.CTkLabel(
            topbar, text="●  未登录",
            font=("Microsoft YaHei", 12), text_color=DANGER)
        self._login_badge.pack(side="right", padx=20)

        # 主体分栏
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(8, 0))

        # 左侧面板
        left = ctk.CTkFrame(body, fg_color=BG_MID, width=220, corner_radius=10)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        self._section(left, "账号", pady_top=16)
        self._btn_login = ctk.CTkButton(
            left, text="扫码登录",
            font=("Microsoft YaHei", 13),
            fg_color=ACCENT, hover_color="#2563B0",
            command=self._on_login_click)
        self._btn_login.pack(fill="x", padx=16)

        self._divider(left)
        self._section(left, "保存目录")
        dir_row = ctk.CTkFrame(left, fg_color="transparent")
        dir_row.pack(fill="x", padx=16, pady=(4, 0))
        self._dir_label = ctk.CTkLabel(
            dir_row, text=self._short(self._save_dir),
            font=("Microsoft YaHei", 11), text_color=FG_DIM, anchor="w")
        self._dir_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(dir_row, text="📁", width=32,
                      font=("Microsoft YaHei", 14),
                      fg_color=BG_CARD, hover_color=BG_DARK,
                      command=self._on_pick_dir).pack(side="right")

        self._divider(left)
        self._section(left, "直接输入课程链接")
        ctk.CTkLabel(left, text="（留空则用右侧选课）",
                     font=("Microsoft YaHei", 10),
                     text_color=FG_DIM).pack(anchor="w", padx=16)
        self._url_entry = ctk.CTkEntry(
            left, placeholder_text="https://edu.51cto.com/course/...",
            font=("Microsoft YaHei", 11))
        self._url_entry.pack(fill="x", padx=16, pady=(6, 0))

        # 右侧课程列表
        right = ctk.CTkFrame(body, fg_color=BG_MID, corner_radius=10)
        right.pack(side="left", fill="both", expand=True)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(hdr, text="已购课程",
                     font=("Microsoft YaHei", 14, "bold")).pack(side="left")
        self._btn_refresh = ctk.CTkButton(
            hdr, text="刷新", width=60,
            font=("Microsoft YaHei", 12),
            fg_color=BG_CARD, hover_color=BG_DARK,
            command=self._on_refresh_click)
        self._btn_refresh.pack(side="right", padx=(4, 0))
        ctk.CTkButton(hdr, text="取消全选", width=72,
                      font=("Microsoft YaHei", 12),
                      fg_color=BG_CARD, hover_color=BG_DARK,
                      command=lambda: self._select_all(False)).pack(side="right", padx=4)
        ctk.CTkButton(hdr, text="全选", width=52,
                      font=("Microsoft YaHei", 12),
                      fg_color=BG_CARD, hover_color=BG_DARK,
                      command=lambda: self._select_all(True)).pack(side="right")

        self._course_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self._course_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self._empty_label = ctk.CTkLabel(
            self._course_scroll,
            text="登录后点击「刷新」获取课程列表",
            font=("Microsoft YaHei", 13), text_color=FG_DIM)
        self._empty_label.pack(pady=40)

        # 底部操作栏
        bottom = ctk.CTkFrame(self, fg_color=BG_MID, height=170, corner_radius=0)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)

        ctrl = ctk.CTkFrame(bottom, fg_color="transparent")
        ctrl.pack(fill="x", padx=16, pady=(10, 4))
        self._btn_dl = ctk.CTkButton(
            ctrl, text="▶  开始下载",
            font=("Microsoft YaHei", 14, "bold"),
            fg_color=SUCCESS, hover_color="#2E8B57", height=38,
            command=self._on_download_click)
        self._btn_dl.pack(side="left")
        self._prog_label = ctk.CTkLabel(
            ctrl, text="", font=("Microsoft YaHei", 12), text_color=FG_DIM)
        self._prog_label.pack(side="left", padx=16)

        self._prog_bar = ctk.CTkProgressBar(bottom, mode="determinate")
        self._prog_bar.set(0)
        self._prog_bar.pack(fill="x", padx=16, pady=(0, 4))

        self._log = ctk.CTkTextbox(
            bottom, font=("Consolas", 11),
            fg_color=BG_CARD, text_color=FG_MAIN, height=80)
        self._log.pack(fill="x", padx=16, pady=(0, 8))
        self._log.configure(state="disabled")

    def _section(self, parent, text, pady_top=8):
        ctk.CTkLabel(parent, text=text,
                     font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_DIM).pack(anchor="w", padx=16, pady=(pady_top, 2))

    def _divider(self, parent):
        ctk.CTkFrame(parent, height=1, fg_color=BG_CARD).pack(
            fill="x", padx=16, pady=12)

    # ── 工具 ──────────────────────────────────────────────────────

    def _short(self, p: Path, n: int = 24) -> str:
        s = str(p)
        return ("…" + s[-(n - 1):]) if len(s) > n else s

    def _log_write(self, text: str, color: str = FG_MAIN):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _set_logged_in(self, ok: bool):
        if ok:
            self._login_badge.configure(text="●  已登录", text_color=SUCCESS)
            self._btn_login.configure(text="重新登录")
        else:
            self._login_badge.configure(text="●  未登录", text_color=DANGER)
            self._btn_login.configure(text="扫码登录")

    def _select_all(self, val: bool):
        for r in self._course_rows:
            r.set_selected(val)

    def _populate_courses(self, courses: list[Course]):
        for r in self._course_rows:
            r.destroy()
        self._course_rows.clear()
        self._empty_label.pack_forget()
        for c in courses:
            row = CourseRow(self._course_scroll, c)
            row.pack(fill="x", pady=3)
            self._course_rows.append(row)
        if not courses:
            self._empty_label.configure(text="未找到已购课程")
            self._empty_label.pack(pady=40)

    # ── 队列轮询 ──────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg, data = self._gui_queue.get_nowait()
                self._dispatch(msg, data)
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

    def _dispatch(self, msg: str, data):
        match msg:
            case "login_status":
                self._set_logged_in(data)
                if data:
                    self._log_write("[*] 登录状态有效")

            case "show_qr":
                if self._qr_window and self._qr_window.winfo_exists():
                    self._qr_window.refresh_image(data)
                else:
                    self._qr_window = QRWindow(self, data)

            case "qr_status":
                if self._qr_window and self._qr_window.winfo_exists():
                    self._qr_window.set_status(*data)

            case "login_ok":
                if self._qr_window and self._qr_window.winfo_exists():
                    self._qr_window.destroy()
                self._qr_window = None
                self._set_logged_in(True)
                self._btn_login.configure(state="normal")
                self._log_write("[*] 扫码登录成功！")
                threading.Thread(target=self._fetch_courses_task, daemon=True).start()

            case "login_fail":
                if self._qr_window and self._qr_window.winfo_exists():
                    self._qr_window.destroy()
                self._btn_login.configure(state="normal")
                self._log_write("[!] 登录超时或失败，请重试", WARN)

            case "courses":
                self._populate_courses(data)
                self._btn_refresh.configure(state="normal")
                self._log_write(f"[*] 已加载 {len(data)} 门课程")

            case "progress":
                cur, total, name = data
                self._prog_bar.set(cur / total if total else 0)
                self._prog_label.configure(text=f"{cur}/{total} 课时")
                if name:
                    self._log_write(f"  → {name}")

            case "lesson_done":
                self._log_write(f"  ✓ {data}", SUCCESS)

            case "lesson_fail":
                self._log_write(f"  ✗ {data}", DANGER)

            case "download_done":
                self._downloading = False
                self._btn_dl.configure(state="normal", text="▶  开始下载")
                ok, total = data
                self._log_write(
                    f"\n完成！成功 {ok}/{total} 课时",
                    SUCCESS if ok == total else WARN)

            case "log":
                color = WARN if "[!]" in data else FG_MAIN
                self._log_write(data, color)

    # ── 事件 ──────────────────────────────────────────────────────

    def _on_login_click(self):
        self._btn_login.configure(state="disabled")
        threading.Thread(target=self._login_task, daemon=True).start()

    def _on_refresh_click(self):
        if not self._cookie_path.exists():
            messagebox.showwarning("提示", "请先扫码登录")
            return
        self._btn_refresh.configure(state="disabled")
        for r in self._course_rows:
            r.destroy()
        self._course_rows.clear()
        self._empty_label.configure(text="加载中…")
        self._empty_label.pack(pady=40)
        threading.Thread(target=self._fetch_courses_task, daemon=True).start()

    def _on_pick_dir(self):
        d = filedialog.askdirectory(title="选择保存目录",
                                    initialdir=str(self._save_dir))
        if d:
            self._save_dir = Path(d)
            self._dir_label.configure(text=self._short(self._save_dir))

    def _on_download_click(self):
        if self._downloading:
            return
        manual_url = self._url_entry.get().strip()
        if manual_url:
            m = re.search(r"/course/(\d+)", manual_url)
            if not m:
                messagebox.showerror("错误",
                    "无法解析课程ID\n"
                    "支持格式：https://edu.51cto.com/course/XXXXXX.html")
                return
            selected = [Course(title=f"课程 {m.group(1)}", course_id=m.group(1))]
        else:
            selected = [r.course for r in self._course_rows if r.selected]

        if not selected:
            messagebox.showwarning("提示", "请选择至少一门课程")
            return
        if not self._cookie_path.exists():
            messagebox.showwarning("提示", "请先扫码登录")
            return

        # 检测 N_m3u8DL-RE 是否可用
        from cto51.download import check_tool
        ok, info = check_tool()
        if not ok:
            messagebox.showerror("缺少下载工具", info)
            return

        self._downloading = True
        self._btn_dl.configure(state="disabled", text="下载中…")
        self._prog_bar.set(0)
        self._prog_label.configure(text="准备中…")
        self._log_write(f"\n{'─' * 44}\n开始下载 {len(selected)} 门课程")
        threading.Thread(
            target=self._download_task,
            args=(selected, self._save_dir),
            daemon=True).start()

    # ── 后台任务 ──────────────────────────────────────────────────

    def _check_login_task(self):
        if not self._cookie_path.exists():
            return
        try:
            with BrowserSession(headless=True, cookie_file=self._cookie_path) as s:
                s.page.goto("https://edu.51cto.com", wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)
                # 等待页面稳定
                try:
                    s.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                time.sleep(1)
                self._gui_queue.put(("login_status", s.is_logged_in()))
        except Exception as e:
            self._gui_queue.put(("log", f"[!] 检查登录状态出错: {e}"))

    def _login_task(self):
        qr_path = Path(tempfile.gettempdir()) / "cto51_qr.png"
        try:
            with BrowserSession(headless=True, cookie_file=None) as sess:
                from cto51.config import URL_LOGIN
                from cto51.auth import (
                    _OPEN_LOGIN_JS, _QR_IMG_SELECTORS,
                    _LOGIN_SUCCESS_SELECTORS, _QR_REFRESH_SELECTORS,
                    _is_qr_expired, _find_first, QR_TIMEOUT,
                )
                page = sess.page
                try:
                    page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=60000)
                except Exception:
                    # 即使超时也继续，页面可能已部分加载
                    pass
                time.sleep(3)
                # JS 点击触发登录弹窗（元素不可见，不能用 playwright click）
                page.evaluate(_OPEN_LOGIN_JS)
                time.sleep(2)

                def snap_qr():
                    el = _find_first(page, _QR_IMG_SELECTORS)
                    if el:
                        try:
                            el.screenshot(path=str(qr_path))
                            return
                        except Exception:
                            pass
                    try:
                        box = page.query_selector("#login-wechat, #login-base, .loginBord")
                        if box:
                            box.screenshot(path=str(qr_path))
                        else:
                            page.screenshot(path=str(qr_path))
                    except Exception:
                        pass

                snap_qr()
                self._gui_queue.put(("show_qr", qr_path))
                self._gui_queue.put(("qr_status", ("等待扫码…", FG_DIM)))

                deadline = time.time() + QR_TIMEOUT
                while time.time() < deadline:
                    time.sleep(2)
                    # 检测登录成功（包裹 try/except 应对页面跳转导致的上下文销毁）
                    try:
                        if any(page.query_selector(s) for s in _LOGIN_SUCCESS_SELECTORS):
                            break
                        if "login" not in page.url and page.url != URL_LOGIN:
                            break
                    except Exception:
                        time.sleep(1)
                        continue
                    try:
                        if _is_qr_expired(page):
                            refresh = _find_first(page, _QR_REFRESH_SELECTORS)
                            if refresh:
                                try:
                                    refresh.click()
                                except Exception:
                                    page.evaluate("() => document.querySelector('.wx_10s a')?.click()")
                            time.sleep(2)
                            snap_qr()
                            self._gui_queue.put(("show_qr", qr_path))
                            self._gui_queue.put(("qr_status", ("二维码已刷新，请重扫", WARN)))
                    except Exception:
                        pass
                    remaining = int(deadline - time.time())
                    self._gui_queue.put(("qr_status", (f"等待扫码… 剩余 {remaining}s", FG_DIM)))
                else:
                    self._gui_queue.put(("login_fail", None))
                    return

                save_cookies(sess.context, self._cookie_path)
                self._gui_queue.put(("login_ok", None))
        except Exception as e:
            self._gui_queue.put(("login_fail", None))
            self._gui_queue.put(("log", f"[!] 登录出错: {e}"))

    def _fetch_courses_task(self):
        try:
            with BrowserSession(headless=True, cookie_file=self._cookie_path) as s:
                courses = fetch_purchased(s.page)
            self._gui_queue.put(("courses", courses))
        except Exception as e:
            self._gui_queue.put(("log", f"[!] 加载课程失败: {e}"))
            self._gui_queue.put(("courses", []))

    def _download_task(self, courses: list[Course], save_dir: Path):
        from cto51.config import RETRY_TIMES

        all_lessons: list[tuple[Course, object, int]] = []  # (course, lesson, lesson_idx)
        ok_count = done = 0

        try:
            with BrowserSession(headless=True, cookie_file=self._cookie_path) as sess:
                # 收集所有课时，按课程分组
                for course in courses:
                    self._gui_queue.put(("log", f"[*] 获取课时：{course.title}"))
                    lessons = list(fetch_lessons(sess.page, course))
                    for idx, ls in enumerate(lessons, 1):
                        all_lessons.append((course, ls, idx))

                total = len(all_lessons)
                self._gui_queue.put(("log", f"[*] 共 {total} 课时，开始下载"))

                for course, lesson, lesson_idx in all_lessons:
                    # 为每个课程创建单独目录
                    course_dir = save_dir / sanitize(course.title)
                    course_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 文件名：序号_课时标题
                    label = f"{lesson_idx:03d}_{sanitize(lesson.title)}"

                    # 断点续传（在课程目录下检查）
                    if list(course_dir.glob(f"{label}*")):
                        self._gui_queue.put(("log", f"  [跳过] {course.title}/{label}"))
                        done += 1
                        ok_count += 1
                        self._gui_queue.put(("progress", (done, total, "")))
                        continue

                    self._gui_queue.put(("progress", (done, total, f"{course.title} - {lesson.title}")))

                    m3u8_url, headers = None, {}
                    for attempt in range(1, RETRY_TIMES + 1):
                        m3u8_url, headers = capture_m3u8(sess.page, lesson.url)
                        if m3u8_url:
                            break
                        self._gui_queue.put(("log", f"  [重试 {attempt}] {lesson.title}"))
                        time.sleep(2)

                    done += 1
                    if not m3u8_url:
                        self._gui_queue.put(("lesson_fail", f"{course.title}/{label}"))
                        self._gui_queue.put(("progress", (done, total, "")))
                        continue

                    ok = dl_m3u8(m3u8_url, headers, label, save_dir=course_dir)
                    if ok:
                        ok_count += 1
                        self._gui_queue.put(("lesson_done", f"{course.title}/{label}"))
                    else:
                        self._gui_queue.put(("lesson_fail", f"{course.title}/{label}"))
                    self._gui_queue.put(("progress", (done, total, "")))
                    time.sleep(random.uniform(1.5, 4.0))  # 随机延迟避免反爬

        except Exception as e:
            self._gui_queue.put(("log", f"[!] 下载出错: {e}"))

        self._gui_queue.put(("download_done", (ok_count, len(all_lessons))))


# ══════════════════════════════════════════════════════════════════
#  启动入口
# ══════════════════════════════════════════════════════════════════
def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
