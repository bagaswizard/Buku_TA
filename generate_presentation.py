#!/usr/bin/env python3
"""Generate PowerPoint presentation for Sidang Tugas Akhir."""

import os
import copy

from pptx import Presentation
from pptx.util import Inches, Pt, Emu, Cm
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# =============================================================================
# DESIGN SYSTEM CONSTANTS
# =============================================================================
PRIMARY = RGBColor(0x00, 0x3A, 0x70)       # #003A70 - Biru ITS
SECONDARY = RGBColor(0x4A, 0x90, 0xD9)     # #4A90D9 - Biru muda
HEADING = RGBColor(0x1A, 0x2B, 0x4C)       # #1A2B4C - Judul
BODY = RGBColor(0x33, 0x33, 0x33)          # #333333 - Teks body
ORANGE = RGBColor(0xF0, 0x8C, 0x2E)        # #F08C2E - Aksen
BOX_FILL = RGBColor(0xE8, 0xF0, 0xFE)     # #E8F0FE - Box
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_BG = RGBColor(0xF5, 0xF9, 0xFF)     # Kartu pertanyaan
WARN_BG = RGBColor(0xFF, 0xF8, 0xF0)      # Panel batasan
DARK_BG = RGBColor(0x00, 0x2B, 0x54)      # Slide 1 gradient fallback
SUBTLE_TEXT = RGBColor(0x55, 0x55, 0x55)  # Captions
BORDER_GRAY = RGBColor(0xE0, 0xE0, 0xE0)

FONT_TITLE = "Montserrat"
FONT_BODY = "Lato"
FONT_CODE = "Fira Code"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

MARGIN = Inches(0.93)  # ~7% margin

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def set_slide_bg(slide, color):
    """Set solid color background for a slide."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, left, top, width, height, fill_color=None, border_color=None, border_width=None, corner_radius=None):
    """Add a rectangle shape."""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if corner_radius else MSO_SHAPE.RECTANGLE,
        left, top, width, height
    )
    shape.line.fill.background()
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.fill.solid()
        if border_width:
            shape.line.width = border_width
    return shape


def add_text_box(slide, left, top, width, height, text, font_name=FONT_BODY,
                 font_size=Pt(16), color=BODY, bold=False, alignment=PP_ALIGN.LEFT,
                 line_spacing=1.2, anchor=MSO_ANCHOR.TOP, italic=False):
    """Add a text box with single paragraph."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    txBox.text_frame.word_wrap = True
    txBox.text_frame.auto_size = None
    p = txBox.text_frame.paragraphs[0]
    p.text = text
    p.font.name = font_name
    p.font.size = font_size
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.italic = italic
    p.alignment = alignment
    p.space_after = Pt(0)
    p.space_before = Pt(0)
    p.line_spacing = Pt(font_size.pt * line_spacing)
    return txBox


def add_rich_text_box(slide, left, top, width, height, paragraphs_data,
                      anchor=MSO_ANCHOR.TOP):
    """Add a text box with multiple paragraphs. paragraphs_data is a list of dicts:
    {text, font_name, font_size, color, bold, alignment, line_spacing, space_after, italic}
    """
    txBox = slide.shapes.add_textbox(left, top, width, height)
    txBox.text_frame.word_wrap = True
    txBox.text_frame.auto_size = None

    for i, pdata in enumerate(paragraphs_data):
        if i == 0:
            p = txBox.text_frame.paragraphs[0]
        else:
            p = txBox.text_frame.add_paragraph()

        p.text = pdata.get("text", "")
        p.font.name = pdata.get("font_name", FONT_BODY)
        p.font.size = pdata.get("font_size", Pt(16))
        p.font.color.rgb = pdata.get("color", BODY)
        p.font.bold = pdata.get("bold", False)
        p.font.italic = pdata.get("italic", False)
        p.alignment = pdata.get("alignment", PP_ALIGN.LEFT)
        ls = pdata.get("line_spacing", 1.3)
        if isinstance(ls, (int, float)):
            p.line_spacing = Pt(pdata["font_size"].pt * ls)
        else:
            p.line_spacing = ls
        p.space_after = pdata.get("space_after", Pt(4))

    return txBox


def add_slide_number(slide, num):
    """Add slide number at bottom right."""
    add_text_box(slide, SLIDE_W - MARGIN - Inches(0.5), SLIDE_H - Inches(0.45),
                 Inches(0.5), Inches(0.3), str(num),
                 font_size=Pt(10), color=SUBTLE_TEXT,
                 alignment=PP_ALIGN.RIGHT)


def add_footer(slide):
    """Add footer text."""
    add_text_box(slide, MARGIN, SLIDE_H - Inches(0.45),
                 Inches(5), Inches(0.3),
                 "Sidang Tugas Akhir  ·  Bagas Surya Wirawan  ·  5022221026",
                 font_size=Pt(9), color=SUBTLE_TEXT, italic=True)


def add_divider(slide, left, top, width, color=ORANGE, height=Pt(2)):
    """Add a horizontal divider line."""
    shape = add_rect(slide, left, top, width, height, fill_color=color)


def add_card(slide, left, top, width, height, number, title, description,
             card_bg=BOX_FILL, accent=SECONDARY):
    """Add a card with number circle, title, and description."""
    card = add_rect(slide, left, top, width, height, fill_color=card_bg, corner_radius=Cm(0.2))
    # Number circle
    circle = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, left + Inches(0.2), top + Inches(0.2),
        Inches(0.5), Inches(0.5)
    )
    circle.fill.solid()
    circle.fill.fore_color.rgb = accent
    circle.line.fill.background()
    tf = circle.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.text = str(number)
    p.font.name = FONT_TITLE
    p.font.size = Pt(16)
    p.font.color.rgb = WHITE
    p.font.bold = True
    p.alignment = PP_ALIGN.CENTER

    # Title
    add_text_box(slide, left + Inches(0.85), top + Inches(0.15),
                 width - Inches(1.1), Inches(0.4),
                 title, font_name=FONT_TITLE, font_size=Pt(14),
                 color=HEADING, bold=True)

    # Description
    add_text_box(slide, left + Inches(0.25), top + Inches(0.7),
                 width - Inches(0.5), height - Inches(0.85),
                 description, font_size=Pt(12), color=BODY,
                 line_spacing=1.35)


def add_icon_bullet(slide, left, top, width, height, icon_char, title, body_text,
                    accent=SECONDARY):
    """Add an icon-style bullet point."""
    # Icon circle
    circle = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, left, top, Inches(0.45), Inches(0.45)
    )
    circle.fill.solid()
    circle.fill.fore_color.rgb = accent
    circle.line.fill.background()
    tf = circle.text_frame
    p = tf.paragraphs[0]
    p.text = icon_char
    p.font.size = Pt(14)
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER

    add_text_box(slide, left + Inches(0.6), top - Inches(0.02),
                 width - Inches(0.6), Inches(0.25),
                 title, font_name=FONT_TITLE, font_size=Pt(14),
                 color=HEADING, bold=True)

    add_text_box(slide, left + Inches(0.6), top + Inches(0.25),
                 width - Inches(0.6), height - Inches(0.25),
                 body_text, font_size=Pt(12), color=BODY,
                 line_spacing=1.3)


# =============================================================================
# SLIDE FUNCTIONS
# =============================================================================

