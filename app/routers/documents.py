from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.database import get_db
from app.models.schemas import DOC_TYPES
from app.config import settings
import uuid

router = APIRouter(prefix="/jobs/{job_id}/documents", tags=["documents"])


@router.post("/", status_code=201)
async def upload_document(
    job_id: str,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
):
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"doc_type must be one of: {DOC_TYPES}")

    db = get_db()

    # Verify job exists
    job = db.table("jobs").select("id").eq("id", job_id).single().execute()
    if not job.data:
        raise HTTPException(404, "Job not found")

    # Read file
    content = await file.read()
    file_size = len(content)

    # Upload to Supabase storage
    storage_path = f"{job_id}/{uuid.uuid4()}-{file.filename}"
    db.storage.from_(settings.supabase_storage_bucket).upload(
        path=storage_path,
        file=content,
        file_options={"content-type": file.content_type or "application/pdf"},
    )

    # Get public URL
    public_url = db.storage.from_(settings.supabase_storage_bucket).get_public_url(storage_path)

    # Insert document record
    doc_record = {
        "job_id": job_id,
        "file_name": file.filename,
        "file_url": public_url,
        "file_size": file_size,
        "doc_type": doc_type,
        "extracted_data": {},
        "processed": False,
    }
    result = db.table("documents").insert(doc_record).execute()

    return result.data[0]


@router.delete("/{doc_id}", status_code=204)
def delete_document(job_id: str, doc_id: str):
    db = get_db()
    doc = db.table("documents").select("*").eq("id", doc_id).eq("job_id", job_id).single().execute()
    if not doc.data:
        raise HTTPException(404, "Document not found")

    # Remove from storage
    try:
        path = doc.data["file_url"].split(f"/{settings.supabase_storage_bucket}/")[-1]
        db.storage.from_(settings.supabase_storage_bucket).remove([path])
    except Exception:
        pass

    db.table("documents").delete().eq("id", doc_id).execute()
