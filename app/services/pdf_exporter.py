"""
PDF export service using fpdf2.
Generates printable Materials Order Form and Crew Order Form.
"""
from fpdf import FPDF
from datetime import datetime
import io


BRAND = "Reliable Exteriors Group"
PRIMARY = (0, 82, 155)      # dark blue
ACCENT = (245, 130, 32)     # orange
LIGHT_GRAY = (245, 245, 245)
MID_GRAY = (180, 180, 180)
DARK = (30, 30, 30)


class RoofPDF(FPDF):
    def __init__(self, title: str, address: str = "", customer: str = ""):
        super().__init__()
        self.title_text = title
        self.address = address
        self.customer = customer
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()

    def header(self):
        # Header bar
        self.set_fill_color(*PRIMARY)
        self.rect(0, 0, 210, 18, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.set_xy(10, 4)
        self.cell(0, 10, BRAND, ln=False)

        self.set_font("Helvetica", "", 9)
        self.set_xy(10, 26)
        self.set_text_color(*DARK)
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 8, self.title_text, ln=True)

        if self.customer or self.address:
            self.set_font("Helvetica", "", 9)
            self.set_text_color(80, 80, 80)
            info = []
            if self.customer:
                info.append(f"Customer: {self.customer}")
            if self.address:
                info.append(f"Address: {self.address}")
            self.cell(0, 5, "  |  ".join(info), ln=True)

        # Date
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.set_xy(130, 24)
        self.cell(0, 5, f"Date: {datetime.now().strftime('%B %d, %Y')}", ln=True)
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, f"Page {self.page_no()} — {BRAND}", align="C")

    def section_header(self, text: str):
        self.set_fill_color(*ACCENT)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 7, f"  {text.upper()}", ln=True, fill=True)
        self.ln(1)

    def kv_row(self, label: str, value: str, w_label=55, shaded=False):
        if shaded:
            self.set_fill_color(*LIGHT_GRAY)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*DARK)
        self.cell(w_label, 6, label, fill=shaded, border=0)
        self.set_font("Helvetica", "", 8)
        self.cell(0, 6, str(value or "—"), ln=True, fill=shaded, border=0)

    def blank_field(self, label: str, width=80):
        self.set_font("Helvetica", "", 8)
        self.set_text_color(80, 80, 80)
        self.cell(40, 6, label + ":")
        self.set_draw_color(*MID_GRAY)
        self.cell(width, 6, "", border="B")
        self.ln(7)


def export_materials_pdf(job: dict, materials: dict) -> bytes:
    """Generate materials order PDF. Returns bytes."""
    items = materials.get("items", [])
    customer = job.get("customer_name", "")
    address = job.get("address", "")

    pdf = RoofPDF("MATERIALS ORDER FORM", address=address, customer=customer)
    pdf.set_left_margin(10)
    pdf.set_right_margin(10)

    # ── Measurements summary ─────────────────────────────────────────────────
    m = job.get("extracted_data", {})
    if m:
        pdf.section_header("Roof Measurements")
        cols = [
            ("Total Squares", f"{m.get('total_squares', 0):.2f} sq"),
            ("Squares w/ Waste", f"{m.get('squares_at_waste', 0):.2f} sq"),
            ("Waste %", f"{m.get('suggested_waste_pct', 10):.0f}%"),
            ("Pitch", m.get("predominant_pitch", "—")),
            ("Ridge", f"{m.get('ridges_ft', 0):.1f} ft"),
            ("Hips", f"{m.get('hips_ft', 0):.1f} ft"),
            ("Valleys", f"{m.get('valleys_ft', 0):.1f} ft"),
            ("Eaves", f"{m.get('eaves_ft', 0):.1f} ft"),
            ("Rakes", f"{m.get('rakes_ft', 0):.1f} ft"),
            ("Facets", str(m.get("roof_facets", "—"))),
        ]
        for i, (lbl, val) in enumerate(cols):
            if i % 2 == 0:
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(*DARK)
                x = pdf.get_x()
                y = pdf.get_y()
                if i > 0:
                    # New row every 2 items
                    pass
                pdf.set_fill_color(*LIGHT_GRAY)
                pdf.cell(45, 6, lbl, fill=True, border=0)
                pdf.set_font("Helvetica", "", 8)
                pdf.cell(50, 6, val, fill=True, border=0)
            else:
                pdf.set_font("Helvetica", "B", 8)
                pdf.cell(45, 6, lbl, fill=True, border=0)
                pdf.set_font("Helvetica", "", 8)
                pdf.cell(0, 6, val, fill=True, border=0, ln=True)
        pdf.ln(3)

    # ── Materials table ───────────────────────────────────────────────────────
    pdf.section_header("Order Line Items")

    # Table header
    col_w = [70, 35, 35, 22, 28]
    headers = ["Item", "Color", "Size", "Qty", "Unit"]
    pdf.set_fill_color(*PRIMARY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    for i, (h, w) in enumerate(zip(headers, col_w)):
        pdf.cell(w, 7, h, border=1, fill=True, align="C" if i >= 3 else "L")
    pdf.ln()

    # Group by category
    categories = {}
    for item in items:
        cat = item.get("category", "other")
        categories.setdefault(cat, []).append(item)

    row_num = 0
    for cat, cat_items in categories.items():
        # Category sub-header
        pdf.set_fill_color(220, 235, 255)
        pdf.set_text_color(*PRIMARY)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(sum(col_w), 5, f"  {cat.upper()}", border=1, fill=True, ln=True)

        for item in cat_items:
            shade = row_num % 2 == 0
            pdf.set_fill_color(*(LIGHT_GRAY if shade else (255, 255, 255)))
            pdf.set_text_color(*DARK)
            pdf.set_font("Helvetica", "", 8)
            qty = item.get("qty", 0)
            qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.1f}"
            values = [
                item.get("item", ""),
                item.get("color", ""),
                item.get("size", ""),
                qty_str,
                item.get("unit", ""),
            ]
            for i, (v, w) in enumerate(zip(values, col_w)):
                align = "C" if i >= 3 else "L"
                pdf.cell(w, 6, str(v), border=1, fill=shade, align=align)
            pdf.ln()
            row_num += 1

    pdf.ln(6)

    # ── Signature block ───────────────────────────────────────────────────────
    pdf.section_header("Authorization")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*DARK)
    pdf.blank_field("Ordered by")
    pdf.blank_field("PO Number")
    pdf.blank_field("Delivery Date")
    pdf.blank_field("Notes", width=120)

    return bytes(pdf.output())


