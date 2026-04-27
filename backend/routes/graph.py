"""
Graph API routes for interactive graph exploration.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Import services
from backend.services.graphify import GraphifyService
from backend.services.graph_sync import GraphSyncService

router = APIRouter(prefix="/api/graph", tags=["graph"])

# Service instances (injected via dependency or global)
_graphify_service: Optional[GraphifyService] = None
_graph_sync_service: Optional[GraphSyncService] = None


def set_graph_services(
    graphify_service: GraphifyService,
    graph_sync_service: GraphSyncService,
):
    """Set service instances for routes."""
    global _graphify_service, _graph_sync_service
    _graphify_service = graphify_service
    _graph_sync_service = graph_sync_service


class GraphStatsResponse(BaseModel):
    node_count: int
    edge_count: int
    community_count: int
    god_nodes: list


@router.get("/stats")
async def get_graph_stats():
    """Get statistics about the current knowledge graph."""
    if not _graph_sync_service:
        raise HTTPException(status_code=503, detail="Graph service not initialized")

    graph_data = _graph_sync_service._graph_data
    if not graph_data:
        raise HTTPException(status_code=404, detail="No graph available. Run ingestion first.")

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", []) or graph_data.get("links", [])

    communities = set()
    for node in nodes:
        # Community can be at top level or in attributes
        comm = node.get("community")
        if comm is None:
            comm = node.get("attributes", {}).get("community")
        if comm is not None:
            communities.add(comm)

    god_nodes = _graph_sync_service.get_god_nodes(top_n=5)

    return GraphStatsResponse(
        node_count=len(nodes),
        edge_count=len(edges),
        community_count=len(communities),
        god_nodes=[{"label": n.label, "degree": n.degree} for n in god_nodes],
    )


@router.get("/full")
async def get_full_graph():
    """Get the full graph.json for visualization with enriched node data."""
    if not _graphify_service:
        raise HTTPException(status_code=503, detail="Graph service not initialized")

    graph_data = _graphify_service.read_graph_json()
    if not graph_data:
        raise HTTPException(status_code=404, detail="No graph available.")

    # Calculate degrees from edges (NetworkX uses 'links')
    nodes = graph_data.get("nodes", [])
    edge_key = "links" if "links" in graph_data else "edges"
    edges = graph_data.get(edge_key, [])
    
    # Build degree map
    degree_map = {}
    for edge in edges:
        source = edge.get("source", "")
        target = edge.get("target", "")
        if source:
            degree_map[source] = degree_map.get(source, 0) + 1
        if target:
            degree_map[target] = degree_map.get(target, 0) + 1
    
    # Enrich nodes with degree
    for node in nodes:
        node_id = node.get("id", "")
        node["degree"] = degree_map.get(node_id, 0)
        # Also ensure attributes exist
        if "attributes" not in node:
            node["attributes"] = {}
        # Copy community to attributes if present at top level
        if "community" in node and node["community"] is not None:
            node["attributes"]["community"] = node["community"]

    return graph_data


@router.get("/query")
async def query_graph(
    q: str = Query(..., description="Natural language query"),
    dfs: bool = Query(False, description="Use DFS for path tracing"),
    budget: Optional[int] = Query(None, description="Max tokens for response"),
):
    """Query the graph with natural language."""
    if not _graphify_service:
        raise HTTPException(status_code=503, detail="Graph service not initialized")

    result = _graphify_service.query_graph(q, dfs=dfs, budget=budget)
    if result is None:
        raise HTTPException(status_code=404, detail="Graph not available")

    return {"query": q, "result": result}


@router.get("/report")
async def get_graph_report():
    """Get the GRAPH_REPORT.md content."""
    if not _graphify_service:
        raise HTTPException(status_code=503, detail="Graph service not initialized")

    report = _graphify_service.read_graph_report()
    if not report:
        raise HTTPException(status_code=404, detail="No graph report available")

    return {"report": report}
