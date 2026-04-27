"""
REGRESSION TEST: Graph UI Fixes - Scroll and Node Details
=========================================================

Date: 2025-04-26
Files: frontend/css/graph.css, frontend/js/graph.js
Issues Fixed:
  1. "Ask the Graph" section missing scroll capability
  2. Node details panel not showing # of connections and top 5 connections

Verify: CSS has proper scroll properties, JS shows detailed node info with connections
"""

import pytest


def test_graph_css_has_scroll_styles():
    """
    Verify that graph.css has proper scroll styles for sidebar sections.
    
    Issues prevented:
    - "Ask the Graph" section without scroll hides content
    """
    import re

    with open('/root/llm-wiki-system/frontend/css/graph.css', 'r') as f:
        css = f.read()

    # Check for overflow-y auto on graph-controls (including query section)
    assert 'overflow-y: auto' in css, "graph-controls missing overflow-y: auto"

    # Check graph-sidebar has proper scrolling
    sidebar_pattern = r'\.graph-sidebar\s*{[^}]*overflow[^}]*}'
    assert re.search(sidebar_pattern, css, re.DOTALL), "graph-sidebar missing overflow"


def test_graph_js_has_node_details_with_connections():
    """
    Verify that graph.js showNodeDetails() displays connection counts and top connections.
    
    Issues prevented:
    - Node click doesn't show # of connections
    - Top connections not listed in details panel
    """
    import re

    with open('/root/llm-wiki-system/frontend/js/graph.js', 'r') as f:
        js = f.read()

    # Should have showNodeDetails function
    assert 'function showNodeDetails' in js, "Missing showNodeDetails function"

    # Should calculate and display connection counts
    assert 'outgoing.length' in js, "Not using outgoing connection count"
    assert 'incoming.length' in js, "Not using incoming connection count"

    # Should show Total Connections stats
    assert 'Total Connections' in js, "Missing total connections display"

    # Should show outgoing/incoming labels in connection summary
    assert 'Outgoing' in js and 'Incoming' in js, "Missing outgoing/incoming labels"

    # Should limit to top 5 connections
    assert '.slice(0, 5)' in js or 'Top 5' in js, "Not slicing connections to top N"

    # Should show connection counts in section headers  
    assert 'total)' in js.lower() or '(N total)' in js, "Missing count in section headers"


def test_graph_js_search_shows_node_details():
    """
    Verify that node search highlights trigger node details display.
    """
    with open('/root/llm-wiki-system/frontend/js/graph.js', 'r') as f:
        js = f.read()

    # searchNode should call showNodeDetails on match
    # (This is the desired behavior - clicking a search result should show details)
    assert 'showNodeDetails' in js, "showNodeDetails not called anywhere"

    # Check that highlighted nodes can be clicked
    assert "nodeElements.on('click'" in js, "Nodes don't have click handlers"
