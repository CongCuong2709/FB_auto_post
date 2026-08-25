"""
updater.py — Kiểm tra GitHub Releases, tự cập nhật nếu có bản mới, rồi chạy app.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

# ─── Cấu hình ────────────────────────────────────────────────────────────────
GITHUB_OWNER = "CongCuong2709"   # <-- điền username GitHub của bạn
GITHUB_REPO  = "FB_auto_post"         # <-- điền tên repo

BASE_DIR     = Path(__file__).parent.resolve()
VERSION_FILE = BASE_DIR / "version.txt"
PYTHON_EXE   = BASE_DIR / "python" / "python.exe"

# Các thư mục KHÔNG bị ghi đè khi update
SKIP_DIRS = {"data", "chrome_profile", "python", "lib", "browsers", ".git"}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def current_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


def parse_version(tag: str):
    """Chuyển 'v1.2.3' hoặc '1.2.3' thành tuple (1, 2, 3)."""
    tag = tag.lstrip("v")
    try:
        return tuple(int(x) for x in tag.split("."))
    except Exception:
        return (0, 0, 0)


def fetch_latest_release():
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "fb-auto-poster-updater"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def download_file(url: str, dest: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "fb-auto-poster-updater"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def apply_update(zip_path: Path):
    """Giải nén ZIP và copy đè lên BASE_DIR, bỏ qua các thư mục quan trọng."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_path)

        # Nếu ZIP có 1 thư mục gốc bên trong, vào bên trong đó
        extracted = list(tmp_path.iterdir())
        src = extracted[0] if len(extracted) == 1 and extracted[0].is_dir() else tmp_path

        for item in src.rglob("*"):
            rel = item.relative_to(src)
            parts = rel.parts

            # Bỏ qua thư mục bảo vệ
            if parts and parts[0] in SKIP_DIRS:
                continue

            dest = BASE_DIR / rel
            if item.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 52)
    print("  FB Auto Poster — Kiểm tra cập nhật...")
    print("=" * 52)

    cur = current_version()
    print(f"  Phiên bản hiện tại: v{cur}")

    # Nếu chưa cấu hình GitHub, bỏ qua update
    if GITHUB_OWNER == "YOUR_GITHUB_USERNAME":
        print("  [!] Chưa cấu hình GitHub — bỏ qua cập nhật.")
    else:
        release = fetch_latest_release()
        if release is None:
            print("  [!] Không kết nối được GitHub — bỏ qua cập nhật.")
        else:
            latest_tag = release.get("tag_name", "0.0.0")
            print(f"  Phiên bản mới nhất : {latest_tag}")

            if parse_version(latest_tag) > parse_version(cur):
                # Tìm asset là file .zip
                assets = [a for a in release.get("assets", []) if a["name"].endswith(".zip")]
                if not assets:
                    print("  [!] Không tìm thấy file ZIP trong release — bỏ qua.")
                else:
                    asset = assets[0]
                    print(f"  --> Đang tải bản mới: {asset['name']} ({asset['size'] // 1024} KB)...")
                    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
                        tmp_zip = Path(tf.name)
                    try:
                        download_file(asset["browser_download_url"], tmp_zip)
                        print("  --> Đang áp dụng cập nhật...")
                        apply_update(tmp_zip)
                        VERSION_FILE.write_text(latest_tag.lstrip("v") + "\n", encoding="utf-8")
                        print(f"  ✅ Đã cập nhật lên {latest_tag}!")
                    finally:
                        tmp_zip.unlink(missing_ok=True)
            else:
                print("  ✅ Đang dùng phiên bản mới nhất.")

    print("=" * 52)
    print()

    # Khởi động app
    app_py = BASE_DIR / "app.py"
    os.execv(str(PYTHON_EXE), [str(PYTHON_EXE), str(app_py)])


if __name__ == "__main__":
    main()
