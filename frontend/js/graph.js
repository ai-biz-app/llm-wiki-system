// Graph Visualization Component
(function() {
  'use strict';

  let graphData = null;
  let simulation = null;
  let svg = null;
  let linkElements = null;
  let nodeElements = null;

  // Colors for communities
  const communityColors = [
    '#4ade80', '#f472b6', '#60a5fa', '#fbbf24', '#a78bfa',
    '#34d399', '#fb7185', '#22d3ee', '#a3e635', '#e879f9'
  ];

  const confidenceColors = {
    'EXTRACTED': '#22c55e',
    'INFERRED': '#f59e0b',
    'AMBIGUOUS': '#ef4444'
  };

  // Initialize graph when Graph tab is shown
  function init() {
    // Setup navigation for graph tab
    const navLinks = document.querySelectorAll('.nav-link[data-page="graph"]');
    navLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        showPage('graph');
        loadGraphData();
      });
    });

    // Setup event listeners
    document.getElementById('graph-search-btn')?.addEventListener('click', searchNode);
    document.getElementById('graph-search')?.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') searchNode();
    });
    document.getElementById('confidence-filter')?.addEventListener('change', filterGraph);
    document.getElementById('path-button')?.addEventListener('click', findPath);
    document.getElementById('query-button')?.addEventListener('click', queryGraph);
    document.getElementById('graph-query')?.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') queryGraph();
    });
  }

  function showPage(pageId) {
    document.querySelectorAll('.page, .nav-link').forEach(el => {
      el.classList.remove('active');
      if (el.classList.contains('page')) el.classList.add('hidden');
    });
    document.getElementById(`page-${pageId}`)?.classList.remove('hidden');
    document.querySelector(`.nav-link[data-page="${pageId}"]`)?.classList.add('active');
  }

  async function loadGraphData() {
    try {
      // Load stats
      const statsRes = await fetch('/api/graph/stats');
      if (!statsRes.ok) throw new Error('Failed to load stats');
      const stats = await statsRes.json();

      document.getElementById('stat-nodes').textContent = stats.node_count;
      document.getElementById('stat-edges').textContent = stats.edge_count;
      document.getElementById('stat-communities').textContent = stats.community_count;
      document.getElementById('stat-god-nodes').textContent = stats.god_nodes?.length || 0;

      // Load full graph
      const graphRes = await fetch('/api/graph/full');
      if (!graphRes.ok) throw new Error('Failed to load graph');
      graphData = await graphRes.json();

      renderGraph(graphData);
      populateCommunityFilter(graphData);
    } catch (err) {
      console.error('Graph load error:', err);
      document.getElementById('graph-viz').innerHTML =
        `<div class="loading">Error loading graph: ${err.message}</div>`;
    }
  }

  function populateCommunityFilter(data) {
    const communities = new Set();
    data.nodes?.forEach(node => {
      const comm = node.community ?? node.attributes?.community;
      if (comm !== undefined) communities.add(comm);
    });

    const select = document.getElementById('community-filter');
    select.innerHTML = '<option value="">All Communities</option>';
    Array.from(communities).sort((a, b) => a - b).forEach(comm => {
      select.innerHTML += `<option value="${comm}">Community ${comm}</option>`;
    });
    select.addEventListener('change', filterGraph);
  }

  function renderGraph(data) {
    const container = document.getElementById('graph-viz');
    container.innerHTML = '';

    if (!data?.nodes?.length) {
      container.innerHTML = '<div class="loading">No graph data available</div>';
      return;
    }

    const width = container.clientWidth;
    const height = container.clientHeight;

    // Prepare nodes and edges
    const nodes = data.nodes.map(d => ({ ...d }));
    const edgeKey = data.links ? 'links' : 'edges';
    const edges = (data[edgeKey] || []).map(d => ({ ...d }));
    console.log(`Graph: ${nodes.length} nodes, ${edges.length} edges (key: ${edgeKey})`);

    // Create SVG
    svg = d3.select('#graph-viz')
      .append('svg')
      .attr('viewBox', [0, 0, width, height])
      .attr('width', width)
      .attr('height', height);

    // Add zoom behavior
    const g = svg.append('g');
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (e) => g.attr('transform', e.transform));
    svg.call(zoom);

    // Create simulation
    simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => (d.degree || 1) * 5 + 10));

    // Draw edges
    const linkGroup = g.append('g');
    
    linkElements = linkGroup
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('class', d => `graph-link ${(d.confidence || 'inferred').toLowerCase()}`)
      .attr('stroke-width', d => Math.sqrt(d.weight || 1));
    
    // Add edge labels
    const edgeLabels = linkGroup
      .selectAll('text')
      .data(edges)
      .join('text')
      .attr('class', 'edge-label')
      .attr('font-size', '8px')
      .attr('fill', '#888')
      .attr('text-anchor', 'middle')
      .attr('dy', -3)
      .text(d => d.relation ? d.relation.substring(0, 15) : '');

    // Draw nodes
    nodeElements = g.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('class', 'graph-node')
      .attr('data-id', d => d.id)
      .call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));

    // Node circles
    nodeElements.append('circle')
      .attr('r', d => Math.max(6, Math.min(20, (d.degree || 1) * 3 + 5)))
      .attr('fill', d => {
        const comm = d.community ?? d.attributes?.community;
        return communityColors[comm % communityColors.length] || '#60a5fa';
      });

    // Node labels - show all labels
    nodeElements.append('text')
      .attr('dx', 12)
      .attr('dy', 4)
      .attr('class', 'node-label')
      .text(d => d.label || d.id);

    // Add tooltips to all nodes
    nodeElements.append('title')
      .text(d => {
        const attrs = d.attributes || {};
        const nodeType = attrs.type && attrs.type !== 'unknown' ? attrs.type : 'Concept';
        const degree = d.degree !== undefined ? d.degree : (attrs.degree || 'N/A');
        const comm = d.community !== undefined ? d.community : attrs.community;
        let tooltip = `${d.label || d.id}\nType: ${nodeType}\nConnections: ${degree}`;
        if (comm !== undefined) tooltip += `\nCommunity: ${comm}`;
        return tooltip;
      });

    // Click handler
    nodeElements.on('click', (event, d) => showNodeDetails(d));

    // Update positions
    simulation.on('tick', () => {
      linkElements
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
      
      edgeLabels
        .attr('x', d => (d.source.x + d.target.x) / 2)
        .attr('y', d => (d.source.y + d.target.y) / 2);

      nodeElements.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    function dragstarted(event, d) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event, d) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event, d) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }
  }

  function filterGraph() {
    if (!graphData || !nodeElements) return;

    const community = document.getElementById('community-filter').value;
    const confidence = document.getElementById('confidence-filter').value;

    nodeElements.classed('dimmed', d => {
      let hidden = false;
      if (community && String(d.community ?? d.attributes?.community) !== community) {
        hidden = true;
      }
      return hidden;
    });

    linkElements.classed('dimmed', d => {
      if (!confidence) return false;
      return (d.confidence || 'INFERRED') !== confidence;
    });
  }

  function searchNode() {
    const query = document.getElementById('graph-search').value.toLowerCase();
    if (!query || !nodeElements) return;

    // Highlight matching nodes
    const matches = nodeElements.classed('highlighted', d =>
      (d.label || d.id).toLowerCase().includes(query)
    );

    // Find all matches
    const matchingNodes = graphData.nodes.filter(d =>
      (d.label || d.id).toLowerCase().includes(query)
    );

    // If single exact match, show details
    if (matchingNodes.length === 1) {
      showNodeDetails(matchingNodes[0]);
      // Zoom to the node
      if (simulation) {
        const match = matchingNodes[0];
        const zoom = d3.zoom().on('zoom', (e) => {
          svg.select('g').attr('transform', e.transform);
        });
        // Center on the matched node
        svg.transition().duration(750).call(
          zoom.transform,
          d3.zoomIdentity.translate(
            svg.attr('width') / 2 - match.x || 0,
            svg.attr('height') / 2 - match.y || 0
          ).scale(1.5)
        );
      }
    } else if (matchingNodes.length > 1) {
      // Multiple matches - clear details panel
      const panel = document.getElementById('graph-node-details');
      panel.innerHTML = `<div class="node-details">
        <p class="no-connections">${matchingNodes.length} nodes found. Click one to view details.</p>
      </div>`;
      panel.classList.add('has-content');
    }

    if (matchingNodes.length > 0 && simulation) {
      simulation.alpha(0.3).restart();
    }
  }

  function showNodeDetails(node) {
    const panel = document.getElementById('graph-node-details');
    const attrs = node.attributes || {};
    const community = node.community ?? attrs.community;
    const nodeType = attrs.type && attrs.type !== 'unknown' ? attrs.type : 'Concept';
    const confidence = node.confidence ?? attrs.confidence ?? 'UNKNOWN';

    // Color code for confidence
    const confidenceColors = {
      'EXTRACTED': '#22c55e',
      'INFERRED': '#f59e0b',
      'AMBIGUOUS': '#ef4444',
      'UNKNOWN': '#888'
    };
    const confColor = confidenceColors[confidence] || confidenceColors['UNKNOWN'];

    // Find all relationships (incoming and outgoing)
    const edgeKey = graphData.links ? 'links' : 'edges';
    const allEdges = (graphData[edgeKey] || []);

    // Separate by direction
    const outgoing = allEdges.filter(e => {
      const srcId = typeof e.source === 'object' ? e.source.id : e.source;
      return srcId === node.id;
    });
    const incoming = allEdges.filter(e => {
      const tgtId = typeof e.target === 'object' ? e.target.id : e.target;
      return tgtId === node.id;
    });

    const totalConnections = outgoing.length + incoming.length;

    let html = `
      <div class="node-details">
        <h3>${node.label || node.id}</h3>
        <div class="node-stats">
          <span class="node-stat" style="background: ${confColor}20; color: ${confColor}; border: 1px solid ${confColor}40;">${confidence}</span>
          <span class="node-stat"><strong>Type:</strong> ${nodeType}</span>
          <span class="node-stat"><strong>Total Connections:</strong> ${totalConnections}</span>
          ${community !== undefined ? `<span class="node-stat"><strong>Community:</strong> ${community}</span>` : ''}
        </div>

        <!-- Connection Summary -->
        <div class="connection-summary">
          <div class="connection-count outgoing">
            <span class="count-num">${outgoing.length}</span>
            <span class="count-label">Outgoing</span>
          </div>
          <div class="connection-count incoming">
            <span class="count-num">${incoming.length}</span>
            <span class="count-label">Incoming</span>
          </div>
        </div>
    `;

    // Helper to get top 5 weighted connections
    function getTopConnections(edges, isOutgoing) {
      const sorted = edges
        .map(e => {
          const otherId = isOutgoing
            ? (typeof e.target === 'object' ? e.target.id : e.target)
            : (typeof e.source === 'object' ? e.source.id : e.source);
          const otherNode = graphData.nodes?.find(n => n.id === otherId);
          return {
            ...e,
            otherId,
            otherLabel: otherNode?.label || otherId,
            otherDegree: otherNode?.degree || otherNode?.attributes?.degree || 0
          };
        })
        .sort((a, b) => (b.weight || 1) - (a.weight || 1) || b.otherDegree - a.otherDegree);
      return sorted.slice(0, 5);
    }

    // Top 5 Outgoing connections
    if (outgoing.length) {
      const topOutgoing = getTopConnections(outgoing, true);
      html += `<div class="relationships"><h4>Top 5 Outgoing (${outgoing.length} total)</h4><ul class="relationship-list">`;
      topOutgoing.forEach(e => {
        const edgeConf = e.confidence || 'inferred';
        const confDot = `<span class="conf-dot ${edgeConf.toLowerCase()}"></span>`;
        html += `<li>${confDot} <strong>${e.relation || 'relates to'}</strong> → ${e.otherLabel}</li>`;
      });
      if (outgoing.length > 5) {
        html += `<li class="more-connections">+${outgoing.length - 5} more outgoing...</li>`;
      }
      html += '</ul></div>';
    }

    // Top 5 Incoming connections
    if (incoming.length) {
      const topIncoming = getTopConnections(incoming, false);
      html += `<div class="relationships"><h4>Top 5 Incoming (${incoming.length} total)</h4><ul class="relationship-list">`;
      topIncoming.forEach(e => {
        const edgeConf = e.confidence || 'inferred';
        const confDot = `<span class="conf-dot ${edgeConf.toLowerCase()}"></span>`;
        html += `<li>${confDot} ← <strong>${e.relation || 'related by'}</strong> ${e.otherLabel}</li>`;
      });
      if (incoming.length > 5) {
        html += `<li class="more-connections">+${incoming.length - 5} more incoming...</li>`;
      }
      html += '</ul></div>';
    }

    // No connections
    if (!outgoing.length && !incoming.length) {
      html += '<p class="no-connections">No connections found for this node.</p>';
    }

    html += '</div>';
    panel.innerHTML = html;
    panel.classList.add('has-content');
  }

  async function findPath() {
    const from = document.getElementById('path-from').value.trim();
    const to = document.getElementById('path-to').value.trim();
    const resultDiv = document.getElementById('path-result');

    if (!from || !to) {
      resultDiv.textContent = 'Enter both nodes';
      return;
    }

    resultDiv.textContent = 'Calculating path...';

    // Simple BFS path finding
    const edgeKey = graphData.edges ? 'edges' : 'links';
    const edges = graphData[edgeKey] || [];
    const adjacency = new Map();

    edges.forEach(e => {
      const sourceId = typeof e.source === 'object' ? e.source.id : e.source;
      const targetId = typeof e.target === 'object' ? e.target.id : e.target;

      if (!adjacency.has(sourceId)) adjacency.set(sourceId, []);
      if (!adjacency.has(targetId)) adjacency.set(targetId, []);
      adjacency.get(sourceId).push({ node: targetId, relation: e.relation });
      adjacency.get(targetId).push({ node: sourceId, relation: e.relation });
    });

    // BFS
    const queue = [[from]];
    const visited = new Set([from]);

    while (queue.length) {
      const path = queue.shift();
      const current = path[path.length - 1];

      if (current === to) {
        resultDiv.innerHTML = `<strong>Path found (${path.length} nodes):</strong><br>${path.join(' → ')}`;
        return;
      }

      for (const neighbor of adjacency.get(current) || []) {
        if (!visited.has(neighbor.node)) {
          visited.add(neighbor.node);
          queue.push([...path, neighbor.node]);
        }
      }
    }

    resultDiv.textContent = 'No path found between nodes';
  }

  async function queryGraph() {
    const query = document.getElementById('graph-query').value.trim();
    const resultDiv = document.getElementById('query-result');

    if (!query) return;

    resultDiv.textContent = 'Querying graph...';

    try {
      const res = await fetch(`/api/graph/query?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error('Query failed');
      const data = await res.json();
      resultDiv.textContent = data.result || 'No results';
    } catch (err) {
      resultDiv.textContent = `Error: ${err.message}`;
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