def slide_title(prs):
    """Slide 1: Title slide — overhang logo bar with clean layered layout."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, DARK_BG)

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # =========================================================================
    # Background: two large circles for depth
    # =========================================================================
    bg_circle = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, Inches(-2.5), Inches(-3.0), Inches(9.0), Inches(9.0)
    )
    bg_circle.fill.solid()
    bg_circle.fill.fore_color.rgb = RGBColor(0x0A, 0x3C, 0x62)
    bg_circle.line.fill.background()

    bg_circle2 = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, SLIDE_W - Inches(3.5), SLIDE_H - Inches(4.5),
        Inches(6.0), Inches(6.0)
    )
    bg_circle2.fill.solid()
    bg_circle2.fill.fore_color.rgb = RGBColor(0x0A, 0x3C, 0x62)
    bg_circle2.line.fill.background()

    # =========================================================================
    # Logo bar — shifted partially off-screen so only bottom-left rounding shows
    # =========================================================================
    LOGO_BAR_W = Inches(2.65)
    LOGO_BAR_H = Inches(0.68)
    LOGO_RADIUS = Cm(0.22)

    OVERHANG = Inches(0.18)
    logo_bar_x = SLIDE_W - LOGO_BAR_W + OVERHANG
    logo_bar_y = Inches(0.0) - OVERHANG

    # Drop shadow — offset behind, matching overhang
    SHADOW_OFFSET = Pt(4)
    shadow = add_rect(slide,
                      logo_bar_x - SHADOW_OFFSET,
                      logo_bar_y + SHADOW_OFFSET,
                      LOGO_BAR_W + SHADOW_OFFSET,
                      LOGO_BAR_H + Pt(2),
                      fill_color=RGBColor(0x00, 0x1A, 0x3A),
                      corner_radius=LOGO_RADIUS)
    shadow.line.fill.background()

    # White foreground bar
    logo_bg = add_rect(slide, logo_bar_x, logo_bar_y, LOGO_BAR_W, LOGO_BAR_H,
                       fill_color=WHITE, corner_radius=LOGO_RADIUS)
    logo_bg.line.fill.background()

    # =========================================================================
    # Logos — three images, uniform reduced height, inside the white bar
    # =========================================================================
    LOGO_H = Inches(0.48)
    LOGO_GAP = Inches(0.12)
    LOGO_PAD_LEFT = Inches(0.12)
    LOGO_CENTER_Y = Inches(0.25)

    its_path = os.path.join(base_dir, "gambar", "Institut Teknologi Sepuluh Nopember - Blue.png")
    its_w = LOGO_H * (1400.0 / 902.0)
    its_x = logo_bar_x + LOGO_PAD_LEFT
    slide.shapes.add_picture(its_path, its_x, LOGO_CENTER_Y, its_w, LOGO_H)

    elektro_path = os.path.join(base_dir, "gambar", "Elektro-trans.png")
    el_w = LOGO_H * (503.0 / 496.0)
    el_x = its_x + its_w + LOGO_GAP
    slide.shapes.add_picture(elektro_path, el_x, LOGO_CENTER_Y, el_w, LOGO_H)

    elka_path = os.path.join(base_dir, "gambar", "ELKA b202.png")
    elka_w = LOGO_H * (701.0 / 588.0)
    elka_x = el_x + el_w + LOGO_GAP
    slide.shapes.add_picture(elka_path, elka_x, LOGO_CENTER_Y, elka_w, LOGO_H)

    # =========================================================================
    # Decorative accent — orange vertical bar aligned with title
    # =========================================================================
    add_rect(slide, Inches(0.55), Inches(1.25), Pt(5), Inches(2.1), fill_color=ORANGE)

    # =========================================================================
    # Title block — positioned below logo bar with clear gap
    # =========================================================================
    TITLE_SIZE = Pt(30)
    title_x = Inches(1.05)
    title_y = Inches(1.25)

    add_rich_text_box(slide, title_x, title_y, Inches(9.0), Inches(2.5), [
        {"text": "NAVIGASI ROBOT BERBASIS", "font_name": FONT_TITLE, "font_size": TITLE_SIZE,
         "color": WHITE, "bold": True, "line_spacing": 1.22},
        {"text": "LAYERED COSTMAP", "font_name": FONT_TITLE, "font_size": TITLE_SIZE,
         "color": WHITE, "bold": True, "line_spacing": 1.22},
        {"text": "UNTUK PERGERAKAN ANTAR LANTAI", "font_name": FONT_TITLE, "font_size": TITLE_SIZE,
         "color": RGBColor(0xC8, 0xDC, 0xEE), "bold": True, "line_spacing": 1.22},
        {"text": "PADA LINGKUNGAN INDOOR PASCA GEMPA BUMI", "font_name": FONT_TITLE, "font_size": TITLE_SIZE,
         "color": RGBColor(0xA0, 0xBE, 0xDA), "bold": True, "line_spacing": 1.3, "space_after": Pt(28)},
    ])

    # =========================================================================
    # Divider — inside title block area, below text
    # =========================================================================
    add_rect(slide, title_x, Inches(3.50), Inches(3.6), Pt(2.5), fill_color=ORANGE)

    # =========================================================================
    # Author info — positioned below divider with clean gap
    # =========================================================================
    add_rich_text_box(slide, title_x, Inches(3.95), Inches(7.0), Inches(2.0), [
        {"text": "Bagas Surya Wirawan", "font_name": FONT_TITLE, "font_size": Pt(22),
         "color": WHITE, "bold": True, "line_spacing": 1.15},
        {"text": "NRP. 5022221026", "font_name": FONT_BODY, "font_size": Pt(16),
         "color": RGBColor(0xBB, 0xD5, 0xEC), "line_spacing": 1.0},
        {"text": "", "font_name": FONT_BODY, "font_size": Pt(8), "color": WHITE, "line_spacing": 1.0},
        {"text": "Dosen Pembimbing:", "font_name": FONT_BODY, "font_size": Pt(14),
         "color": RGBColor(0xCC, 0xCC, 0xCC), "bold": True, "line_spacing": 1.05},
        {"text": "Dr. Ir. Djoko Purwanto, M.Eng.", "font_name": FONT_BODY, "font_size": Pt(14),
         "color": RGBColor(0xBB, 0xD5, 0xEC), "line_spacing": 0.95},
        {"text": "Fajar Budiman, S.T., M.Sc.", "font_name": FONT_BODY, "font_size": Pt(14),
         "color": RGBColor(0xBB, 0xD5, 0xEC), "line_spacing": 0.95},
        {"text": "", "font_name": FONT_BODY, "font_size": Pt(8), "color": WHITE, "line_spacing": 1.0},
        {"text": "Departemen Teknik Elektro", "font_name": FONT_BODY, "font_size": Pt(12),
         "color": RGBColor(0x9B, 0xBB, 0xDB), "line_spacing": 0.95},
        {"text": "Fakultas Teknologi Elektro dan Informatika Cerdas", "font_name": FONT_BODY, "font_size": Pt(12),
         "color": RGBColor(0x9B, 0xBB, 0xDB), "line_spacing": 0.95},
        {"text": "Institut Teknologi Sepuluh Nopember  ·  Surabaya  ·  2026", "font_name": FONT_BODY, "font_size": Pt(12),
         "color": RGBColor(0x85, 0xA8, 0xCA), "line_spacing": 0.95},
    ])

    # =========================================================================
    # Bottom accent
    # =========================================================================
    add_rect(slide, Inches(0.55), SLIDE_H - Inches(0.35), Inches(2.5), Pt(1.5),
             fill_color=RGBColor(0x14, 0x4D, 0x77))


def slide_outline(prs):
    """Slide 2: Outline / Daftar Isi."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.4), Inches(4), Inches(0.6),
                 "DAFTAR ISI", font_name=FONT_TITLE, font_size=Pt(30),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.95), Inches(1.8))

    items = [
        ("01", "Latar Belakang", "Konteks gempa bumi di Indonesia dan urgensi robot SAR otonom"),
        ("02", "Rumusan Masalah & Tujuan", "Pertanyaan penelitian, batasan, dan tujuan yang ingin dicapai"),
        ("03", "Metodologi & Desain Sistem", "Arsitektur navigasi: costmap, ICP, A*, dan DWA planner"),
        ("04", "Hasil Pengujian", "Evaluasi ICP, costmap, dan navigasi penuh pada arena simulasi"),
        ("05", "Kesimpulan & Saran", "Temuan utama dan arah pengembangan selanjutnya"),
    ]

    card_w = Inches(3.8)
    card_h = Inches(0.95)
    start_x = MARGIN
    start_y = Inches(1.35)
    gap_x = Inches(0.25)
    gap_y = Inches(0.18)

    positions = [
        (start_x, start_y),
        (start_x, start_y + card_h + gap_y),
        (start_x + card_w + gap_x, start_y),
        (start_x + card_w + gap_x, start_y + card_h + gap_y),
        (start_x + 2 * (card_w + gap_x), start_y),
    ]

    for (x, y), (num, title, desc) in zip(positions, items):
        card = add_rect(slide, x, y, card_w, card_h, fill_color=BOX_FILL, corner_radius=Cm(0.2))
        # Big number
        add_text_box(slide, x + Inches(0.2), y + Inches(0.1),
                     Inches(0.7), Inches(0.6),
                     num, font_name=FONT_TITLE, font_size=Pt(28),
                     color=SECONDARY, bold=True)
        add_text_box(slide, x + Inches(0.85), y + Inches(0.1),
                     card_w - Inches(1.1), Inches(0.35),
                     title, font_name=FONT_TITLE, font_size=Pt(15),
                     color=HEADING, bold=True)
        add_text_box(slide, x + Inches(0.85), y + Inches(0.48),
                     card_w - Inches(1.1), Inches(0.4),
                     desc, font_size=Pt(11), color=SUBTLE_TEXT,
                     line_spacing=1.25)

    add_slide_number(slide, 2)
    add_footer(slide)


