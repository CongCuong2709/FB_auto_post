import json
import os
import queue
import re
import threading
import webbrowser
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from datetime import datetime

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from flask import Flask, Response, jsonify, render_template, request, send_file

from poster import FacebookPoster
from crawler.fb_crawler import FBCrawler
from crawler.deduplicator import deduplicate_posts

# ─── App setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
GROUPS_F  = os.path.join(DATA_DIR, "groups.json")
TMPLS_F   = os.path.join(DATA_DIR, "templates.json")
HISTORY_F = os.path.join(DATA_DIR, "history.json")
os.makedirs(DATA_DIR, exist_ok=True)

log_queue = queue.Queue()
poster    = FacebookPoster(log_queue)

# Chỉ cho 1 lượt đăng chạy tại một thời điểm (chặn bấm đúp / bấm khi đang đăng)
_post_lock = threading.Lock()

# Thời gian nghỉ mặc định giữa 2 group khi đăng (giây)
DEFAULT_MIN_DELAY = 30
DEFAULT_MAX_DELAY = 90

# Số Chrome crawl chạy song song (cố định)
CRAWL_WORKERS = 2

# ─── Crawl Posts state ───────────────────────────────────────────────────────
_crawl_state: dict = {
    "running": False,
    "done": False,
    "progress": 0,
    "total": 0,
    "current_group": "",
    "current_keyword": "",
    "raw_count": 0,
    "results": [],
    "error": None,
    "active_workers": 0,
}
_crawl_lock  = threading.Lock()
_crawl_stop  = threading.Event()


def _cset(**kwargs):
    with _crawl_lock:
        _crawl_state.update(kwargs)

# ─── JSON helpers ─────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# Real-time log stream (Server-Sent Events)
@app.route("/api/stream")
def stream():
    def generate():
        while True:
            try:
                msg = log_queue.get(timeout=20)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield 'data: {"type":"ping"}\n\n'
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ── Groups ────────────────────────────────────────────────────────────────────
@app.route("/api/groups", methods=["GET", "POST"])
def groups():
    if request.method == "GET":
        return jsonify(load_json(GROUPS_F, []))
    save_json(GROUPS_F, request.json)
    return jsonify({"status": "ok"})

@app.route("/api/groups/<int:idx>", methods=["DELETE"])
def delete_group(idx):
    data = load_json(GROUPS_F, [])
    if 0 <= idx < len(data):
        data.pop(idx)
        save_json(GROUPS_F, data)
    return jsonify({"status": "ok"})

# ── Templates ─────────────────────────────────────────────────────────────────
@app.route("/api/templates", methods=["GET", "POST"])
def templates():
    if request.method == "GET":
        return jsonify(load_json(TMPLS_F, []))
    save_json(TMPLS_F, request.json)
    return jsonify({"status": "ok"})

# ── Facebook connect ──────────────────────────────────────────────────────────
_connecting = threading.Event()   # cửa sổ "Kết nối Facebook" đang mở (đang giữ chrome_profile)


def _crawl_running() -> bool:
    with _crawl_lock:
        return _crawl_state["running"]


def _run_connect():
    try:
        poster.connect_facebook()
    finally:
        _connecting.clear()


@app.route("/api/connect-facebook", methods=["POST"])
def connect_facebook():
    if poster.is_running or _post_lock.locked():
        return jsonify({"status": "error", "message": "Đang đăng bài — hãy đợi đăng xong rồi mới kết nối lại Facebook."})
    if _crawl_running():
        return jsonify({"status": "error", "message": "Đang crawl — hãy đợi crawl xong rồi mới kết nối lại Facebook."})
    if _connecting.is_set():
        return jsonify({"status": "error", "message": "Cửa sổ kết nối Facebook đang mở rồi."})
    _connecting.set()
    threading.Thread(target=_run_connect, daemon=True).start()
    return jsonify({"status": "ok"})