def export_crew_pdf(job: dict, crew: dict) -> bytes:
    """Generate crew order PDF. Returns bytes."""
    data = crew.get("data", crew)
    customer = data.get("customer_name") or job.get("customer_name", "")
    address = data.get("address") or job.get("address", "")

    pdf = RoofPDF("CREW ORDER FORM", address=address, customer=customer)
    pdf.set_left_margin(10)
    pdf.set_right_margin(10)

    # ── Job Info ──────────────────────────────────────────────────────────────
    pdf.section_header("Job Information")
    pdf.kv_row("Customer", customer, shaded=True)
    pdf.kv_row("Address", address)
    pdf.kv_row("Scope of Work", data.get("scope_of_work", ""), shaded=True)
    pdf.kv_row("Shingle Brand/Type", f"{data.get('shingle_brand','')} {data.get('shingle_type','')}".strip())
    pdf.kv_row("Shingle Color", data.get("shingle_color", ""), shaded=True)
    pdf.ln(2)

    # ── Roof Measurements ─────────────────────────────────────────────────────
    m = data.get("measurements", {})
    if m:
        pdf.section_header("Roof Measurements")
        rows = [
            ("Total Squares", f"{m.get('total_squares', 0):.2f} sq"),
            ("Squares w/ Waste", f"{m.get('squares_at_waste', 0):.2f} sq"),
            ("Pitch", m.get("predominant_pitch", "—")),
            ("Facets", str(m.get("roof_facets", "—"))),
            ("Existing Layers", str(m.get("existing_layers", "—"))),
            ("Current Material", m.get("current_material", "—")),
            ("Ridge ft", f"{m.get('ridges_ft', 0):.1f}"),
            ("Hip ft", f"{m.get('hips_ft', 0):.1f}"),
            ("Valley ft", f"{m.get('valleys_ft', 0):.1f}"),
            ("Eave ft", f"{m.get('eaves_ft', 0):.1f}"),
            ("Rake ft", f"{m.get('rakes_ft', 0):.1f}"),
        ]
        for i, (lbl, val) in enumerate(rows):
            pdf.kv_row(lbl, val, shaded=(i % 2 == 0))
        pdf.ln(2)

    # ── Special Features ──────────────────────────────────────────────────────
    features = data.get("special_features", [])
    if features:
        pdf.section_header("Special Features / Accessories")
        for i, feat in enumerate(features):
            pdf.kv_row("", feat, w_label=5, shaded=(i % 2 == 0))
        pdf.ln(2)

    # ── Insurance ─────────────────────────────────────────────────────────────
    ins = data.get("insurance", {})
    if any(ins.values()):
        pdf.section_header("Insurance Details")
        pdf.kv_row("Carrier", ins.get("carrier", ""), shaded=True)
        pdf.kv_row("Claim Number", ins.get("claim_number", ""))
        pdf.kv_row("Deductible", f"${ins.get('deductible', 0):,.2f}", shaded=True)
        pdf.ln(2)

    # ── City Code ─────────────────────────────────────────────────────────────
    cc = data.get("city_code", {})
    if cc.get("jurisdiction") or cc.get("requirements"):
        pdf.section_header("City / County Code Requirements")
        pdf.kv_row("Jurisdiction", cc.get("jurisdiction", ""), shaded=True)
        pdf.kv_row("Permit Required", "YES" if cc.get("permit_required") else "NO")
        reqs = cc.get("requirements", [])
        for i, req in enumerate(reqs):
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(5, 5, "•")
            pdf.multi_cell(0, 5, req)
        pdf.ln(2)

    # ── Crew Assignment ───────────────────────────────────────────────────────
    pdf.section_header("Crew Assignment")
    pdf.blank_field("Crew Lead")
    pdf.blank_field("Crew Size")
    pdf.blank_field("Start Date")
    pdf.blank_field("Target Completion")
    pdf.blank_field("Equipment / Dumpster Notes", width=120)
    pdf.ln(3)

    pdf.section_header("Special Instructions / Safety Notes")
    # Lined area for notes
    pdf.set_draw_color(*MID_GRAY)
    for _ in range(5):
        pdf.cell(0, 8, "", border="B", ln=True)

    return bytes(pdf.output())