def slide_background(prs):
    """Slide 3: Latar Belakang."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(5), Inches(0.55),
                 "LATAR BELAKANG", font_name=FONT_TITLE, font_size=Pt(30),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.2))

    # Left side: bullet points
    bullet_data = [
        ("1", "INDONESIA RAWAN GEMPA BUMI",
         "Terletak di pertemuan 4 lempeng tektonik (Pasifik, Eurasia, Indo-Australia, Laut Filipina). "
         "Rata-rata 18 gempa per hari (BMKG, 2020)."),
        ("2", "OPERASI SAR BERISIKO TINGGI",
         "Petugas SAR menghadapi ancaman keselamatan di area terdampak. "
         "Bangunan rusak, atap hampir roboh, struktur tidak stabil. "
         "Robot darat pernah digunakan pasca gempa Jepang untuk inspeksi bangunan (Lin et al., 2022)."),
        ("3", "ROBOT OTONOM MEMBANTU MISI SAR",
         "Robot UAV memberi gambaran medan dari udara. Robot darat (track/quadruped/hexapod) "
         "mengangkut barang berat dan inspeksi area berbahaya. "
         "Robot otonom krusial saat infrastruktur komunikasi rusak."),
        ("4", "TANTANGAN: NAVIGASI INDOOR PASCA GEMPA",
         "Lingkungan tidak terstruktur: puing, lantai tidak rata, tangga. "
         "Costmap 2D konvensional terbatas pada satu bidang datar. "
         "Robot perlu bernavigasi ANTAR LANTAI."),
        ("5", "SOLUSI: LAYERED COSTMAP",
         "Menyederhanakan informasi 3D → beberapa bidang costmap 2D. "
         "Setiap layer mewakili satu lantai/region. Layer transisi menghubungkan antar lantai. "
         "Robot berpindah layer sesuai posisi di bangunan."),
    ]

    y = Inches(1.1)
    for num, title, desc in bullet_data:
        draw_background_bullet(slide, MARGIN, y, Inches(6.8), Inches(1.0), num, title, desc)
        y += Inches(1.08)

    # Right side: visual area with box diagrams
    right_x = Inches(7.9)
    # Box 1: Indonesia map hint
    box1 = add_rect(slide, right_x, Inches(1.1), Inches(4.8), Inches(1.5),
                    fill_color=BOX_FILL, corner_radius=Cm(0.2))
    add_text_box(slide, right_x + Inches(0.2), Inches(1.15), Inches(4.4), Inches(0.3),
                 "Kondisi Geografis Indonesia", font_name=FONT_TITLE, font_size=Pt(12),
                 color=HEADING, bold=True)
    add_rich_text_box(slide, right_x + Inches(0.2), Inches(1.45), Inches(4.4), Inches(1.0), [
        {"text": "4 Lempeng Tektonik Aktif", "font_size": Pt(12), "color": BODY, "bold": True, "line_spacing": 1.15},
        {"text": "Pasifik · Eurasia · Indo-Australia · Laut Filipina", "font_size": Pt(11), "color": SUBTLE_TEXT, "line_spacing": 1.15},
        {"text": "± 18 gempa / hari (BMKG 2020)", "font_size": Pt(11), "color": BODY, "line_spacing": 1.3},
    ])

    # Box 2: Post-earthquake scenario
    box2 = add_rect(slide, right_x, Inches(2.8), Inches(4.8), Inches(1.5),
                    fill_color=BOX_FILL, corner_radius=Cm(0.2))
    add_text_box(slide, right_x + Inches(0.2), Inches(2.85), Inches(4.4), Inches(0.3),
                 "Pasca Gempa Bumi", font_name=FONT_TITLE, font_size=Pt(12),
                 color=HEADING, bold=True)
    add_rich_text_box(slide, right_x + Inches(0.2), Inches(3.15), Inches(4.4), Inches(1.0), [
        {"text": "Dampak pada Bangunan:", "font_size": Pt(12), "color": BODY, "bold": True, "line_spacing": 1.15},
        {"text": "Puing dan reruntuhan • Lantai tidak rata", "font_size": Pt(11), "color": SUBTLE_TEXT, "line_spacing": 1.15},
        {"text": "Tangga rusak • Struktur multi-lantai tidak stabil", "font_size": Pt(11), "color": SUBTLE_TEXT, "line_spacing": 1.15},
        {"text": "Robot darat digunakan di Jepang untuk inspeksi (Lin 2022)", "font_size": Pt(11), "color": BODY, "line_spacing": 1.3},
    ])

    # Box 3: Layered costmap concept
    box3 = add_rect(slide, right_x, Inches(4.5), Inches(4.8), Inches(1.5),
                    fill_color=RGBColor(0xFD, 0xF2, 0xE3), corner_radius=Cm(0.2))
    add_text_box(slide, right_x + Inches(0.2), Inches(4.55), Inches(4.4), Inches(0.3),
                 "Solusi: Layered Costmap", font_name=FONT_TITLE, font_size=Pt(12),
                 color=ORANGE, bold=True)
    add_rich_text_box(slide, right_x + Inches(0.2), Inches(4.85), Inches(4.4), Inches(1.0), [
        {"text": "3D → 2D Multi-Layer", "font_size": Pt(12), "color": BODY, "bold": True, "line_spacing": 1.15},
        {"text": "Setiap layer = 1 lantai/region pada bangunan", "font_size": Pt(11), "color": SUBTLE_TEXT, "line_spacing": 1.15},
        {"text": "Layer transisi = penghubung antar lantai", "font_size": Pt(11), "color": SUBTLE_TEXT, "line_spacing": 1.15},
        {"text": "Robot berpindah layer sesuai posisi di bangunan", "font_size": Pt(11), "color": BODY, "line_spacing": 1.3},
    ])

    # Highlight callout box
    callout = add_rect(slide, MARGIN, Inches(6.55), Inches(11.5), Inches(0.45),
                       fill_color=RGBColor(0xFF, 0xF3, 0xE0), corner_radius=Cm(0.1))
    # Orange left border accent
    accent_bar = add_rect(slide, MARGIN, Inches(6.55), Pt(4), Inches(0.45), fill_color=ORANGE)
    add_text_box(slide, MARGIN + Inches(0.12), Inches(6.55), Inches(11.3), Inches(0.45),
                 "Pendekatan ini menyederhanakan kompleksitas 3D menjadi representasi 2D yang manageable, "
                 "memungkinkan penggunaan sensor LiDAR 2D.",
                 font_size=Pt(11), color=BODY, italic=True, line_spacing=1.2)

    add_slide_number(slide, 3)
    add_footer(slide)


def draw_background_bullet(slide, left, top, width, height, num, title, desc):
    """Draw a numbered bullet point for latar belakang."""
    # Number circle
    circle = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, left, top + Inches(0.05), Inches(0.4), Inches(0.4)
    )
    circle.fill.solid()
    circle.fill.fore_color.rgb = SECONDARY
    circle.line.fill.background()
    tf = circle.text_frame
    p = tf.paragraphs[0]
    p.text = num
    p.font.name = FONT_TITLE
    p.font.size = Pt(14)
    p.font.color.rgb = WHITE
    p.font.bold = True
    p.alignment = PP_ALIGN.CENTER

    add_text_box(slide, left + Inches(0.55), top, width - Inches(0.55), Inches(0.25),
                 title, font_name=FONT_TITLE, font_size=Pt(13), color=HEADING, bold=True)
    add_text_box(slide, left + Inches(0.55), top + Inches(0.27), width - Inches(0.55),
                 height - Inches(0.27),
                 desc, font_size=Pt(11), color=BODY, line_spacing=1.3)


def slide_problem(prs):
    """Slide 4: Rumusan Masalah."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(5), Inches(0.55),
                 "RUMUSAN MASALAH", font_name=FONT_TITLE, font_size=Pt(30),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.5))

    # Three question cards
    questions = [
        ("01", "REPRESENTASI LINGKUNGAN",
         "Bagaimana merepresentasikan informasi lingkungan multi-lantai menggunakan "
         "layered costmap agar dapat digunakan pada algoritma navigasi antar lantai?"),
        ("02", "ALGORITMA NAVIGASI",
         "Bagaimana merancang algoritma lokalisasi, path planning, dan path tracking "
         "yang bekerja pada sistem navigasi berbasis layered costmap?"),
        ("03", "VALIDASI SISTEM",
         "Apakah robot darat otonom dapat melakukan navigasi hingga mencapai tujuan "
         "pada arena uji menggunakan metode navigasi antar lantai yang dikembangkan?"),
    ]

    card_w = Inches(11.5)
    card_h = Inches(1.0)
    card_x = MARGIN
    card_y = Inches(1.15)

    for i, (num, title, desc) in enumerate(questions):
        y = card_y + i * (card_h + Inches(0.18))
        card = add_rect(slide, card_x, y, card_w, card_h,
                        fill_color=LIGHT_BG, corner_radius=Cm(0.15))
        # Left accent bar
        add_rect(slide, card_x, y, Pt(5), card_h, fill_color=SECONDARY)
        # Number
        add_text_box(slide, card_x + Inches(0.2), y + Inches(0.1),
                     Inches(0.6), Inches(0.45),
                     num, font_name=FONT_TITLE, font_size=Pt(22),
                     color=SECONDARY, bold=True)
        # Title
        add_text_box(slide, card_x + Inches(0.8), y + Inches(0.08),
                     Inches(3.5), Inches(0.35),
                     title, font_name=FONT_TITLE, font_size=Pt(13),
                     color=HEADING, bold=True)
        # Description
        add_text_box(slide, card_x + Inches(0.8), y + Inches(0.42),
                     card_w - Inches(1.1), Inches(0.5),
                     desc, font_size=Pt(12), color=BODY, line_spacing=1.25)

    # Constraints panel
    constraint_y = Inches(4.55)
    constraint_h = Inches(2.3)
    constraint_bg = add_rect(slide, MARGIN, constraint_y, Inches(11.5), constraint_h,
                             fill_color=WARN_BG, corner_radius=Cm(0.15))

    add_text_box(slide, MARGIN + Inches(0.25), constraint_y + Inches(0.1),
                 Inches(3), Inches(0.35),
                 "BATASAN PENELITIAN", font_name=FONT_TITLE, font_size=Pt(14),
                 color=ORANGE, bold=True)

    constraints = [
        "Pengujian dilakukan pada SIMULASI (Mujoco) — bukan kondisi pasca gempa\n"
        "sebenarnya, melainkan rekayasa arena uji (rintangan tidak diketahui,\n"
        "tanjakan, permukaan tidak rata)",
        "Robot yang digunakan: HEXAPOD (6 kaki), navigasi otonom dari titik\n"
        "awal ke tujuan yang telah ditentukan",
        "Algoritma navigasi bekerja pada kondisi rintangan statis yang SUDAH\n"
        "DIKETAHUI (known map)",
    ]

    for i, ctext in enumerate(constraints):
        c_y = constraint_y + Inches(0.55) + i * Inches(0.55)
        # Warning icon (simple triangle shape)
        tri = slide.shapes.add_shape(
            MSO_SHAPE.ISOSCELES_TRIANGLE,
            MARGIN + Inches(0.35), c_y + Inches(0.12),
            Inches(0.2), Inches(0.18)
        )
        tri.fill.solid()
        tri.fill.fore_color.rgb = ORANGE
        tri.line.fill.background()

        add_text_box(slide, MARGIN + Inches(0.7), c_y,
                     Inches(10.3), Inches(0.55),
                     ctext, font_size=Pt(11), color=SUBTLE_TEXT,
                     line_spacing=1.3)

    add_slide_number(slide, 4)
    add_footer(slide)


