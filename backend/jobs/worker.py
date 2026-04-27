import json
import uuid
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import httpx

from backend.config import settings
from backend.services.file_storage import save_uploaded_file, save_text_as_md, url_to_filename, ensure_wiki_dirs
from backend.services import extraction
from backend.services import ingestion


class JobQueue:
    def __init__(self, queue_path: str, results_dir: str):
        self.queue_path = Path(queue_path)
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._running = False

    def _result_path(self, job_id: str) -> Path:
        return self.results_dir / f"{job_id}.json"

    async def add_job(self, job_type: str, payload: Dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "type": job_type,
            "payload": payload,
            "status": "queued",
            "message": "Waiting in queue...",
            "result": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        async with self._lock:
            with open(self.queue_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(job) + "\n")
        return job_id

    async def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        result_path = self._result_path(job_id)
        if result_path.exists():
            with open(result_path, "r", encoding="utf-8") as f:
                return json.load(f)
        # Search queue file for latest state
        async with self._lock:
            if not self.queue_path.exists():
                return None
            with open(self.queue_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                data = json.loads(line.strip())
                if data.get("job_id") == job_id:
                    return data
        return None

    async def _update_job(self, job_id: str, status: str, message: str, result: Optional[dict] = None):
        updated = {
            "job_id": job_id,
            "status": status,
            "message": message,
            "result": result,
            "updated_at": datetime.now().isoformat(),
        }
        result_path = self._result_path(job_id)
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(updated, f, indent=2)

    async def _process_job(self, job: Dict[str, Any]):
        job_id = job["job_id"]
        job_type = job["type"]
        payload = job["payload"]

        def progress(status: str, message: Optional[str]):
            asyncio.create_task(self._update_job(job_id, status, message or ""))

        try:
            if job_type == "url":
                url = payload["url"]
                slug = url_to_filename(url)
                await self._update_job(job_id, "running", "Fetching and extracting URL content...")
                extracted_text = await extraction.extract_text_from_url(url)
                # Save raw
                raw_path = save_text_as_md(extracted_text, slug, settings.raw_sources_dir)

                meta = {
                    "url": url,
                    "title": payload.get("title") or slug,
                    "author": payload.get("author", ""),
                    "published": payload.get("published", ""),
                }

                ingest_payload = {
                    "source_type": "url",
                    "raw_path": str(raw_path),
                    "extracted_text": extracted_text,
                    "meta": meta,
                }

                await ingestion.run_ingestion(job_id, ingest_payload, progress)
                await self._update_job(
                    job_id, "done", f"Ingestion complete: {meta['title']}",
                    result={"saved_to": str(raw_path), "slug": slug, "type": "url", "title": meta["title"]}
                )

            elif job_type == "upload":
                filename = payload["filename"]
                file_bytes = bytes.fromhex(payload["file_bytes_hex"])
                ext = Path(filename).suffix.lower().lstrip(".")
                await self._update_job(job_id, "running", "Extracting file content...")
                raw_path = save_uploaded_file(file_bytes, filename, settings.raw_assets_dir)
                extracted_text = extraction.extract_text(file_bytes, ext)
                slug = Path(filename).stem

                meta = {
                    "title": payload.get("title") or slug,
                    "filename": filename,
                }

                ingest_payload = {
                    "source_type": "upload",
                    "raw_path": str(raw_path),
                    "extracted_text": extracted_text,
                    "meta": meta,
                }

                await ingestion.run_ingestion(job_id, ingest_payload, progress)
                await self._update_job(
                    job_id, "done", f"Ingestion complete: {meta['title']}",
                    result={"saved_to": str(raw_path), "slug": slug, "type": "upload", "title": meta["title"]}
                )

            else:
                await self._update_job(job_id, "failed", f"Unknown job type: {job_type}")

        except Exception as e:
            await self._update_job(job_id, "failed", str(e))

    async def run_worker(self):
        self._running = True
        while self._running:
            job = None
            async with self._lock:
                if self.queue_path.exists():
                    with open(self.queue_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for i, line in enumerate(lines):
                        data = json.loads(line.strip())
                        if data.get("status") == "queued":
                            data["status"] = "running"
                            data["updated_at"] = datetime.now().isoformat()
                            lines[i] = json.dumps(data) + "\n"
                            job = data
                            break
                    if job:
                        with open(self.queue_path, "w", encoding="utf-8") as f:
                            f.writelines(lines)

            if job:
                await self._process_job(job)
            else:
                await asyncio.sleep(2)

    def stop(self):
        self._running = False


queue = JobQueue(settings.job_queue_path, settings.job_results_path)