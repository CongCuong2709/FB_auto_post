"""
tao_tai_lieu.py
Tạo file HƯỚNG DẪN SỬ DỤNG.docx cho ứng dụng FB Auto Poster.
Chạy: python tao_tai_lieu.py
"""

from docx import Document
from docx.shared import Pt, RGBColor, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

# ── Màu sắc thương hiệu ───────────────────────────────────────────────────────
COLOR_PRIMARY   = RGBColor(0x63, 0x66, 0xF1)   # tím indigo
COLOR_HEADING   = RGBColor(0x1E, 0x2A, 0x3D)   # xanh đậm
COLOR_WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
COLOR_LIGHTBG   = RGBColor(0xF0, 0xF4, 0xFF)   # nền nhạt
COLOR_WARNING   = RGBColor(0xF5, 0x9E, 0x0B)   # vàng cảnh báo
COLOR_SUCCESS   = RGBColor(0x10, 0xB9, 0x81)   # xanh lá
COLOR_DANGER    = RGBColor(0xEF, 0x44, 0x44)   # đỏ
COLOR_GRAY      = RGBColor(0x64, 0x74, 0x8B)
COLOR_NOTE_BG   = RGBColor(0xFF, 0xF7, 0xED)
COLOR_NOTE_BORDER = RGBColor(0xF5, 0x9E, 0x0B)

# ── Helpers ───────────────────────────────────────────────────────────────────

