import json
import os
import queue
import threading
import webbrowser
from datetime import datetime

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from apscheduler.executors.pool import ThreadPoolExecutor as APThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response, jsonify, render_template, request, send_file

from poster import FacebookPoster
from crawler.fb_crawler import DEFAULT_JOBSEEKER_KEYWORDS, FBCrawler
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

scheduler = BackgroundScheduler(executors={"default": APThreadPoolExecutor(1)})
scheduler.start()

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
@app.route("/api/connect-facebook", methods=["POST"])
def connect_facebook():
    t = threading.Thread(target=poster.connect_facebook, daemon=True)
    t.start()
    return jsonify({"status": "ok"})

# ── Post now ──────────────────────────────────────────────────────────────────
@app.route("/api/post", methods=["POST"])
def post_now():
    if poster.is_running:
        return jsonify({"status": "error", "message": "Đang có lần đăng đang chạy!"})

    d        = request.json
    content  = d.get("content", "").strip()
    html_content = d.get("html_content", "").strip()
    groups   = d.get("groups", [])
    min_del  = int(d.get("min_delay", 180))
    max_del  = int(d.get("max_delay", 600))

    if not content:
        return jsonify({"status": "error", "message": "Nội dung không được để trống!"})
    if not groups:
        return jsonify({"status": "error", "message": "Chưa chọn group nào!"})

    # Save history entry
    hist = load_json(HISTORY_F, [])
    hist.insert(0, {
        "id":      datetime.now().isoformat(),
        "preview": content[:80] + ("…" if len(content) > 80 else ""),
        "groups":  len(groups),
        "time":    datetime.now().strftime("%d/%m/%Y %H:%M"),
        "status":  "running",
    })
    save_json(HISTORY_F, hist[:30])

    t = threading.Thread(
        target=poster.post_to_groups,
        args=[groups, content, min_del, max_del, html_content],
        daemon=True,
    )
    t.start()
    return jsonify({"status": "ok"})

# ── Schedule ──────────────────────────────────────────────────────────────────
@app.route("/api/schedule", methods=["POST"])
def schedule_post():
    d       = request.json
    content = d.get("content", "").strip()
    html_content = d.get("html_content", "").strip()
    groups  = d.get("groups", [])
    rt_str  = d.get("run_time", "")
    min_del = int(d.get("min_delay", 180))
    max_del = int(d.get("max_delay", 600))

    if not (content and groups and rt_str):
        return jsonify({"status": "error", "message": "Thiếu thông tin!"})

    try:
        run_dt = datetime.fromisoformat(rt_str)
    except ValueError:
        return jsonify({"status": "error", "message": "Thời gian không hợp lệ!"})

    job_id = f"post_{int(run_dt.timestamp())}"
    scheduler.add_job(
        poster.post_to_groups,
        trigger="date",
        run_date=run_dt,
        args=[groups, content, min_del, max_del, html_content],
        id=job_id,
        replace_existing=True,
    )
    return jsonify({"status": "ok", "job_id": job_id, "run_time": rt_str})

@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    return jsonify([
        {"id": j.id, "next_run": j.next_run_time.strftime("%d/%m/%Y %H:%M:%S")}
        for j in scheduler.get_jobs() if j.next_run_time
    ])

