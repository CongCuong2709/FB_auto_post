# 🚀 FB Auto Poster

Công cụ tự động đăng bài lên nhiều Facebook Group cùng lúc, có lên lịch hẹn giờ và delay ngẫu nhiên chống spam.

---

## ✨ Tính năng

| Tính năng | Mô tả |
|---|---|
| 📤 Đăng hàng loạt | Đăng bài lên nhiều group chỉ với 1 cú click |
| ⏰ Lên lịch hẹn giờ | Đặt thời gian đăng bài cụ thể trong tương lai |
| ⏳ Delay ngẫu nhiên | Tự động nghỉ ngẫu nhiên giữa các group để tránh bị khóa |
| 🎨 Hỗ trợ Rich Text | Giữ nguyên định dạng Bold, Italic, Underline khi đăng |
| 📋 Quản lý Template | Lưu sẵn các mẫu nội dung để dùng lại |
| 📊 Real-time Log | Theo dõi tiến trình đăng bài trực tiếp trên giao diện |
| ⏹️ Dừng giữa chừng | Có thể dừng quá trình đang chạy bất kỳ lúc nào |
| 📜 Lịch sử | Xem lại các lần đăng bài trước đó |

---

## 🛠️ Yêu cầu hệ thống

- **Windows** 10/11
- **Python** 3.9 trở lên — [Tải tại đây](https://python.org/downloads) *(nhớ tick "Add Python to PATH")*

---

## ⚡ Cài đặt

**Chỉ cần làm 1 lần duy nhất:**

```
Double-click vào file: install.bat
```

Script sẽ tự động:
1. Cài các thư viện Python (`flask`, `playwright`, `apscheduler`)
2. Tải trình duyệt Chromium cho Playwright
3. Tạo các thư mục dữ liệu cần thiết

---

## ▶️ Sử dụng

### Bước 1 — Khởi động ứng dụng

```
Double-click vào file: start.bat
```

Trình duyệt sẽ tự mở tại **http://localhost:5000**

---

### Bước 2 — Kết nối Facebook

1. Nhấn nút **"Kết nối Facebook"** trong giao diện
2. Cửa sổ Chrome mở ra → đăng nhập Facebook bình thường
3. Đăng nhập xong → **đóng cửa sổ Chrome** để lưu session
4. Session được lưu lại, **không cần đăng nhập lại** những lần sau

---

### Bước 3 — Thêm danh sách Group

Thêm URL các Facebook Group bạn muốn đăng bài vào, ví dụ:
```
https://www.facebook.com/groups/123456789
```

---

### Bước 4 — Soạn nội dung & Đăng

- **Đăng ngay**: Chọn group → nhập nội dung → nhấn **Đăng ngay**
- **Hẹn giờ**: Chọn group → nhập nội dung → chọn thời gian → nhấn **Lên lịch**

> **Delay giữa các group**: Mặc định 3–10 phút (có thể tùy chỉnh). Khuyến nghị giữ mức delay cao để tránh bị Facebook hạn chế.

---

## 📁 Cấu trúc thư mục

```
tim_nhan_su/
├── app.py              # Backend Flask – API & scheduler
├── poster.py           # Automation Playwright – đăng bài Facebook
├── install.bat         # Script cài đặt một lần
├── start.bat           # Script khởi động
├── requirements.txt    # Danh sách thư viện Python
├── templates/
│   └── index.html      # Giao diện web
├── data/               # Dữ liệu người dùng (tự tạo khi cài)
│   ├── groups.json     # Danh sách group đã lưu
│   ├── templates.json  # Mẫu nội dung đã lưu
│   └── history.json    # Lịch sử đăng bài
└── chrome_profile/     # Session đăng nhập Facebook (tự tạo)
```

---

## ⚙️ Cấu hình

| Tham số | Mặc định | Mô tả |
|---|---|---|
| Delay tối thiểu | 180 giây (3 phút) | Thời gian nghỉ tối thiểu giữa 2 group |
| Delay tối đa | 600 giây (10 phút) | Thời gian nghỉ tối đa giữa 2 group |

---

## 🔧 Tech Stack

- **Backend**: Python, Flask, APScheduler
- **Browser Automation**: Playwright (Chromium)
- **Frontend**: HTML, CSS, JavaScript (Vanilla)
- **Real-time**: Server-Sent Events (SSE)

---

## ⚠️ Lưu ý

- Chỉ đăng bài vào các group mà bạn là **thành viên hợp lệ**
- Đặt delay đủ lớn để tránh bị Facebook phát hiện là spam
- Thư mục `chrome_profile/` chứa session đăng nhập — **không chia sẻ** thư mục này cho người khác
