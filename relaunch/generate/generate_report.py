"""
generate_report.py
BrightWork Realty Advocates — Property Report PDF Generator

Generates an 8-page PDF report from a content dict (produced by the Claude API)
and a property data dict (from properties.csv).

Called by batch_generate.py. Can also be run standalone for testing.

Usage:
    from generate_report import generate_report
    generate_report(content, property_data, assets_dir='./assets', output_path='./output/test.pdf')
"""

import os
import textwrap
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable, Frame
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from pypdf import PdfWriter, PdfReader
from PIL import Image as PILImage


# ─────────────────────────────────────────────────────────────────────────────
# BRAND COLORS
# ─────────────────────────────────────────────────────────────────────────────
DARK_TEAL   = HexColor('#005d7a')
BRIGHT_BLUE = HexColor('#00aedb')
YELLOW      = HexColor('#ffe200')
LIGHT_TEAL  = HexColor('#e6f4f8')
MID_TEAL    = HexColor('#b8dce8')
NEAR_BLACK  = HexColor('#222222')
MED_GRAY    = HexColor('#555555')
LIGHT_GRAY  = HexColor('#cccccc')

# Page geometry (all values in points: 1 inch = 72 points)
PW, PH = letter       # 612 x 792
M  = 54               # margin (0.75 inch — gives a bit more content room than 1")
CW = PW - 2 * M      # content width
LOGO_WIDTH = 120

# ─────────────────────────────────────────────────────────────────────────────
# FONT SETUP
# Tries to load custom fonts from assets/fonts/
# Falls back cleanly to Helvetica on any system without them.
# To use custom fonts, download from Google Fonts and place in assets/fonts/:
#   Montserrat-Bold.ttf, OpenSans-Regular.ttf,
#   OpenSans-Bold.ttf, OpenSans-Italic.ttf
# ─────────────────────────────────────────────────────────────────────────────
_FONT_MAP = {}


def _setup_fonts(assets_dir):
    global _FONT_MAP
    if _FONT_MAP:
        return  # already done

    font_dir = os.path.join(assets_dir, 'fonts')
    candidates = {
        'H':  ('Montserrat-Bold.ttf',  'Montserrat-Bold'),
        'B':  ('OpenSans-Regular.ttf', 'OpenSans'),
        'BB': ('OpenSans-Bold.ttf',    'OpenSans-Bold'),
        'BI': ('OpenSans-Italic.ttf',  'OpenSans-Italic'),
    }
    fallbacks = {
        'H': 'Helvetica-Bold',
        'B': 'Helvetica',
        'BB': 'Helvetica-Bold',
        'BI': 'Helvetica-Oblique',
    }
    for key, (fname, regname) in candidates.items():
        path = os.path.join(font_dir, fname)
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(regname, path))
                _FONT_MAP[key] = regname
            except Exception:
                _FONT_MAP[key] = fallbacks[key]
        else:
            _FONT_MAP[key] = fallbacks[key]


def f(role):
    """Return font name for a role. Call after _setup_fonts()."""
    return _FONT_MAP.get(role, 'Helvetica')


# ─────────────────────────────────────────────────────────────────────────────
# CANVAS HELPER FUNCTIONS
# Used for drawing fixed-position elements: logo, rules, headers, footers
# ─────────────────────────────────────────────────────────────────────────────

def _draw_logo(c, x, y_top, assets_dir, width=148):
    """Draw the BrightWork logo. y_top is the top edge of the logo area."""
    logo_path = os.path.join(assets_dir, 'logo.jpg')
    if os.path.exists(logo_path):
        try:
            img = PILImage.open(logo_path)
            aspect = img.height / img.width
            h = width * aspect
            c.drawImage(logo_path, x, y_top - h, width=width, height=h,
                        preserveAspectRatio=True, mask='auto')
            return h
        except Exception:
            pass
    # Text fallback if logo file not found
    c.setFont(f('H'), 16)
    c.setFillColor(DARK_TEAL)
    c.drawString(x, y_top - 20, 'BRIGHTWORK')
    c.setFont(f('B'), 9)
    c.setFillColor(MED_GRAY)
    c.drawString(x, y_top - 33, 'REALTY ADVOCATES')
    return 36


def _draw_blue_rule(c, y, x1=None, x2=None, weight=0.8):
    c.setStrokeColor(BRIGHT_BLUE)
    c.setLineWidth(weight)
    c.line(x1 or M, y, x2 or (PW - M), y)


def _draw_yellow_rule(c, y, x1=None, x2=None, weight=2.5):
    c.setStrokeColor(YELLOW)
    c.setLineWidth(weight)
    c.line(x1 or M, y, x2 or (PW - M), y)


def _draw_footer(c, page_num=None):
    """Draw footer. Pass page_num=None to omit page number (e.g. letter page)."""
    y = 28
    c.setFont(f('B'), 7)
    c.setFillColor(MED_GRAY)
    c.drawString(M, y,
        'BrightWork Realty Advocates  |  brightworkrealty.com  |  DRE# 02014153  |  Moraga \u00b7 Lafayette \u00b7 Orinda')
    if page_num is not None:
        c.drawRightString(PW - M, y, f'Page {page_num}')
    c.setStrokeColor(LIGHT_GRAY)
    c.setLineWidth(0.4)
    c.line(M, y + 9, PW - M, y + 9)


