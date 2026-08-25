from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import time
import random
import os
import queue
from datetime import datetime

# Trỏ Playwright tới thư mục browsers/ trong folder ứng dụng
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "browsers"),
)


USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile")


class FacebookPoster:
    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue
        self.is_running = False
        self.should_stop = False

    # ─── Logging ──────────────────────────────────────────────────────────────
    def log(self, message: str, level: str = "info"):
        self.log_queue.put({
            "type": "log",
            "message": message,
            "level": level,
            "time": datetime.now().strftime("%H:%M:%S"),
        })

    # ─── Facebook login ────────────────────────────────────────────────────────
    def connect_facebook(self):
        """Open a persistent Chrome window for the user to log in to Facebook."""
        self.log("🔐 Đang mở trình duyệt… Vui lòng đăng nhập Facebook rồi đóng cửa sổ.", "info")
        try:
            with sync_playwright() as p:
                ctx = p.chromium.launch_persistent_context(
                    USER_DATA_DIR,
                    headless=False,
                    viewport={"width": 1366, "height": 768},
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                )
                page = ctx.new_page()
                page.goto("https://www.facebook.com")
                self.log("✅ Trình duyệt mở. Đăng nhập xong thì đóng cửa sổ Chrome lại.", "success")
                try:
                    ctx.wait_for_event("close", timeout=300_000)  # 5 min
                except Exception:
                    pass
                self.log("✅ Đã lưu session Facebook. Sẵn sàng đăng bài!", "success")
        except Exception as e:
            msg = str(e)
            if "closed" in msg.lower():
                self.log("✅ Session đã được lưu thành công!", "success")
            else:
                self.log(f"❌ Lỗi khi mở trình duyệt: {msg[:120]}", "error")

    # ─── Multi-group posting ───────────────────────────────────────────────────
    def post_to_groups(self, groups: list, content: str,
                       min_delay: int = 180, max_delay: int = 600,
                       html_content: str = None):
        """Post *content* to every group in *groups*, with random delays in between."""
        self.is_running = True
        self.should_stop = False
        total = len(groups)
        ok = 0
        fail = 0

        self.log(f"🚀 Bắt đầu đăng lên {total} group…", "info")

        try:
            with sync_playwright() as p:
                ctx = p.chromium.launch_persistent_context(
                    USER_DATA_DIR,
                    headless=False,
                    viewport={"width": 1366, "height": 768},
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                )

                for i, group in enumerate(groups):
                    if self.should_stop:
                        self.log("⏹️ Dừng theo yêu cầu.", "warning")
                        break

                    name = group.get("name", group.get("url", "???"))
                    self.log(f"📤  [{i + 1}/{total}]  {name}", "info")

                    if self._post_single(ctx, group["url"], content, html_content):
                        ok += 1
                        self.log(f"✅ Thành công: {name}", "success")
                    else:
                        fail += 1
                        self.log(f"❌ Thất bại: {name}", "error")

                    # Delay (except after the last group)
                    if i < total - 1 and not self.should_stop:
                        delay = random.randint(min_delay, max_delay)
                        self.log(
                            f"⏳ Nghỉ {delay // 60} phút {delay % 60} giây…",
                            "info",
                        )
                        elapsed = 0
                        while elapsed < delay and not self.should_stop:
                            time.sleep(5)
                            elapsed += 5

                try:
                    ctx.close()
                except Exception:
                    pass

        except Exception as e:
            self.log(f"❌ Lỗi nghiêm trọng: {str(e)[:150]}", "error")

        self.is_running = False
        level = "success" if fail == 0 else ("warning" if ok > 0 else "error")
        self.log(
            f"🏁 Xong!  ✅ {ok} thành công  |  ❌ {fail} thất bại",
            level,
        )
        self.log_queue.put({"type": "done", "success": ok, "failed": fail})

    # ─── Single-group posting (internal) ──────────────────────────────────────
    def _post_single(self, ctx, group_url: str, content: str, html_content: str = None) -> bool:
        page = ctx.new_page()
        try:
            page.goto(group_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(random.randint(2_500, 4_000))

            # Detect login wall
            if any(k in page.url for k in ("login", "checkpoint", "recover")):
                self.log("⚠️ Chưa đăng nhập Facebook! Hãy kết nối trước.", "error")
                return False

            # ── Step 1: find & click the "create post" trigger ──────────────
            clicked = False
            triggers = [
                # VN UI
                'div[role="button"]:has-text("Bạn đang nghĩ gì")',
                'div[role="button"]:has-text("Viết gì đó")',
                '[placeholder*="nghĩ gì"]',
                '[placeholder*="Viết gì"]',
                # EN UI
                'div[role="button"]:has-text("Write something")',
                'div[role="button"]:has-text("What\'s on your mind")',
                '[placeholder*="Write something"]',
                '[placeholder*="mind"]',
                # Generic fallback
                '[data-testid="status-attachment-mentions-input"]',
            ]
            for sel in triggers:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2_000):
                        el.click()
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                # Last resort: click first button in main area
                try:
                    page.locator('[role="main"] [role="button"]').first.click()
                    page.wait_for_timeout(1_500)
                    clicked = True
                except Exception:
                    pass

            if not clicked:
                return False

            page.wait_for_timeout(random.randint(1_000, 2_000))

            # ── Step 2: enter content ────────────────────────────────────────
            # After the click the editable area should be focused.
            # We use rich HTML paste to preserve Word/tool styles like Bold, Italic, Underline.
            if html_content:
                page.evaluate(
                    """(data) => {
                        const dt = new DataTransfer();
                        dt.setData('text/plain', data.plain);
                        dt.setData('text/html', data.html);
                        const event = new ClipboardEvent('paste', {
                            bubbles: true,
                            cancelable: true,
                            clipboardData: dt
                        });
                        document.activeElement.dispatchEvent(event);
                    }""",
                    {"plain": content, "html": html_content}
                )
            else:
                page.keyboard.type(content, delay=random.randint(25, 60))
            page.wait_for_timeout(random.randint(1_200, 2_200))

            # ── Step 3: click Post / Đăng ───────────────────────────────────
            submit_sels = [
                'div[aria-label="Đăng"]',
                'div[aria-label="Post"]',
                'button[aria-label="Đăng"]',
                'button[aria-label="Post"]',
                '[data-testid="react-composer-post-button"]',
                'div[role="button"]:has-text("Đăng")',
                'button:has-text("Đăng")',
            ]
            submitted = False
            for sel in submit_sels:
                try:
                    btn = page.locator(sel).last
                    if btn.is_visible(timeout=2_000) and btn.is_enabled():
                        btn.click()
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                return False

            page.wait_for_timeout(random.randint(3_000, 5_000))
            return True

        except PlaywrightTimeout:
            self.log("⚠️ Timeout khi tải trang.", "warning")
            return False
        except Exception as e:
            self.log(f"⚠️ Lỗi: {str(e)[:100]}", "warning")
            return False
        finally:
            try:
                page.close()
            except Exception:
                pass

    # ─── Stop ─────────────────────────────────────────────────────────────────
    def stop(self):
        self.should_stop = True
