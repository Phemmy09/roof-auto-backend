from fastapi import APIRouter, HTTPException
from app.database import get_db
from app.models.schemas import FormulaCreate, FormulaUpdate
from app.services.formula_engine import seed_default_formulas, evaluate_formula

router = APIRouter(prefix="/formulas", tags=["formulas"])


@router.get("/")
def list_formulas():
    db = get_db()
    result = db.table("formulas").select("*").order("sort_order").execute()
    return result.data


@router.post("/", status_code=201)
def create_formula(formula: FormulaCreate):
    db = get_db()
    result = db.table("formulas").insert(formula.model_dump()).execute()
    return result.data[0]


@router.put("/{formula_id}")
def update_formula(formula_id: str, formula: FormulaUpdate):
    db = get_db()
    payload = {k: v for k, v in formula.model_dump().items() if v is not None}
    result = db.table("formulas").update(payload).eq("id", formula_id).execute()
    if not result.data:
        raise HTTPException(404, "Formula not found")
    return result.data[0]


@router.delete("/{formula_id}", status_code=204)
def delete_formula(formula_id: str):
    db = get_db()
    db.table("formulas").delete().eq("id", formula_id).execute()


@router.post("/seed")
def seed_formulas():
    return seed_default_formulas()


@router.post("/preview")
def preview_formula(payload: dict):
    """
    Preview what a formula expression evaluates to given sample measurements.
    payload: { "formula_expr": "ceil(squares_at_waste * 3)", "measurements": {...} }
    """
    expr = payload.get("formula_expr", "")
    measurements = payload.get("measurements", {})
    try:
        result = evaluate_formula(expr, measurements)
        return {"result": result, "error": None}
    except Exception as e:
        return {"result": 0, "error": str(e)}