@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def cancel_job(job_id):
    try:
        scheduler.remove_job(job_id)
        return jsonify({"status": "ok"})
    except Exception:
        return jsonify({"status": "error", "message": "Không tìm thấy lịch này."})

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

    data      = request.get_json(force=True)
    raw_groups = data.get("groups", [])
    groups    = []
    for g in raw_groups:
        if isinstance(g, dict):
            if g.get("id") or g.get("url"):
                groups.append(g)
        elif isinstance(g, str) and g.strip():
            groups.append(g.strip())

    extra_kws = [k.strip() for k in data.get("extra_keywords", []) if isinstance(k, str) and k.strip()]

    if not groups:
        return jsonify({"error": "Vui lòng chọn ít nhất 1 Group"}), 400

    # Gộp từ khoá mặc định + từ khoá người dùng thêm
    seen_kw: set[str] = set()
    keywords: list[str] = []
    for kw in DEFAULT_JOBSEEKER_KEYWORDS + extra_kws:
        lk = kw.lower()
        if lk not in seen_kw:
            seen_kw.add(lk)
            keywords.append(kw)

    total = len(groups) * len(keywords)
    _crawl_stop.clear()
    _cset(
        running=True, done=False, progress=0, total=total,
        current_group="", current_keyword="",
        raw_count=0, results=[], error=None,
    )

    t = threading.Thread(
        target=_run_crawl_posts,
        args=(groups, keywords),
        daemon=True,
    )
    t.start()
    return jsonify({"status": "started", "total": total, "keywords": keywords})


def _run_crawl_posts(groups, keywords):
    crawler = None
    try:
        print("[crawl-posts] Đang khởi động Chrome...")
        crawler = FBCrawler(stop_event=_crawl_stop)
        print("[crawl-posts] Chrome đã mở!")
        all_posts: list[dict] = []

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
                if _crawl_stop.is_set():
                    break
                _cset(current_group=g_name or g_id, current_keyword=kw)
                print(f"[crawl-posts] Tìm: group={g_name!r} ({g_id}), keyword={kw!r}")
                try:
                    posts = crawler.search_group(g_id, kw, group_name=g_name)
                    print(f"[crawl-posts] Tìm thấy {len(posts)} bài")
                    all_posts.extend(posts)
                except RuntimeError as e:
                    print(f"[crawl-posts] RuntimeError: {e}")
                    _cset(running=False, done=True, error="Session hết hạn. Vui lòng kết nối lại Facebook.")
                    return
                except Exception as exc:
                    print(f"[crawl-posts] Bỏ qua lỗi: {exc}")
                finally:
                    with _crawl_lock:
                        _crawl_state["progress"] += 1
                        _crawl_state["raw_count"] = len(all_posts)
            if _crawl_stop.is_set():
                break

        unique = deduplicate_posts(all_posts)
        clean  = [{k: v for k, v in p.items() if k != "date_obj"} for p in unique]
        print(f"[crawl-posts] Xong: {len(all_posts)} bài thô → {len(unique)} sau dedup")
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
    finally:
        if crawler:
            try:
                crawler.dump_debug()
            except Exception as e:
                print(f"[crawl-posts] Không ghi debug: {e}")
            crawler.close()


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
    start = (page - 1) * per
    return jsonify({
        "total": len(all_r), "page": page, "per_page": per,
        "items": all_r[start: start + per],
    })


@app.route("/api/crawl-posts/stop", methods=["POST"])
def crawl_posts_stop():
    _crawl_stop.set()
    return jsonify({"status": "stopping"})


@app.route("/api/crawl-posts/export")
def crawl_posts_export():
    with _crawl_lock:
        results = list(_crawl_state["results"])
    if not results:
        return jsonify({"error": "Không có kết quả để xuất"}), 400

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Người tìm việc"

    headers = ["STT", "Tên", "Nội dung bài viết", "Group", "Link bài"]
    ws.append(headers)

    hdr_font  = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    hdr_fill  = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for cell in ws[1]:
        cell.font = hdr_font; cell.fill = hdr_fill; cell.alignment = hdr_align

    even_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    wrap_top  = Alignment(vertical="top", wrap_text=True)

    for idx, post in enumerate(results, 1):
        ws.append([idx, post.get("author", ""), post.get("content", ""),
                   post.get("group_name", post.get("group_id", "")), post.get("url", "")])
        for cell in ws[idx + 1]:
            cell.alignment = wrap_top
            if idx % 2 == 0:
                cell.fill = even_fill

    for ci, w in enumerate([6, 28, 85, 28, 60], 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 28
    for r in range(2, len(results) + 2):
        ws.row_dimensions[r].height = 90
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

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