# ── Post now ──────────────────────────────────────────────────────────────────
def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _finish_history(hist_id: str, ok: int, failed: int):
    hist = load_json(HISTORY_F, [])
    for h in hist:
        if h.get("id") == hist_id:
            h["status"] = "success" if failed == 0 else ("partial" if ok else "failed")
            h["ok"], h["failed"] = ok, failed
            break
    save_json(HISTORY_F, hist)


def _run_post(hist_id, groups, content, min_del, max_del, html_content):
    try:
        ok, failed = poster.post_to_groups(groups, content, min_del, max_del, html_content)
        _finish_history(hist_id, ok, failed)
    finally:
        _post_lock.release()


@app.route("/api/post", methods=["POST"])
def post_now():
    if _connecting.is_set():
        return jsonify({"status": "error", "message": "Hãy đóng cửa sổ 'Kết nối Facebook' trước khi đăng."})
    if _crawl_running():
        return jsonify({"status": "error", "message": "Đang crawl — hãy đợi crawl xong (hoặc bấm Dừng) rồi mới đăng."})
    # Mỗi lần chỉ 1 lượt đăng
    if not _post_lock.acquire(blocking=False):
        return jsonify({"status": "error", "message": "Đang có lượt đăng đang chạy, đợi xong rồi đăng tiếp!"})

    started = False
    try:
        d        = request.get_json(silent=True) or {}
        content  = (d.get("content") or "").strip()
        html_content = (d.get("html_content") or "").strip()
        groups   = d.get("groups") or []
        min_del  = max(0, _to_int(d.get("min_delay"), DEFAULT_MIN_DELAY))
        max_del  = max(0, _to_int(d.get("max_delay"), DEFAULT_MAX_DELAY))
        if min_del > max_del:
            min_del, max_del = max_del, min_del

        if not content:
            return jsonify({"status": "error", "message": "Nội dung không được để trống!"})
        if not groups:
            return jsonify({"status": "error", "message": "Chưa chọn group nào!"})

        # Save history entry
        hist_id = datetime.now().isoformat()
        hist = load_json(HISTORY_F, [])
        hist.insert(0, {
            "id":      hist_id,
            "preview": content[:80] + ("…" if len(content) > 80 else ""),
            "groups":  len(groups),
            "time":    datetime.now().strftime("%d/%m/%Y %H:%M"),
            "status":  "running",
        })
        save_json(HISTORY_F, hist[:30])

        poster.is_running = True   # báo "đang chạy" ngay, trước khi thread kịp khởi động
        threading.Thread(
            target=_run_post,
            args=(hist_id, groups, content, min_del, max_del, html_content),
            daemon=True,
        ).start()
        started = True
        return jsonify({"status": "ok"})
    finally:
        if not started:
            poster.is_running = False
            _post_lock.release()


# ── Stop / status / history ───────────────────────────────────────────────────
@app.route("/api/stop", methods=["POST"])
def stop():
    poster.stop()
    return jsonify({"status": "ok"})

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"is_running": poster.is_running})

@app.route("/api/history", methods=["GET"])
def history():
    return jsonify(load_json(HISTORY_F, []))

# ─── Crawl Posts routes ───────────────────────────────────────────────────────