def set_cell_bg(cell, rgb: RGBColor):
    """Đặt màu nền cho ô bảng."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}")
    tcPr.append(shd)

def set_para_shading(para, rgb: RGBColor):
    """Đặt màu nền cho đoạn văn."""
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}")
    pPr.append(shd)

def set_para_border_left(para, color_hex: str, width_pt: int = 18):
    """Thêm đường viền trái cho đoạn văn (kiểu blockquote)."""
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), str(width_pt))
    left.set(qn("w:space"), "6")
    left.set(qn("w:color"), color_hex)
    pBdr.append(left)
    pPr.append(pBdr)

def add_run(para, text: str, bold=False, italic=False, color=None, size_pt=None, underline=False):
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    run.underline = underline
    if color:
        run.font.color.rgb = color
    if size_pt:
        run.font.size = Pt(size_pt)
    return run

def heading1(doc, text: str):
    """Tiêu đề cấp 1 – màu nền primary."""
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pPr = para._p.get_or_add_pPr()
    # spacing
    pPr_spacing = OxmlElement("w:spacing")
    pPr_spacing.set(qn("w:before"), "240")
    pPr_spacing.set(qn("w:after"), "120")
    pPr.append(pPr_spacing)
    set_para_shading(para, COLOR_PRIMARY)
    # indent
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "160")
    pPr.append(ind)
    run = para.add_run(text)
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = COLOR_WHITE
    run.font.name = "Arial"
    return para

def heading2(doc, text: str):
    """Tiêu đề cấp 2 – gạch dưới màu primary."""
    para = doc.add_paragraph()
    pPr = para._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "200")
    spacing.set(qn("w:after"), "80")
    pPr.append(spacing)
    run = para.add_run(f"▸  {text}")
    run.bold = True
    run.font.size = Pt(13)
    run.font.color.rgb = COLOR_PRIMARY
    run.font.name = "Arial"
    return para

def heading3(doc, text: str):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.bold = True
    run.font.size = Pt(11.5)
    run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
    run.font.name = "Arial"
    pPr = para._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "160")
    spacing.set(qn("w:after"), "60")
    pPr.append(spacing)
    return para

def body(doc, text: str, color=None):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.size = Pt(11)
    run.font.name = "Arial"
    if color:
        run.font.color.rgb = color
    pPr = para._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:after"), "60")
    pPr.append(spacing)
    return para

def step_box(doc, num: str, title: str, lines: list):
    """Khối hướng dẫn có số bước nổi bật."""
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.autofit = False
    table.columns[0].width = Cm(1.4)
    table.columns[1].width = Cm(14.0)

    # Ô số bước
    cell_num = table.cell(0, 0)
    cell_num.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    set_cell_bg(cell_num, COLOR_PRIMARY)
    p_num = cell_num.paragraphs[0]
    p_num.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_num.add_run(num)
    r.bold = True
    r.font.size = Pt(18)
    r.font.color.rgb = COLOR_WHITE
    r.font.name = "Arial"

    # Ô nội dung
    cell_content = table.cell(0, 1)
    set_cell_bg(cell_content, COLOR_LIGHTBG)
    # Tiêu đề bước
    p_title = cell_content.paragraphs[0]
    rt = p_title.add_run(title)
    rt.bold = True
    rt.font.size = Pt(11.5)
    rt.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
    rt.font.name = "Arial"
    # Các dòng nội dung
    for line in lines:
        p = cell_content.add_paragraph()
        rr = p.add_run(line)
        rr.font.size = Pt(10.5)
        rr.font.name = "Arial"
        pPr = p._p.get_or_add_pPr()
        ind = OxmlElement("w:ind")
        ind.set(qn("w:left"), "80")
        pPr.append(ind)

    # Khoảng cách sau bảng
    doc.add_paragraph()
    return table

def image_placeholder(doc, label: str, height_cm=5.5):
    """Chèn ô giả placeholder cho ảnh."""
    para = doc.add_paragraph()
    pPr = para._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "60")
    spacing.set(qn("w:after"), "100")
    pPr.append(spacing)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run(label)
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
    run.font.name = "Arial"
    run.italic = True

    # Vẽ hộp placeholder bằng table 1×1
    tbl = doc.add_table(rows=1, cols=1)
    tbl.style = "Table Grid"
    cell = tbl.cell(0, 0)
    set_cell_bg(cell, RGBColor(0xF3, 0xF4, 0xF6))
    ph = cell.paragraphs[0]
    ph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ph.paragraph_format.space_before = Pt(height_cm * 28.35 / 2)
    ph.paragraph_format.space_after  = Pt(height_cm * 28.35 / 2)
    rh = ph.add_run(f"[ {label} ]")
    rh.font.size = Pt(11)
    rh.font.color.rgb = RGBColor(0x9C, 0xA3, 0xAF)
    rh.font.name = "Arial"
    rh.italic = True

    doc.add_paragraph()
    return tbl

def note_box(doc, text: str, kind="warning"):
    """Hộp ghi chú có viền trái màu."""
    icon_map   = {"warning": "⚠️", "info": "ℹ️", "tip": "💡", "danger": "❌"}
    color_map  = {"warning": "F59E0B", "info": "38BDF8", "tip": "10B981", "danger": "EF4444"}
    bg_map     = {"warning": RGBColor(0xFF, 0xF7, 0xED),
                  "info":    RGBColor(0xF0, 0xF9, 0xFF),
                  "tip":     RGBColor(0xF0, 0xFD, 0xF4),
                  "danger":  RGBColor(0xFF, 0xF1, 0xF1)}
    icon  = icon_map.get(kind, "ℹ️")
    color = color_map.get(kind, "38BDF8")
    bg    = bg_map.get(kind, RGBColor(0xF0, 0xF9, 0xFF))

    para = doc.add_paragraph()
    set_para_shading(para, bg)
    set_para_border_left(para, color, width_pt=24)
    pPr = para._p.get_or_add_pPr()
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "160")
    pPr.append(ind)
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "80")
    spacing.set(qn("w:after"), "80")
    pPr.append(spacing)
    run = para.add_run(f"{icon}  {text}")
    run.font.size = Pt(10.5)
    run.font.name = "Arial"
    doc.add_paragraph()
    return para

def bullet(doc, text: str, indent_cm=0.5):
    para = doc.add_paragraph(style="List Bullet")
    run = para.add_run(text)
    run.font.size = Pt(10.5)
    run.font.name = "Arial"
    para.paragraph_format.left_indent = Cm(indent_cm)
    return para

def divider(doc):
    para = doc.add_paragraph()
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "CCCCCC")
    pBdr.append(bottom)
    pPr.append(pBdr)

# ══════════════════════════════════════════════════════════════════════════════
# Nội dung tài liệu
# ══════════════════════════════════════════════════════════════════════════════

def build_doc():
    doc = Document()

    # ── Thiết lập trang A4 ────────────────────────────────────────────────────
    section = doc.sections[0]
    section.page_width  = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin   = Cm(2.5)
    section.right_margin  = Cm(2.5)
    section.top_margin    = Cm(2.5)
    section.bottom_margin = Cm(2.5)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TRANG BÌA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    for _ in range(5):
        doc.add_paragraph()

    cover_title = doc.add_paragraph()
    cover_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cover_title.add_run("📘  HƯỚNG DẪN SỬ DỤNG")
    r.bold = True; r.font.size = Pt(26); r.font.name = "Arial"
    r.font.color.rgb = COLOR_PRIMARY

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = sub.add_run("Công cụ Đăng Tuyển Dụng Tự Động lên Facebook")
    rs.font.size = Pt(14); rs.font.name = "Arial"
    rs.font.color.rgb = COLOR_GRAY

    doc.add_paragraph()
    line = doc.add_paragraph()
    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rl = line.add_run("─" * 45)
    rl.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph()
    audience = doc.add_paragraph()
    audience.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ra = audience.add_run("Dành cho bộ phận Nhân sự  •  Không cần kiến thức kỹ thuật")
    ra.italic = True; ra.font.size = Pt(11); ra.font.name = "Arial"
    ra.font.color.rgb = COLOR_GRAY

    for _ in range(8):
        doc.add_paragraph()

    version = doc.add_paragraph()
    version.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rv = version.add_run("Phiên bản 1.0  •  Tháng 8 / 2026")
    rv.font.size = Pt(10); rv.font.name = "Arial"; rv.font.color.rgb = COLOR_GRAY

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # MỤC LỤC
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "📋  MỤC LỤC")
    toc_items = [
        ("1.", "Giới thiệu ứng dụng"),
        ("2.", "Cài đặt lần đầu (chỉ làm 1 lần)"),
        ("3.", "Khởi động ứng dụng hàng ngày"),
        ("4.", "Kết nối tài khoản Facebook"),
        ("5.", "Quản lý danh sách Group"),
        ("6.", "Soạn & Đăng bài ngay lập tức"),
        ("7.", "Lên lịch đăng bài tự động"),
        ("8.", "Sử dụng Mẫu bài viết (Template)"),
        ("9.", "Tìm kiếm ứng viên (Crawl bài viết tìm việc)"),
        ("10.", "Theo dõi nhật ký & dừng khẩn cấp"),
        ("11.", "Các lỗi thường gặp & cách xử lý"),
    ]
    for num, title in toc_items:
        p = doc.add_paragraph()
        add_run(p, f"  {num}  ", bold=True, color=COLOR_PRIMARY, size_pt=11)
        add_run(p, title, size_pt=11)
        pPr = p._p.get_or_add_pPr()
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:after"), "40")
        pPr.append(spacing)

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 1: GIỚI THIỆU
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "1. 🏠  GIỚI THIỆU ỨNG DỤNG")
    body(doc,
         "FB Auto Poster là công cụ giúp bộ phận Nhân sự tự động đăng tin tuyển dụng "
         "lên nhiều group Facebook cùng một lúc, tiết kiệm hàng giờ làm việc thủ công mỗi ngày.")

    doc.add_paragraph()
    heading3(doc, "✅  Ứng dụng có thể làm được gì?")
    bullet(doc, "Đăng một bài viết tuyển dụng lên hàng chục / hàng trăm group Facebook chỉ với vài cú nhấp chuột.")
    bullet(doc, "Tự động chờ giữa các lần đăng để tránh bị Facebook khóa tài khoản.")
    bullet(doc, "Lên lịch đăng bài trước (ví dụ: đặt lịch đăng lúc 7 giờ sáng hôm sau).")
    bullet(doc, "Lưu sẵn các mẫu bài viết để dùng lại cho các đợt tuyển dụng sau.")
    bullet(doc, "Theo dõi kết quả đăng bài theo thời gian thực.")

    doc.add_paragraph()
    note_box(doc,
             "Ứng dụng chạy hoàn toàn trên máy tính của bạn, không cần Internet riêng ngoài "
             "kết nối Facebook thông thường. Dữ liệu được lưu an toàn trong máy.",
             kind="info")

    image_placeholder(doc, "Hình 1 – Giao diện tổng quan của ứng dụng", height_cm=6)

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 2: CÀI ĐẶT LẦN ĐẦU
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "2. ⚙️  CÀI ĐẶT LẦN ĐẦU  (Chỉ làm 1 lần duy nhất)")
    note_box(doc,
             "Bước cài đặt này chỉ thực hiện MỘT LẦN. Sau khi cài xong, "
             "những lần sau bạn chỉ cần nhấp đúp start.bat là dùng được ngay.",
             kind="tip")

    doc.add_paragraph()
    heading2(doc, "Yêu cầu trước khi cài đặt")
    bullet(doc, "Máy tính chạy Windows 10 / 11 (64-bit).")
    bullet(doc, "Kết nối Internet ổn định trong suốt quá trình cài đặt (khoảng 5–15 phút).")
    bullet(doc, "Thư mục ứng dụng đã được giải nén ra Desktop hoặc ổ D:\\, C:\\…")

    doc.add_paragraph()
    heading2(doc, "Các bước cài đặt")

    step_box(doc, "1", "Giải nén thư mục ứng dụng",
             ["Bạn nhận được file .zip từ bộ phận IT.",
              "Nhấp chuột phải vào file .zip → chọn 'Extract All...' (hoặc 'Giải nén tất cả...')",
              "Chọn nơi lưu (ví dụ D:\\tim_nhan_su) → nhấn Extract."])

    image_placeholder(doc, "Hình 2 – Nhấp chuột phải vào file .zip và chọn Extract All")

    step_box(doc, "2", "Mở thư mục vừa giải nén",
             ["Sau khi giải nén xong, mở thư mục tim_nhan_su.",
              "Bạn sẽ thấy các file: install.bat, start.bat, app.py, …"])

    image_placeholder(doc, "Hình 3 – Nội dung thư mục ứng dụng sau khi giải nén")

    step_box(doc, "3", "Chạy file install.bat",
             ["Nhấp đúp vào file install.bat.",
              "Nếu Windows hỏi 'Do you want to allow this app to make changes?' → nhấn Yes.",
              "Màn hình đen xuất hiện và tự động cài đặt — VUI LÒNG KHÔNG ĐÓNG CỬA SỔ này.",
              "Quá trình cài đặt mất khoảng 5–15 phút tùy tốc độ mạng.",
              "Khi thấy dòng chữ 'Cài đặt hoàn tất!' và nhấn phím bất kỳ để đóng → xong!"])

    image_placeholder(doc, "Hình 4 – Cửa sổ cài đặt đang chạy (chữ trắng trên nền đen)")

    note_box(doc,
             "Nếu màn hình báo lỗi màu đỏ, hãy chụp ảnh màn hình và gửi cho bộ phận IT hỗ trợ.",
             kind="danger")

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 3: KHỞI ĐỘNG HÀNG NGÀY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "3. 🚀  KHỞI ĐỘNG ỨNG DỤNG HÀNG NGÀY")
    body(doc,
         "Mỗi lần muốn sử dụng, bạn chỉ cần thực hiện 2 bước đơn giản dưới đây:")

    doc.add_paragraph()
    step_box(doc, "1", "Nhấp đúp vào file start.bat",
             ["Tìm file start.bat trong thư mục ứng dụng.",
              "Nhấp đúp chuột trái vào đó.",
              "Một cửa sổ đen nhỏ xuất hiện trong vài giây (đang kiểm tra cập nhật)."])

    image_placeholder(doc, "Hình 5 – File start.bat trong thư mục ứng dụng")

    step_box(doc, "2", "Trình duyệt tự động mở ứng dụng",
             ["Sau khoảng 3–5 giây, trình duyệt Chrome / Edge sẽ tự mở.",
              "Bạn thấy giao diện FB Auto Poster → sẵn sàng sử dụng!",
              "Nếu trình duyệt không tự mở, hãy gõ vào thanh địa chỉ: http://localhost:5000"])

    image_placeholder(doc, "Hình 6 – Ứng dụng đã khởi động, giao diện chính xuất hiện trên trình duyệt")

    note_box(doc,
             "KHÔNG đóng cửa sổ đen (command prompt) trong khi đang dùng ứng dụng. "
             "Khi dùng xong, hãy đóng cửa sổ đen trước rồi mới tắt máy.",
             kind="warning")

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 4: KẾT NỐI FACEBOOK
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "4. 🔐  KẾT NỐI TÀI KHOẢN FACEBOOK")
    body(doc,
         "Bước này giúp ứng dụng biết bạn là ai trên Facebook để đăng bài thay bạn. "
         "Bạn chỉ cần làm một lần, hoặc làm lại khi bị đăng xuất Facebook.")

    doc.add_paragraph()
    step_box(doc, "1", "Nhấn nút 'Kết nối Facebook'",
             ["Trên giao diện ứng dụng, nhìn góc trên bên phải.",
              "Tìm nút màu xanh dương 'Kết nối Facebook' và nhấn vào đó."])

    image_placeholder(doc, "Hình 7 – Vị trí nút 'Kết nối Facebook' trên giao diện")

    step_box(doc, "2", "Đăng nhập Facebook trong cửa sổ trình duyệt mở ra",
             ["Một cửa sổ Chrome riêng sẽ tự động mở và trỏ vào trang Facebook.",
              "Nhập email / số điện thoại và mật khẩu Facebook của bạn như thường lệ.",
              "Xác nhận OTP nếu Facebook yêu cầu."])

    image_placeholder(doc, "Hình 8 – Trang đăng nhập Facebook mở ra trong cửa sổ mới")

    step_box(doc, "3", "Đóng cửa sổ trình duyệt sau khi đăng nhập xong",
             ["Sau khi đã thấy trang chủ Facebook, hãy ĐÓNG cửa sổ đó lại.",
              "Ứng dụng sẽ tự ghi nhớ đăng nhập (không cần làm lại lần sau)."])

    step_box(doc, "4", "Kiểm tra kết quả",
             ["Quay lại ứng dụng, xem khu vực LOG phía dưới.",
              "Nếu thấy dòng chữ màu xanh lá '✅ Đã lưu session Facebook. Sẵn sàng đăng bài!' → thành công!"])

    image_placeholder(doc, "Hình 9 – Thông báo kết nối thành công xuất hiện trong LOG")

    note_box(doc,
             "Bạn chỉ cần kết nối lại Facebook nếu: đổi mật khẩu Facebook, "
             "Facebook tự đăng xuất, hoặc chuyển sang dùng tài khoản khác.",
             kind="info")

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 5: QUẢN LÝ GROUP
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "5. 👥  QUẢN LÝ DANH SÁCH GROUP FACEBOOK")
    body(doc,
         "Trước khi đăng bài, bạn cần thêm các group Facebook vào danh sách. "
         "Ứng dụng sẽ đăng bài lên tất cả các group bạn đã thêm (hoặc chỉ những group bạn chọn).")

    doc.add_paragraph()
    heading2(doc, "5.1  Thêm group mới")

    step_box(doc, "1", "Vào tab 'Groups'",
             ["Nhìn thanh menu bên trái của ứng dụng.",
              "Nhấn vào mục 'Groups' (biểu tượng 👥)."])

    image_placeholder(doc, "Hình 10 – Tab Groups trong menu bên trái")

    step_box(doc, "2", "Lấy link của group Facebook",
             ["Mở Facebook bằng trình duyệt thông thường.",
              "Vào trang của group muốn thêm.",
              "Copy toàn bộ đường dẫn trên thanh địa chỉ (ví dụ: https://www.facebook.com/groups/123456789)"])

    image_placeholder(doc, "Hình 11 – Cách lấy link group từ thanh địa chỉ trình duyệt")

    step_box(doc, "3", "Điền thông tin group vào ứng dụng",
             ["Trong tab Groups của ứng dụng, tìm form 'Thêm group mới'.",
              "Điền: Tên group (để bạn dễ nhận ra), Link group (vừa copy), Danh mục (VD: IT, Kế toán…).",
              "Nhấn nút 'Thêm Group'."])

    image_placeholder(doc, "Hình 12 – Form thêm group mới trong ứng dụng")

    doc.add_paragraph()
    heading2(doc, "5.2  Xóa group khỏi danh sách")

    body(doc,
         "Trong tab Groups, tìm group cần xóa trong danh sách. "
         "Nhấn biểu tượng 🗑️ (thùng rác) bên cạnh tên group đó → group sẽ bị xóa khỏi danh sách.")

    image_placeholder(doc, "Hình 13 – Nút xóa group (biểu tượng thùng rác)")

    note_box(doc,
             "Xóa group chỉ xóa khỏi danh sách trong ứng dụng, "
             "không ảnh hưởng gì đến group thật trên Facebook.",
             kind="info")

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 6: SOẠN & ĐĂNG BÀI NGAY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "6. ✍️  SOẠN VÀ ĐĂNG BÀI NGAY LẬP TỨC")
    body(doc, "Đây là chức năng chính bạn sẽ dùng thường xuyên nhất.")

    doc.add_paragraph()

    step_box(doc, "1", "Vào tab 'Compose' (Soạn bài)",
             ["Nhấn vào mục 'Compose' trong menu trái."])

    step_box(doc, "2", "Chọn các group muốn đăng",
             ["Phía bên phải màn hình, bạn thấy danh sách group.",
              "Nhấn vào tên group để chọn (ô sẽ chuyển màu tím khi được chọn).",
              "Muốn chọn tất cả → nhấn nút 'Chọn tất cả'.",
              "Số group đã chọn hiển thị ở phía trên danh sách."])

    image_placeholder(doc, "Hình 14 – Chọn group để đăng bài (ô màu tím = đã chọn)")

    step_box(doc, "3", "Soạn nội dung bài viết",
             ["Nhấn vào ô soạn thảo lớn ở giữa màn hình.",
              "Gõ nội dung bài tuyển dụng vào đó.",
              "Có thể dùng sẵn mẫu: nhấn nút 'Mẫu bài viết' để chọn template có sẵn (xem Phần 8)."])

    image_placeholder(doc, "Hình 15 – Ô soạn thảo nội dung bài viết")

    step_box(doc, "4", "Cài thời gian chờ giữa các group (tuỳ chọn)",
             ["Kéo thanh trượt 'Thời gian chờ tối thiểu' và 'Tối đa'.",
              "Mặc định: chờ 3–10 phút giữa mỗi lần đăng (khuyến nghị giữ nguyên để tránh bị Facebook hạn chế)."])

    image_placeholder(doc, "Hình 16 – Thanh điều chỉnh thời gian chờ giữa các lần đăng")

    step_box(doc, "5", "Nhấn nút 'Đăng Ngay'",
             ["Kiểm tra lại nội dung và danh sách group.",
              "Nhấn nút lớn màu tím '🚀 Đăng Ngay'.",
              "Ứng dụng sẽ tự mở trình duyệt và đăng bài lên từng group.",
              "Theo dõi tiến trình ở khu vực LOG phía dưới màn hình."])

    image_placeholder(doc, "Hình 17 – Nút Đăng Ngay và khu vực LOG hiển thị tiến trình")

    note_box(doc,
             "Trong khi đang đăng, KHÔNG tắt máy hoặc đóng ứng dụng. "
             "Quá trình đăng lên nhiều group có thể mất từ vài phút đến vài giờ tùy số lượng group.",
             kind="warning")

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 7: LÊN LỊCH ĐĂNG BÀI
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "7. 🕐  LÊN LỊCH ĐĂNG BÀI TỰ ĐỘNG")
    body(doc,
         "Tính năng này giúp bạn đặt lịch để ứng dụng tự đăng vào giờ cụ thể, "
         "ví dụ: cài đặt vào buổi chiều để tự động đăng lúc 7 giờ sáng hôm sau.")

    doc.add_paragraph()

    step_box(doc, "1", "Soạn bài và chọn group (như Phần 6, bước 1–4)",
             ["Thực hiện các bước 1–4 ở phần 6 như bình thường."])

    step_box(doc, "2", "Chọn thời gian đăng",
             ["Thay vì nhấn 'Đăng Ngay', tìm ô 'Thời gian đăng'.",
              "Nhấn vào ô đó → bộ chọn ngày giờ xuất hiện.",
              "Chọn ngày và giờ muốn đăng (ví dụ: 25/08/2026  07:00)."])

    image_placeholder(doc, "Hình 18 – Ô chọn thời gian lên lịch đăng bài")

    step_box(doc, "3", "Nhấn 'Lên lịch'",
             ["Nhấn nút 'Lên Lịch' để xác nhận.",
              "Ứng dụng sẽ tự nhớ và đăng đúng giờ bạn đã chọn.",
              "Bạn có thể xem danh sách lịch đã đặt trong tab 'Schedule'."])

    image_placeholder(doc, "Hình 19 – Xác nhận lịch đăng bài thành công")

    step_box(doc, "4", "Hủy lịch đăng (nếu cần)",
             ["Vào tab 'Schedule' trong menu trái.",
              "Tìm lịch muốn hủy → nhấn nút 🗑️ (xóa) cạnh lịch đó."])

    image_placeholder(doc, "Hình 20 – Tab Schedule hiển thị danh sách lịch đã đặt")

    note_box(doc,
             "Máy tính và ứng dụng phải đang BẬT và đang chạy vào thời điểm lịch kích hoạt. "
             "Nếu máy tắt, lịch đó sẽ bị bỏ qua.",
             kind="warning")

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 8: MẪU BÀI VIẾT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "8. 📄  SỬ DỤNG MẪU BÀI VIẾT (TEMPLATE)")
    body(doc,
         "Thay vì gõ lại từ đầu mỗi lần, bạn có thể lưu sẵn các mẫu bài tuyển dụng "
         "để dùng lại chỉ với một cú nhấp.")

    doc.add_paragraph()
    heading2(doc, "8.1  Xem và áp dụng mẫu có sẵn")

    step_box(doc, "1", "Vào tab 'Templates'",
             ["Nhấn vào mục 'Templates' (biểu tượng 📄) trong menu trái."])

    step_box(doc, "2", "Chọn mẫu và nhấn 'Dùng mẫu này'",
             ["Bạn thấy danh sách các mẫu bài viết đã lưu.",
              "Nhấn vào mẫu muốn dùng để xem trước nội dung.",
              "Nhấn nút 'Dùng mẫu này' → nội dung sẽ tự điền vào ô soạn thảo."])

    image_placeholder(doc, "Hình 21 – Tab Templates hiển thị các mẫu bài viết có sẵn")

    doc.add_paragraph()
    heading2(doc, "8.2  Lưu mẫu bài viết mới")

    step_box(doc, "1", "Soạn bài trong tab Compose",
             ["Gõ nội dung bài viết vào ô soạn thảo như bình thường."])

    step_box(doc, "2", "Lưu làm mẫu",
             ["Nhấn nút '💾 Lưu làm Template'.",
              "Đặt tên cho mẫu (ví dụ: 'Mẫu tuyển IT tháng 8') → nhấn OK.",
              "Mẫu sẽ xuất hiện trong tab Templates để dùng lại lần sau."])

    image_placeholder(doc, "Hình 22 – Hộp thoại đặt tên và lưu mẫu bài viết")

    note_box(doc,
             "Mẫu bài viết chứa các ký hiệu như [Tên vị trí], [Mức lương]… "
             "Hãy thay thế các ký hiệu đó bằng thông tin thực trước khi đăng.",
             kind="tip")

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 9: TÌM KIẾM ỨNG VIÊN (CRAWL BÀI VIẾT TÌM VIỆC)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "9. 🔍  TÌM KIẾM ỨNG VIÊN (CRAWL BÀI VIẾT TÌM VIỆC)")
    body(doc,
         "Ngoài tính năng đăng bài tự động, ứng dụng còn hỗ trợ HR quét (crawl) "
         "các bài đăng tìm việc của ứng viên từ các Group Facebook, tự động lọc rác, "
         "phân loại theo từ khoá vị trí tuyển dụng của HR và xuất báo cáo Excel đa-sheet chuyên nghiệp.")

    doc.add_paragraph()
    heading2(doc, "9.1  Các bước tìm kiếm bài viết ứng viên")

    step_box(doc, "1", "Vào tab '🔍 Crawl Posts'",
             ["Nhấn vào mục 'Crawl Posts' (biểu tượng 🔍) trên thanh menu trái.",
              "Màn hình cấu hình tìm kiếm ứng viên sẽ xuất hiện."])

    step_box(doc, "2", "Chọn danh sách Group để quét",
             ["Các Group được tự động phân nhóm theo thư mục (giống tab Soạn & Đăng).",
              "Bạn có thể nhấn nút '☑ Tất cả' ở từng thư mục nhóm để chọn nhanh cả nhóm, "
              "hoặc tích chọn từng Group riêng lẻ."])

    image_placeholder(doc, "Hình 23 – Giao diện chọn Group theo phân nhóm trong tab Crawl Posts")

    step_box(doc, "3", "Nhập từ khoá vị trí tuyển dụng (HR Words)",
             ["Trong ô 'Từ khoá tuyển dụng (HR Words)', gõ tên vị trí cần tuyển.",
              "Ví dụ: Kế toán, Sales, Gia sư, Telesale... rồi nhấn Enter.",
              "Hệ thống sẽ thực hiện chiến lược quét kép:",
              "  • Tìm chính: Tìm trực tiếp theo các vị trí/kỹ năng do HR nhập vào.",
              "  • Vét cạn: Tự động chạy từ khoá mặc định ('em', 'tôi', 'mình') để không bỏ sót ứng viên."])

    image_placeholder(doc, "Hình 24 – Nhập từ khoá vị trí tuyển dụng HR Words")

    step_box(doc, "4", "Nhấn nút '🔍 Bắt đầu Crawl'",
             ["Nhấn nút màu xanh '🔍 Bắt đầu Crawl'.",
              "Trình duyệt Playwright Chromium sẽ tự động mở, truy cập từng Group và cuộn trang tìm bài.",
              "Quá trình quét tự động dừng khi quét xong hoặc gặp thông báo 'End of results'."])

    note_box(doc,
             "Bộ lọc thông minh được tích hợp sẵn: Tự động loại bỏ bài đăng dài (tin tuyển dụng của người khác), "
             "bắt buộc bài viết chứa đại từ xưng hô ngôi thứ nhất (em, mình, tôi...), "
             "và tự động lọc trùng 3 cấp độ (Fuzzy match 85%).",
             kind="tip")

    doc.add_paragraph()
    heading2(doc, "9.2  Xem kết quả & Phân loại Sub-tabs")
    body(doc,
         "Sau khi hoàn thành crawl, kết quả sẽ tự động nhảy ra màn hình bảng dữ liệu mà không cần F5:")

    bullet(doc, "🌐 Thẻ 'Tất cả': Hiển thị danh sách tổng hợp toàn bộ bài viết tìm việc sau khi đã lọc trùng.")
    bullet(doc, "🔑 Các thẻ 'Từ khoá HR': Phân loại các bài viết khớp với từng vị trí HR đã nhập (hỗ trợ khớp linh hoạt không phân biệt dấu tiếng Việt hay chữ hoa/thường, ví dụ: 'ke toan' khớp cả 'Kế toán').")
    bullet(doc, "📦 Thẻ 'Dư thừa / Còn lại': Danh sách các ứng viên quét vét cạn còn lại chưa thuộc nhóm từ khoá HR nào.")

    image_placeholder(doc, "Hình 25 – Bảng kết quả với các thẻ Sub-tabs phân loại theo vị trí tuyển dụng")

    doc.add_paragraph()
    heading2(doc, "9.3  Xuất báo cáo Excel đa-sheet (Multi-Sheet Export)")

    step_box(doc, "1", "Nhấn nút '📥 Export Excel'",
             ["Nhấn nút '📥 Export Excel' ở phía trên góc phải bảng kết quả.",
              "File Excel (.xlsx) sẽ tự động tải về máy tính của bạn."])

    step_box(doc, "2", "Cấu trúc File Excel đa-sheet chuyên nghiệp",
             ["Sheet 1 ('Tất cả bài viết'): Chứa danh sách tổng hợp toàn bộ ứng viên.",
              "Sheet 2, 3... ('KW - [Tên vị trí]'): Mỗi vị trí HR nhập được tách thành 1 Sheet riêng.",
              "Sheet cuối ('Dư thừa (Còn lại)'): Chứa danh sách các ứng viên vét cạn còn lại.",
              "Cột SĐT: Tự động trích xuất và chuẩn hoá thành dạng chuỗi 10 số (0984xxxxxx).",
              "Cột Link bài: Là Hyperlink có thể nhấp chuột trực tiếp (🔗 Link) để mở ngay bài đăng trên Facebook."])

    image_placeholder(doc, "Hình 26 – Báo cáo Excel xuất ra với nhiều Sheet phân loại và Link click trực tiếp")

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 10: LOG & DỪNG KHẨN CẤP
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "10. 📊  THEO DÕI NHẬT KÝ & DỪNG KHẨN CẤP")

    heading2(doc, "10.1  Đọc khu vực LOG (Nhật ký hoạt động)")
    body(doc,
         "Khu vực LOG nằm phía dưới cùng của màn hình. "
         "Mỗi hành động của ứng dụng đều được ghi lại tại đây.")

    doc.add_paragraph()
    # Bảng màu sắc LOG
    heading3(doc, "Ý nghĩa của các màu sắc trong LOG:")
    tbl = doc.add_table(rows=5, cols=2)
    tbl.style = "Table Grid"
    tbl.columns[0].width = Cm(5)
    tbl.columns[1].width = Cm(10.4)
    rows_data = [
        ("Màu xanh lá ✅", "Thành công – bài đã được đăng lên group"),
        ("Màu đỏ ❌", "Thất bại – không đăng được, kiểm tra lại"),
        ("Màu vàng ⚠️", "Cảnh báo – cần chú ý nhưng chưa nghiêm trọng"),
        ("Màu xám (bình thường)", "Thông tin – ứng dụng đang hoạt động bình thường"),
        ("Dòng '⏳ Nghỉ X phút…'", "Đang chờ giữa các lần đăng để tránh bị Facebook hạn chế"),
    ]
    for i, (col1, col2) in enumerate(rows_data):
        tbl.cell(i, 0).paragraphs[0].add_run(col1).font.size = Pt(10)
        tbl.cell(i, 1).paragraphs[0].add_run(col2).font.size = Pt(10)

    doc.add_paragraph()
    image_placeholder(doc, "Hình 27 – Khu vực LOG với các màu sắc thể hiện trạng thái")

    doc.add_paragraph()
    heading2(doc, "10.2  Dừng quá trình đăng bài khẩn cấp")

    body(doc, "Nếu cần dừng ngay lập tức (ví dụ: phát hiện nội dung bị sai):")
    step_box(doc, "1", "Nhấn nút '⏹️ Dừng'",
             ["Tìm nút màu đỏ '⏹️ Dừng' trên giao diện.",
              "Nhấn một lần – ứng dụng sẽ hoàn thành group hiện tại rồi dừng hẳn.",
              "Không nhấn nhiều lần vì ứng dụng đang cần hoàn thành thao tác dở."])

    image_placeholder(doc, "Hình 28 – Nút Dừng khẩn cấp (màu đỏ)")

    note_box(doc,
             "Sau khi nhấn Dừng, ứng dụng cần hoàn thành lần đăng hiện tại rồi mới dừng "
             "(thường mất 10–30 giây). Đây là hoạt động bình thường.",
             kind="info")

    doc.add_page_break()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHẦN 11: LỖI THƯỜNG GẶP
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    heading1(doc, "11. 🛠️  CÁC LỖI THƯỜNG GẶP & CÁCH XỬ LÝ")

    # Bảng lỗi
    errors = [
        ("Lỗi / Triệu chứng", "Nguyên nhân có thể", "Cách xử lý"),
        ("Nhấp đúp start.bat không mở được ứng dụng",
         "Chưa cài đặt (chưa chạy install.bat)",
         "Chạy install.bat trước, sau đó thử lại"),
        ("Thấy dòng '⚠️ Chưa đăng nhập Facebook!'",
         "Session Facebook hết hạn hoặc chưa kết nối",
         "Thực hiện lại Phần 4: Kết nối Facebook"),
        ("Đăng bài liên tục bị ❌ Thất bại",
         "Facebook tạm thời hạn chế tài khoản, hoặc group đã đổi cài đặt bài đăng",
         "Nghỉ 1–2 tiếng rồi thử lại. Nếu vẫn lỗi, báo IT kiểm tra"),
        ("Ứng dụng báo 'Đang có lần đăng đang chạy'",
         "Đang có quá trình đăng bài chưa kết thúc",
         "Chờ xong hoặc nhấn nút Dừng rồi thử lại"),
        ("Trình duyệt không tự mở sau khi chạy start.bat",
         "Ứng dụng khởi động chậm",
         "Chờ thêm 10–15 giây, hoặc tự gõ http://localhost:5000 vào trình duyệt"),
        ("Lỗi màu đỏ trong cửa sổ cài đặt",
         "Mất mạng hoặc thiếu quyền ghi file",
         "Kiểm tra kết nối mạng, chạy lại install.bat với quyền Administrator"),
    ]

    tbl_err = doc.add_table(rows=len(errors), cols=3)
    tbl_err.style = "Table Grid"
    tbl_err.columns[0].width = Cm(5.0)
    tbl_err.columns[1].width = Cm(4.5)
    tbl_err.columns[2].width = Cm(5.9)

    for i, (c1, c2, c3) in enumerate(errors):
        for j, text in enumerate([c1, c2, c3]):
            cell = tbl_err.cell(i, j)
            p = cell.paragraphs[0]
            run = p.add_run(text)
            run.font.size = Pt(9.5)
            run.font.name = "Arial"
            if i == 0:
                run.bold = True
                run.font.color.rgb = COLOR_WHITE
                set_cell_bg(cell, COLOR_PRIMARY)

    doc.add_paragraph()
    note_box(doc,
             "Nếu gặp lỗi không có trong danh sách trên, hãy chụp màn hình khu vực LOG "
             "và gửi cho bộ phận IT. Đừng tự ý xóa hoặc sửa file trong thư mục ứng dụng.",
             kind="danger")

    doc.add_paragraph()
    divider(doc)

    # ── Trang kết / liên hệ ──────────────────────────────────────────────────
    doc.add_paragraph()
    contact = doc.add_paragraph()
    contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(contact, "📞  Liên hệ hỗ trợ kỹ thuật: Bộ phận IT  •  [Email / Số điện thoại nội bộ]",
            italic=True, color=COLOR_GRAY, size_pt=10)

    doc.add_paragraph()
    footer_p = doc.add_paragraph()
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(footer_p, "© 2026 — Tài liệu nội bộ, không phát hành ra ngoài.",
            italic=True, color=COLOR_GRAY, size_pt=9)

    return doc


# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "HUONG_DAN_SU_DUNG.docx")
    doc = build_doc()
    doc.save(out_path)
    print(f"\n✅  Đã tạo tài liệu: {out_path}")
    print("   Mở file bằng Microsoft Word hoặc LibreOffice để xem.")
