"""
cto51-dl 命令行入口 + 交互式课程选择流程
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from cto51 import __version__
from cto51.config import COOKIE_FILE, RETRY_TIMES, SAVE_DIR
from cto51.utils import sanitize, parse_selection
from cto51.browser import BrowserSession
from cto51.auth import qr_login
from cto51.courses import Course, fetch_purchased, fetch_lessons
from cto51.capture import capture_m3u8
from cto51.download import download


# ── 显示工具 ──────────────────────────────────────────────────────

def _divider(char="─", width=54):
    print(char * width)


def _show_course_menu(courses: list[Course]) -> None:
    _divider()
    print(f"  {'#':>3}  {'课程名称':<36}  课时")
    _divider()
    for i, c in enumerate(courses, 1):
        count = f"{c.lesson_count}节" if c.lesson_count else "?"
        title = c.title[:34] + "…" if len(c.title) > 35 else c.title
        print(f"  {i:>3}. {title:<36} {count}")
    _divider()


def _prompt_course_selection(courses: list[Course]) -> list[Course]:
    """展示课程列表，返回用户选择的 Course 列表"""
    _show_course_menu(courses)
    print("选择课程（示例：1 / 1,3 / 1-5 / all）")
    while True:
        raw = input(">>> ").strip()
        try:
            indices = parse_selection(raw, len(courses))
            if not indices:
                print("未选择任何课程，请重试")
                continue
            selected = [courses[i] for i in indices]
            print(f"[*] 已选 {len(selected)} 门课程")
            return selected
        except ValueError:
            print("输入格式有误，请重试")


def _prompt_lesson_range(course: Course) -> tuple[int, int]:
    """
    询问课时下载范围，返回 (start_idx, end_idx)（0-based，含两端）。
    直接回车 = 全部。
    """
    n = len(course.lessons)
    print(f"\n  课程：{course.title}（共 {n} 课时）")
    print(f"  下载范围（回车=全部 / 1-10 / 5）：", end="")
    raw = input().strip()
    if not raw:
        return 0, n - 1
    try:
        indices = parse_selection(raw, n)
        return indices[0], indices[-1]
    except (ValueError, IndexError):
        print("  格式有误，下载全部")
        return 0, n - 1


# ── 核心下载流程 ───────────────────────────────────────────────────

def _download_course(page, course: Course, start: int, end: int) -> list[str]:
    """
    下载单门课程的指定课时范围。
    返回失败课时名称列表。
    """
    lessons = course.lessons[start: end + 1]
    total = len(lessons)
    global_start = start + 1
    failed: list[str] = []

    for i, lesson in enumerate(lessons):
        num = global_start + i
        label = f"{num:03d}_{lesson.title}"
        print(f"\n  [{num}/{global_start + total - 1}] {lesson.title}")

        # 断点续传
        if list(SAVE_DIR.glob(f"{sanitize(label)}*")):
            print("    [跳过] 已存在")
            continue

        # 带重试的 m3u8 抓取
        m3u8_url = None
        headers: dict = {}
        for attempt in range(1, RETRY_TIMES + 1):
            m3u8_url, headers = capture_m3u8(page, lesson.url)
            if m3u8_url:
                break
            print(f"    [重试 {attempt}/{RETRY_TIMES}]")
            time.sleep(2)

        if not m3u8_url:
            print("    [失败] 未抓到 m3u8")
            failed.append(label)
            continue

        print(f"    [m3u8] {m3u8_url[:72]}…")
        if not download(m3u8_url, headers, label):
            print("    [下载失败]")
            failed.append(label)

        time.sleep(1)

    return failed


# ── CLI 入口 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="cto51-dl",
        description="51CTO 课程批量下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  cto51-dl                          # 交互模式：显示已购课程 → 选择 → 下载
  cto51-dl --login                  # 重新扫码登录
  cto51-dl --course 640846          # 直接下载指定课程
  cto51-dl --course 640846 --start 3 --end 10
  cto51-dl --dry-run                # 只列出课程，不下载
        """,
    )
    parser.add_argument("--version", action="version", version=f"cto51-dl {__version__}")
    parser.add_argument("--login", action="store_true", help="扫码重新登录并保存 cookie")
    parser.add_argument("--cookie", default=None, help=f"指定 cookie 文件（默认 {COOKIE_FILE}）")
    parser.add_argument("--course", default=None, metavar="ID", help="直接指定课程ID，跳过选课菜单")
    parser.add_argument("--start", type=int, default=None, help="从第几课时开始（配合 --course）")
    parser.add_argument("--end", type=int, default=None, help="到第几课时结束（配合 --course）")
    parser.add_argument("--dry-run", action="store_true", help="只列出课程/课时，不执行下载")
    args = parser.parse_args()

    cookie_path = Path(args.cookie) if args.cookie else COOKIE_FILE

    # ── 登录模式 ──────────────────────────────────────────────────
    if args.login:
        print(f"cto51-dl v{__version__} — 扫码登录")
        with BrowserSession(headless=True, cookie_file=None) as sess:
            ok = qr_login(sess, cookie_path)
        if ok:
            print(f"\n登录成功！Cookie 保存于 {cookie_path}")
            print("现在可以运行：cto51-dl")
        else:
            print("[!] 登录失败，请重试")
            sys.exit(1)
        return

    # ── 检查 cookie ───────────────────────────────────────────────
    if not cookie_path.exists():
        print("[!] 未找到登录状态，请先运行：")
        print("      cto51-dl --login")
        sys.exit(1)

    # ── 下载模式 ──────────────────────────────────────────────────
    print(f"cto51-dl v{__version__} — 正在启动浏览器…")

    with BrowserSession(headless=True, cookie_file=cookie_path) as sess:
        page = sess.page

        # 验证 cookie 有效性（等待页面完全稳定后再检测，兼容 Windows 跳转时序）
        try:
            page.goto("https://edu.51cto.com", wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass
        time.sleep(3)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        time.sleep(2)

        if not sess.is_logged_in():
            print("[!] Cookie 已失效，请重新登录：")
            print("      cto51-dl --login")
            sys.exit(1)
        print("[*] 已登录")

        # ── 模式 A：直接指定课程ID ────────────────────────────────
        if args.course:
            from cto51.courses import Course
            course = Course(title=f"课程 {args.course}", course_id=args.course)
            lessons = fetch_lessons(page, course)
            if not lessons:
                print("[!] 未找到任何课时，请检查课程ID或 selector")
                sys.exit(1)

            n = len(lessons)
            print(f"[*] 共 {n} 课时")

            if args.dry_run:
                for i, ls in enumerate(lessons, 1):
                    print(f"  {i:03d}. {ls.title}")
                return

            start = (args.start - 1) if args.start else 0
            end = (args.end - 1) if args.end else (n - 1)

            failed = _download_course(page, course, start, end)
            _print_summary([course], {course.course_id: failed})
            return

        # ── 模式 B：交互式选课（主流程）─────────────────────────
        courses = fetch_purchased(page)
        if not courses:
            print("[!] 未找到已购课程。")
            print("    可能原因：页面结构有变 / 未购买课程 / selector 需更新")
            print("    也可以直接指定课程ID：cto51-dl --course <ID>")
            sys.exit(1)

        print(f"\n[*] 共找到 {len(courses)} 门已购课程")

        if args.dry_run:
            _show_course_menu(courses)
            return

        # 选择要下载的课程
        selected = _prompt_course_selection(courses)

        all_failed: dict[str, list[str]] = {}

        for course in selected:
            print(f"\n{'═' * 54}")
            print(f"  课程：{course.title}")
            print(f"{'═' * 54}")

            lessons = fetch_lessons(page, course)
            if not lessons:
                print("  [!] 未找到课时，跳过")
                continue

            # 询问下载范围
            start, end = _prompt_lesson_range(course)
            failed = _download_course(page, course, start, end)
            if failed:
                all_failed[course.title] = failed

        _print_summary(selected, all_failed)


def _print_summary(courses: list[Course], failed: dict) -> None:
    print(f"\n{'═' * 54}")
    print("下载完成！")
    total_fail = sum(len(v) for v in failed.values())
    if total_fail == 0:
        print("全部课时下载成功")
    else:
        print(f"失败 {total_fail} 课时：")
        for course_title, items in failed.items():
            for item in items:
                print(f"  [{course_title}] {item}")
    print(f"{'═' * 54}")
