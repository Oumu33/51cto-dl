"""
已购课程列表 + 课时列表抓取
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from cto51.config import URL_MY_COURSES, URL_COURSE


@dataclass
class Lesson:
    title: str
    url: str


@dataclass
class Course:
    title: str
    course_id: str
    lesson_count: int = 0
    lessons: list[Lesson] = field(default_factory=list)

    @property
    def url(self) -> str:
        return URL_COURSE.format(course_id=self.course_id)


# ── 已购课程 ───────────────────────────────────────────────────────

def _close_popups(page) -> None:
    """关闭常见的弹窗/遮罩"""
    popup_selectors = [
        # 关闭按钮
        ".close-btn", ".close", ".modal-close", ".dialog-close",
        "[class*='close']", "[class*='shut']", ".popup-close",
        # 蒙层点击关闭
        ".modal-mask", ".overlay", ".mask",
        # 新手引导
        ".guide-close", ".新手引导 .close",
        # 活动弹窗
        ".activity-close", ".promo-close", ".ad-close",
    ]
    for sel in popup_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                time.sleep(0.3)
        except Exception:
            pass

    # 按 ESC 尝试关闭弹窗
    try:
        page.keyboard.press("Escape")
        time.sleep(0.2)
    except Exception:
        pass


def fetch_purchased(page) -> list[Course]:
    """
    进入「我的课程」页，提取所有已购课程。
    返回 Course 对象列表。
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    print(f"[*] 加载已购课程页：{URL_MY_COURSES}")
    page.goto(URL_MY_COURSES, wait_until="domcontentloaded")

    # 等待页面基本渲染
    time.sleep(2)

    # 关闭可能存在的弹窗
    _close_popups(page)

    # 等待课程元素出现（局部刷新场景，不用 networkidle）
    _COURSE_SELECTORS = [
        'a[href*="/course/"]',
        '.course-item',
        '.course-card',
        '.course-list a',
        '.my-course a',
        '[class*="course"] a',
        '.list-item a',
        '.item a[href*="course"]',
    ]
    course_found = False
    for sel in _COURSE_SELECTORS:
        try:
            page.wait_for_selector(sel, timeout=8000, state="visible")
            course_found = True
            print(f"[+] 检测到课程元素: {sel}")
            break
        except PlaywrightTimeout:
            continue

    if not course_found:
        print("[!] 未检测到课程元素，等待页面加载…")
        time.sleep(3)
        # 再次尝试关闭弹窗
        _close_popups(page)

    # 检查是否被重定向到登录页
    if "login" in page.url or not page.url.startswith("https://edu.51cto.com"):
        print("[!] 被重定向到登录页，cookie 可能已失效")
        return []

    # 加强懒加载处理：多滚动几次
    print("[*] 触发懒加载...")
    for i in range(5):
        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {(i+1)/5})")
        time.sleep(0.8)

    # 最后滚动到顶部
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.5)

    courses: list[Course] = page.evaluate("""() => {
        const results = [];

        // 候选 selector 组合（按优先级，已扩展）
        const strategies = [
            // 策略 A: 课程卡片含 href /course/
            {
                card: 'a[href*="/course/"]',
                titleFn: el => (el.querySelector('[class*="title"], h3, h4, p, .name') || el).textContent,
                countFn: el => {
                    const m = el.textContent.match(/(\\d+)\\s*课时/);
                    return m ? parseInt(m[1]) : 0;
                },
                idFn: el => {
                    const m = el.href.match(/\\/course\\/(\\d+)/);
                    return m ? m[1] : null;
                }
            },
            // 策略 B: li 元素中含课程链接
            {
                card: 'li:has(a[href*="/course/"])',
                titleFn: el => {
                    const a = el.querySelector('a[href*="/course/"]');
                    return (el.querySelector('[class*="title"], [class*="name"]') || a || el).textContent;
                },
                countFn: el => {
                    const m = el.textContent.match(/(\\d+)\\s*课时/);
                    return m ? parseInt(m[1]) : 0;
                },
                idFn: el => {
                    const a = el.querySelector('a[href*="/course/"]');
                    if (!a) return null;
                    const m = a.href.match(/\\/course\\/(\\d+)/);
                    return m ? m[1] : null;
                }
            },
            // 策略 C: div 课程容器
            {
                card: 'div[class*="course-item"], div[class*="course-card"], div[class*="item"][class*="course"]',
                titleFn: el => (el.querySelector('[class*="title"], [class*="name"], h3, h4') || el).textContent,
                countFn: el => {
                    const m = el.textContent.match(/(\\d+)\\s*课时/);
                    return m ? parseInt(m[1]) : 0;
                },
                idFn: el => {
                    const a = el.querySelector('a[href*="/course/"]');
                    if (!a) return null;
                    const m = a.href.match(/\\/course\\/(\\d+)/);
                    return m ? m[1] : null;
                }
            },
            // 策略 D: 任意包含课程链接的容器
            {
                card: '.list a[href*="/course/"], .items a[href*="/course/"]',
                titleFn: el => (el.querySelector('[class*="title"]') || el).textContent,
                countFn: el => 0,
                idFn: el => {
                    const m = el.href.match(/\\/course\\/(\\d+)/);
                    return m ? m[1] : null;
                }
            },
        ];

        const seen = new Set();
        for (const s of strategies) {
            const els = document.querySelectorAll(s.card);
            console.log('[DEBUG] 策略', s.card, '找到', els.length, '个元素');
            if (els.length === 0) continue;
            for (const el of els) {
                const id = s.idFn(el);
                if (!id || seen.has(id)) continue;
                seen.add(id);
                results.push({
                    course_id: id,
                    title: (s.titleFn(el) || '').trim().replace(/\\s+/g, ' '),
                    lesson_count: s.countFn(el),
                });
            }
            if (results.length > 0) break;
        }
        
        console.log('[DEBUG] 最终找到', results.length, '门课程');
        return results;
    }""")

    if not courses:
        # 调试：打印页面上的所有链接
        print("[!] 未找到课程，尝试调试...")
        debug_info = page.evaluate("""() => {
            const links = document.querySelectorAll('a');
            const courseLinks = [];
            links.forEach(a => {
                if (a.href && a.href.includes('course')) {
                    courseLinks.push(a.href);
                }
            });
            return {
                totalLinks: links.length,
                courseLinks: courseLinks.slice(0, 10),
                bodyText: document.body.innerText.substring(0, 500)
            };
        }""")
        print(f"    页面链接总数: {debug_info['totalLinks']}")
        print(f"    包含 course 的链接: {debug_info['courseLinks']}")
        if not debug_info['courseLinks']:
            print(f"    页面内容预览: {debug_info['bodyText'][:200]}...")

    return [Course(**c) for c in courses]