def slide_objectives(prs):
    """Slide 5: Tujuan & Manfaat."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(5), Inches(0.55),
                 "TUJUAN & MANFAAT", font_name=FONT_TITLE, font_size=Pt(30),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.2))

    # Left column: Tujuan
    add_text_box(slide, MARGIN, Inches(1.1), Inches(2.5), Inches(0.4),
                 "Tujuan Penelitian", font_name=FONT_TITLE, font_size=Pt(18),
                 color=PRIMARY, bold=True)

    goals = [
        ("🎯", "Representasi Multi-Lantai",
         "Mengembangkan metode representasi lingkungan menggunakan layered costmap untuk "
         "menyederhanakan informasi lingkungan multi-lantai"),
        ("🎯", "Algoritma Navigasi Antar Lantai",
         "Merancang dan mengimplementasikan algoritma lokalisasi, path planning, dan path tracking "
         "yang menggunakan layered costmap"),
        ("🎯", "Evaluasi di Simulasi",
         "Melakukan pengujian sistem di lingkungan simulasi untuk mengevaluasi efektivitas "
         "dan keterbatasan pendekatan yang diusulkan"),
    ]

    y = Inches(1.6)
    for icon, title, desc in goals:
        add_icon_goal(slide, MARGIN + Inches(0.1), y, Inches(5.8), Inches(1.1), title, desc)
        y += Inches(1.25)

    # Right column: Manfaat
    right_x = Inches(7.0)
    add_text_box(slide, right_x, Inches(1.1), Inches(2.5), Inches(0.4),
                 "Manfaat Penelitian", font_name=FONT_TITLE, font_size=Pt(18),
                 color=PRIMARY, bold=True)

    benefits = [
        ("⭐", "Kontribusi pada sistem navigasi robot otonom di lingkungan kompleks"),
        ("⭐", "Dasar awal navigasi robot di area bertingkat atau runtuh pasca gempa"),
        ("⭐", "Fondasi penelitian lanjutan untuk robot SAR otonom di area bencana"),
    ]

    by = Inches(1.6)
    for icon, desc in benefits:
        add_icon_bullet(slide, right_x + Inches(0.1), by, Inches(5.8), Inches(0.55),
                        icon, "", desc)
        by += Inches(0.95)

    add_slide_number(slide, 5)
    add_footer(slide)


def add_icon_goal(slide, left, top, width, height, title, desc):
    """Draw a goal item."""
    # Icon circle
    circle = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, left, top + Inches(0.02), Inches(0.4), Inches(0.4)
    )
    circle.fill.solid()
    circle.fill.fore_color.rgb = SECONDARY
    circle.line.fill.background()
    tf = circle.text_frame
    p = tf.paragraphs[0]
    p.text = "•"
    p.font.size = Pt(16)
    p.font.color.rgb = WHITE
    p.font.bold = True
    p.alignment = PP_ALIGN.CENTER

    add_text_box(slide, left + Inches(0.55), top, width - Inches(0.55), Inches(0.25),
                 title, font_name=FONT_TITLE, font_size=Pt(13), color=HEADING, bold=True)
    add_text_box(slide, left + Inches(0.55), top + Inches(0.28), width - Inches(0.55),
                 height - Inches(0.28),
                 desc, font_size=Pt(11), color=BODY, line_spacing=1.35)


def slide_literature(prs):
    """Slide 6: Tinjauan Pustaka (Konsep Dasar)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(6), Inches(0.55),
                 "TINJAUAN PUSTAKA", font_name=FONT_TITLE, font_size=Pt(30),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.2))

    concepts = [
        ("Layered Costmap", "Grid 2D bertingkat (0–255). Layers: static map, obstacle, inflation. "
         "Setiap layer menyimpan informasi lingkungan spesifik. (macenski 2023)"),
        ("ICP Localization", "Scan matching berbasis point cloud. Iterative minimization MSD antara "
         "data sensor dan fixed map. Prekomputasi KNN untuk lookup O(1)."),
        ("A* Path Planning", "BFS dengan fungsi heuristik f(n)=g(n)+h(n). Open/closed list. "
         "Kualitas path bergantung pada kualitas fungsi heuristik."),
        ("DWA Local Planner", "Dynamic Window Approach. Sampling velocity → simulasi kinematik → "
         "scoring trajectory → pilih terbaik. Mampu menghindari obstacle tidak diketahui."),
    ]

    card_w = Inches(5.6)
    card_h = Inches(2.0)
    positions = [
        (MARGIN, Inches(1.15)),
        (MARGIN + card_w + Inches(0.3), Inches(1.15)),
        (MARGIN, Inches(3.4)),
        (MARGIN + card_w + Inches(0.3), Inches(3.4)),
    ]

    colors = [PRIMARY, SECONDARY, RGBColor(0x1A, 0x6B, 0x3C), ORANGE]

    for (x, y), (title, desc), color in zip(positions, concepts, colors):
        card = add_rect(slide, x, y, card_w, card_h, fill_color=BOX_FILL, corner_radius=Cm(0.2))
        # Top accent bar
        add_rect(slide, x, y, card_w, Pt(4), fill_color=color)
        add_text_box(slide, x + Inches(0.2), y + Inches(0.15), card_w - Inches(0.4), Inches(0.35),
                     title, font_name=FONT_TITLE, font_size=Pt(15), color=HEADING, bold=True)
        add_text_box(slide, x + Inches(0.2), y + Inches(0.55), card_w - Inches(0.4),
                     card_h - Inches(0.75),
                     desc, font_size=Pt(11), color=BODY, line_spacing=1.4)

    # State of the art row
    add_text_box(slide, MARGIN, Inches(5.55), Inches(11.5), Inches(0.3),
                 "State of the Art — Navigasi Antar Lantai",
                 font_name=FONT_TITLE, font_size=Pt(13), color=HEADING, bold=True)

    sota = ("Hu 2022: Adaptive slope navigation dengan multi-layer costmap · "
            "Kim 2024: Indoor delivery robot multi-floor dengan integrated nav map · "
            "Palacin 2023: Inter-floor navigation menggunakan elevator + ICP · "
            "Jung 2024: A* dengan realistic cost functions (elevator vs stairs)")
    add_text_box(slide, MARGIN, Inches(5.9), Inches(11.5), Inches(0.8),
                 sota, font_size=Pt(10), color=SUBTLE_TEXT, line_spacing=1.4)

    add_slide_number(slide, 6)
    add_footer(slide)


def slide_system_overview(prs):
    """Slide 7: Gambaran Umum Sistem."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(6), Inches(0.55),
                 "GAMBARAN UMUM SISTEM", font_name=FONT_TITLE, font_size=Pt(30),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.8))

    # Architecture flow diagram
    blocks = [
        ("Sensor\n(LiDAR)", Inches(1.0), Inches(1.5), PRIMARY),
        ("Lokalisasi\n(ICP + Region\nSwitcher)", Inches(3.2), Inches(1.5), SECONDARY),
        ("Costmap\n(Global / Local /\nTransition)", Inches(5.8), Inches(1.5), SECONDARY),
        ("Global Planner\n(A* + Path\nInterceptor)", Inches(8.4), Inches(1.5), PRIMARY),
        ("Local Planner\n(DWA +\nTrajectory)", Inches(11.0), Inches(1.5), PRIMARY),
    ]

    for text, x, w, color in blocks:
        block = add_rect(slide, x, Inches(2.0), w, Inches(1.6),
                         fill_color=RGBColor(0xE8, 0xF0, 0xFE), corner_radius=Cm(0.2))
        # Accent top
        add_rect(slide, x, Inches(2.0), w, Pt(4), fill_color=color)
        add_text_box(slide, x + Inches(0.1), Inches(2.2), w - Inches(0.2), Inches(1.2),
                     text, font_name=FONT_TITLE, font_size=Pt(11), color=HEADING, bold=True,
                     alignment=PP_ALIGN.CENTER, line_spacing=1.3)

    # Arrows between blocks (simple triangles)
    arrows = [
        (Inches(2.55), Inches(2.55), 0),
        (Inches(5.05), Inches(2.55), 0),
        (Inches(7.7), Inches(2.55), 0),
        (Inches(10.35), Inches(2.55), 0),
    ]
    for ax, ay, rot in arrows:
        arrow = slide.shapes.add_shape(
            MSO_SHAPE.RIGHT_ARROW, ax, ay, Inches(0.55), Inches(0.3)
        )
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = ORANGE
        arrow.line.fill.background()

    # Feedback loop arrow below
    # add a curved arrow concept using text
    add_text_box(slide, MARGIN + Inches(3.5), Inches(4.0), Inches(6), Inches(0.4),
                 "← Feedback loop: odometry + sensor data → perbarui costmap lokal ←",
                 font_size=Pt(10), color=SUBTLE_TEXT, italic=True, alignment=PP_ALIGN.CENTER)

    # Component descriptions
    components = [
        ("Occupancy Grid", "Menyimpan peta lingkungan\n(static known map)"),
        ("Lokalisasi ICP", "Estimasi pose robot\nvia scan matching"),
        ("Costmap", "Layer bertingkat: static,\ninflation, transition"),
        ("Path Planning (A*)", "Rencana rute global\nmulti-region"),
        ("Path Tracking (DWA)", "Eksekusi trajectory\ndan obstacle avoidance"),
    ]

    cx = Inches(1.0)
    for title, desc in components:
        y = Inches(4.6)
        add_text_box(slide, cx, y, Inches(2.1), Inches(0.25),
                     title, font_name=FONT_TITLE, font_size=Pt(10),
                     color=PRIMARY, bold=True, alignment=PP_ALIGN.CENTER)
        add_text_box(slide, cx, y + Inches(0.25), Inches(2.1), Inches(0.55),
                     desc, font_size=Pt(9), color=SUBTLE_TEXT,
                     alignment=PP_ALIGN.CENTER, line_spacing=1.3)
        cx += Inches(2.55)

    # Keterangan tambahan
    add_text_box(slide, MARGIN, Inches(5.5), Inches(11.5), Inches(0.3),
                 "Alur Navigasi: Scan → Localize → Build Costmap → Plan Path → Execute Trajectory → Update",
                 font_size=Pt(11), color=BODY, bold=True, alignment=PP_ALIGN.CENTER)

    add_slide_number(slide, 7)
    add_footer(slide)


def slide_map_processing(prs):
    """Slide 8: Pengolahan Data Map (Multi-Region)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(7), Inches(0.55),
                 "PENGOLAHAN DATA MAP", font_name=FONT_TITLE, font_size=Pt(28),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.0))

    # Three columns: Environment → Slicing → Combined + Transition
    col_w = Inches(3.6)
    col_gap = Inches(0.3)

    # Column 1
    c1 = add_rect(slide, MARGIN, Inches(1.1), col_w, Inches(1.8),
                  fill_color=BOX_FILL, corner_radius=Cm(0.2))
    add_text_box(slide, MARGIN + Inches(0.15), Inches(1.15), col_w - Inches(0.3), Inches(0.3),
                 "Lingkungan 3D", font_name=FONT_TITLE, font_size=Pt(13),
                 color=HEADING, bold=True)
    add_text_box(slide, MARGIN + Inches(0.15), Inches(1.5), col_w - Inches(0.3), Inches(1.2),
                 "Lingkungan indoor bertingkat\n"
                 "• Bangunan dengan beberapa lantai\n"
                 "• Puing dan rintangan\n"
                 "• Tangga / ramp penghubung\n"
                 "• Data 3D occupancy grid",
                 font_size=Pt(11), color=BODY, line_spacing=1.5)

    # Arrow 1→2
    arr1 = slide.shapes.add_shape(
        MSO_SHAPE.RIGHT_ARROW, MARGIN + col_w + Inches(0.02), Inches(1.7),
        Inches(0.26), Inches(0.22)
    )
    arr1.fill.solid()
    arr1.fill.fore_color.rgb = ORANGE
    arr1.line.fill.background()

    # Column 2
    c2_x = MARGIN + col_w + col_gap
    c2 = add_rect(slide, c2_x, Inches(1.1), col_w, Inches(1.8),
                  fill_color=BOX_FILL, corner_radius=Cm(0.2))
    add_text_box(slide, c2_x + Inches(0.15), Inches(1.15), col_w - Inches(0.3), Inches(0.3),
                 "Pembagian Region", font_name=FONT_TITLE, font_size=Pt(13),
                 color=HEADING, bold=True)
    add_text_box(slide, c2_x + Inches(0.15), Inches(1.5), col_w - Inches(0.3), Inches(1.2),
                 "Lingkungan 3D dibagi menjadi\nregion 2D:\n"
                 "• Region A — lorong & ramp\n"
                 "• Region B — lorong sempit\n"
                 "• Region C — area terbuka\n\n"
                 "ROI detection pada tiap\npeta pisah",
                 font_size=Pt(11), color=BODY, line_spacing=1.5)

    # Arrow 2→3
    arr2 = slide.shapes.add_shape(
        MSO_SHAPE.RIGHT_ARROW, c2_x + col_w + Inches(0.02), Inches(1.7),
        Inches(0.26), Inches(0.22)
    )
    arr2.fill.solid()
    arr2.fill.fore_color.rgb = ORANGE
    arr2.line.fill.background()

    # Column 3
    c3_x = c2_x + col_w + col_gap
    c3 = add_rect(slide, c3_x, Inches(1.1), col_w + Inches(0.5), Inches(1.8),
                  fill_color=BOX_FILL, corner_radius=Cm(0.2))
    add_text_box(slide, c3_x + Inches(0.15), Inches(1.15), col_w + Inches(0.2), Inches(0.3),
                 "Combined & Transition Map", font_name=FONT_TITLE, font_size=Pt(13),
                 color=HEADING, bold=True)
    add_text_box(slide, c3_x + Inches(0.15), Inches(1.5), col_w + Inches(0.2), Inches(1.2),
                 "Combined Map:\n"
                 "• Gabungan region A, B, C\n"
                 "• Satu frame referensi\n\n"
                 "Transition Map:\n"
                 "• Koneksi spasial antar region\n"
                 "• Koordinat konektor & orientasi\n"
                 "• Posisi awal robot",
                 font_size=Pt(11), color=BODY, line_spacing=1.5)

    # Details section
    add_text_box(slide, MARGIN, Inches(3.2), Inches(6), Inches(0.3),
                 "Detail Combined & Transition Map", font_name=FONT_TITLE,
                 font_size=Pt(16), color=HEADING, bold=True)

    detail_w = Inches(5.6)
    # Combined map detail
    d1 = add_rect(slide, MARGIN, Inches(3.6), detail_w, Inches(1.5),
                  fill_color=BOX_FILL, corner_radius=Cm(0.15))
    add_text_box(slide, MARGIN + Inches(0.2), Inches(3.65), detail_w - Inches(0.4), Inches(0.25),
                 "Combined Map — ROI Detection", font_name=FONT_TITLE, font_size=Pt(12),
                 color=PRIMARY, bold=True)
    add_text_box(slide, MARGIN + Inches(0.2), Inches(3.95), detail_w - Inches(0.4), Inches(1.0),
                 "ROI = {(x,y) : I(x,y) < T}\n"
                 "Di mana I(x,y) = intensitas piksel, T = threshold.\n"
                 "Peta gabungan tersusun dari beberapa bagian,\n"
                 "setiap bagian ditempati oleh satu region.",
                 font_size=Pt(11), color=BODY, line_spacing=1.4)

    # Transition map detail
    d2_x = MARGIN + detail_w + Inches(0.3)
    d2 = add_rect(slide, d2_x, Inches(3.6), detail_w, Inches(1.5),
                  fill_color=BOX_FILL, corner_radius=Cm(0.15))
    add_text_box(slide, d2_x + Inches(0.2), Inches(3.65), detail_w - Inches(0.4), Inches(0.25),
                 "Transition Map — Metadata", font_name=FONT_TITLE, font_size=Pt(12),
                 color=ORANGE, bold=True)
    add_text_box(slide, d2_x + Inches(0.2), Inches(3.95), detail_w - Inches(0.4), Inches(1.0),
                 "Connection pairs: A↔B, B↔C\n"
                 "Orientasi tiap region (quaternion)\n"
                 "Posisi awal robot (375, 75) pixel\n"
                 "Zona transisi: area di ujung region tempat\n"
                 "robot berpindah ke region berikutnya",
                 font_size=Pt(11), color=BODY, line_spacing=1.4)

    add_slide_number(slide, 8)
    add_footer(slide)


