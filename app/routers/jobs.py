from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.database import get_db
from app.models.schemas import JobCreate, JobUpdate, JobOut, DOC_TYPES
from app.services.ai_extractor import extract_document, merge_extracted_data, build_crew_order
from app.services.formula_engine import run_formula_engine
from datetime import datetime, timezone

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _now():
    return datetime.now(timezone.utc).isoformat()


# ── List / Create ─────────────────────────────────────────────────────────────

@router.get("/")
def list_jobs():
    db = get_db()
    result = db.table("jobs").select("*").order("created_at", desc=True).execute()
    return result.data


@router.post("/", status_code=201)
def create_job(job: JobCreate):
    db = get_db()
    payload = {
        "name": job.name,
        "address": job.address,
        "customer_name": job.customer_name,
        "notes": job.notes,
        "status": "pending",
        "extracted_data": {},
    }
    result = db.table("jobs").insert(payload).execute()
    return result.data[0]


@router.get("/{job_id}")
def get_job(job_id: str):
    db = get_db()
    job = db.table("jobs").select("*").eq("id", job_id).single().execute()
    if not job.data:
        raise HTTPException(404, "Job not found")

    docs = db.table("documents").select("*").eq("job_id", job_id).execute()
    materials = db.table("materials_orders").select("*").eq("job_id", job_id).execute()
    crew = db.table("crew_orders").select("*").eq("job_id", job_id).execute()

    return {
        **job.data,
        "documents": docs.data or [],
        "materials_order": materials.data[0] if materials.data else None,
        "crew_order": crew.data[0] if crew.data else None,
    }


@router.put("/{job_id}")
def update_job(job_id: str, job: JobUpdate):
    db = get_db()
    payload = {k: v for k, v in job.model_dump().items() if v is not None}
    payload["updated_at"] = _now()
    result = db.table("jobs").update(payload).eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(404, "Job not found")
    return result.data[0]


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str):
    db = get_db()
    # Delete storage files
    docs = db.table("documents").select("file_url").eq("job_id", job_id).execute()
    for doc in (docs.data or []):
        try:
            path = doc["file_url"].split("/roof-documents/")[-1]
            db.storage.from_("roof-documents").remove([path])
        except Exception:
            pass
    db.table("jobs").delete().eq("id", job_id).execute()


# ── Process (AI extraction) ───────────────────────────────────────────────────

@router.post("/{job_id}/process")
def process_job(job_id: str):
    db = get_db()

    # Fetch job
    job_res = db.table("jobs").select("*").eq("id", job_id).single().execute()
    if not job_res.data:
        raise HTTPException(404, "Job not found")

    # Fetch all documents
    docs_res = db.table("documents").select("*").eq("job_id", job_id).execute()
    docs = docs_res.data or []

    if not docs:
        raise HTTPException(400, "No documents uploaded. Upload documents first.")

    # Mark as processing
    db.table("jobs").update({"status": "processing", "updated_at": _now()}).eq("id", job_id).execute()

    errors = []
    processed_docs = []

    for doc in docs:
        # Download file from Supabase storage
        try:
            path = doc["file_url"].split("/roof-documents/")[-1]
            file_bytes_res = db.storage.from_("roof-documents").download(path)
            file_bytes = file_bytes_res
        except Exception as e:
            errors.append({"doc_id": doc["id"], "error": f"Download failed: {e}"})
            continue

        # Extract using Claude
        extracted = extract_document(file_bytes, doc["file_name"], doc["doc_type"])

        # Update document record
        db.table("documents").update({
            "extracted_data": extracted,
            "processed": True,
        }).eq("id", doc["id"]).execute()

        processed_docs.append({**doc, "extracted_data": extracted})

    # Merge all extracted data
    merged = merge_extracted_data(processed_docs)

    # Update job extracted_data
    db.table("jobs").update({
        "extracted_data": merged,
        "updated_at": _now(),
    }).eq("id", job_id).execute()

    # Run formula engine → materials order
    items = run_formula_engine(merged)
    existing_mat = db.table("materials_orders").select("id").eq("job_id", job_id).execute()
    if existing_mat.data:
        db.table("materials_orders").update({
            "items": items,
            "updated_at": _now(),
        }).eq("job_id", job_id).execute()
    else:
        db.table("materials_orders").insert({
            "job_id": job_id,
            "items": items,
        }).execute()

    # Build crew order
    crew_data = build_crew_order(merged, processed_docs)
    existing_crew = db.table("crew_orders").select("id").eq("job_id", job_id).execute()
    if existing_crew.data:
        db.table("crew_orders").update({
            "data": crew_data,
            "updated_at": _now(),
        }).eq("job_id", job_id).execute()
    else:
        db.table("crew_orders").insert({
            "job_id": job_id,
            "data": crew_data,
        }).execute()

    # Mark complete
    db.table("jobs").update({"status": "review", "updated_at": _now()}).eq("id", job_id).execute()

    return {
        "status": "review",
        "documents_processed": len(processed_docs),
        "materials_items": len(items),
        "errors": errors,
        "measurements": merged,
    }


# ── Materials order ───────────────────────────────────────────────────────────

@router.get("/{job_id}/materials")
def get_materials(job_id: str):
    db = get_db()
    result = db.table("materials_orders").select("*").eq("job_id", job_id).execute()
    if not result.data:
        return {"job_id": job_id, "items": []}
    return result.data[0]


@router.put("/{job_id}/materials")
def update_materials(job_id: str, payload: dict):
    db = get_db()
    items = payload.get("items", [])
    existing = db.table("materials_orders").select("id").eq("job_id", job_id).execute()
    if existing.data:
        db.table("materials_orders").update({
            "items": items,
            "updated_at": _now(),
        }).eq("job_id", job_id).execute()
    else:
        db.table("materials_orders").insert({
            "job_id": job_id,
            "items": items,
        }).execute()
    return {"job_id": job_id, "items": items}


# ── Crew order ────────────────────────────────────────────────────────────────

@router.get("/{job_id}/crew")
def get_crew(job_id: str):
    db = get_db()
    result = db.table("crew_orders").select("*").eq("job_id", job_id).execute()
    if not result.data:
        return {"job_id": job_id, "data": {}}
    return result.data[0]


@router.put("/{job_id}/crew")
def update_crew(job_id: str, payload: dict):
    db = get_db()
    data = payload.get("data", payload)
    existing = db.table("crew_orders").select("id").eq("job_id", job_id).execute()
    if existing.data:
        db.table("crew_orders").update({
            "data": data,
            "updated_at": _now(),
        }).eq("job_id", job_id).execute()
    else:
        db.table("crew_orders").insert({
            "job_id": job_id,
            "data": data,
        }).execute()
    return {"job_id": job_id, "data": data}
