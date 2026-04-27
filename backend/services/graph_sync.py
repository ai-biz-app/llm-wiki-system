"""
Graph-to-Wiki synchronization service.
Cross-references Graphify's knowledge graph with wiki pages.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GraphNode:
    """Represents a node in the knowledge graph."""
    id: str
    label: str
    node_type: str  # "entity", "concept", "source", etc.
    community: Optional[int] = None
    degree: int = 0
    source_file: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Represents an edge in the knowledge graph."""
    source: str
    target: str
    relation: str
    confidence: str  # "EXTRACTED", "INFERRED", "AMBIGUOUS"
    confidence_score: Optional[float] = None


@dataclass
class GraphRelationship:
    """Relationship data for injection into wiki pages."""
    target_title: str
    relation_type: str
    confidence: str
    confidence_score: Optional[float]
    edge_type: str  # "inbound" or "outbound"


@dataclass
class PageGraphInfo:
    """Graph-derived information for a wiki page."""
    page_title: str
    page_path: Path
    community: Optional[int] = None
    community_name: Optional[str] = None
    degree: int = 0
    is_god_node: bool = False
    relationships: List[GraphRelationship] = field(default_factory=list)
    neighbors: List[str] = field(default_factory=list)


class GraphSyncService:
    """
    Synchronizes Graphify's knowledge graph with wiki pages.
    Injects graph-derived cross-references into markdown rendering.
    """

    # Confidence order for sorting (highest first)
    CONFIDENCE_ORDER = {"EXTRACTED": 3, "INFERRED": 2, "AMBIGUOUS": 1}

    def __init__(
        self,
        wiki_dir: Path,
        graphify_output_dir: Path,
        god_node_threshold: float = 0.9,  # Top 10% by degree are god nodes
    ):
        self.wiki_dir = Path(wiki_dir)
        self.graphify_output_dir = Path(graphify_output_dir)
        self.god_node_threshold = god_node_threshold
        self._graph_data: Optional[Dict] = None
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: List[GraphEdge] = []
        self._page_to_node: Dict[str, str] = {}  # Maps page title to node ID
        self._community_names: Dict[int, str] = {}

    def load_graph(self) -> bool:
        """Load graph.json from graphify output."""
        graph_path = self.graphify_output_dir / "graph.json"
        if not graph_path.exists():
            logger.warning(f"Graph file not found: {graph_path}")
            return False

        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                self._graph_data = json.load(f)
            self._parse_graph()
            self._build_page_mappings()
            self._generate_community_names()
            logger.info(f"Loaded graph: {len(self._nodes)} nodes, {len(self._edges)} edges")
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse graph JSON: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load graph: {e}")
            return False

    def _parse_graph(self):
        """Parse graph data into node and edge objects."""
        self._nodes = {}
        self._edges = []

        if not self._graph_data:
            return

        # Parse nodes
        for node_data in self._graph_data.get("nodes", []):
            node_id = node_data.get("id", "")
            if not node_id:
                continue

            # Calculate degree from edges
            degree = 0

            # Extract community from attributes
            attrs = node_data.get("attributes", {})
            community = attrs.get("community")

            node = GraphNode(
                id=node_id,
                label=node_data.get("label", node_id),
                node_type=attrs.get("type", "unknown"),
                community=community,
                degree=degree,  # Will be updated after parsing edges
                source_file=attrs.get("source_file"),
                attributes=attrs,
            )
            self._nodes[node_id] = node

        # Parse edges (NetworkX uses 'links' key in exported JSON)
        edge_key = "edges" if "edges" in self._graph_data else "links"
        for edge_data in self._graph_data.get(edge_key, []):
            edge = GraphEdge(
                source=edge_data.get("source", ""),
                target=edge_data.get("target", ""),
                relation=edge_data.get("relation", "related_to"),
                confidence=edge_data.get("confidence", "INFERRED"),
                confidence_score=edge_data.get("confidence_score"),
            )
            self._edges.append(edge)

            # Update node degrees
            if edge.source in self._nodes:
                self._nodes[edge.source].degree += 1
            if edge.target in self._nodes:
                self._nodes[edge.target].degree += 1

    def _build_page_mappings(self):
        """Build mappings between wiki page titles and graph node IDs."""
        self._page_to_node = {}

        # Index all wiki pages
        wiki_pages = self._get_all_wiki_pages()
        page_titles = {self._normalize_title(p.stem): p for p in wiki_pages}

        # Map nodes to pages
        for node_id, node in self._nodes.items():
            normalized_label = self._normalize_title(node.label)

            # Direct match
            if normalized_label in page_titles:
                self._page_to_node[normalized_label] = node_id
                continue

            # Partial match (node label contained in page title or vice versa)
            for page_title, page_path in page_titles.items():
                if normalized_label in page_title or page_title in normalized_label:
                    self._page_to_node[page_title] = node_id
                    break

    def _generate_community_names(self):
        """Generate human-readable names for communities based on god nodes."""
        if not self._nodes:
            return

        # Group nodes by community
        communities: Dict[int, List[GraphNode]] = {}
        for node in self._nodes.values():
            if node.community is not None:
                communities.setdefault(node.community, []).append(node)

        # Name each community by its highest-degree node
        for comm_id, nodes in communities.items():
            sorted_nodes = sorted(nodes, key=lambda n: n.degree, reverse=True)
            top_node = sorted_nodes[0] if sorted_nodes else None
            if top_node:
                self._community_names[comm_id] = f"{top_node.label} Cluster"
            else:
                self._community_names[comm_id] = f"Community {comm_id}"

    def _get_all_wiki_pages(self) -> List[Path]:
        """Get all markdown pages in the wiki directory."""
        wiki_root = self.wiki_dir / "wiki"
        if not wiki_root.exists():
            return []
        return list(wiki_root.rglob("*.md"))

    def _normalize_title(self, title: str) -> str:
        """Normalize a title for comparison."""
        # Lowercase, replace hyphens/underscores with spaces
        normalized = title.lower().replace("-", " ").replace("_", " ")
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        return normalized

    def get_page_graph_info(self, page_path: Path) -> Optional[PageGraphInfo]:
        """
        Get graph-derived information for a wiki page.

        Args:
            page_path: Path to the wiki markdown file

        Returns:
            PageGraphInfo with relationships and metadata, or None if not in graph
        """
        if not self._nodes:
            self.load_graph()

        page_title = page_path.stem
        normalized_title = self._normalize_title(page_title)

        # Find corresponding node
        node_id = self._page_to_node.get(normalized_title)
        if not node_id or node_id not in self._nodes:
            return None

        node = self._nodes[node_id]

        # Calculate god node threshold
        all_degrees = [n.degree for n in self._nodes.values()]
        if all_degrees:
            import statistics
            mean_degree = statistics.mean(all_degrees)
            std_degree = statistics.stdev(all_degrees) if len(all_degrees) > 1 else 0
            god_threshold = mean_degree + 2 * std_degree  # 2 sigma above mean
            is_god_node = node.degree >= god_threshold
        else:
            is_god_node = False

        # Find relationships
        relationships = []
        neighbor_titles = []

        for edge in self._edges:
            rel = None
            neighbor_id = None

            if edge.source == node_id:
                rel = GraphRelationship(
                    target_title=self._get_node_title(edge.target),
                    relation_type=edge.relation,
                    confidence=edge.confidence,
                    confidence_score=edge.confidence_score,
                    edge_type="outbound",
                )
                neighbor_id = edge.target
            elif edge.target == node_id:
                rel = GraphRelationship(
                    target_title=self._get_node_title(edge.source),
                    relation_type=f"{edge.relation}_by",
                    confidence=edge.confidence,
                    confidence_score=edge.confidence_score,
                    edge_type="inbound",
                )
                neighbor_id = edge.source

            if rel and neighbor_id:
                relationships.append(rel)
                neighbor_titles.append(self._get_node_title(neighbor_id))

        # Sort relationships by confidence
        relationships.sort(
            key=lambda r: (
                self.CONFIDENCE_ORDER.get(r.confidence, 0),
                r.confidence_score or 0,
            ),
            reverse=True,
        )

        return PageGraphInfo(
            page_title=page_title,
            page_path=page_path,
            community=node.community,
            community_name=self._community_names.get(node.community),
            degree=node.degree,
            is_god_node=is_god_node,
            relationships=relationships[:10],  # Top 10 relationships
            neighbors=neighbor_titles[:20],  # Top 20 neighbors
        )

    def _get_node_title(self, node_id: str) -> str:
        """Get human-readable title for a node."""
        if node_id in self._nodes:
            return self._nodes[node_id].label
        return node_id

    def inject_graph_section(self, markdown_content: str, page_path: Path) -> str:
        """
        Inject a ## Related (from graph) section into markdown content.

        Args:
            markdown_content: Original markdown content
            page_path: Path to the markdown file

        Returns:
            Modified markdown with graph-derived relationships appended
        """
        graph_info = self.get_page_graph_info(page_path)
        if not graph_info or not graph_info.relationships:
            return markdown_content

        # Build graph section
        lines = ["\n\n## Related (from graph)\n"]

        if graph_info.community_name:
            lines.append(f"**Community:** {graph_info.community_name}\n")

        if graph_info.is_god_node:
            lines.append(f"⭐ **God Node** — connects to {graph_info.degree} concepts\n")

        lines.append("\n### Graph Connections\n")

        # Group by confidence
        extracted = [r for r in graph_info.relationships if r.confidence == "EXTRACTED"]
        inferred = [r for r in graph_info.relationships if r.confidence == "INFERRED"]
        ambiguous = [r for r in graph_info.relationships if r.confidence == "AMBIGUOUS"]

        if extracted:
            lines.append("\n**Verified (extracted from source):**\n")
            for rel in extracted:
                conf_str = f" ({rel.confidence_score:.2f})" if rel.confidence_score else ""
                arrow = "→" if rel.edge_type == "outbound" else "←"
                lines.append(f"- [[{rel.target_title}]] — `{rel.relation_type}{conf_str}` {arrow}\n")

        if inferred:
            lines.append("\n**Inferred (probable connections):**\n")
            for rel in inferred:
                conf_str = f" ({rel.confidence_score:.2f})" if rel.confidence_score else ""
                arrow = "→" if rel.edge_type == "outbound" else "←"
                lines.append(f"- [[{rel.target_title}]] — `{rel.relation_type}{conf_str}` {arrow}\n")

        if ambiguous:
            lines.append("\n**Ambiguous (needs review):**\n")
            for rel in ambiguous:
                arrow = "→" if rel.edge_type == "outbound" else "←"
                lines.append(f"- [[{rel.target_title}]] — `{rel.relation_type}` {arrow}\n")

        graph_section = "".join(lines)

        # Check if section already exists
        if "## Related (from graph)" in markdown_content:
            # Replace existing section
            pattern = r"## Related \(from graph\).*?(?=\n## |\Z)"
            import re
            return re.sub(pattern, graph_section.strip(), markdown_content, flags=re.DOTALL)

        # Append to end
        return markdown_content + graph_section

    def suggest_missing_pages(self) -> List[Tuple[str, int]]:
        """
        Suggest wiki pages that should be created based on graph nodes.

        Returns:
            List of (node_label, degree) tuples for nodes not yet in wiki
        """
        if not self._nodes:
            self.load_graph()

        existing_pages = set()
        for page in self._get_all_wiki_pages():
            existing_pages.add(self._normalize_title(page.stem))

        missing = []
        for node_id, node in self._nodes.items():
            normalized_label = self._normalize_title(node.label)
            if normalized_label not in existing_pages:
                missing.append((node.label, node.degree))

        # Sort by degree (importance)
        missing.sort(key=lambda x: x[1], reverse=True)
        return missing[:20]  # Top 20 suggestions

    def get_god_nodes(self, top_n: int = 10) -> List[GraphNode]:
        """Get the top N highest-degree nodes (god nodes)."""
        if not self._nodes:
            self.load_graph()

        sorted_nodes = sorted(self._nodes.values(), key=lambda n: n.degree, reverse=True)
        return sorted_nodes[:top_n]

    def get_community_summary(self, community_id: int) -> Dict[str, Any]:
        """Get summary information for a community."""
        if not self._nodes:
            self.load_graph()

        nodes = [n for n in self._nodes.values() if n.community == community_id]
        if not nodes:
            return {}

        # Sort by degree
        nodes.sort(key=lambda n: n.degree, reverse=True)

        return {
            "id": community_id,
            "name": self._community_names.get(community_id, f"Community {community_id}"),
            "node_count": len(nodes),
            "top_nodes": [n.label for n in nodes[:5]],
            "total_degree": sum(n.degree for n in nodes),
        }


# Global instance
_graph_sync_service: Optional[GraphSyncService] = None


def init_graph_sync_service(
    wiki_dir: Path,
    graphify_output_dir: Path,
    god_node_threshold: float = 0.9,
) -> GraphSyncService:
    """Initialize global graph sync service."""
    global _graph_sync_service
    _graph_sync_service = GraphSyncService(
        wiki_dir=wiki_dir,
        graphify_output_dir=graphify_output_dir,
        god_node_threshold=god_node_threshold,
    )
    _graph_sync_service.load_graph()
    return _graph_sync_service


def get_graph_sync_service() -> Optional[GraphSyncService]:
    """Get global graph sync service instance."""
    return _graph_sync_service
