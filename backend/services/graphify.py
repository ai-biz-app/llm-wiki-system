"""
Graphify integration service for LLM Wiki.
Wraps the graphify Python library to build knowledge graphs from raw sources.
"""

import asyncio
import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GraphifyResult:
    """Result from running graphify pipeline."""
    success: bool
    graph_json_path: Optional[Path] = None
    graph_html_path: Optional[Path] = None
    graph_report_path: Optional[Path] = None
    obsidian_vault_path: Optional[Path] = None
    message: str = ""
    stats: Dict[str, Any] = None


class GraphifyService:
    """Service for running Graphify on wiki corpus."""

    def __init__(
        self,
        output_dir: Path,
        mode: str = "standard",
        obsidian_export: bool = True,
        directed: bool = False,
        timeout_default: int = 10,
        timeout_query: int = 30,
        timeout_ingest: int = 300,
    ):
        self.output_dir = Path(output_dir)
        self.mode = mode
        self.obsidian_export = obsidian_export
        self.directed = directed
        self.timeout_default = timeout_default
        self.timeout_query = timeout_query
        self.timeout_ingest = timeout_ingest
        self.graphify_available = self._check_graphify()

    def _check_graphify(self) -> bool:
        """Check if graphify CLI is available."""
        graphify_path = shutil.which("graphify")
        if graphify_path:
            return True
        # Try via python -m
        try:
            result = subprocess.run(
                ["python", "-m", "graphify", "--help"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            pass
        return False

    async def run_graphify(
        self,
        corpus_dir: Path,
        update: bool = True,
    ) -> GraphifyResult:
        """
        Run graphify on the corpus directory.

        Args:
            corpus_dir: Directory containing raw sources
            update: If True, only process changed files (uses SHA256 cache)

        Returns:
            GraphifyResult with paths to outputs and status
        """
        if not self.graphify_available:
            return GraphifyResult(
                success=False,
                message="graphify is not installed. Run: pip install graphifyy",
            )

        corpus_dir = Path(corpus_dir)
        if not corpus_dir.exists():
            return GraphifyResult(
                success=False,
                message=f"Corpus directory does not exist: {corpus_dir}",
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Build command
        cmd = self._build_command(corpus_dir, update)

        logger.info(f"Running graphify: {' '.join(cmd)}")

        try:
            # Run graphify as subprocess with strict timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Use timeout_ingest for full corpus processing
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_ingest
            )
            stdout_str = stdout.decode() if stdout else ""
            stderr_str = stderr.decode() if stderr else ""

            if process.returncode != 0:
                logger.error(f"Graphify failed: {stderr_str}")
                return GraphifyResult(
                    success=False,
                    message=f"Graphify failed: {stderr_str}",
                )

            # Parse results
            result = self._parse_output(stdout_str, stderr_str)

            logger.info(f"Graphify completed: {result.message}")
            return result

        except asyncio.TimeoutError:
            return GraphifyResult(
                success=False,
                message="Graphify timed out (may need more time for large corpus)",
            )
        except Exception as e:
            logger.exception("Graphify error")
            return GraphifyResult(
                success=False,
                message=f"Graphify error: {str(e)}",
            )

    def _build_command(self, corpus_dir: Path, update: bool) -> List[str]:
        """Build graphify command with arguments."""
        # Prefer CLI if available
        if shutil.which("graphify"):
            cmd = ["graphify", str(corpus_dir)]
        else:
            cmd = ["python", "-m", "graphify", str(corpus_dir)]

        # Output directory
        cmd.extend(["--output-dir", str(self.output_dir)])

        # Mode
        if self.mode == "deep":
            cmd.append("--deep")

        # Update mode (incremental)
        if update:
            cmd.append("--update")

        # Directed graph
        if self.directed:
            cmd.append("--directed")

        # Obsidian export
        if self.obsidian_export:
            cmd.append("--obsidian")
            cmd.extend(["--obsidian-dir", str(self.output_dir / "obsidian")])

        # Wiki export (for LLM wiki integration)
        cmd.append("--wiki")

        # SVG export
        cmd.append("--svg")

        return cmd

    def _parse_output(self, stdout: str, stderr: str) -> GraphifyResult:
        """Parse graphify output to extract results."""
        stats = {}

        # Look for stats in output
        for line in stdout.split("\n"):
            if "nodes" in line.lower() and "edges" in line.lower():
                # Extract numbers like "47 nodes, 312 edges"
                import re
                nodes_match = re.search(r"(\d+)\s+nodes", line, re.I)
                edges_match = re.search(r"(\d+)\s+edges", line, re.I)
                if nodes_match:
                    stats["node_count"] = int(nodes_match.group(1))
                if edges_match:
                    stats["edge_count"] = int(edges_match.group(1))

            if "token" in line.lower() and "reduction" in line.lower():
                # Extract token reduction stat
                import re
                reduction_match = re.search(r"([\d.]+)x", line)
                if reduction_match:
                    stats["token_reduction"] = float(reduction_match.group(1))

        # Check for output files
        graph_json = self.output_dir / "graph.json"
        graph_html = self.output_dir / "graph.html"
        graph_report = self.output_dir / "GRAPH_REPORT.md"
        obsidian_vault = self.output_dir / "obsidian"

        # Check if files were created
        files_created = []
        if graph_json.exists():
            files_created.append("graph.json")
        if graph_html.exists():
            files_created.append("graph.html")
        if graph_report.exists():
            files_created.append("GRAPH_REPORT.md")
        if obsidian_vault.exists():
            files_created.append("obsidian_vault/")

        success = len(files_created) > 0

        # Try to extract a summary message
        message = f"Created: {', '.join(files_created)}"
        if stats.get("node_count"):
            message += f" | {stats['node_count']} nodes, {stats.get('edge_count', 0)} edges"

        return GraphifyResult(
            success=success,
            graph_json_path=graph_json if graph_json.exists() else None,
            graph_html_path=graph_html if graph_html.exists() else None,
            graph_report_path=graph_report if graph_report.exists() else None,
            obsidian_vault_path=obsidian_vault if obsidian_vault.exists() else None,
            message=message,
            stats=stats,
        )

    def read_graph_json(self) -> Optional[Dict[str, Any]]:
        """Read and parse the graph.json file."""
        graph_path = self.output_dir / "graph.json"
        if not graph_path.exists():
            return None
        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read graph.json: {e}")
            return None

    def read_graph_report(self) -> Optional[str]:
        """Read the GRAPH_REPORT.md file."""
        report_path = self.output_dir / "GRAPH_REPORT.md"
        if not report_path.exists():
            return None
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read GRAPH_REPORT.md: {e}")
            return None

    def query_graph(
        self,
        query: str,
        dfs: bool = False,
        budget: Optional[int] = None,
    ) -> Optional[str]:
        """
        Query the graph using graphify CLI.

        Args:
            query: Natural language query
            dfs: Use depth-first search for path tracing
            budget: Max tokens for response

        Returns:
            Query result as string, or None on error
        """
        graph_json = self.output_dir / "graph.json"
        if not graph_json.exists():
            return None

        cmd = ["graphify", "query", query]
        cmd.extend(["--graph", str(graph_json)])

        if dfs:
            cmd.append("--dfs")
        if budget:
            cmd.extend(["--budget", str(budget)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_query,
            )
            if result.returncode == 0:
                return result.stdout
            else:
                logger.error(f"Graph query failed: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error(f"Graph query timed out after {self.timeout_query}s")
            return None
        except Exception as e:
            logger.error(f"Graph query error: {e}")
            return None

    def get_path(self, from_node: str, to_node: str) -> Optional[str]:
        """Get shortest path between two nodes."""
        graph_json = self.output_dir / "graph.json"
        if not graph_json.exists():
            return None

        cmd = [
            "graphify", "path",
            from_node, to_node,
            "--graph", str(graph_json),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_default,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception as e:
            logger.error(f"Path query error: {e}")
            return None

    def explain_node(self, node: str) -> Optional[str]:
        """Get plain-language explanation of a node."""
        graph_json = self.output_dir / "graph.json"
        if not graph_json.exists():
            return None

        cmd = [
            "graphify", "explain", node,
            "--graph", str(graph_json),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_default,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except subprocess.TimeoutExpired:
            logger.error(f"Explain timed out after {self.timeout_default}s")
            return None
        except Exception as e:
            logger.error(f"Explain error: {e}")
            return None


# Global service instance (initialized from config)
_graphify_service: Optional[GraphifyService] = None


def init_graphify_service(
    output_dir: Path,
    mode: str = "standard",
    obsidian_export: bool = True,
    directed: bool = False,
    timeout_default: int = 10,
    timeout_query: int = 30,
    timeout_ingest: int = 300,
) -> GraphifyService:
    """Initialize global graphify service."""
    global _graphify_service
    _graphify_service = GraphifyService(
        output_dir=output_dir,
        mode=mode,
        obsidian_export=obsidian_export,
        directed=directed,
        timeout_default=timeout_default,
        timeout_query=timeout_query,
        timeout_ingest=timeout_ingest,
    )
    return _graphify_service


def get_graphify_service() -> Optional[GraphifyService]:
    """Get global graphify service instance."""
    return _graphify_service
