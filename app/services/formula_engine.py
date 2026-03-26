"""
Formula engine — evaluates material quantity formulas against job measurements.
Uses simpleeval for safe math expression evaluation.
"""
import math
from simpleeval import simple_eval, EvalWithCompoundTypes
from app.database import get_db

# ── Default formula seed data ─────────────────────────────────────────────────
# Derived from real ABC Supply invoice for Bramlage job (June 2025):
# - Shingles: 60 bundles for 20 squares (8% waste) = ceil(sq_at_waste * 3)
# - Ridge/Hip cap: 33.3 LF/bundle (TAMKO PROLINE)
# - Starter: 120 LF/bundle (GAF Pro-Start)
# - Underlayment: 10 SQ/roll (ABC Pro Guard 20)
# - Ice & water: 2 SQ/roll (Rhinoroof Gran Self Adhered)
# - Drip edge pieces: 10ft sticks

DEFAULT_FORMULAS = [
    # Shingles
    {
        "name": "Architectural Shingles",
        "item_name": "Architectural Shingles",
        "formula_expr": "ceil(squares_at_waste * 3)",
        "unit": "bundles",
        "default_color": "",
        "default_size": "Architectural",
        "category": "shingles",
        "sort_order": 1,
    },
    # Ridge / Hip cap
    {
        "name": "Hip & Ridge Cap",
        "item_name": "Hip & Ridge Cap",
        "formula_expr": "ceil((ridges_ft + hips_ft) / 33.3)",
        "unit": "bundles",
        "default_color": "",
        "default_size": "33.3 LF",
        "category": "shingles",
        "sort_order": 2,
    },
    # Starter strip
    {
        "name": "Starter Strip",
        "item_name": "Starter Strip",
        "formula_expr": "ceil((eaves_ft + rakes_ft) / 120)",
        "unit": "bundles",
        "default_color": "",
        "default_size": "120 LF",
        "category": "shingles",
        "sort_order": 3,
    },
    # Synthetic underlayment
    {
        "name": "Synthetic Underlayment",
        "item_name": "Synthetic Underlayment",
        "formula_expr": "ceil(squares_at_waste / 10)",
        "unit": "rolls",
        "default_color": "",
        "default_size": "10 SQ",
        "category": "underlayment",
        "sort_order": 4,
    },
    # Ice & water shield
    {
        "name": "Ice & Water Shield",
        "item_name": "Ice & Water Shield",
        "formula_expr": "ceil((eaves_ft * 6 + valleys_ft * 3) / 200)",
        "unit": "rolls",
        "default_color": "",
        "default_size": "2 SQ",
        "category": "underlayment",
        "sort_order": 5,
    },
    # Rake drip edge
    {
        "name": "Rake Drip Edge",
        "item_name": "Drip Edge - Rake",
        "formula_expr": "ceil(rakes_ft / 10 * 1.15)",
        "unit": "pieces",
        "default_color": "Black",
        "default_size": '2x4 28Ga 10ft',
        "category": "trim",
        "sort_order": 6,
    },
    # Eave / gutter apron
    {
        "name": "Eave / Gutter Apron",
        "item_name": "Drip Edge - Eave/Gutter Apron",
        "formula_expr": "ceil(eaves_ft / 10 * 1.25)",
        "unit": "pieces",
        "default_color": "Black",
        "default_size": '2x4 28Ga 10ft',
        "category": "trim",
        "sort_order": 7,
    },
    # Ridge vents (Lomanco OR4 — 4 LF each)
    {
        "name": "Ridge Vents",
        "item_name": "Ridge Vent",
        "formula_expr": "ceil(ridges_ft / 4)",
        "unit": "pieces",
        "default_color": "",
        "default_size": '12" OR4',
        "category": "ventilation",
        "sort_order": 8,
    },
    # Valley metal (W-metal 24" roll, 50 LF)
    {
        "name": "Valley Metal",
        "item_name": "Valley Metal W-Metal 24\"",
        "formula_expr": "ceil(valleys_ft / 50) if valleys_ft > 0 else 0",
        "unit": "rolls",
        "default_color": "Mill",
        "default_size": '24" 50LF',
        "category": "flashing",
        "sort_order": 9,
    },
    # Step flashing
    {
        "name": "Step Flashing",
        "item_name": "Step Flashing 4x4x8",
        "formula_expr": "1 if step_flashing_ft > 0 or chimneys_count > 0 else 0",
        "unit": "bundles",
        "default_color": "Black",
        "default_size": "4x4x8 Galv",
        "category": "flashing",
        "sort_order": 10,
    },
    # Pipe boots (multi-size pack)
    {
        "name": "Pipe Boots - Multi Size",
        "item_name": "Pipe Boots Multi-Size 1.5\"/2\"/3\"",
        "formula_expr": "pipe_boots_count",
        "unit": "each",
        "default_color": "",
        "default_size": "1.5/2/3 in",
        "category": "accessories",
        "sort_order": 11,
    },
    # Coil nails
    {
        "name": "Coil Nails 1-1/4\"",
        "item_name": "Coil Nails 1-1/4\" EG",
        "formula_expr": "ceil(squares_at_waste / 10)",
        "unit": "boxes",
        "default_color": "",
        "default_size": "1-1/4\"",
        "category": "fasteners",
        "sort_order": 12,
    },
    # Plastic cap nails (for underlayment)
    {
        "name": "Plastic Cap Nails 1-1/4\"",
        "item_name": "Plastic Cap Nails 1-1/4\" 2.5M",
        "formula_expr": "ceil(squares_at_waste / 20)",
        "unit": "pails",
        "default_color": "",
        "default_size": "1-1/4\"",
        "category": "fasteners",
        "sort_order": 13,
    },
    # Roof sealant
    {
        "name": "Roof Sealant",
        "item_name": "Geocel Sealant #2300 Clear",
        "formula_expr": "ceil(total_squares / 6)",
        "unit": "tubes",
        "default_color": "Clear",
        "default_size": "10oz",
        "category": "accessories",
        "sort_order": 14,
    },
    # Touch-up paint
    {
        "name": "Roof Accessory Paint",
        "item_name": "Roof Accessory Touch-Up Paint",
        "formula_expr": "3 if total_squares > 0 else 0",
        "unit": "cans",
        "default_color": "",
        "default_size": "",
        "category": "accessories",
        "sort_order": 15,
    },
    # OSB decking (field-determined — default 0)
    {
        "name": "OSB Decking 7/16\"",
        "item_name": "OSB Decking 7/16\" 4x8",
        "formula_expr": "0",
        "unit": "sheets",
        "default_color": "",
        "default_size": "4x8",
        "category": "decking",
        "sort_order": 16,
    },
]