def slide_costmap_structure(prs):
    """Slide 9: Struktur Layered Costmap."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(7), Inches(0.55),
                 "STRUKTUR LAYERED COSTMAP", font_name=FONT_TITLE, font_size=Pt(28),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.5))

    # Three layer cards stacked vertically on the left
    layers = [
        ("GLOBAL COSTMAP", "Static layer (obstacle tetap) + Inflation layer",
         PRIMARY, "Cost Scaling Factor (CSF) mempengaruhi\ngradient biaya di sekitar obstacle"),
        ("LOCAL COSTMAP", "Obstacle layer (LiDAR real-time) + Inflation layer",
         SECONDARY, "Diperbarui secara dinamis dari\ndata scan LiDAR"),
        ("TRANSITION COSTMAP", "Menyimpan informasi koneksi antar region",
         ORANGE, "Memungkinkan robot berpindah\nregion secara mulus"),
    ]

    layer_y = Inches(1.1)
    layer_h = Inches(1.05)
    layer_w = Inches(5.8)

    for title, desc, color, note in layers:
        card = add_rect(slide, MARGIN, layer_y, layer_w, layer_h,
                        fill_color=BOX_FILL, corner_radius=Cm(0.15))
        add_rect(slide, MARGIN, layer_y, Pt(5), layer_h, fill_color=color)
        add_text_box(slide, MARGIN + Inches(0.2), layer_y + Inches(0.08),
                     layer_w - Inches(0.4), Inches(0.3),
                     title, font_name=FONT_TITLE, font_size=Pt(14),
                     color=color, bold=True)
        add_text_box(slide, MARGIN + Inches(0.2), layer_y + Inches(0.38),
                     Inches(3.5), Inches(0.25),
                     desc, font_size=Pt(11), color=BODY)
        add_text_box(slide, MARGIN + Inches(3.8), layer_y + Inches(0.08),
                     Inches(1.8), Inches(0.9),
                     note, font_size=Pt(9), color=SUBTLE_TEXT,
                     italic=True, line_spacing=1.3)
        layer_y += layer_h + Inches(0.15)

    # Right side: Inflation formula and costmap values
    right_x = Inches(7.2)

    # Inflation formula box
    formula_box = add_rect(slide, right_x, Inches(1.1), Inches(5.5), Inches(1.3),
                           fill_color=RGBColor(0xFD, 0xF2, 0xE3), corner_radius=Cm(0.15))
    add_text_box(slide, right_x + Inches(0.2), Inches(1.15), Inches(5.1), Inches(0.25),
                 "Fungsi Inflasi", font_name=FONT_TITLE, font_size=Pt(13),
                 color=ORANGE, bold=True)
    add_text_box(slide, right_x + Inches(0.2), Inches(1.45), Inches(5.1), Inches(0.7),
                 "C(d) = 253 · e^(-α · (d − r_inscribed))   untuk d ≤ R\n"
                 "C(d) = 0                                            untuk d > R\n\n"
                 "Di mana d = jarak dari obstacle, R = radius inflasi",
                 font_size=Pt(12), color=BODY, line_spacing=1.4)

    # Costmap values table
    vals_box = add_rect(slide, right_x, Inches(2.65), Inches(5.5), Inches(2.0),
                        fill_color=BOX_FILL, corner_radius=Cm(0.15))
    add_text_box(slide, right_x + Inches(0.2), Inches(2.7), Inches(5.1), Inches(0.25),
                 "Nilai Sel Costmap (Occupancy Grid)", font_name=FONT_TITLE,
                 font_size=Pt(13), color=HEADING, bold=True)

    values = [
        ("FREE_SPACE", "0", "Area bebas, dapat dilalui"),
        ("TRANSITION_CELL", "1–5", "Zona transisi antar region"),
        ("INFLATED_OBSTACLE", "6–252", "Area inflasi di sekitar obstacle"),
        ("LETHAL_OBSTACLE", "254", "Obstacle tidak dapat dilalui"),
        ("NO_INFORMATION", "255", "Area belum diketahui"),
    ]

    vy = Inches(3.05)
    for name, val, desc in values:
        add_text_box(slide, right_x + Inches(0.2), vy, Inches(1.8), Inches(0.2),
                     name, font_size=Pt(10), color=HEADING, bold=True)
        add_text_box(slide, right_x + Inches(2.1), vy, Inches(0.8), Inches(0.2),
                     val, font_size=Pt(10), color=PRIMARY, bold=True,
                     alignment=PP_ALIGN.CENTER)
        add_text_box(slide, right_x + Inches(3.0), vy, Inches(2.3), Inches(0.2),
                     desc, font_size=Pt(9), color=SUBTLE_TEXT)
        vy += Inches(0.28)

    add_slide_number(slide, 9)
    add_footer(slide)


def slide_icp(prs):
    """Slide 10: Lokalisasi ICP & Region Switcher."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(7), Inches(0.55),
                 "LOKALISASI ICP & REGION SWITCHER", font_name=FONT_TITLE, font_size=Pt(26),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.5))

    # Left: ICP pipeline
    add_text_box(slide, MARGIN, Inches(1.1), Inches(3), Inches(0.3),
                 "ICP (Iterative Closest Point)", font_name=FONT_TITLE,
                 font_size=Pt(16), color=PRIMARY, bold=True)

    icp_steps = [
        ("1", "Prekomputasi KNN", "Hash table, lookup O(1)\nk=8, r=10"),
        ("2", "Correspondence\nMatching", "Pasangkan titik\nscan → map"),
        ("3", "SVD Solver", "Estimasi rotasi &\ntranslasi optimal"),
        ("4", "Transformasi", "Perbarui pose robot\n(R, t)"),
    ]

    step_x = MARGIN
    step_y = Inches(1.55)
    step_w = Inches(2.0)
    step_h = Inches(1.4)

    for i, (num, title, desc) in enumerate(icp_steps):
        sx = step_x + i * (step_w + Inches(0.15))
        card = add_rect(slide, sx, step_y, step_w, step_h,
                        fill_color=BOX_FILL, corner_radius=Cm(0.15))
        # Number
        circle = slide.shapes.add_shape(
            MSO_SHAPE.OVAL, sx + Inches(0.05), step_y + Inches(0.05),
            Inches(0.35), Inches(0.35)
        )
        circle.fill.solid()
        circle.fill.fore_color.rgb = PRIMARY
        circle.line.fill.background()
        tf = circle.text_frame
        p = tf.paragraphs[0]
        p.text = num
        p.font.size = Pt(12)
        p.font.color.rgb = WHITE
        p.font.bold = True
        p.alignment = PP_ALIGN.CENTER

        add_text_box(slide, sx + Inches(0.45), step_y + Inches(0.05),
                     step_w - Inches(0.55), Inches(0.35),
                     title, font_name=FONT_TITLE, font_size=Pt(10),
                     color=HEADING, bold=True, line_spacing=1.2)
        add_text_box(slide, sx + Inches(0.15), step_y + Inches(0.55),
                     step_w - Inches(0.3), step_h - Inches(0.65),
                     desc, font_size=Pt(9), color=BODY, line_spacing=1.35)

        # Arrow between steps
        if i < len(icp_steps) - 1:
            arr = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW,
                sx + step_w + Inches(0.01), step_y + Inches(0.55),
                Inches(0.13), Inches(0.15)
            )
            arr.fill.solid()
            arr.fill.fore_color.rgb = ORANGE
            arr.line.fill.background()

    # Parameters
    add_text_box(slide, MARGIN, Inches(3.15), Inches(11.5), Inches(0.25),
                 "Parameter: max_iter=50, k=8, r=10, t_norm=0.01m, r_norm=0.01rad, s=2",
                 font_size=Pt(10), color=SUBTLE_TEXT, italic=True)

    # Right side: Region Switcher
    add_text_box(slide, MARGIN, Inches(3.6), Inches(4), Inches(0.3),
                 "Region Switcher & Zona Transisi", font_name=FONT_TITLE,
                 font_size=Pt(16), color=ORANGE, bold=True)

    # Region switching diagram
    regions = ["Region A", "Region B", "Region C"]
    rx = MARGIN + Inches(0.5)
    ry = Inches(4.1)

    for i, rname in enumerate(regions):
        rx_pos = rx + i * Inches(3.8)
        rcard = add_rect(slide, rx_pos, ry, Inches(2.8), Inches(1.1),
                         fill_color=BOX_FILL, corner_radius=Cm(0.15))
        add_text_box(slide, rx_pos + Inches(0.1), ry + Inches(0.1),
                     Inches(2.6), Inches(0.3),
                     rname, font_name=FONT_TITLE, font_size=Pt(14),
                     color=PRIMARY, bold=True, alignment=PP_ALIGN.CENTER)
        add_text_box(slide, rx_pos + Inches(0.1), ry + Inches(0.45),
                     Inches(2.6), Inches(0.5),
                     "Peta 2D region\nNavigasi di dalam region",
                     font_size=Pt(10), color=SUBTLE_TEXT,
                     alignment=PP_ALIGN.CENTER, line_spacing=1.3)

    # Transition arrows
    for i in range(2):
        tx_x = rx + (i + 1) * Inches(3.8) - Inches(0.8)
        tarr = slide.shapes.add_shape(
            MSO_SHAPE.RIGHT_ARROW,
            tx_x, ry + Inches(0.4), Inches(0.55), Inches(0.25)
        )
        tarr.fill.solid()
        tarr.fill.fore_color.rgb = ORANGE
        tarr.line.fill.background()

        # Transition label
        add_text_box(slide, tx_x - Inches(0.1), ry + Inches(0.7),
                     Inches(0.75), Inches(0.25),
                     "Transisi", font_size=Pt(8), color=ORANGE,
                     bold=True, alignment=PP_ALIGN.CENTER)

    # Key fact box
    key_box = add_rect(slide, MARGIN, Inches(5.5), Inches(11.5), Inches(0.6),
                       fill_color=RGBColor(0xFF, 0xF3, 0xE0), corner_radius=Cm(0.1))
    add_rect(slide, MARGIN, Inches(5.5), Pt(4), Inches(0.6), fill_color=ORANGE)
    add_text_box(slide, MARGIN + Inches(0.15), Inches(5.52), Inches(11.2), Inches(0.55),
                 "Zona transisi memerlukan radius minimal 0.26 m agar robot dapat berpindah region "
                 "dengan aman sebelum kualitas lokalisasi ICP menurun signifikan.",
                 font_size=Pt(11), color=BODY, line_spacing=1.3)

    add_slide_number(slide, 10)
    add_footer(slide)


