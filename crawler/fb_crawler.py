"""
fb_crawler.py — Playwright-based Facebook Group Crawler
─────────────────────────────────────────────────────────────────────────────
Sử dụng Playwright Chromium chung profile với FacebookPoster (chrome_profile).
"""

import json
import os
import re
import time
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright

# ─── Paths ────────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_DIR = os.path.join(_BASE, "chrome_profile")

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(_BASE, "browsers"),
)

# ─── Từ khoá job-seeker mặc định ─────────────────────────────────────────────
DEFAULT_JOBSEEKER_KEYWORDS = [
    "em là"
]

# ─── Noise lines (innerText của các nav/icon element) ─────────────────────────
_SKIP_EXACT = {
    "facebook", "like", "comment", "share",
    "thích", "bình luận", "chia sẻ",
    "xem thêm", "see more",
    "reels", "watch", "marketplace", "groups", "gaming",
    "messenger", "notifications", "most relevant", "phù hợp nhất",
    "all comments", "all reactions", "view more comments",
    "write a comment", "viết bình luận",
    "send", "gửi", "</>", "gif", "sticker",
    "ảnh/video", "photo/video", "feeling/activity",
    "tag friends", "check in",
    "anonymous participant", "thành viên ẩn danh", "người dùng ẩn danh", "anonymous",
}

# Pattern nhận biết dòng "Shared with …" / "Chia sẻ với …"
_SHARED_RE = re.compile(
    r"(shared with|chia\s+s[eê].*v[oơ]i|· public|· công khai"
    r"|đã chia sẻ|trong nhóm|in group)",
    re.IGNORECASE,
)

# Pattern loại bỏ số reaction (32, 162, 1.2K, …)
_REACTION_RE = re.compile(r"^\d{1,7}[.,]?\d{0,3}[KkMm]?$")