def _draw_report_header(c, address_line, page_num, assets_dir):
    """Header for body pages (3+): logo left, address breadcrumb right, rule below both."""
    logo_h = _draw_logo(c, M, PH - 10, assets_dir, width=LOGO_WIDTH)
    rule_y = PH - 10 - logo_h - 10   # 10pt gap below logo bottom
    # Address sits vertically centred in the logo zone, right-aligned
    c.setFont(f('B'), 7.5)
    c.setFillColor(MED_GRAY)
    c.drawRightString(PW - M, PH - 10 - logo_h * 0.55, address_line)
    _draw_blue_rule(c, rule_y)
    _draw_footer(c, page_num)


def _draw_section_label(c, x, y, text, width=None):
    """
    Draws a section header label: yellow left accent bar + light teal fill.
    Returns the height used.
    """
    w = width or CW
    h = 18
    bar_w = 4
    # Light teal background
    c.setFillColor(LIGHT_TEAL)
    c.rect(x, y - h, w, h, fill=1, stroke=0)
    # Yellow left accent
    c.setFillColor(YELLOW)
    c.rect(x, y - h, bar_w, h, fill=1, stroke=0)
    # Label text
    c.setFont(f('BB'), 7.5)
    c.setFillColor(DARK_TEAL)
    c.drawString(x + bar_w + 7, y - h + 5, text.upper())
    return h


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM PLATYPUS FLOWABLES
# These are reusable building blocks for the report body pages (3-8).
# ─────────────────────────────────────────────────────────────────────────────

class SectionLabel(Flowable):
    """Yellow-accented section header label."""
    def __init__(self, text, width=None):
        super().__init__()
        self.label_text = text
        self._width = width or CW
        self.height = 20

    def draw(self):
        c = self.canv
        w, h = self._width, 18
        # Teal fill
        c.setFillColor(LIGHT_TEAL)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        # Yellow left bar
        c.setFillColor(YELLOW)
        c.rect(0, 0, 4, h, fill=1, stroke=0)
        # Text
        c.setFont(f('BB'), 7.5)
        c.setFillColor(DARK_TEAL)
        c.drawString(11, 5, self.label_text.upper())

    def wrap(self, avail_w, avail_h):
        return (self._width, self.height)