@app.route("/api/crawl-posts", methods=["POST"])
def crawl_posts_start():
    with _crawl_lock:
        if _crawl_state["running"]:
            return jsonify({"error": "Đang crawl, vui lòng đợi…"}), 409
    if poster.is_running or _post_lock.locked():
        return jsonify({"error": "Đang đăng bài — hãy đợi đăng xong (hoặc bấm Dừng) rồi mới crawl."}), 409
    if _connecting.is_set():
        return jsonify({"error": "Hãy đóng cửa sổ 'Kết nối Facebook' trước khi crawl."}), 409

    data      = request.get_json(force=True)
    raw_groups = data.get("groups", [])
    groups    = []
    for g in raw_groups:
        if isinstance(g, dict):
            if g.get("id") or g.get("url"):
                groups.append(g)
        elif isinstance(g, str) and g.strip():
            groups.append(g.strip())

    role_kws = [k.strip() for k in data.get("role_keywords", data.get("extra_keywords", [])) if isinstance(k, str) and k.strip()]

    if not groups:
        return jsonify({"error": "Vui lòng chọn ít nhất 1 Group"}), 400

    if not role_kws:
        return jsonify({"error": "Vui lòng nhập ít nhất 1 từ khoá tìm kiếm (VD: kế toán, telesale, lập trình...)"}), 400

    # Danh sách từ khoá tìm kiếm: chỉ dùng từ khoá HR nhập — không dùng từ khoá mặc định
    # Bộ lọc đại từ xưng hô (em, mình, tôi...) vẫn được áp dụng sau khi crawl
    keywords: list[str] = []
    seen_kw: set[str] = set()
    for r_kw in role_kws:
        lk = r_kw.lower()
        if lk not in seen_kw:
            seen_kw.add(lk)
            keywords.append(r_kw)

    max_workers = CRAWL_WORKERS

    total = len(groups) * len(keywords)
    _crawl_stop.clear()
    _cset(
        running=True, done=False, progress=0, total=total,
        current_group="", current_keyword="",
        raw_count=0, results=[], error=None,
        role_keywords=role_kws,
        active_workers=0,
    )

    t = threading.Thread(
        target=_run_crawl_posts,
        args=(groups, keywords, max_workers),
        daemon=True,
    )
    t.start()
    return jsonify({"status": "started", "total": total, "keywords": keywords, "max_workers": max_workers})



def _crawl_one_task(g_id: str, g_name: str, kw: str) -> list[dict]:
    """Crawl 1 cặp (group, keyword) trên 1 Chrome riêng. Chạy trong ThreadPoolExecutor."""
    if _crawl_stop.is_set():
        return []

    with _crawl_lock:
        _crawl_state["active_workers"] += 1
        _crawl_state["current_group"] = g_name or g_id
        _crawl_state["current_keyword"] = kw

    print(f"[crawl-posts][worker] Tìm: group={g_name!r} ({g_id}), keyword={kw!r}")
    crawler = None
    posts: list[dict] = []
    try:
        crawler = FBCrawler(stop_event=_crawl_stop, use_session_file=True)
        posts = crawler.search_group(g_id, kw, group_name=g_name)
        print(f"[crawl-posts][worker] {g_name!r} × {kw!r}: tìm thấy {len(posts)} bài")
    except RuntimeError as e:
        # Session hết hạn / không mở được trình duyệt → dừng cả đợt và ghi lại lý do
        print(f"[crawl-posts][worker] RuntimeError: {e}")
        with _crawl_lock:
            if not _crawl_state.get("error"):
                _crawl_state["error"] = str(e)
        _crawl_stop.set()
    except Exception as exc:
        print(f"[crawl-posts][worker] Bỏ qua lỗi: {exc}")
    finally:
        if crawler:
            try:
                crawler.dump_debug()
            except Exception:
                pass
            crawler.close()
        with _crawl_lock:
            _crawl_state["active_workers"] = max(0, _crawl_state["active_workers"] - 1)
            _crawl_state["progress"] += 1
            _crawl_state["raw_count"] += len(posts)

    return posts