class FBCrawler:
    """
    Crawl Facebook Group bằng Playwright Chromium.
    Sử dụng chung persistent profile (chrome_profile) với Playwright trong poster.py.
    """

    FB = "https://www.facebook.com"

    def __init__(self, cookies: dict = None, stop_event=None):
        self._debug_log: list[dict] = []
        self._stop_event = stop_event
        self.playwright = None
        self.context = None
        self.page = None
        self._start_browser()

    def _start_browser(self):
        os.makedirs(PROFILE_DIR, exist_ok=True)
        print(f"[crawler] Đang mở Playwright Chromium profile: {PROFILE_DIR}")
        try:
            self.playwright = sync_playwright().start()
            self.context = self.playwright.chromium.launch_persistent_context(
                PROFILE_DIR,
                headless=False,
                viewport={"width": 1366, "height": 768},
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"],
            )
            self.page = self.context.new_page()
            print("[crawler] Chromium đã sẵn sàng!")
        except Exception as e:
            print(f"[crawler] Lỗi khởi động Playwright: {e}")
            self.close()
            raise RuntimeError(
                "Không thể mở cửa sổ trình duyệt. Hãy đảm bảo bạn đã ĐÓNG cửa sổ 'Kết nối Facebook' trước khi bấm Crawl!"
            ) from e

    def search_group(
        self,
        group_id: str,
        keyword: str,
        max_posts: int = 150,
        group_name: str = "",
    ) -> list[dict]:
        posts: list[dict] = []
        seen: set[str] = set()

        search_url = (
            f"{self.FB}/groups/{group_id.strip()}/search/"
            f"?q={urllib.parse.quote(keyword)}"
        )

        try:
            self.page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
            self.page.wait_for_timeout(4000)

            if "/login" in self.page.url or "checkpoint" in self.page.url:
                raise RuntimeError("Session hết hạn hoặc chưa đăng nhập. Vui lòng nhấn 'Kết nối Facebook' để đăng nhập lại!")

            last_h = 0
            stale_cnt = 0
            scrolls = 0

            while len(posts) < max_posts and scrolls < 40:
                if self._stop_event and self._stop_event.is_set():
                    break

                self._expand_all()

                new_posts = self._collect(group_id, keyword, seen, group_name)
                for p in new_posts:
                    posts.append(p)

                if self._is_end_of_results():
                    print(f"[crawler] {group_id}/{keyword}: Đã gặp 'End of results'. Dừng crawl group này.")
                    break

                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                self.page.wait_for_timeout(2500)
                scrolls += 1

                new_h = self.page.evaluate("document.body.scrollHeight")
                if new_h == last_h:
                    stale_cnt += 1
                    if stale_cnt >= 3:
                        print(f"[crawler] {group_id}/{keyword}: Không thể cuộn thêm (scrollHeight giữ nguyên). Dừng crawl.")
                        break
                    self.page.wait_for_timeout(2000)
                else:
                    stale_cnt = 0
                    last_h = new_h

        except RuntimeError:
            raise
        except Exception as exc:
            print(f"[crawler] {group_id}/{keyword}: {exc}")

        return posts

    def _is_end_of_results(self) -> bool:
        try:
            end_elem = self.page.locator('span:has-text("End of results"), span:has-text("Kết thúc kết quả")')
            if end_elem.count() > 0:
                for i in range(end_elem.count()):
                    if end_elem.nth(i).is_visible(timeout=200):
                        return True
        except Exception:
            pass
        return False

    def dump_debug(self) -> str:
        debug_dir = os.path.join(_BASE, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(debug_dir, f"scan_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._debug_log, f, ensure_ascii=False, indent=2, default=str)
        print(f"[debug] Đã ghi {len(self._debug_log)} articles → {path}")

        # Tự động dọn dẹp các file debug cũ, chỉ giữ lại 5 file mới nhất
        try:
            files = sorted(
                [os.path.join(debug_dir, f) for f in os.listdir(debug_dir) if f.startswith("scan_") and f.endswith(".json")],
                key=os.path.getmtime,
                reverse=True,
            )
            for old_file in files[5:]:
                try:
                    os.remove(old_file)
                except Exception:
                    pass
        except Exception:
            pass

        return path

    def close(self):
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

    def _expand_all(self):
        for text in ["Xem thêm", "See more"]:
            try:
                btns = self.page.locator(f'div[role="button"]:has-text("{text}"), span[role="button"]:has-text("{text}")')
                count = btns.count()
                for i in range(min(count, 15)):
                    try:
                        btn = btns.nth(i)
                        if btn.is_visible(timeout=300):
                            btn.click(timeout=800)
                            self.page.wait_for_timeout(300)
                    except Exception:
                        pass
            except Exception:
                pass

    def _collect(
        self,
        group_id: str,
        keyword: str,
        seen: set[str],
        group_name: str = "",
    ) -> list[dict]:
        results: list[dict] = []

        try:
            items_data = self.page.evaluate('''() => {
                let feed = document.querySelector('div[role="feed"]');
                let els = [];
                if (feed) {
                    els = Array.from(feed.querySelectorAll('div[data-virtualized="false"]'));
                }
                if (!els || els.length === 0) {
                    els = Array.from(document.querySelectorAll('div[role="article"]'));
                }
                return els.map(el => ({ innerText: el.innerText || '' }));
            }''')
        except Exception:
            return results

        for item in items_data:
            raw_text = item.get("innerText", "")

            content, author = self._parse_post_text(raw_text)

            if len(content) < 10:
                continue

            is_anon = (
                not author
                or author == "Thành viên ẩn danh"
                or "ẩn danh" in author.lower()
                or "anonymous" in author.lower()
            )

            if is_anon:
                author = "Thành viên ẩn danh"
                words = content.split()[:7]
                snippet = " ".join(words)
                search_q = urllib.parse.quote(snippet)
            else:
                search_q = urllib.parse.quote(author)

            search_link = f"https://www.facebook.com/groups/{group_id.strip()}/search/?q={search_q}"

            raw_rec: dict = {
                "group_id": group_id,
                "group_name": group_name or group_id,
                "keyword": keyword,
                "scan_at": datetime.now().isoformat(timespec="seconds"),
                "raw_text": raw_text[:800],
                "extracted": {
                    "author": author,
                    "content_preview": content[:200],
                    "url": search_link,
                },
                "kept": False,
                "filter_reason": "",
            }

            # Lọc bài có số lần xuống dòng > 5 (tin tuyển dụng thường liệt kê > 5 dòng)
            line_cnt = content.count("\n")
            if line_cnt > 5:
                raw_rec["filter_reason"] = f"too_many_lines ({line_cnt})"
                self._debug_log.append(raw_rec)
                continue

            content_key = content[:50].lower().replace(" ", "").replace("\n", "")
            if content_key and content_key in seen:
                raw_rec["filter_reason"] = "duplicate_content"
                self._debug_log.append(raw_rec)
                continue

            if content_key:
                seen.add(content_key)

            raw_rec["kept"] = True
            self._debug_log.append(raw_rec)

            results.append({
                "author": author,
                "content": content[:500],
                "url": search_link,
                "group_id": group_id,
                "group_name": group_name or group_id,
            })

        return results

    def _parse_post_text(self, text: str) -> tuple[str, str]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        author = ""
        content_lines: list[str] = []
        prev_line = ""

        for ln in lines:
            ll = ln.lower()

            if ll in _SKIP_EXACT or _REACTION_RE.match(ln):
                prev_line = ""
                continue

            if "·" in ln:
                parts = ln.split("·", 1)
                before = parts[0].strip()
                after = parts[1].strip() if len(parts) > 1 else ""

                if before:
                    author = before
                elif prev_line:
                    author = prev_line

                if after:
                    content_lines.append(after)
                prev_line = ""
                continue

            if _SHARED_RE.search(ll):
                if prev_line and not author:
                    author = prev_line
                prev_line = ""
                continue

            prev_line = ln
            content_lines.append(ln)

        if author:
            if any(k in author.lower() for k in ["facebook", "marketplace", "reels", "watch"]):
                author = ""
            elif any(k in author.lower() for k in ["ẩn danh", "anonymous"]):
                author = "Thành viên ẩn danh"

        if not author:
            author = "Thành viên ẩn danh"

        content_lines_clean = []
        for c in content_lines:
            cl = c.lower()
            if c == author or c == "·":
                continue
            if any(k in cl for k in ["anonymous participant", "thành viên ẩn danh", "người dùng ẩn danh"]):
                continue
            content_lines_clean.append(c)

        content = "\n".join(content_lines_clean).strip()
        # Loại bỏ các tiền tố label ẩn danh nếu nằm đầu chuỗi content
        content = re.sub(r"^(anonymous\s+participant|thành\s+viên\s+ẩn\s+danh|người\s+dùng\s+ẩn\s+danh)\s*", "", content, flags=re.IGNORECASE).strip()
        return content, author