def _build_vars(measurements: dict) -> dict:
    """Build the variable namespace for formula evaluation."""
    m = measurements
    total_sq = float(m.get("total_squares") or 0)
    waste_pct = float(m.get("suggested_waste_pct") or 10)
    sq_at_waste = float(m.get("squares_at_waste") or 0)
    if sq_at_waste == 0 and total_sq > 0:
        sq_at_waste = round(total_sq * (1 + waste_pct / 100), 2)

    return {
        "total_squares": total_sq,
        "squares_at_waste": sq_at_waste,
        "waste_pct": waste_pct,
        "ridges_ft": float(m.get("ridges_ft") or 0),
        "hips_ft": float(m.get("hips_ft") or 0),
        "valleys_ft": float(m.get("valleys_ft") or 0),
        "rakes_ft": float(m.get("rakes_ft") or 0),
        "eaves_ft": float(m.get("eaves_ft") or 0),
        "flashing_ft": float(m.get("flashing_ft") or 0),
        "step_flashing_ft": float(m.get("step_flashing_ft") or 0),
        "drip_edge_ft": float(m.get("drip_edge_ft") or 0),
        "pitch_num": float(m.get("pitch_num") or 4),
        "roof_facets": int(m.get("roof_facets") or 0),
        "obstructions_count": int(m.get("obstructions_count") or 0),
        "skylights_count": int(m.get("skylights_count") or 0),
        "chimneys_count": int(m.get("chimneys_count") or 0),
        "pipe_boots_count": int(m.get("pipe_boots_count") or 0),
        "vents_count": int(m.get("vents_count") or 0),
        "satellite_dishes_count": int(m.get("satellite_dishes_count") or 0),
        "existing_layers_count": int(m.get("existing_layers_count") or 1),
        # Math helpers
        "ceil": math.ceil,
        "floor": math.floor,
        "round": round,
        "max": max,
        "min": min,
        "abs": abs,
    }


def evaluate_formula(expr: str, measurements: dict) -> float:
    """Safely evaluate a formula expression against job measurements."""
    try:
        variables = _build_vars(measurements)
        result = simple_eval(expr, names=variables)
        return max(0.0, float(result))
    except Exception:
        return 0.0


def run_formula_engine(measurements: dict) -> list[dict]:
    """
    Load all active formulas from DB and evaluate each against measurements.
    Returns a list of material line items.
    """
    db = get_db()
    result = (
        db.table("formulas")
        .select("*")
        .eq("active", True)
        .order("sort_order")
        .execute()
    )
    formulas = result.data or []

    items = []
    for f in formulas:
        qty = evaluate_formula(f["formula_expr"], measurements)
        if qty > 0:
            items.append(
                {
                    "item": f["item_name"],
                    "color": f.get("default_color", ""),
                    "size": f.get("default_size", ""),
                    "qty": qty,
                    "unit": f["unit"],
                    "category": f.get("category", ""),
                }
            )

    return items


def seed_default_formulas():
    """Insert default formulas if the table is empty."""
    db = get_db()
    existing = db.table("formulas").select("id").execute()
    if existing.data:
        return {"seeded": 0, "message": "Formulas already exist"}

    db.table("formulas").insert(DEFAULT_FORMULAS).execute()
    return {"seeded": len(DEFAULT_FORMULAS), "message": "Default formulas seeded"}