def slide_path_planning(prs):
    """Slide 11: Path Planning (A* Global Planner)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(7), Inches(0.55),
                 "PATH PLANNING — A* GLOBAL PLANNER", font_name=FONT_TITLE, font_size=Pt(26),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.5))

    # Left section: A* description
    add_text_box(slide, MARGIN, Inches(1.1), Inches(3), Inches(0.3),
                 "Algoritma A*", font_name=FONT_TITLE, font_size=Pt(18),
                 color=PRIMARY, bold=True)

    astar_content = (
        "• f(n) = g(n) + h(n)\n"
        "    g(n) = biaya dari start ke node n\n"
        "    h(n) = estimasi heuristik dari n ke goal\n\n"
        "• Quadratic potential calculation untuk\n"
        "  menghitung cost gradient pada grid\n\n"
        "• Open list / Closed list untuk eksplorasi\n"
        "  node secara optimal"
    )
    add_text_box(slide, MARGIN, Inches(1.5), Inches(5.0), Inches(2.0),
                 astar_content, font_size=Pt(12), color=BODY, line_spacing=1.4)

    # Path Interceptor
    add_text_box(slide, MARGIN, Inches(3.6), Inches(5), Inches(0.3),
                 "Path Interceptor (Multi-Region)", font_name=FONT_TITLE,
                 font_size=Pt(14), color=ORANGE, bold=True)

    interceptor_content = (
        "Memecah path multi-region menjadi segmen per region:\n\n"
        "Region A  →  Titik Transisi A-B  →  Region B  →\n"
        "Titik Transisi B-C  →  Region C  →  Goal"
    )
    add_text_box(slide, MARGIN, Inches(3.95), Inches(5.0), Inches(1.5),
                 interceptor_content, font_size=Pt(12), color=BODY, line_spacing=1.4)

    # Right section: Cost Scaling Factor
    right_x = Inches(7.0)
    add_text_box(slide, right_x, Inches(1.1), Inches(5), Inches(0.3),
                 "Cost Scaling Factor (CSF)", font_name=FONT_TITLE,
                 font_size=Pt(18), color=PRIMARY, bold=True)

    csf_data = [
        ("CSF = 10", "Path di tengah,\nkonservatif, lebih\naman tapi lebih\npanjang", PRIMARY),
        ("CSF = 50", "Path transisi antara\nkonservatif dan\nagresif", SECONDARY),
        ("CSF = 100", "Path dekat obstacle,\nlebih pendek &\nlurus (OPTIMAL)", ORANGE),
    ]

    csy = Inches(1.55)
    for title, desc, color in csf_data:
        cscard = add_rect(slide, right_x, csy, Inches(5.5), Inches(0.85),
                          fill_color=BOX_FILL, corner_radius=Cm(0.1))
        add_rect(slide, right_x, csy, Pt(4), Inches(0.85), fill_color=color)
        add_text_box(slide, right_x + Inches(0.15), csy + Inches(0.05),
                     Inches(2.0), Inches(0.25),
                     title, font_name=FONT_TITLE, font_size=Pt(13),
                     color=color, bold=True)
        add_text_box(slide, right_x + Inches(2.2), csy + Inches(0.05),
                     Inches(3.1), Inches(0.75),
                     desc, font_size=Pt(10), color=BODY, line_spacing=1.35)
        csy += Inches(0.95)

    # Key finding
    key_box = add_rect(slide, right_x, Inches(4.55), Inches(5.5), Inches(0.75),
                       fill_color=RGBColor(0xFF, 0xF3, 0xE0), corner_radius=Cm(0.1))
    add_text_box(slide, right_x + Inches(0.15), Inches(4.6), Inches(5.2), Inches(0.65),
                 "CSF 100 menghasilkan path terpendek dengan\n"
                 "clearance obstacle yang masih memadai.\n"
                 "Region B (lorong sempit): CSF tidak signifikan berpengaruh.",
                 font_size=Pt(11), color=BODY, line_spacing=1.35)

    add_slide_number(slide, 11)
    add_footer(slide)


def slide_dwa(prs):
    """Slide 12: Path Tracking (DWA Local Planner)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(7), Inches(0.55),
                 "PATH TRACKING — DWA LOCAL PLANNER", font_name=FONT_TITLE, font_size=Pt(26),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.5))

    # Top: 5-step flow
    steps = [
        ("1. Velocity\nSampling", "6 vx × 6 vy × 30 ω\n= 1080 trajectory"),
        ("2. Kinematic\nSimulation", "Simulasi robot\nselama Δt"),
        ("3. Trajectory\nScoring", "7 kriteria\npenilaian"),
        ("4. Best\nSelection", "Pilih trajectory\ndengan biaya terendah"),
        ("5. Send to\nRobot", "Eksekusi gerakan\npada hexapod"),
    ]

    sx = MARGIN
    sy = Inches(1.15)
    sw = Inches(2.1)
    sh = Inches(1.45)

    for i, (title, desc) in enumerate(steps):
        scard = add_rect(slide, sx, sy, sw, sh,
                         fill_color=BOX_FILL, corner_radius=Cm(0.15))
        add_rect(slide, sx, sy, sw, Pt(4), fill_color=PRIMARY)
        add_text_box(slide, sx + Inches(0.1), sy + Inches(0.1),
                     sw - Inches(0.2), Inches(0.5),
                     title, font_name=FONT_TITLE, font_size=Pt(10),
                     color=HEADING, bold=True, alignment=PP_ALIGN.CENTER,
                     line_spacing=1.2)
        add_text_box(slide, sx + Inches(0.1), sy + Inches(0.65),
                     sw - Inches(0.2), Inches(0.7),
                     desc, font_size=Pt(9), color=SUBTLE_TEXT,
                     alignment=PP_ALIGN.CENTER, line_spacing=1.35)

        if i < len(steps) - 1:
            arr = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW,
                sx + sw + Inches(0.02), sy + Inches(0.55),
                Inches(0.22), Inches(0.2)
            )
            arr.fill.solid()
            arr.fill.fore_color.rgb = ORANGE
            arr.line.fill.background()

        sx += sw + Inches(0.26)

    # Bottom: 7 scoring criteria
    add_text_box(slide, MARGIN, Inches(2.8), Inches(11.5), Inches(0.3),
                 "7 Kriteria Scoring DWA", font_name=FONT_TITLE,
                 font_size=Pt(16), color=HEADING, bold=True)

    criteria = [
        ("C_osc", "Oscillation\npenalty"),
        ("C_obs", "Obstacle\ndistance"),
        ("C_gf", "Goal front\nalignment"),
        ("C_align", "Path\nalignment"),
        ("C_path", "Distance to\nglobal path"),
        ("C_goal", "Distance\nto goal"),
        ("C_twirl", "Rotation\npenalty"),
    ]

    weights = ["w_osc", "w_obs", "w_gf", "w_align", "w_path", "w_goal", "w_twirl"]
    colors_crit = [PRIMARY, SECONDARY, SECONDARY, SECONDARY, SECONDARY, SECONDARY, ORANGE]

    cx = MARGIN
    cy = Inches(3.25)
    cw = Inches(1.55)
    ch = Inches(1.1)

    for i, ((c_name, c_desc), w_name, color) in enumerate(zip(criteria, weights, colors_crit)):
        ccard = add_rect(slide, cx, cy, cw, ch,
                         fill_color=BOX_FILL, corner_radius=Cm(0.1))
        add_text_box(slide, cx + Inches(0.05), cy + Inches(0.05),
                     Inches(1.1), Inches(0.2),
                     c_name, font_size=Pt(10), color=color, bold=True)
        add_text_box(slide, cx + Inches(0.05), cy + Inches(0.28),
                     cw - Inches(0.1), Inches(0.45),
                     c_desc, font_size=Pt(8), color=SUBTLE_TEXT,
                     line_spacing=1.3)
        add_text_box(slide, cx + Inches(0.05), cy + Inches(0.78),
                     cw - Inches(0.1), Inches(0.2),
                     w_name, font_size=Pt(7), color=BODY)
        cx += cw + Inches(0.1)

    # Formula
    add_text_box(slide, MARGIN, Inches(4.55), Inches(11.5), Inches(0.35),
                 "C_total = C_osc + Σ(wi · Ci)  →  Minimalkan total cost",
                 font_size=Pt(12), color=BODY, bold=True, alignment=PP_ALIGN.CENTER)

    # Key feature
    key_box = add_rect(slide, MARGIN, Inches(5.15), Inches(11.5), Inches(0.55),
                       fill_color=RGBColor(0xFF, 0xF3, 0xE0), corner_radius=Cm(0.1))
    add_text_box(slide, MARGIN + Inches(0.15), Inches(5.2), Inches(11.2), Inches(0.45),
                 "Mampu menghindari obstacle dinamis yang tidak ada di global path, "
                 "tercermin dari peningkatan max cross track error pada kondisi gempa.",
                 font_size=Pt(11), color=BODY, line_spacing=1.3)

    add_slide_number(slide, 12)
    add_footer(slide)