class CalloutBox(Flowable):
    """
    BrightWork Difference callout box:
    Light teal fill, mid-teal left border, bold label + italic body text.
    """
    def __init__(self, label, body_text, width=None):
        super().__init__()
        self.label = label
        self.body_text = body_text
        self._width = width or CW
        # Estimate height based on text length
        chars_per_line = int(self._width / 5.5)
        lines = max(3, len(body_text) // chars_per_line + 1)
        self.height = 14 + lines * 13 + 14

    def draw(self):
        c = self.canv
        w = self._width
        h = self.height
        border_w = 4
        pad = 10

        # Light teal background
        c.setFillColor(LIGHT_TEAL)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        # Mid-teal left border
        c.setFillColor(MID_TEAL)
        c.rect(0, 0, border_w, h, fill=1, stroke=0)

        # Label (dark teal + slightly larger for print contrast)
        c.setFont(f('BB'), 8.5)
        c.setFillColor(DARK_TEAL)
        c.drawString(border_w + pad, h - 14, f'\u2733 {self.label}')

        # Body text (italic, wrapped)
        text_x = border_w + pad
        text_w = w - border_w - pad * 2
        wrapped = textwrap.wrap(self.body_text, width=int(text_w / 5.2))
        text_y = h - 28
        c.setFont(f('BI'), 9)
        c.setFillColor(DARK_TEAL)
        for line in wrapped:
            if text_y < 8:
                break
            c.drawString(text_x, text_y, line)
            text_y -= 13

    def wrap(self, avail_w, avail_h):
        return (self._width, self.height)


class StatsBlock(Flowable):
    """Three-column statistics row with large number values."""
    def __init__(self, stats, width=None):
        """stats: list of (value, label) tuples, max 3."""
        super().__init__()
        self.stats = stats[:3]
        self._width = width or CW
        self.height = 56

    def draw(self):
        c = self.canv
        col_w = self._width / 3
        # Yellow top rule
        c.setStrokeColor(YELLOW)
        c.setLineWidth(2)
        c.line(0, self.height, self._width, self.height)
        # Yellow bottom rule
        c.line(0, 0, self._width, 0)

        for i, (value, label) in enumerate(self.stats):
            cx = col_w * i + col_w / 2
            # Large value
            c.setFont(f('H'), 22)
            c.setFillColor(DARK_TEAL)
            c.drawCentredString(cx, 24, str(value))
            # Small label
            c.setFont(f('B'), 8)
            c.setFillColor(MED_GRAY)
            c.drawCentredString(cx, 11, label)

    def wrap(self, avail_w, avail_h):
        return (self._width, self.height)


# ─────────────────────────────────────────────────────────────────────────────
# PARAGRAPH STYLES
# ─────────────────────────────────────────────────────────────────────────────

def _make_styles():
    return {
        'body': ParagraphStyle('body',
            fontName=f('B'), fontSize=9.5, leading=15,
            textColor=NEAR_BLACK, alignment=TA_JUSTIFY,
            spaceAfter=8),

        'body_left': ParagraphStyle('body_left',
            fontName=f('B'), fontSize=9.5, leading=15,
            textColor=NEAR_BLACK, alignment=TA_LEFT,
            spaceAfter=8),

        'h1': ParagraphStyle('h1',
            fontName=f('H'), fontSize=22, leading=28,
            textColor=DARK_TEAL, spaceAfter=4),

        'h2': ParagraphStyle('h2',
            fontName=f('H'), fontSize=16, leading=22,
            textColor=DARK_TEAL, spaceAfter=6),

        'h3': ParagraphStyle('h3',
            fontName=f('BB'), fontSize=11, leading=16,
            textColor=BRIGHT_BLUE, spaceAfter=4),

        'pillar_title': ParagraphStyle('pillar_title',
            fontName=f('BB'), fontSize=11, leading=16,
            textColor=BRIGHT_BLUE, spaceAfter=4),

        'friction_title': ParagraphStyle('friction_title',
            fontName=f('BB'), fontSize=10.5, leading=15,
            textColor=BRIGHT_BLUE, spaceAfter=4),

        'small_gray': ParagraphStyle('small_gray',
            fontName=f('B'), fontSize=8, leading=12,
            textColor=MED_GRAY, spaceAfter=4),

        'italic_teal': ParagraphStyle('italic_teal',
            fontName=f('BI'), fontSize=10, leading=14,
            textColor=DARK_TEAL, spaceAfter=4),

        'caption': ParagraphStyle('caption',
            fontName=f('BI'), fontSize=9, leading=13,
            textColor=MED_GRAY, spaceAfter=6, alignment=TA_CENTER),

        'verdict': ParagraphStyle('verdict',
            fontName=f('B'), fontSize=9.5, leading=15,
            textColor=NEAR_BLACK, alignment=TA_LEFT, spaceAfter=8),

        'cta': ParagraphStyle('cta',
            fontName=f('BB'), fontSize=11, leading=16,
            textColor=DARK_TEAL, spaceAfter=4),

        'bullet': ParagraphStyle('bullet',
            fontName=f('B'), fontSize=9.5, leading=14,
            textColor=NEAR_BLACK, leftIndent=12, spaceAfter=6),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1: COVER LETTER
# ─────────────────────────────────────────────────────────────────────────────

def _draw_letter_signature_block(c, closing_y, closing_text, assets_dir):
    """Draw closing line, signature image, and contact block below the letter body."""
    sig_w, sig_h = 150, 52
    closing_to_sig = 12

    c.setFont(f('B'), 10)
    c.setFillColor(NEAR_BLACK)
    c.drawString(M, closing_y, closing_text)

    sig_y = closing_y - closing_to_sig - sig_h
    sig_path = os.path.join(assets_dir, 'signature.png')
    if os.path.exists(sig_path):
        c.drawImage(sig_path, M, sig_y, width=sig_w, height=sig_h, mask='auto')

    name_y = sig_y - 9
    c.setFont(f('BB'), 11)
    c.setFillColor(DARK_TEAL)
    c.drawString(M, name_y, 'Ben Olsen')

    c.setFont(f('B'), 8.5)
    c.setFillColor(NEAR_BLACK)
    c.drawString(M, name_y - 13, 'REALTOR \u00b7 BrightWork Realty Advocates')
    c.drawString(M, name_y - 25, '(925) 255-9727  \u00b7  brightworkrealty.com')
    c.drawString(M, name_y - 37, '455 Moraga Road, Suite I  \u00b7  Moraga, CA 94556')


def _build_letter_page(content, property_data, assets_dir):
    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=letter)
    S = _make_styles()

    # Logo + blue rule with proper spacing
    logo_h = _draw_logo(c, M, PH - 14, assets_dir, width=LOGO_WIDTH)
    rule_y = PH - 14 - logo_h - 10

    # Date
    y = rule_y - 20
    c.setFont(f('B'), 10)
    c.setFillColor(NEAR_BLACK)
    c.drawString(M, y, property_data.get('batch_date', 'June 2026'))

    # Salutation
    y -= 32
    c.setFont(f('BB'), 10)
    c.setFillColor(NEAR_BLACK)
    c.drawString(M, y, content['letter']['salutation'])

    # Letter body — flow from salutation, then place signature directly below
    y -= 20
    body_top = y
    footer_zone = 50
    min_closing_y = 165

    story = []
    for para in content['letter']['paragraphs']:
        story.append(Paragraph(para, S['body_left']))
        story.append(Spacer(1, 4))

    letter_frame = Frame(
        M, footer_zone, CW, body_top - footer_zone,
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
    )
    letter_frame.addFromList(story, c)

    closing_y = max(min_closing_y, letter_frame._y - 20)
    _draw_letter_signature_block(c, closing_y, content['letter']['closing'], assets_dir)

    _draw_footer(c)   # no page number on letter page
    c.save()
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2: COVER PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _build_cover_page(content, property_data, assets_dir):
    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=letter)

    # Logo + yellow rule with proper spacing
    logo_h = _draw_logo(c, M, PH - 14, assets_dir, width=LOGO_WIDTH)
    _draw_yellow_rule(c, PH - 14 - logo_h - 10, weight=1.5)

    # Report title (italic blue)
    c.setFont(f('BI'), 13)
    c.setFillColor(BRIGHT_BLUE)
    c.drawString(M, PH - 14 - logo_h - 38, content['cover']['report_title'])

    # Address as large heading
    addr = property_data.get('address', '')
    # Truncate if very long
    if len(addr) > 35:
        parts = addr.split(',')
        addr_display = parts[0].strip()
    else:
        addr_display = addr.split(',')[0].strip()

    c.setFont(f('H'), 28)
    c.setFillColor(DARK_TEAL)
    c.drawString(M, PH - 14 - logo_h - 80, addr_display)

    # City, State Zip - fallback: extract city from address if not in data
    city = property_data.get('city', '')
    if not city:
        parts = property_data.get('address', '').split(',')
        if len(parts) >= 2:
            city = parts[1].strip()
    zip_code = property_data.get('zip', '')
    city_line = f"{city}, CA {zip_code}" if city else f"CA {zip_code}"
    c.setFont(f('B'), 13)
    c.setFillColor(DARK_TEAL)
    c.drawString(M, PH - 14 - logo_h - 104, city_line)

    # Blue rule
    _draw_blue_rule(c, PH - 14 - logo_h - 124)

    # Specs line - use the city we already resolved above
    beds  = property_data.get('beds', '')
    baths = property_data.get('baths', '')
    sqft  = property_data.get('sqft', '')
    specs = f"{beds} Beds  \u00b7  {baths} Baths  \u00b7  {sqft:,} Sq Ft  \u00b7  {city}" \
            if isinstance(sqft, int) else \
            f"{beds} Beds  \u00b7  {baths} Baths  \u00b7  {sqft} Sq Ft  \u00b7  {city}"

    c.setFont(f('BB'), 11)
    c.setFillColor(BRIGHT_BLUE)
    c.drawString(M, PH - 14 - logo_h - 148, specs)

    # Tagline
    c.setFont(f('BI'), 10.5)
    c.setFillColor(MED_GRAY)
    c.drawString(M, PH - 14 - logo_h - 168, content['cover']['tagline'])

    # Blue rule
    _draw_blue_rule(c, PH - 14 - logo_h - 188)

    # Prepared For / Presented By
    c.setFont(f('BB'), 10)
    c.setFillColor(NEAR_BLACK)
    c.drawString(M, PH - 14 - logo_h - 216, 'Prepared For:')
    c.setFont(f('B'), 10)
    c.drawString(M + 100, PH - 14 - logo_h - 216, f'The Owners of {addr_display}')

    c.setFont(f('BB'), 10)
    c.drawString(M, PH - 14 - logo_h - 236, 'Presented By:')
    c.setFont(f('B'), 10)
    c.drawString(M + 100, PH - 14 - logo_h - 236, 'Ben Olsen  \u00b7  BrightWork Realty Advocates')

    # No footer on cover page
    c.save()
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# PAGES 3-7: REPORT BODY (Platypus)
# ─────────────────────────────────────────────────────────────────────────────

