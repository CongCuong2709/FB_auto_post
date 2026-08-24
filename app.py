import json
import os
import queue
import threading
import webbrowser
from datetime import datetime

from apscheduler.executors.pool import ThreadPoolExecutor as APThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response, jsonify, render_template, request

from poster import FacebookPoster

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
