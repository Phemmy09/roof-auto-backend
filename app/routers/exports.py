from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.database import get_db
from app.services.pdf_exporter import export_materials_pdf, export_crew_pdf

router = APIRouter(prefix="/jobs/{job_id}/export", tags=["exports"])


@router.get("/materials")
def export_materials(job_id: str):
    db = get_db()

    job = db.table("jobs").select("*").eq("id", job_id).single().execute()
    if not job.data:
        raise HTTPException(404, "Job not found")

    materials = db.table("materials_orders").select("*").eq("job_id", job_id).execute()
    mat_data = materials.data[0] if materials.data else {"items": []}

    pdf_bytes = export_materials_pdf(job.data, mat_data)
    filename = f"materials-{job.data.get('name', job_id).replace(' ', '_')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/crew")
def export_crew(job_id: str):
    db = get_db()

    job = db.table("jobs").select("*").eq("id", job_id).single().execute()
    if not job.data:
        raise HTTPException(404, "Job not found")

    crew = db.table("crew_orders").select("*").eq("job_id", job_id).execute()
    crew_data = crew.data[0] if crew.data else {"data": {}}

    pdf_bytes = export_crew_pdf(job.data, crew_data)
    filename = f"crew-{job.data.get('name', job_id).replace(' ', '_')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
