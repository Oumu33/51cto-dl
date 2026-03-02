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

def fetch_purchased(page) -> list[Course]:
    """
    进入「我的课程」页，提取所有已购课程。
    返回 Course 对象列表。
    """
    print(f"[*] 加载已购课程页：{URL_MY_COURSES}")
    page.goto(URL_MY_COURSES, wait_until="domcontentloaded")
    time.sleep(3)

    # 尝试滚动到底，触发懒加载
    for _ in range(3):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

    courses: list[Course] = page.evaluate("""() => {
        const results = [];

        // 候选 selector 组合（按优先级）
        const strategies = [
            // 策略 A: 课程卡片含 href /course/
            {
                card: 'a[href*="/course/"]',
                titleFn: el => (el.querySelector('[class*="title"], h3, h4, p') || el).textContent,
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
                    return (el.querySelector('[class*="title"]') || a || el).textContent;
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
                card: 'div[class*="course-item"], div[class*="course-card"]',
                titleFn: el => (el.querySelector('[class*="title"]') || el).textContent,
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
        ];

        const seen = new Set();
        for (const s of strategies) {
            const els = document.querySelectorAll(s.card);
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
        return results;
    }""")

    return [Course(**c) for c in courses]


# ── 课时列表 ───────────────────────────────────────────────────────

def fetch_lessons(page, course: Course) -> list[Lesson]:
    """进入课程页，提取所有课时链接"""
    print(f"[*] 加载课程页：{course.url}")
    page.goto(course.url, wait_until="domcontentloaded")
    time.sleep(3)

    # 展开所有折叠章节
    try:
        for btn in page.query_selector_all(
            ".chapter-item .chapter-title, [class*='chapter'] [class*='title'], .collapse-btn"
        ):
            btn.click()
            time.sleep(0.2)
    except Exception:
        pass

    raw: list[dict] = page.evaluate("""() => {
        const items = [];
        const selectors = [
            'a[href*="/lesson/"]',
            '.lesson-item a',
            '[class*="lesson"] a',
            '.course-list li a',
        ];
        for (const sel of selectors) {
            const els = document.querySelectorAll(sel);
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

    lessons = [Lesson(**r) for r in raw]
    course.lessons = lessons
    return lessons