def _run_crawl_posts(groups, keywords, max_workers: int = CRAWL_WORKERS):
    # ── Bước 1: Export session từ main profile ra file JSON ──────────────
    print("[crawl-posts] Đang export session Facebook cho workers...")
    if not FBCrawler.export_session():
        _cset(
            running=False, done=True,
            error="Không thể mở session Facebook. Vui lòng bấm 'Kết nối Facebook' rồi đăng nhập lại."
        )
        return

    all_posts: list[dict] = []

    # Xây danh sách tất cả task (g_id, g_name, kw)
    tasks: list[tuple[str, str, str]] = []
    for group in groups:
        if isinstance(group, dict):
            g_id = group.get("id", "").strip()
            g_name = group.get("name", g_id)
        else:
            g_id = str(group).strip()
            g_name = g_id
        if not g_id:
            continue
        for kw in keywords:
            tasks.append((g_id, g_name, kw))

    print(f"[crawl-posts] Bắt đầu song song: {len(tasks)} task, max_workers={max_workers}")

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_crawl_one_task, g_id, g_name, kw): (g_id, g_name, kw)
                for (g_id, g_name, kw) in tasks
            }
            for future in as_completed(futures):
                g_id, g_name, kw = futures[future]
                # Luôn lấy kết quả của task đã xong (kể cả khi đang dừng) để không mất bài
                try:
                    all_posts.extend(future.result())
                except CancelledError:
                    pass
                except Exception as exc:
                    print(f"[crawl-posts] Future lỗi ({g_name!r} × {kw!r}): {exc}")
                if _crawl_stop.is_set():
                    # Huỷ các task chưa bắt đầu; task đang chạy sẽ tự dừng theo stop_event
                    for f in futures:
                        f.cancel()

        unique = deduplicate_posts(all_posts)
        clean  = [{k: v for k, v in p.items() if k != "date_obj"} for p in unique]
        print(f"[crawl-posts] Xong: {len(all_posts)} bài thô → {len(unique)} sau dedup")
        # Giữ nguyên "error" (nếu worker đã ghi) để giao diện hiện lý do dừng
        _cset(running=False, done=True, results=clean)

        log_queue.put({
            "type": "crawl_done",
            "result_count": len(unique),
            "time": datetime.now().strftime("%H:%M:%S")
        })

    except Exception as exc:
        print(f"[crawl-posts] LỖI: {exc}")
        import traceback; traceback.print_exc()
        _cset(running=False, done=True, error=str(exc))


@app.route("/api/crawl-posts/status")
def crawl_posts_status():
    with _crawl_lock:
        snap = {k: v for k, v in _crawl_state.items() if k != "results"}
        snap["result_count"] = len(_crawl_state["results"])
    return jsonify(snap)


@app.route("/api/crawl-posts/results")
def crawl_posts_results():
    page = max(1, int(request.args.get("page", 1)))
    per  = max(1, min(int(request.args.get("per_page", 25)), 100))
    with _crawl_lock:
        all_r = list(_crawl_state["results"])
        role_kws = list(_crawl_state.get("role_keywords", []))
    start = (page - 1) * per
    return jsonify({
        "total": len(all_r), "page": page, "per_page": per,
        "role_keywords": role_kws,
        "items": all_r[start: start + per],
        "all_items": all_r,
    })


@app.route("/api/crawl-posts/stop", methods=["POST"])
def crawl_posts_stop():
    _crawl_stop.set()
    return jsonify({"status": "stopping"})


import unicodedata