def slide_arena(prs):
    """Slide 13: Arena Pengujian & Skenario."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(6), Inches(0.55),
                 "ARENA PENGUJIAN & SKENARIO", font_name=FONT_TITLE, font_size=Pt(28),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.5))

    # Arena cards (2x2 grid)
    arenas = [
        ("Region A", "Lorong dengan ramp.\nArea awal navigasi.\nRintangan statis.", PRIMARY),
        ("Region B", "Lorong sempit.\nPenghubung A dan C.\nLayout terbatas.", SECONDARY),
        ("Region C", "Area terbuka.\nBanyak obstacle.\nTrajectory kompleks.", ORANGE),
        ("Rough Floor\n(Pasca Gempa)", "Permukaan tidak rata.\nObstacle tidak\ndiketahui.", RGBColor(0xCC, 0x33, 0x33)),
    ]

    positions_arena = [
        (MARGIN, Inches(1.2)),
        (MARGIN + Inches(5.85), Inches(1.2)),
        (MARGIN, Inches(3.45)),
        (MARGIN + Inches(5.85), Inches(3.45)),
    ]

    aw = Inches(5.5)
    ah = Inches(2.0)

    for (x, y), (title, desc, color) in zip(positions_arena, arenas):
        acard = add_rect(slide, x, y, aw, ah, fill_color=BOX_FILL, corner_radius=Cm(0.15))
        add_rect(slide, x, y, aw, Pt(4), fill_color=color)
        add_text_box(slide, x + Inches(0.2), y + Inches(0.1),
                     aw - Inches(0.4), Inches(0.4),
                     title, font_name=FONT_TITLE, font_size=Pt(15),
                     color=color, bold=True)
        add_text_box(slide, x + Inches(0.2), y + Inches(0.55),
                     aw - Inches(0.4), Inches(1.3),
                     desc, font_size=Pt(11), color=BODY, line_spacing=1.5)

    # Simulator & robot info
    add_text_box(slide, MARGIN, Inches(5.6), Inches(11.5), Inches(0.35),
                 "Platform: Mujoco Simulator  ·  Robot: Hexapod (6 kaki)  ·  "
                 "Sensor: LiDAR 2D  ·  Peta: Known Map",
                 font_size=Pt(11), color=SUBTLE_TEXT, bold=False)

    add_slide_number(slide, 13)
    add_footer(slide)


def slide_results_icp_costmap(prs):
    """Slide 14: Hasil Pengujian — ICP & Costmap."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(7), Inches(0.55),
                 "HASIL PENGUJIAN: ICP & COSTMAP", font_name=FONT_TITLE, font_size=Pt(26),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.5))

    # Left column: ICP results
    add_text_box(slide, MARGIN, Inches(1.1), Inches(5.5), Inches(0.3),
                 "Hasil ICP Localization", font_name=FONT_TITLE,
                 font_size=Pt(16), color=PRIMARY, bold=True)

    icp_results = [
        ("Region A (Rata)", "Error rendah & stabil. Lonjakan\nerror di t ≈ 50 detik (zona transisi)\nkarena fitur LiDAR terbatas.",
         RGBColor(0x2E, 0x7D, 0x32)),
        ("Region A (Rough)", "Osilasi signifikan pada sumbu x\ndan yaw. Permukaan tidak rata →\nvariasi vertikal scan LiDAR ↑.",
         RGBColor(0xF5, 0x7F, 0x17)),
        ("Region C (Kompleks)", "Error lebih tinggi. Lebih banyak\nobstacle → KNN lookup lebih\nbesar. Trajectory banyak rotasi.",
         ORANGE),
        ("Zona Transisi", "Diameter minimal: 0.26 m.\nKualitas ICP menurun saat robot\n< 0.24 m dari ujung map.",
         RGBColor(0x7B, 0x1F, 0xA2)),
    ]

    iy = Inches(1.5)
    for title, desc, color in icp_results:
        icard = add_rect(slide, MARGIN, iy, Inches(5.5), Inches(0.9),
                         fill_color=BOX_FILL, corner_radius=Cm(0.1))
        add_rect(slide, MARGIN, iy, Pt(4), Inches(0.9), fill_color=color)
        add_text_box(slide, MARGIN + Inches(0.15), iy + Inches(0.05),
                     Inches(5.2), Inches(0.2),
                     title, font_name=FONT_TITLE, font_size=Pt(11),
                     color=color, bold=True)
        add_text_box(slide, MARGIN + Inches(0.15), iy + Inches(0.28),
                     Inches(5.2), Inches(0.55),
                     desc, font_size=Pt(9), color=BODY, line_spacing=1.35)
        iy += Inches(0.98)

    # Right column: Costmap results
    right_x = Inches(7.0)
    add_text_box(slide, right_x, Inches(1.1), Inches(5.5), Inches(0.3),
                 "Hasil Costmap", font_name=FONT_TITLE,
                 font_size=Pt(16), color=ORANGE, bold=True)

    costmap_results = [
        ("Region A — CSF 100",
         "Path terpendek dan lurus.\nCSF 10: path di tengah (konservatif),\nlebih panjang.",
         PRIMARY),
        ("Region B — CSF tidak signifikan",
         "Layout lorong sempit → semua CSF\nmenghasilkan path hampir identik.",
         SECONDARY),
        ("Region C — CSF 100 optimal",
         "CSF 100: path pendek & lurus.\nCSF 10: di tengah, lebih panjang.\n\n"
         "Trade-off: path pendek vs deviasi\nground truth. CSF 100 deviasi\ntertinggi tapi paling efisien.",
         ORANGE),
    ]

    cy = Inches(1.5)
    for title, desc, color in costmap_results:
        ch = Inches(1.4) if "CSF 100 optimal" in title else Inches(1.0)
        ccard = add_rect(slide, right_x, cy, Inches(5.5), ch,
                         fill_color=BOX_FILL, corner_radius=Cm(0.1))
        add_rect(slide, right_x, cy, Pt(4), ch, fill_color=color)
        add_text_box(slide, right_x + Inches(0.15), cy + Inches(0.05),
                     Inches(5.2), Inches(0.2),
                     title, font_name=FONT_TITLE, font_size=Pt(11),
                     color=color, bold=True)
        add_text_box(slide, right_x + Inches(0.15), cy + Inches(0.3),
                     Inches(5.2), ch - Inches(0.35),
                     desc, font_size=Pt(9), color=BODY, line_spacing=1.35)
        cy += ch + Inches(0.1)

    add_slide_number(slide, 14)
    add_footer(slide)


