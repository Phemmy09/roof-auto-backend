from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime


# ── Job ──────────────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    name: str
    address: Optional[str] = None
    customer_name: Optional[str] = None
    notes: Optional[str] = None


class JobUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    customer_name: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class JobOut(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    customer_name: Optional[str] = None
    status: str
    notes: Optional[str] = None
    extracted_data: dict = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ── Document ──────────────────────────────────────────────────────────────────

DOC_TYPES = ["eagle_view", "contract", "insurance", "city_code", "photos"]


class DocumentOut(BaseModel):
    id: str
    job_id: str
    file_name: str
    file_url: str
    file_size: Optional[int] = None
    doc_type: str
    extracted_data: dict = {}
    processed: bool = False
    created_at: Optional[str] = None


# ── Materials ─────────────────────────────────────────────────────────────────

class MaterialItem(BaseModel):
    item: str
    color: Optional[str] = ""
    size: Optional[str] = ""
    qty: float
    unit: str
    category: Optional[str] = ""


class MaterialsOrderUpdate(BaseModel):
    items: list[MaterialItem]


class MaterialsOrderOut(BaseModel):
    id: Optional[str] = None
    job_id: str
    items: list[dict] = []
    updated_at: Optional[str] = None


# ── Crew Order ────────────────────────────────────────────────────────────────

class CrewOrderUpdate(BaseModel):
    data: dict[str, Any]


class CrewOrderOut(BaseModel):
    id: Optional[str] = None
    job_id: str
    data: dict = {}
    updated_at: Optional[str] = None


# ── Formula ───────────────────────────────────────────────────────────────────

class FormulaCreate(BaseModel):
    name: str
    item_name: str
    formula_expr: str
    unit: str
    default_color: Optional[str] = ""
    default_size: Optional[str] = ""
    category: Optional[str] = "main"
    active: bool = True
    sort_order: int = 0


class FormulaUpdate(BaseModel):
    name: Optional[str] = None
    item_name: Optional[str] = None
    formula_expr: Optional[str] = None
    unit: Optional[str] = None
    default_color: Optional[str] = None
    default_size: Optional[str] = None
    category: Optional[str] = None
    active: Optional[bool] = None
    sort_order: Optional[int] = None


class FormulaOut(BaseModel):
    id: str
    name: str
    item_name: str
    formula_expr: str
    unit: str
    default_color: str = ""
    default_size: str = ""
    category: str = "main"
    active: bool = True
    sort_order: int = 0
    created_at: Optional[str] = None
