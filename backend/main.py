import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from backend.routes import ingest, viewer
from backend.routes.graph import router as graph_router, set_graph_services
from backend.jobs.worker import JobQueue

from backend.services.graphify import init_graphify_service
from backend.services.graph_sync import init_graph_sync_service
from backend.config import settings

logger = logging.getLogger(__name__)

# Global queue instance
queue = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with Graphify initialization."""
    global queue

    logger.info("Starting up...")

    # Initialize job queue
    queue = JobQueue(
        queue_path=settings.job_queue_path,
        results_dir=settings.job_results_path,
    )

    # Initialize Graphify service
    if getattr(settings, 'graphify_enabled', False):
        logger.info("Initializing Graphify service...")
        try:
            graphify_output = Path(settings.wiki_path) / "graphify-out"
            graphify_service = init_graphify_service(
                output_dir=graphify_output,
                mode=getattr(settings, 'graphify_mode', 'standard'),
                obsidian_export=getattr(settings, 'graphify_obsidian_export', True),
                directed=getattr(settings, 'graphify_directed', False),
                timeout_default=getattr(settings, 'graphify_timeout_default', 10),
                timeout_query=getattr(settings, 'graphify_timeout_query', 30),
                timeout_ingest=getattr(settings, 'graphify_timeout_ingest', 300),
            )

            # Initialize Graph Sync service
            graph_sync_service = init_graph_sync_service(
                wiki_dir=Path(settings.wiki_path),
                graphify_output_dir=graphify_output,
            )

            # Set for routes
            set_graph_services(graphify_service, graph_sync_service)
            logger.info(f"Graphify initialized at {graphify_output}")
        except Exception as e:
            logger.error(f"Failed to initialize Graphify: {e}")
    else:
        logger.info("Graphify is disabled")

    # Start worker
    worker_task = asyncio.create_task(queue.run_worker())
    logger.info("Worker started")

    yield

    # Cleanup
    logger.info("Shutting down...")
    queue.stop()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="LLM Wiki", lifespan=lifespan)

# Mount API routes
app.include_router(ingest.router)
app.include_router(viewer.router)
app.include_router(graph_router)

# Mount frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(frontend_dir / "index.html")


@app.get("/overview")
async def overview_page():
    return FileResponse(frontend_dir / "index.html")


@app.get("/log")
async def log_page():
    return FileResponse(frontend_dir / "index.html")


@app.get("/wiki")
async def wiki_root():
    return FileResponse(frontend_dir / "index.html")


@app.get("/wiki/{path:path}")
async def wiki_page(path: str):
    return FileResponse(frontend_dir / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.web_host, port=settings.web_port, reload=False)