def slide_results_navigation(prs):
    """Slide 15: Hasil Pengujian — DWA & Navigasi Penuh."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(7), Inches(0.55),
                 "HASIL PENGUJIAN: DWA & NAVIGASI PENUH", font_name=FONT_TITLE, font_size=Pt(24),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.5))

    # DWA results
    add_text_box(slide, MARGIN, Inches(1.1), Inches(5.5), Inches(0.3),
                 "Hasil DWA Planner", font_name=FONT_TITLE,
                 font_size=Pt(16), color=PRIMARY, bold=True)

    dwa_results = [
        ("Kondisi Normal", "Mean & max cross track error rendah.\nDWA mengikuti global path dengan baik.",
         RGBColor(0x2E, 0x7D, 0x32), "✓"),
        ("Kondisi Gempa", "Max cross track error meningkat signifikan.\nObstacle tidak diketahui di global path →\nDWA menyimpang untuk menghindari tabrakan.",
         ORANGE, "⚠"),
    ]

    dry = Inches(1.55)
    for title, desc, color, status in dwa_results:
        drcard = add_rect(slide, MARGIN, dry, Inches(5.8), Inches(1.15),
                          fill_color=BOX_FILL, corner_radius=Cm(0.1))
        add_rect(slide, MARGIN, dry, Pt(4), Inches(1.15), fill_color=color)
        add_text_box(slide, MARGIN + Inches(0.15), dry + Inches(0.05),
                     Inches(4.5), Inches(0.25),
                     f"{status}  {title}", font_name=FONT_TITLE, font_size=Pt(13),
                     color=color, bold=True)
        add_text_box(slide, MARGIN + Inches(0.15), dry + Inches(0.35),
                     Inches(5.5), Inches(0.7),
                     desc, font_size=Pt(10), color=BODY, line_spacing=1.4)
        dry += Inches(1.25)

    # Navigation result highlight
    right_x = Inches(7.2)

    # Big result box
    result_box = add_rect(slide, right_x, Inches(1.1), Inches(5.5), Inches(2.3),
                          fill_color=RGBColor(0xE3, 0xF0, 0xFD), corner_radius=Cm(0.2))
    add_rect(slide, right_x, Inches(1.1), Inches(5.5), Pt(4), fill_color=PRIMARY)

    add_text_box(slide, right_x + Inches(0.2), Inches(1.2), Inches(5.1), Inches(0.35),
                 "NAVIGASI PENUH (Region A → C)",
                 font_name=FONT_TITLE, font_size=Pt(16), color=PRIMARY, bold=True,
                 alignment=PP_ALIGN.CENTER)

    add_text_box(slide, right_x + Inches(0.2), Inches(1.65), Inches(5.1), Inches(0.7),
                 "127.26",
                 font_name=FONT_TITLE, font_size=Pt(52), color=PRIMARY, bold=True,
                 alignment=PP_ALIGN.CENTER)

    add_text_box(slide, right_x + Inches(0.2), Inches(2.25), Inches(5.1), Inches(0.25),
                 "DETIK",
                 font_name=FONT_TITLE, font_size=Pt(18), color=PRIMARY, bold=True,
                 alignment=PP_ALIGN.CENTER)

    add_text_box(slide, right_x + Inches(0.2), Inches(2.6), Inches(5.1), Inches(0.3),
                 "Robot berhasil menavigasi dari Region A ke Region C\n"
                 "melalui Region B secara otonom penuh.",
                 font_size=Pt(11), color=BODY, alignment=PP_ALIGN.CENTER,
                 line_spacing=1.3)

    # Component integration box
    int_box = add_rect(slide, right_x, Inches(3.65), Inches(5.5), Inches(1.4),
                       fill_color=BOX_FILL, corner_radius=Cm(0.15))
    add_text_box(slide, right_x + Inches(0.2), Inches(3.7), Inches(5.1), Inches(0.25),
                 "Semua Komponen Bekerja Terintegrasi",
                 font_name=FONT_TITLE, font_size=Pt(13), color=HEADING, bold=True,
                 alignment=PP_ALIGN.CENTER)

    integrations = [
        "✓  ICP Localization → estimasi pose real-time",
        "✓  Costmap Transisi → perpindahan antar region",
        "✓  A* Global Planner → rute multi-region",
        "✓  DWA Local Planner → trajectory + obstacle avoidance",
    ]

    inty = Inches(4.0)
    for item in integrations:
        add_text_box(slide, right_x + Inches(0.3), inty, Inches(5.0), Inches(0.22),
                     item, font_size=Pt(10), color=BODY, line_spacing=1.2)
        inty += Inches(0.24)

    add_slide_number(slide, 15)
    add_footer(slide)


def slide_conclusion(prs):
    """Slide 16: Kesimpulan."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(3.5), Inches(0.55),
                 "KESIMPULAN", font_name=FONT_TITLE, font_size=Pt(30),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(1.8))

    conclusions = [
        ("1", "Layered costmap berhasil merepresentasikan lingkungan\nmulti-lantai sebagai kumpulan peta 2D region", SECONDARY),
        ("2", "ICP localization akurat untuk navigasi, dengan peningkatan\nerror pada lantai tidak rata dan region kompleks", SECONDARY),
        ("3", "Cost Scaling Factor 100 menghasilkan jalur terpendek\ndengan tetap menghindari obstacle", ORANGE),
        ("4", "Costmap transisi berhasil menggabungkan region pada\nradius transisi minimal 0.26 meter", SECONDARY),
        ("5", "DWA Planner mampu mengakomodasi obstacle tidak\ndiketahui dan menghasilkan trajectory aman", ORANGE),
    ]

    card_w = Inches(3.55)
    card_h = Inches(2.2)
    positions = [
        (MARGIN, Inches(1.15)),
        (MARGIN + card_w + Inches(0.25), Inches(1.15)),
        (MARGIN + 2 * (card_w + Inches(0.25)), Inches(1.15)),
        (MARGIN + Inches(1.9), Inches(3.6)),
        (MARGIN + card_w + Inches(0.25) + Inches(1.9), Inches(3.6)),
    ]

    for (x, y), (num, desc, color) in zip(positions, conclusions):
        card = add_rect(slide, x, y, card_w, card_h,
                        fill_color=BOX_FILL, corner_radius=Cm(0.15))
        # Big number background
        num_bg = add_rect(slide, x, y, card_w, Inches(0.6), fill_color=color,
                          corner_radius=Cm(0.15))
        add_text_box(slide, x, y + Inches(0.05), card_w, Inches(0.5),
                     num, font_name=FONT_TITLE, font_size=Pt(26),
                     color=WHITE, bold=True, alignment=PP_ALIGN.CENTER)
        add_text_box(slide, x + Inches(0.2), y + Inches(0.8),
                     card_w - Inches(0.4), Inches(1.2),
                     desc, font_size=Pt(12), color=BODY, line_spacing=1.45)

    add_slide_number(slide, 16)
    add_footer(slide)


def slide_future_work(prs):
    """Slide 17: Saran / Future Work."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    add_text_box(slide, MARGIN, Inches(0.35), Inches(4), Inches(0.55),
                 "SARAN PENGEMBANGAN", font_name=FONT_TITLE, font_size=Pt(30),
                 color=HEADING, bold=True)
    add_divider(slide, MARGIN, Inches(0.85), Inches(2.0))

    suggestions = [
        ("1", "Prekomputasi KNN per Region",
         "Parameter radius dan jumlah nearest neighbors\ndapat disetel independen per region untuk\nakurasi ICP yang lebih optimal.",
         PRIMARY),
        ("2", "Fusion ICP + IMU",
         "Kompensasi lonjakan error ICP di zona transisi\ndengan data IMU saat fitur LiDAR terbatas.",
         SECONDARY),
        ("3", "Integrasi Depth Camera",
         "Keterbatasan LiDAR 2D dalam mendeteksi\nobstacle vertikal dapat dilengkapi dengan\ndata visual dari depth sensor.",
         SECONDARY),
        ("4", "Pengujian pada Robot Fisik",
         "Validasi sistem di lingkungan nyata setelah\nterbukti berhasil di lingkungan simulasi Mujoco.",
         ORANGE),
    ]

    card_w = Inches(5.6)
    card_h = Inches(2.1)
    positions_sug = [
        (MARGIN, Inches(1.15)),
        (MARGIN + card_w + Inches(0.3), Inches(1.15)),
        (MARGIN, Inches(3.5)),
        (MARGIN + card_w + Inches(0.3), Inches(3.5)),
    ]

    for (x, y), (num, title, desc, color) in zip(positions_sug, suggestions):
        card = add_rect(slide, x, y, card_w, card_h,
                        fill_color=BOX_FILL, corner_radius=Cm(0.15))
        add_rect(slide, x, y, card_w, Pt(4), fill_color=color)
        add_text_box(slide, x + Inches(0.2), y + Inches(0.1),
                     Inches(0.4), Inches(0.35),
                     num, font_name=FONT_TITLE, font_size=Pt(20),
                     color=color, bold=True)
        add_text_box(slide, x + Inches(0.6), y + Inches(0.1),
                     card_w - Inches(0.8), Inches(0.35),
                     title, font_name=FONT_TITLE, font_size=Pt(13),
                     color=HEADING, bold=True)
        add_text_box(slide, x + Inches(0.2), y + Inches(0.65),
                     card_w - Inches(0.4), Inches(1.3),
                     desc, font_size=Pt(11), color=BODY, line_spacing=1.5)

    add_slide_number(slide, 17)
    add_footer(slide)


def slide_thanks(prs):
    """Slide 18: Penutup / Thank You."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, DARK_BG)

    # Decorative line
    add_rect(slide, SLIDE_W / 2 - Inches(1.5), Inches(1.2), Inches(3.0), Pt(3), fill_color=ORANGE)

    add_text_box(slide, Inches(0), Inches(1.5), SLIDE_W, Inches(1.0),
                 "TERIMA KASIH", font_name=FONT_TITLE, font_size=Pt(42),
                 color=WHITE, bold=True, alignment=PP_ALIGN.CENTER)

    add_text_box(slide, Inches(0), Inches(2.8), SLIDE_W, Inches(0.5),
                 "Bagas Surya Wirawan  ·  NRP. 5022221026",
                 font_name=FONT_TITLE, font_size=Pt(18),
                 color=RGBColor(0xBB, 0xD5, 0xEC),
                 alignment=PP_ALIGN.CENTER)

    add_text_box(slide, Inches(0), Inches(3.5), SLIDE_W, Inches(1.5),
                 "Dosen Pembimbing:\n"
                 "Dr. Ir. Djoko Purwanto, M.Eng.\n"
                 "Fajar Budiman, S.T., M.Sc.",
                 font_name=FONT_BODY, font_size=Pt(14),
                 color=RGBColor(0x99, 0xBB, 0xDD),
                 alignment=PP_ALIGN.CENTER, line_spacing=1.4)

    add_text_box(slide, Inches(0), Inches(5.3), SLIDE_W, Inches(1.0),
                 "Departemen Teknik Elektro\n"
                 "Fakultas Teknologi Elektro dan Informatika Cerdas\n"
                 "Institut Teknologi Sepuluh Nopember\n"
                 "Surabaya · 2026",
                 font_name=FONT_BODY, font_size=Pt(12),
                 color=RGBColor(0x88, 0xAA, 0xCC),
                 alignment=PP_ALIGN.CENTER, line_spacing=1.4)

    # Bottom decorative bars
    for i, color in enumerate([PRIMARY, SECONDARY, ORANGE]):
        bar_w = Inches(3.5)
        add_rect(slide, SLIDE_W / 2 - Inches(5.2) + i * (bar_w + Inches(0.1)),
                 SLIDE_H - Inches(0.35), bar_w, Pt(2), fill_color=color)


# =============================================================================
# MAIN
# =============================================================================

def main():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    # Build all slides
    slide_title(prs)
    slide_outline(prs)
    slide_background(prs)
    slide_problem(prs)
    slide_objectives(prs)
    slide_literature(prs)
    slide_system_overview(prs)
    slide_map_processing(prs)
    slide_costmap_structure(prs)
    slide_icp(prs)
    slide_path_planning(prs)
    slide_dwa(prs)
    slide_arena(prs)
    slide_results_icp_costmap(prs)
    slide_results_navigation(prs)
    slide_conclusion(prs)
    slide_future_work(prs)
    slide_thanks(prs)

    output_path = "/home/bagas/Documents/TUGAS-AKHIR/Presentasi_Sidang_TA.pptx"
    prs.save(output_path)
    print(f"Presentation saved to: {output_path}")
    print(f"Total slides: {len(prs.slides)}")


if __name__ == "__main__":
    main()
