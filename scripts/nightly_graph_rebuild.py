#!/usr/bin/env python3
"""
Nightly graph rebuild script.
Called by cron to ensure the graph is never stale for more than 24 hours.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_settings
from backend.services.graphify import init_graphify_service, get_graphify_service
from backend.services.graph_sync import init_graph_sync_service, get_graph_sync_service
from backend.services.graph_rebuild import init_graph_rebuild_scheduler, get_graph_rebuild_scheduler


async def main():
    settings = get_settings()

    if not getattr(settings, 'graphify_enabled', False):
        print("Graphify is disabled. Skipping nightly rebuild.")
        return 0

    graphify_output = Path(settings.wiki_path) / "graphify-out"

    # Initialize services (same as main.py)
    init_graphify_service(
        output_dir=graphify_output,
        mode=getattr(settings, 'graphify_mode', 'standard'),
        obsidian_export=getattr(settings, 'graphify_obsidian_export', True),
        directed=getattr(settings, 'graphify_directed', False),
        timeout_default=getattr(settings, 'graphify_timeout_default', 10),
        timeout_query=getattr(settings, 'graphify_timeout_query', 30),
        timeout_ingest=getattr(settings, 'graphify_timeout_ingest', 300),
    )

    init_graph_sync_service(
        wiki_dir=Path(settings.wiki_path),
        graphify_output_dir=graphify_output,
    )

    init_graph_rebuild_scheduler()

    scheduler = get_graph_rebuild_scheduler()
    if not scheduler:
        print("Failed to initialize scheduler", file=sys.stderr)
        return 1

    print("Starting nightly graph rebuild...")
    status = await scheduler.rebuild_now()
    print(f"Status: {status['status']}")
    print(f"Message: {status['message']}")

    return 0 if status['status'] in ('idle', 'running') else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