class _ReportPageCanvas(rl_canvas.Canvas):
    """
    Custom canvas that draws the header/footer on every report body page.
    Page numbers start at 3 (letter=1, cover=2).
    """
    def __init__(self, filename, address_line, assets_dir, **kwargs):
        super().__init__(filename, **kwargs)
        self._saved_page_states = []
        self._address_line = address_line
        self._assets_dir = assets_dir

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            page_num = self._pageNumber + 2  # offset: 1=letter, 2=cover
            _draw_report_header(self, self._address_line, page_num, self._assets_dir)
            super().showPage()
        super().save()


def _build_report_body(content, property_data, assets_dir):
    """Builds report pages 3-8 (exec summary through disclaimer) as PDF bytes."""
    buffer = BytesIO()
    addr_line = property_data.get('address', '')
    S = _make_styles()

    # Header/footer strip: 75pt at top (logo + gap + rule), 38pt at bottom
    HEADER_H = 75
    FOOTER_H = 42

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=M, rightMargin=M,
        topMargin=HEADER_H, bottomMargin=FOOTER_H,
    )

    story = []
    exec_s = content.get('exec_summary', {})
    forensics = content.get('forensics', [])
    table_data = content.get('positioning_table', {})
    pillars = content.get('pillars', [])

    # ── PAGE 3: EXECUTIVE SUMMARY ────────────────────────────────────────────

    story.append(SectionLabel('Executive Summary'))
    story.append(Spacer(1, 10))

    story.append(Paragraph(exec_s.get('headline', ''), S['h2']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(exec_s.get('p1', ''), S['body']))
    story.append(Paragraph(exec_s.get('p2', ''), S['body']))
    story.append(Spacer(1, 10))

    # Stats block
    raw_stats = exec_s.get('stats', {})
    stats_data = [
        (raw_stats.get('list_price', '-'),    'List Price'),
        (raw_stats.get('price_per_sqft', '-'), 'Price Per Sq. Ft.'),
        (raw_stats.get('hoa', 'None'),         'HOA Fees'),
    ]
    story.append(StatsBlock(stats_data))
    story.append(Spacer(1, 12))
    story.append(Paragraph(exec_s.get('p3', ''), S['body']))
    story.append(Spacer(1, 14))

    # ── MARKET FORENSICS INTRO ───────────────────────────────────────────────
    story.append(SectionLabel('Market Forensics: Why It Didn\'t Sell'))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        'Every expired listing has a story. Here\'s what the listing history tells us '
        'about what held this one back, and what a different strategy would have done.',
        S['body']
    ))
    story.append(Spacer(1, 10))

    # ── PAGE 4: FRICTION POINTS ───────────────────────────────────────────────
    for friction in forensics:
        block = []
        block.append(Paragraph(friction.get('title', ''), S['friction_title']))
        block.append(Paragraph(friction.get('body', ''), S['body']))
        block.append(Spacer(1, 6))
        block.append(CalloutBox(
            friction.get('brightwork_contrast_label', 'THE BRIGHTWORK DIFFERENCE'),
            friction.get('brightwork_contrast', ''),
        ))
        block.append(Spacer(1, 14))
        story.append(KeepTogether(block))

    # ── PAGE 5: POSITIONING TABLE ─────────────────────────────────────────────
    subj_label   = table_data.get('subject_label', 'Subject Property')
    market_label = table_data.get('market_label', 'Market Context')
    rows = table_data.get('rows', [])

    pos_block = [
        SectionLabel('Positioning Analysis'),
        Spacer(1, 10),
    ]
    if rows:
        table_header = [
            Paragraph('<b>Metric</b>', S['small_gray']),
            Paragraph(f'<b>{subj_label}</b>', S['small_gray']),
            Paragraph(f'<b>{market_label}</b>', S['small_gray']),
        ]
        table_rows = [table_header]
        for row in rows:
            table_rows.append([
                Paragraph(row.get('metric', ''), S['body_left']),
                Paragraph(f"<b>{row.get('subject', '')}</b>", S['body_left']),
                Paragraph(row.get('market', ''), S['body_left']),
            ])

        col_widths = [CW * 0.26, CW * 0.30, CW * 0.44]
        t = Table(table_rows, colWidths=col_widths, repeatRows=1, hAlign='LEFT')

        style = TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0), MID_TEAL),
            ('TEXTCOLOR',   (0, 0), (-1, 0), DARK_TEAL),
            ('FONTNAME',    (0, 0), (-1, 0), f('BB')),
            ('FONTSIZE',    (0, 0), (-1, 0), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [LIGHT_TEAL, white]),
            ('TEXTCOLOR',   (1, 1), (1, -1), DARK_TEAL),
            ('FONTNAME',    (1, 1), (1, -1), f('BB')),
            ('GRID',        (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
            ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
            ('ALIGN',       (0, 0), (-1, -1), 'LEFT'),
            ('TOPPADDING',  (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',(0, 0), (-1, -1), 8),
        ])
        t.setStyle(style)
        pos_block.append(t)
        pos_block.append(Spacer(1, 8))

    story.append(KeepTogether(pos_block))

    verdict = table_data.get('verdict', '')
    if verdict:
        story.append(Paragraph(f'<b>The verdict:</b> {verdict}', S['verdict']))
    story.append(Spacer(1, 14))

    # ── RELAUNCH STRATEGY ────────────────────────────────────────────────────
    if pillars:
        first_pillar = pillars[0]
        strategy_block = [
            SectionLabel('The Relaunch Strategy: 3 Pillars'),
            Spacer(1, 8),
            Paragraph(
                'We don\'t re-list this home. We relaunch it with new media, a narrative '
                'that finally does it justice, and distribution designed for the buyer it deserves.',
                S['body']
            ),
            Spacer(1, 8),
            Paragraph(first_pillar.get('title', ''), S['pillar_title']),
            Paragraph(first_pillar.get('body', ''), S['body']),
            Spacer(1, 10),
        ]
        story.append(KeepTogether(strategy_block))

        for pillar in pillars[1:]:
            block = [
                Paragraph(pillar.get('title', ''), S['pillar_title']),
                Paragraph(pillar.get('body', ''), S['body']),
                Spacer(1, 10),
            ]
            story.append(KeepTogether(block))
    else:
        story.append(SectionLabel('The Relaunch Strategy: 3 Pillars'))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            'We don\'t re-list this home. We relaunch it with new media, a narrative '
            'that finally does it justice, and distribution designed for the buyer it deserves.',
            S['body']
        ))
        story.append(Spacer(1, 8))

    # ── PAGE 6: QUIET LISTING (static content) ───────────────────────────────
    story.append(PageBreak())
    story.append(SectionLabel('A Different Option: The Quiet Listing'))
    story.append(Spacer(1, 10))

    story.append(Paragraph('Sell Without the Disruption', S['h2']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'A traditional listing puts a sign in your yard, opens your door to strangers '
        'every weekend, and puts your home\'s history on public record. For a home that '
        'already went through one listing cycle, there\'s a better starting point.',
        S['body']
    ))
    story.append(Paragraph(
        'BrightWork maintains an active private buyer list through our off-market platform. '
        'These are Bay Area buyers who\'ve opted in specifically to receive property alerts '
        'before anything hits Zillow. They\'re motivated, pre-qualified, and they believe an '
        'off-market home represents a real opportunity, which means they engage seriously.',
        S['body']
    ))
    story.append(Spacer(1, 8))

    quiet_points = [
        ('<b>No public days on market.</b> The prior listing history stays private. '
         'A new buyer sees none of it.'),
        ('<b>No sign, no open houses, no disruption.</b> The sale is a private conversation '
         'between a motivated buyer and a motivated seller.'),
        ('<b>Option to go public anytime.</b> If the right off-market offer doesn\'t '
         'materialize in an agreed window, we transition directly into a full relaunch '
         'strategy with no time lost.'),
    ]
    for pt in quiet_points:
        story.append(Paragraph(
            f'<font color="#005d7a" size="13"><b>\u2733</b></font>  {pt}', S['bullet']))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 10))

    # How it works callout
    story.append(CalloutBox(
        'HOW IT WORKS',
        'We alert our private buyer list through offmarket.brightworkrealty.com - '
        'Bay Area buyers specifically seeking properties before they go public. If a serious '
        'match emerges within the agreed window, we negotiate and close privately. If not, '
        'we launch the full relaunch strategy immediately, with clean momentum and no '
        'days-on-market exposure.'
    ))
    story.append(Spacer(1, 14))

    # Timeline
    story.append(SectionLabel('Timeline: The BrightWork Smart Way'))
    story.append(Spacer(1, 10))

    phases = [
        ('Phase 1 - Pre-Market Preparation (Weeks 1\u20132)',
         'Staging, full media production, and a Coming Soon campaign - or a quiet listing '
         'launch to our private buyer network, depending on your preference.'),
        ('Phase 2 - Strategic Launch (Week 3)',
         'Thursday launch on Zillow Showcase with the full media package in premium placement. '
         'Targeted SF/Oakland digital ads go live the same day.'),
        ('Phase 3 - Momentum Management (Weeks 4\u20135)',
         'Active follow-up on every save, inquiry, and open house visitor. Final Offer gives '
         'serious buyers a transparent channel to submit competitive offers.'),
        ('Phase 4 - The Close (Weeks 6\u20137)',
         'We engineer competition, not just field offers. Our process keeps both sides of the '
         'transaction moving cleanly toward a close.'),
    ]

    for title, body in phases:
        story.append(Paragraph(f'<b>{title}</b>', S['body_left']))
        story.append(Paragraph(body, S['body']))
        story.append(HRFlowable(width=CW, thickness=0.3, color=LIGHT_GRAY,
                                spaceAfter=8, spaceBefore=0))

    # ── PAGE 7: WHY BRIGHTWORK ───────────────────────────────────────────────
    story.append(SectionLabel('Why BrightWork Realty Advocates'))
    story.append(Spacer(1, 10))

    why_points = [
        ('Deep local roots',
         '45+ years in Moraga, Lafayette, and Orinda. Ground-level knowledge '
         'of what buyers in each community are actually paying for.'),
        ('Premium marketing as a baseline',
         'Cinematic photography, floor plans, 3D tours, and Sky Tours on every listing. '
         'Not a luxury add-on.'),
        ('Portal dominance',
         'Zillow Showcase and homes.com premium placement. More views, enhanced listing '
         'pages, all leads to your team.'),
        ('Modern offer tools',
         'Final Offer gives buyers a transparent path to engage and gives you real-time '
         'demand data in one place.'),
        ('True advocacy',
         'We don\'t re-list homes. We forensically review what went wrong and rebuild the '
         'strategy from the ground up.'),
    ]

    for label, body in why_points:
        story.append(Paragraph(
            f'<font color="#005d7a" size="13"><b>\u2733</b></font>  <b>{label}:</b> {body}',
            S['bullet']))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 18))

    # CTA closing
    story.append(HRFlowable(width=CW, thickness=1.5, color=YELLOW,
                             spaceAfter=12, spaceBefore=0))
    story.append(Paragraph(
        f'This home has real assets that the market never got to properly evaluate. '
        f'That\'s a correctable problem. The window to correct it is still open.',
        S['body']
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        '<b>Ready to talk?</b>  brightworkrealty.com  \u00b7  (925) 255-9727',
        S['cta']
    ))
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width=CW, thickness=1.5, color=YELLOW,
                             spaceAfter=12, spaceBefore=0))
    story.append(Paragraph(
        'Scan to see what a relaunch looks like for your home:  '
        'relaunch.brightworkrealty.com',
        S['small_gray']
    ))
    story.append(Spacer(1, 48))

    # ── PAGE 8: DISCLAIMER ───────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Spacer(1, 40))
    story.append(Paragraph('Important Notice', S['h3']))
    story.append(Spacer(1, 10))

    disclaimer_paras = [
        'If you have entered into a listing agreement or active representation agreement '
        'with a licensed real estate agent in connection with this property, please '
        'disregard this mailing.',

        'BrightWork Realty Advocates is a licensed real estate team operated by Ben Olsen, '
        'REALTOR, California DRE License #01409268. This communication is not intended '
        'to solicit properties currently listed for sale or under active representation.',

        'The market analysis and strategic observations contained in this report are based on '
        'publicly available listing data and BrightWork\'s professional assessment of market '
        'conditions. They are not a formal appraisal and should not be relied upon as a '
        'certified valuation.',

        'All property data referenced in this report was obtained from public records and MLS '
        'history. BrightWork Realty Advocates makes no warranty as to the accuracy of third-'
        'party data sources.',
    ]

    for para in disclaimer_paras:
        story.append(Paragraph(para, S['small_gray']))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        'brightworkrealty.com  \u00b7  (925) 255-9727  \u00b7  '
        '455 Moraga Road, Suite I, Moraga, CA 94556',
        S['small_gray']
    ))

    # Build
    def _make_canvas(filename, **kw):
        kw.pop('pagesize', None)  # avoid duplicate kwarg
        return _ReportPageCanvas(
            filename,
            address_line=addr_line,
            assets_dir=assets_dir,
            pagesize=letter,
            **kw
        )

    doc.build(story, canvasmaker=_make_canvas)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# PDF MERGE UTILITY
