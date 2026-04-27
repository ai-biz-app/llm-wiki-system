from typing import Optional  # REGRESSION RISK: Required for Optional[] type hints below

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pathlib import Path

from backend.config import settings
from backend.models import OverviewResponse, LogResponse, RecentResponse, RecentJob, WikiPagesResponse, WikiPageInfo, WikiPageResponse, SearchResponse, SearchResult
from backend.services.markdown_render import md_to_html, paginate_log, extract_title
from backend.jobs.worker import queue
from backend.services.graph_sync import get_graph_sync_service
from datetime import datetime

router = APIRouter(prefix="/api", tags=["viewer"])


def _read_md(path: Path) -> str:
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_updated_date(md_content: str) -> str:
    """Try to pull updated date from frontmatter."""
    import re
    m = re.search(r'^updated:\s*(\d{4}-\d{2}-\d{2})', md_content, re.MULTILINE)
    if m:
        return m.group(1)
    return datetime.now().strftime("%Y-%m-%d")


@router.get("/overview", response_model=OverviewResponse)
async def get_overview():
    path = settings.wiki_dir / "wiki" / "overview.md"
    content = _read_md(path)
    html = md_to_html(content, settings.wiki_dir, "overview.md") if content else "<p>No overview available yet.</p>"
    updated = _extract_updated_date(content)
    return OverviewResponse(html=html, updated=updated)


@router.get("/log")
async def get_log(page: int = 1, per_page: int = 50):
    path = settings.wiki_dir / "wiki" / "log.md"
    content = _read_md(path)
    if not content:
        return LogResponse(html="<p>No log entries yet.</p>", total_entries=0, page=1, pages=1)
    result = paginate_log(content, page=page, per_page=per_page)
    return LogResponse(**result)


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    status = await queue.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=status)


def _extract_job_title(data: dict) -> str:
    """Extract a human-readable title from job data."""
    import re, json
    result = data.get("result") or {}
    msg = data.get("message", "")
    job_id = data.get("job_id")

    # Helper: read payload from queue file
    def _payload_from_queue():
        if job_id and queue.queue_path.exists():
            try:
                with open(queue.queue_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        queued = json.loads(line.strip())
                        if queued.get("job_id") == job_id:
                            return queued.get("payload", {})
            except Exception:
                pass
        return {}

    # 1. result.title is best
    if result.get("title"):
        return result["title"]

    # 2. result.slug formatted nicely
    if result.get("slug") and result["slug"] != "untitled":
        slug = result["slug"]
        return slug.replace("-", " ").replace("_", " ").title()

    # 3. Parse from message
    m = re.search(r"Ingestion complete:?\s*(.+)", msg)
    if m:
        return m.group(1).strip()
    m = re.search(r"saved to\s+([^/]+\.md)", msg, re.IGNORECASE)
    if m:
        filename = m.group(1).strip()
        clean = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", filename)
        clean = clean.replace(".md", "").replace("-", " ").replace("_", " ")
        return clean.title()

    # 4. Look at original queue payload for URL or filename
    payload = _payload_from_queue()
    if payload.get("url"):
        from urllib.parse import urlparse
        parsed = urlparse(payload["url"])
        domain = parsed.netloc.replace("www.", "")
        path = parsed.path.strip("/")
        if path:
            return f"{domain}/{path.split('/')[0]}"
        return domain or "URL ingest"
    if payload.get("filename"):
        return payload["filename"]

    # 5. Message-based fallback
    if msg and msg != "Waiting in queue...":
        short = msg.split("\n")[0][:60]
        return short

    return "Untitled"


def _extract_job_source(data: dict) -> Optional[str]:
    """Extract the source URL or filename from job data."""
    import json
    result = data.get("result") or {}
    job_id = data.get("job_id")

    # Look at result first
    if result.get("saved_to"):
        # Return just the filename from path
        path = result.get("saved_to", "")
        if path:
            return Path(path).name
    if result.get("slug"):
        return result.get("slug")

    # Look in queue for original payload
    if job_id and queue.queue_path.exists():
        try:
            with open(queue.queue_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    queued = json.loads(line.strip())
                    if queued.get("job_id") == job_id:
                        payload = queued.get("payload", {})
                        # URL job
                        if payload.get("url"):
                            return payload["url"]
                        # Upload job
                        if payload.get("filename"):
                            return payload["filename"]
        except Exception:
            pass

    return None


@router.get("/recent", response_model=RecentResponse)
async def get_recent():
    jobs = []
    if queue.results_dir.exists():
        files = sorted(
            queue.results_dir.iterdir(),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:10]
        for f in files:
            try:
                import json
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                title = _extract_job_title(data)
                source = _extract_job_source(data)
                jobs.append(RecentJob(
                    job_id=data.get("job_id", f.stem),
                    status=data.get("status", "unknown"),
                    title=title,
                    source=source,
                    date=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
                ))
            except Exception:
                continue
    return RecentResponse(jobs=jobs)


@router.get("/pages", response_model=WikiPagesResponse)
async def get_pages():
    wiki_root = settings.wiki_dir / "wiki"
    pages = []
    if wiki_root.exists():
        for md_file in sorted(wiki_root.rglob("*.md")):
            rel = md_file.relative_to(wiki_root).as_posix()
            content = _read_md(md_file)
            title = extract_title(content, md_file.stem.replace("-", " ").replace("_", " ").title())
            folder = md_file.parent.relative_to(wiki_root).as_posix() if md_file.parent != wiki_root else "(root)"
            pages.append(WikiPageInfo(path=rel, title=title, folder=folder))
    return WikiPagesResponse(pages=pages)


@router.get("/pages/{path:path}", response_model=WikiPageResponse)
async def get_page(path: str):
    # Security: prevent directory traversal
    wiki_root = settings.wiki_dir / "wiki"
    requested = (wiki_root / path).resolve()
    if not str(requested).startswith(str(wiki_root.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    if not requested.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    if requested.suffix != ".md":
        raise HTTPException(status_code=400, detail="Only markdown files are viewable")
    content = _read_md(requested)

    # Inject graph-derived cross-references
    sync = get_graph_sync_service()
    if sync is not None:
        content = sync.inject_graph_section(content, requested)

    html = md_to_html(content, settings.wiki_dir, path) if content else "<p>Empty page.</p>"
    title = extract_title(content, requested.stem.replace("-", " ").replace("_", " ").title())
    return WikiPageResponse(html=html, title=title, path=path)


@router.get("/search")
async def search_pages(q: str = ""):
    if not q or len(q) < 2:
        return SearchResponse(query=q, results=[])
    wiki_root = settings.wiki_dir / "wiki"
    results = []
    query_lower = q.lower()
    if wiki_root.exists():
        for md_file in sorted(wiki_root.rglob("*.md")):
            rel = md_file.relative_to(wiki_root).as_posix()
            content = _read_md(md_file)
            if query_lower in content.lower():
                title = extract_title(content, md_file.stem.replace("-", " ").replace("_", " ").title())
                # Build snippet around first match
                idx = content.lower().find(query_lower)
                start = max(0, idx - 80)
                end = min(len(content), idx + len(q) + 80)
                snippet = content[start:end].replace("\n", " ")
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                results.append(SearchResult(path=rel, title=title, snippet=snippet))
    return SearchResponse(query=q, results=results[:20])