def remove_accents(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFD', str(text))
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.replace('đ', 'd').replace('Đ', 'D').lower()

def match_hr_keyword(kw: str, content: str, author: str = "") -> bool:
    if not kw:
        return False
    norm_kw = remove_accents(kw).strip()
    if not norm_kw:
        return False
    norm_target = remove_accents(f"{author} {content}")

    if norm_kw in norm_target:
        return True

    kw_words = norm_kw.split()
    if len(kw_words) > 1 and all(w in norm_target for w in kw_words):
        return True

    return False


_PHONE_PATTERN = re.compile(r"(?:(?:\+?84|0)\s*[\.\-\s]?\s*)?(?:\d\s*[\.\-\s]?\s*){9,10}")


def extract_phone(text: str) -> str:
    if not text:
        return ""
    matches = _PHONE_PATTERN.findall(text)
    for m in matches:
        digits = re.sub(r"\D", "", m)
        if digits.startswith("84") and len(digits) == 11:
            digits = "0" + digits[2:]
        if len(digits) == 10 and digits.startswith("0"):
            return digits
    return ""


@app.route("/api/crawl-posts/export")
def crawl_posts_export():
    with _crawl_lock:
        results = list(_crawl_state["results"])
        role_kws = list(_crawl_state.get("role_keywords", []))
    if not results:
        return jsonify({"error": "Không có kết quả để xuất"}), 400

    wb = openpyxl.Workbook()

    def _format_sheet(ws, post_list):
        headers = ["STT", "Tên", "SĐT", "Nội dung bài viết", "Group", "Link bài"]
        ws.append(headers)

        hdr_font  = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
        hdr_fill  = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for cell in ws[1]:
            cell.font = hdr_font; cell.fill = hdr_fill; cell.alignment = hdr_align

        even_fill  = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        wrap_top   = Alignment(vertical="top", wrap_text=True)
        center_top = Alignment(horizontal="center", vertical="top")
        link_font  = Font(name="Calibri", color="0563C1", underline="single")

        for idx, post in enumerate(post_list, 1):
            url = (post.get("url") or "").strip()
            phone = post.get("phone") or extract_phone(post.get("content", ""))
            ws.append([idx, post.get("author", ""), phone or "—", post.get("content", ""),
                       post.get("group_name", post.get("group_id", "")), "🔗 Link" if url else "—"])
            
            row_idx = idx + 1
            for cell in ws[row_idx]:
                cell.alignment = wrap_top
                if idx % 2 == 0:
                    cell.fill = even_fill

            # Căn giữa cột STT (1) và SĐT (3)
            ws.cell(row=row_idx, column=1).alignment = center_top
            ws.cell(row=row_idx, column=3).alignment = center_top

            if url:
                link_cell = ws.cell(row=row_idx, column=6)
                link_cell.hyperlink = url
                link_cell.font = link_font
                link_cell.alignment = center_top

        for ci, w in enumerate([6, 24, 16, 80, 25, 15], 1):
            ws.column_dimensions[get_column_letter(ci)].width = w
        ws.row_dimensions[1].height = 28
        for r in range(2, len(post_list) + 2):
            ws.row_dimensions[r].height = 90
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    def _safe_sheet_title(name):
        clean_name = re.sub(r'[\\/*?:\[\]]', '', name).strip()
        return clean_name[:31] if clean_name else "Sheet"

    # Sheet 1: Tất cả
    ws_all = wb.active
    ws_all.title = "Tất cả bài viết"
    _format_sheet(ws_all, results)

    # Nếu có từ khoá HR nhập, tạo từng Sheet cho mỗi từ khoá + Sheet Dư thừa
    if role_kws:
        matched_indices = set()
        for kw in role_kws:
            matching = []
            for idx, post in enumerate(results):
                content = post.get("content") or ""
                author = post.get("author") or ""
                if match_hr_keyword(kw, content, author):
                    matching.append(post)
                    matched_indices.add(idx)

            title = _safe_sheet_title(f"KW - {kw}")
            ws_kw = wb.create_sheet(title=title)
            _format_sheet(ws_kw, matching)

        # Sheet "Dư thừa" (bài không khớp bất kỳ từ khoá HR nào)
        remainder = [post for idx, post in enumerate(results) if idx not in matched_indices]
        ws_rem = wb.create_sheet(title="Dư thừa (Còn lại)")
        _format_sheet(ws_rem, remainder)

    os.makedirs("data", exist_ok=True)
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"nguoi_tim_viec_{ts}.xlsx"
    fpath = os.path.join("data", fname)
    wb.save(fpath)

    return send_file(fpath, as_attachment=True, download_name=fname,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "═" * 52)
    print("  🚀  FB Auto Poster  —  http://localhost:5000")
    print("═" * 52 + "\n")

    def _open():
        import time; time.sleep(1.5)
        webbrowser.open("http://localhost:5000")

    threading.Thread(target=_open, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