# ─────────────────────────────────────────────────────────────────────────────

def _merge_pdfs(*pdf_bytes_list):
    """Merge multiple PDF byte strings into one. Returns bytes."""
    writer = PdfWriter()
    for pdf_bytes in pdf_bytes_list:
        if not pdf_bytes:
            continue
        reader = PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def generate_report(content, property_data, assets_dir='./assets', output_path=None):
    """
    Generate a complete BrightWork property report packet.

    Args:
        content (dict):        Parsed JSON from the Claude API call.
        property_data (dict):  Row from properties.csv, enriched with computed fields.
        assets_dir (str):      Path to assets folder (logo, signature, fonts).
        output_path (str):     Where to write the final PDF. If None, returns bytes.

    Returns:
        bytes if output_path is None, else writes file and returns output_path.
    """
    _setup_fonts(assets_dir)

    letter_bytes  = _build_letter_page(content, property_data, assets_dir)
    cover_bytes   = _build_cover_page(content, property_data, assets_dir)
    body_bytes    = _build_report_body(content, property_data, assets_dir)

    final_bytes = _merge_pdfs(letter_bytes, cover_bytes, body_bytes)

    if output_path:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_path, 'wb') as fh:
            fh.write(final_bytes)
        return output_path
    return final_bytes


# ─────────────────────────────────────────────────────────────────────────────
# QUICK TEST (run this file directly to generate a sample report)
# python generate_report.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    SAMPLE_CONTENT = {
        'letter': {
            'salutation': 'Dear Mr. and Mrs. Floyd,',
            'paragraphs': [
                "I've been watching 1409 Rimer Drive and I'll be direct — a home on a "
                ".43-acre cul-de-sac lot with two family rooms and 3,100 square feet "
                "doesn't sit on the market without a reason. The lot alone is rare in "
                "Moraga. This one should have found its buyer.",
                "When I looked more closely at the listing, I think I understand what "
                "happened. The marketing described the home the way someone fills out "
                "a form. It never explained what life actually looks like on that lot — "
                "the space, the privacy, the two family rooms that give you options most "
                "Moraga homes simply can't. Buyers paying this price need to feel "
                "something before they schedule a showing. This listing didn't give "
                "them much to feel.",
                "I've put together a short analysis of what the listing history suggests "
                "went wrong and how I'd approach it differently. The fundamentals here "
                "are solid. The strategy just needs to match what the property actually offers.",
                "Take a look, and I'd welcome the chance to walk through it with you."
            ],
            'closing': 'With respect,',
        },
        'cover': {
            'report_title': 'The Path to Sold:',
            'tagline': 'The Blueprint for a Successful Sale',
        },
        'exec_summary': {
            'headline': 'A Home Built for How Families Actually Live — and a Listing That Described It Plainly',
            'p1': (
                '1409 Rimer Drive has the kind of fundamentals Moraga buyers look for: '
                'a .43-acre level lot on a quiet cul-de-sac, two separate family rooms, '
                'four large bedrooms, and a floor plan that gives a growing family real '
                'flexibility. At $2,500,000, those assets can support that price — but '
                'only if buyers understand what they are actually getting.'
            ),
            'p2': (
                'The listing was withdrawn without a sale. The description gave buyers '
                'a list of facts with no story attached. In a market where families are '
                'comparing Moraga options carefully, a listing that reads like a data '
                'sheet gets skipped. The home deserved a better introduction.'
            ),
            'stats': {
                'list_price': '$2,500,000',
                'price_per_sqft': '$803',
                'hoa': 'None',
            },
            'p3': (
                'The goal is a relaunch that leads with the lot, the layout, and the '
                'lifestyle — reaching the specific Moraga buyer who is looking for exactly '
                'this kind of space and has the budget to act on it.'
            ),
        },
        'forensics': [
            {
                'title': 'Friction #1: The Listing Never Explained What .43 Acres Actually Buys',
                'body': (
                    'A nearly half-acre level cul-de-sac lot is a genuine rarity in Moraga — '
                    'most buyers can describe what they want but can\'t find it. If the listing '
                    'photos didn\'t lead with that lot, and the remarks didn\'t spend a paragraph '
                    'on what outdoor life looks like here, buyers browsing online had no reason '
                    'to prioritize this home over a newer one with a smaller yard. The asset '
                    'was there. The story wasn\'t.'
                ),
                'brightwork_contrast_label': 'THE BRIGHTWORK DIFFERENCE',
                'brightwork_contrast': (
                    'A Sky Tour shows exactly what .43 flat acres looks like from above — '
                    'context that satellite images and standard photography can\'t provide. '
                    'It\'s the kind of visual that makes buyers stop scrolling.'
                ),
            },
            {
                'title': 'Friction #2: Two Family Rooms Is a Feature That Requires a Story',
                'body': (
                    'Most Moraga buyers aren\'t searching the MLS for "two family rooms." '
                    'They\'re searching for space, flexibility, and a home that works for '
                    'their specific life stage. The listing had "2 fam rms" in a line of '
                    'abbreviations. That\'s not the same as helping a buyer picture what '
                    'those two rooms actually solve for their family — a playroom and a '
                    'TV room, a home office and a den, a teenager\'s space that isn\'t in '
                    'the main living area. The feature was listed. The benefit was never explained.'
                ),
                'brightwork_contrast_label': 'THE BRIGHTWORK DIFFERENCE',
                'brightwork_contrast': (
                    'Our listing remarks are written the way a buyer\'s agent describes a home — '
                    'specific, vivid, and focused on what makes it work. Zillow Showcase puts '
                    'that narrative in front of buyers at the top of their search results.'
                ),
            },
            {
                'title': 'Friction #3: The Buyer Pool at This Price Needed to Be Found, Not Waited For',
                'body': (
                    'At $2,500,000 in Moraga, the buyer pool is real but selective. These '
                    'are often families relocating from San Francisco or the Peninsula who '
                    'have researched the market extensively before they make contact. A '
                    'standard MLS listing and a wait-and-see approach doesn\'t reach them '
                    'early enough in their process. By the time they find the listing on '
                    'Zillow, they may already have a shortlist of three other homes.'
                ),
                'brightwork_contrast_label': 'THE BRIGHTWORK DIFFERENCE',
                'brightwork_contrast': (
                    'Geo-targeted digital campaigns reach SF and East Bay buyers who are '
                    'actively researching Moraga before they\'ve found what they\'re looking '
                    'for — putting this home in front of decision-makers, not just browsers.'
                ),
            },
        ],
        'positioning_table': {
            'subject_label': '1409 Rimer Dr',
            'market_label': 'Moraga Market Context',
            'rows': [
                {'metric': 'Price per Sq. Ft.',
                 'subject': '$803/sqft',
                 'market': '$750–$830 (renovated / premium lot)'},
                {'metric': 'Lot / Setting',
                 'subject': '.43 acres · level · cul-de-sac',
                 'market': 'Typical .15–.25 acres'},
                {'metric': 'Architectural Character',
                 'subject': 'Expanded ranch · custom floor plan',
                 'market': 'Standard builder layouts'},
                {'metric': 'Bonus Spaces',
                 'subject': 'Two family rooms + island kitchen',
                 'market': 'Single family room standard'},
                {'metric': 'HOA', 'subject': 'None', 'market': 'Varies ($0–$250/mo)'},
            ],
            'verdict': (
                'The price per sqft is at the upper end of the renovated Moraga range, '
                'but the lot and floor plan justify it. A .43-acre level cul-de-sac lot '
                'isn\'t available at a lower price point — it simply doesn\'t exist in '
                'this market. The challenge was never the valuation. It was building the '
                'case for it before the listing went live.'
            ),
        },
        'pillars': [
            {
                'title': 'Pillar I \u2014 Make the Lot the Hero',
                'body': (
                    'A Sky Tour and cinematic ground photography that lead with the outdoor '
                    'space, the cul-de-sac position, and the scale of the lot. Buyers need '
                    'to understand what .43 flat acres feels like before they visit. The '
                    'exterior and the yard are this home\'s most powerful first impression — '
                    'the media needs to treat them that way.'
                ),
            },
            {
                'title': 'Pillar II \u2014 Write the Floor Plan into the Story',
                'body': (
                    'The listing remarks should explain — in plain language — what two '
                    'family rooms and four large bedrooms actually solve for a family. '
                    'A 3D Matterport tour lets buyers walk the layout before they schedule '
                    'a showing, so the people who arrive already understand what makes '
                    'this floor plan different from every other four-bedroom in Moraga.'
                ),
            },
            {
                'title': 'Pillar III \u2014 Find the Family Before They Find Another Home',
                'body': (
                    'Targeted digital campaigns in SF and the East Bay, timed to intercept '
                    'buyers early in their Moraga research. Zillow Showcase gives this home '
                    'premium placement and enhanced visibility — so when a family starts '
                    'comparing options at this price, this one appears at the top with a '
                    'listing that earns their attention.'
                ),
            },
        ],
    }

    SAMPLE_PROPERTY = {
        'address': '1409 Rimer Dr, Moraga, CA 94556',
        'city': 'Moraga',
        'zip': '94556',
        'beds': 4,
        'baths': 3,
        'sqft': 3113,
        'owner_display': 'Mr. and Mrs. Floyd',
    }

    out = generate_report(
        SAMPLE_CONTENT,
        SAMPLE_PROPERTY,
        assets_dir='./assets',
        output_path='./output/test_1409_Rimer.pdf'
    )
    print(f'Generated: {out}')
