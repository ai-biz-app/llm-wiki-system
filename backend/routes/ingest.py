from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from backend.models import IngestUrlRequest, IngestResponse, JobStatusResponse
from backend.jobs.worker import queue

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/url", response_model=IngestResponse)
async def ingest_url(request: IngestUrlRequest):
    job_id = await queue.add_job("url", {"url": str(request.url)})
    return IngestResponse(job_id=job_id, status="queued")


@router.post("/upload", response_model=IngestResponse)
async def ingest_upload(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    job_id = await queue.add_job("upload", {
        "filename": file.filename,
        "file_bytes_hex": contents.hex(),
    })
    return IngestResponse(job_id=job_id, status="queued")