# ── 课时列表 ───────────────────────────────────────────────────────

def fetch_lessons(page, course: Course) -> list[Lesson]:
    """进入课程页，提取所有课时链接"""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    print(f"[*] 加载课程页：{course.url}")
    page.goto(course.url, wait_until="domcontentloaded")

    time.sleep(2)

    # 关闭可能存在的弹窗
    _close_popups(page)

    # 等待课时元素出现
    _LESSON_SELECTORS = [
        'a[href*="/lesson/"]',
        '.lesson-item a',
        '.lesson-item',
        '[class*="lesson"] a',
        '.course-list li a',
        '.chapter-list a',
        '[class*="chapter"] a[href*="lesson"]',
    ]
    lesson_found = False
    for sel in _LESSON_SELECTORS:
        try:
            page.wait_for_selector(sel, timeout=8000, state="visible")
            lesson_found = True
            print(f"[+] 检测到课时元素: {sel}")
            break
        except PlaywrightTimeout:
            continue

    if not lesson_found:
        print("[!] 未检测到课时元素，等待页面加载…")
        time.sleep(3)
        _close_popups(page)

    # 展开所有折叠章节（增强版）
    expand_selectors = [
        ".chapter-item .chapter-title",
        "[class*='chapter'] [class*='title']",
        ".collapse-btn",
        "[class*='expand']",
        "[class*='fold']",
        ".section-title",
    ]
    for sel in expand_selectors:
        try:
            for btn in page.query_selector_all(sel):
                btn.click()
                time.sleep(0.3)
        except Exception:
            pass

    # 滚动加载所有课时
    for i in range(3):
        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {(i+1)/3})")
        time.sleep(0.5)

    raw: list[dict] = page.evaluate("""() => {
        const items = [];
        const selectors = [
            'a[href*="/lesson/"]',
            'a[href*="lesson/index"]',
            'a[href*="lesson?id"]',
            '.lesson-item a',
            '[class*="lesson"] a',
            '.course-list li a',
            '.chapter-list a[href*="lesson"]',
        ];
        for (const sel of selectors) {
            const els = document.querySelectorAll(sel);
            console.log('[DEBUG] 课时选择器', sel, '找到', els.length, '个元素');
            if (els.length === 0) continue;
            for (let i = 0; i < els.length; i++) {
                const el = els[i];
                const href = el.href;
                const title = (el.textContent || el.title || '').trim().replace(/\\s+/g, ' ');
                if (href && !items.find(x => x.url === href))
                    items.push({ title: title || `课时${i+1}`, url: href });
            }
            break;
        }
        return items;
    }""")

    if not raw:
        # 调试输出
        print("[!] 未找到课时，尝试调试...")
        debug_info = page.evaluate("""() => {
            const links = document.querySelectorAll('a');
            const lessonLinks = [];
            links.forEach(a => {
                if (a.href && a.href.includes('lesson')) {
                    lessonLinks.push(a.href);
                }
            });
            return {
                totalLinks: links.length,
                lessonLinks: lessonLinks.slice(0, 10),
            };
        }""")
        print(f"    页面链接总数: {debug_info['totalLinks']}")
        print(f"    包含 lesson 的链接: {debug_info['lessonLinks']}")

    lessons = [Lesson(**r) for r in raw]
    course.lessons = lessons
    return lessons
