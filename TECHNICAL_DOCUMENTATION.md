# LLM Wiki System — Technical Documentation

> **Project**: Web-based LLM Wiki with Graphify Integration  
> **Purpose**: Build a Personal Knowledge Management (PKM) system without Obsidian dependency, running on a cheap Linux server  
> **Development Method**: Fully autonomous via Hermes AI Agents  
> **License**: MIT  
> **Created**: April 2025

---

## Executive Summary

This document provides a complete technical specification of the LLM Wiki System — a web-based personal knowledge management platform that enables automated ingestion of content from URLs and files into a structured markdown knowledge base. The system leverages Large Language Models (LLM) for content synthesis and includes an integrated knowledge graph visualization powered by Graphify.

The entire development was conducted autonomously using Hermes AI agents, with no manual coding required.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [System Components](#system-components)
3. [Technology Stack](#technology-stack)
4. [Directory Structure](#directory-structure)
5. [Backend Services](#backend-services)
6. [Frontend Architecture](#frontend-architecture)
7. [Graphify Integration](#graphify-integration)
8. [Deployment & Infrastructure](#deployment--infrastructure)
9. [Configuration Reference](#configuration-reference)
10. [API Reference](#api-reference)
11. [Security Considerations](#security-considerations)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             CLIENT LAYER                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Web Browser (SPA - Single Page Application)                        │    │
│  │  - Vanilla JavaScript (no build step)                               │    │
│  │  - Client-side routing via History API                              │    │
│  │  - D3.js for graph visualization                                    │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               │                                              │
│                           HTTPS (Caddy)                                      │
│                               │                                              │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                               ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  REVERSE PROXY LAYER                                                │    │
│  │  ┌───────────────────────────────────────────────────────────────┐  │    │
│  │  │  Caddy Server (Port 80/443 → 8080)                              │  │    │
│  │  │  - HTTPS with Let's Encrypt automatic certs                     │  │    │
│  │  │  - Basic Authentication (username/password)                     │  │    │
│  │  │  - Reverse proxy to FastAPI                                     │  │    │
│  │  └───────────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                               │                                              │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                               ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  APPLICATION LAYER (FastAPI + Uvicorn on Port 8080)                 │    │
│  │                                                                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │    │
│  │  │ REST API     │  │ Job Queue    │  │ Wiki Browser │  │ Graph   │ │    │
│  │  │ Routes       │  │ Worker       │  │ API          │  │ API     │ │    │
│  │  │              │  │              │  │              │  │         │ │    │
│  │  │ /api/ingest  │  │ JSON-lines   │  │ /api/pages   │  │ /api/   │ │    │
│  │  │ /api/status  │  │ based async  │  │ /api/search  │  │ graph/  │ │    │
│  │  │ /api/upload  │  │ processing   │  │ /api/overview│  │         │ │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └─────────┘ │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────────┐ │    │
│  │  │ Service Layer                                                  │ │    │
│  │  │ - Extraction (URL, PDF, DOCX, TXT)                            │ │    │
│  │  │ - Ingestion (LLM synthesis via Kimi-2.5/OpenRouter)           │ │    │
│  │  │ - Markdown Rendering (Obsidian-compatible)                    │ │    │
│  │  │ - Graphify Integration (Knowledge Graph)                      │ │    │
│  │  │ - Graph Sync (Cross-reference injection)                      │ │    │
│  │  └───────────────────────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                               │                                              │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                               ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  DATA LAYER (Local Filesystem)                                      │    │
│  │                                                                     │    │
│  │  ~/Documents/Obsidian Vault/LLM-Wiki/                               │    │
│  │  ├── SCHEMA.md          # Wiki schema & conventions                 │    │
│  │  ├── index.md           # Master page index                         │    │
│  │  ├── log.md             # Chronological action log                  │    │
│  │  ├── overview.md        # High-level topical overview               │    │
│  │  ├── raw/               # Layer 1: Immutable sources                │    │
│  │  │   ├── sources/       # Text documents, articles                  │    │
│  │  │   └── assets/        # Images, media files                       │    │
│  │  ├── wiki/              # Layer 2: Synthesized markdown            │    │
│  │  │   ├── sources/       # Source summaries                          │    │
│  │  │   ├── entities/      # People, orgs, products pages              │    │
│  │  │   ├── concepts/      # Topic pages                               │    │
│  │  │   └── analyses/      # Deep dive analyses                        │    │
│  │  └── graphify-out/      # Graphify outputs (NEW)                   │    │
│  │      ├── graph.json     # Network data (vis.js/D3 compatible)       │    │
│  │      ├── graph.html     # Standalone visualization                │    │
│  │      ├── GRAPH_REPORT.md# Generated summary report                 │    │
│  │      └── obsidian/       # Obsidian-compatible vault export         │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## System Components

### 1. Backend (FastAPI Application)

The backend is built on FastAPI with an asynchronous architecture supporting background job processing via a custom JSON-lines queue.

| Component | Purpose | Key Files |
|-----------|---------|-----------|
| **Main Application** | FastAPI app initialization, lifespan management | `backend/main.py` |
| **Configuration** | Pydantic settings with environment overrides | `backend/config.py` |
| **Job Queue** | Async task processing without Redis | `backend/jobs/worker.py` |
| **Routes** | REST API endpoints | `backend/routes/*.py` |
| **Services** | Business logic layer | `backend/services/*.py` |

### 2. Frontend (Vanilla JS SPA)

A single-page application without build dependencies, using vanilla JavaScript for client-side routing and D3.js for graph visualization.

### 3. LLM Integration

Content synthesis performed by Kimi-2.5 via OpenRouter API (or native Kimi API). The LLM transforms raw sources into structured markdown with automatic cross-linking.

### 4. Knowledge Graph (Graphify)

Multimodal knowledge extraction and visualization engine that:
- Parses code ASTs
- Extracts entities from text
- Builds interactive network visualizations
- Provides natural language graph queries

---

## Technology Stack

### Core Dependencies

```
Python 3.11+
├── FastAPI 2.x          # Web framework
├── Uvicorn              # ASGI server
├── Pydantic 2.x         # Settings & validation
├── httpx                # Async HTTP client
├── markdown             # Markdown → HTML
├── beautifulsoup4       # HTML parsing
├── PyMuPDF (fitz)       # PDF extraction
├── python-docx          # DOCX extraction
├── graphifyy            # Knowledge graph (pip install graphifyy)
├── faster-whisper       # Audio/video transcription
└── d3.v7.js             # Frontend visualization (CDN)
```

### Infrastructure

| Layer | Technology | Purpose |
|-------|------------|---------|
| Hosting | Hetzner CX23 VPS ($5/mo) | Ubuntu 24.04 in Helsinki |
| Web Server | Caddy | HTTPS + Reverse Proxy + Basic Auth |
| Firewall | UFW | IP-based access control |
| Process Manager | Systemd | Service management |

---

## Directory Structure

```
/root/llm-wiki-system/
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Pydantic settings
│   ├── models.py               # Request/response schemas
│   ├── __init__.py
│   ├── routes/
│   │   ├── ingest.py           # URL/file ingestion endpoints
│   │   ├── viewer.py           # Wiki browser API
│   │   ├── graph.py            # Graph query endpoints
│   │   └── __init__.py
│   ├── services/
│   │   ├── extraction.py       # Text extraction (URL, PDF, DOCX)
│   │   ├── extraction_enhanced.py  # Extended extraction
│   │   ├── ingestion.py        # LLM synthesis pipeline
│   │   ├── markdown_render.py  # MD → HTML with link rewriting
│   │   ├── file_storage.py     # File operations & slugs
│   │   ├── graphify.py         # Graphify wrapper service
│   │   └── graph_sync.py       # Graph-to-wiki synchronization
│   └── jobs/
│       ├── worker.py           # Async job queue worker
│       ├── queue.jsonl         # Job queue storage
│       └── results/            # Job result JSONs
├── frontend/
│   ├── index.html              # SPA shell
│   ├── css/
│   │   ├── style.css           # Main stylesheet
│   │   └── graph.css           # Graph visualization styles
│   ├── js/
│   │   ├── app.js              # SPA routing & UI logic
│   │   └── graph.js            # D3.js graph visualization
│   ├── overview.html           # Legacy (unused)
│   └── log.html                # Legacy (unused)
├── venv/                       # Python virtual environment
├── requirements.txt            # Python dependencies
├── start.sh                    # Startup script
└── README.md                   # Basic setup guide

/root/Documents/Obsidian Vault/LLM-Wiki/   # Data directory
├── SCHEMA.md
├── index.md
├── log.md
├── overview.md
├── raw/
│   ├── sources/
│   └── assets/
├── wiki/
│   ├── sources/
│   ├── entities/
│   ├── concepts/
│   └── analyses/
└── graphify-out/               # Generated by Graphify
    ├── graph.json
    ├── graph.html
    ├── GRAPH_REPORT.md
    └── obsidian/
```

---

## Backend Services

### Configuration Service (`config.py`)

Uses Pydantic Settings with environment variable support.

**Key Settings:**

```python
wiki_path: str                    # Wiki root directory
llm_model: str                    # Default: "kimi-k2.5"
llm_provider: str                 # "openrouter" or "kimi"
llm_base_url: str                 # API endpoint
llm_api_key: str                  # From ~/.hermes/.env
web_host: str                     # "0.0.0.0"
web_port: int                     # 8080
graphify_enabled: bool            # Enable knowledge graph
graphify_timeout_default: int     # 10 seconds
graphify_timeout_query: int       # 30 seconds
graphify_timeout_ingest: int      # 300 seconds (5 min)
```

### Job Queue Worker (`jobs/worker.py`)

A lightweight file-based async queue using JSON-lines format.

**Features:**
- No Redis/infrastructure required
- Job persistence across restarts
- Async processing with configurable workers
- Status tracking via JSON result files

**States:** `queued` → `running` → `done` | `failed`

### Extraction Service (`services/extraction*.py`)

Handles content extraction from multiple source types:

| Source | Method | Library |
|--------|--------|---------|
| URL (HTML) | HTTP GET + BeautifulSoup | httpx, bs4 |
| URL (PDF) | Binary download + PyMuPDF | httpx, fitz |
| PDF file | Direct extraction | PyMuPDF |
| DOCX file | XML parsing | python-docx |
| TXT/MD | Direct read | stdlib |

**Timeout:** 30 seconds per extraction

### Ingestion Service (`services/ingestion.py`)

Orchestrates LLM-based content synthesis.

**Pipeline:**
1. Extract text from source
2. Collect existing wiki pages for context
3. Build structured prompt with SCHEMA guidelines
4. Call LLM for synthesis
5. Parse JSON response
6. Write/update wiki pages
7. Update index.md, log.md, overview.md
8. Trigger graph rebuild (if enabled)

**LLM Prompt Structure:**
```
SCHEMA context (from KIMI.md)
EXISTING PAGES (for cross-linking)
SOURCE TEXT (first 80KB)
META information

→ Return JSON with:
   - source_page (new/updated)
   - entities[]
   - concepts[]
   - analyses[]
   - log_entry
   - index_entries
```

### Markdown Rendering (`services/markdown_render.py`)

Converts markdown to HTML with Obsidian compatibility:

- **Frontmatter stripping** — YAML headers don't render as `<hr>`
- **WikiLink rewriting** — `[[Page Title]]` → `/wiki/page-title`
- **Relative link conversion** — `.md` links work in SPA
- **Code highlighting** — via markdown.extensions.codehilite

### Graphify Service (`services/graphify.py`)

Wrapper around the `graphifyy` Python library with strict timeout handling.

**Capabilities:**
- AST extraction from code files
- Multimodal extraction (images via vision models)
- Video/audio transcription (Whisper)
- Entity/concept extraction
- Confidence scoring (EXTRACTED/INFERRED/AMBIGUOUS)

**Timeout Configuration:**
```python
timeout_default: int = 10   # Pathfinding, explain
timeout_query: int = 30     # Natural language queries
timeout_ingest: int = 300   # Full corpus rebuild (5 min)
```

### Graph Sync Service (`services/graph_sync.py`)

Synchronizes Graphify's knowledge graph with wiki pages.

**Features:**
- Loads `graph.json` into memory
- Maps wiki pages to graph nodes
- Identifies "God Nodes" (high-degree hubs)
- Generates "Related (from graph)" sections
- Injects cross-references into markdown

**God Node Detection:**
```python
mean_degree + 2 * std_dev  # Threshold for hub detection
```

---

## Frontend Architecture

### SPA Router (`app.js`)

Client-side routing without page reloads:

| Route | Content |
|-------|---------|
| `/` | Ingest page (URL + file upload) |
| `/wiki/` | Wiki browser with sidebar |
| `/wiki/path/to/page` | Specific wiki page |
| `/graph` | Knowledge graph visualization |

**History API Integration:**
```javascript
window.history.pushState({}, '', '/wiki/concepts/agentic-ai');
// Intercept clicks on internal links
// Update view without server round-trip
```

### Wiki Browser Components

**Sidebar Tree:**
- Recursive folder rendering
- Expandable `<details>` elements
- Alphabetical sorting
- Active page highlighting

**Search:**
- Backend-powered full-text search
- Debounced input (300ms)
- Snippet extraction
- Click-through to pages

**Breadcrumbs:**
- Path-based navigation
- Clickable segments
- Home shortcut

### Graph Visualization (`graph.js`)

D3.js-based force-directed graph with interactive features.

**Features:**
- **Force simulation** — d3.forceSimulation with link/charge/center forces
- **Zoom & pan** — d3.zoom binding
- **Node sizing** — Proportional to degree (connections)
- **Community coloring** — Spectral color palette
- **Edge labels** — Relationship types
- **Node tooltips** — On-hover details

**Interactions:**
- Click node → Show details panel
- Drag node → Reposition
- Scroll wheel → Zoom
- Search → Highlight matching nodes
- Path finding → BFS shortest path

**Performance:**
- SVG rendering (not Canvas — simpler manipulation)
- 500+ node datasets tested
- FPS maintained via requestAnimationFrame

---

## Graphify Integration

### What is Graphify?

Graphify is an open-source knowledge graph engine by [@safishamsi](https://github.com/safishamsi/graphify) that extracts semantic relationships from mixed content (text, code, images, video).

### Integration Points

```
┌─────────────────────────────────────────────────────────────────┐
│                    Graphify Integration Flow                     │
└─────────────────────────────────────────────────────────────────┘

1. Ingestion completes
       │
       ▼
2. Worker calls GraphifyService
       │
       └──▶ graphifyy library
              ├── Parse source files
              ├── Extract entities/relations
              ├── Run community detection
              └── Generate outputs
       │
       ▼
3. Graph JSON created (graphify-out/graph.json)
       │
       ▼
4. GraphSyncService loads graph
       │
       ▼
5. Wiki pages updated with "Related (from graph)" sections
       │
       ▼
6. Frontend calls /api/graph/full for D3 rendering
```

### Graph JSON Schema

```json
{
  "nodes": [
    {
      "id": "entity-uuid",
      "label": "Entity Name",
      "attributes": {
        "type": "person|org|concept|code",
        "community": 3,
        "source_file": "path/to/source.md",
        "confidence": "EXTRACTED"
      },
      "degree": 42
    }
  ],
  "edges": [
    {
      "source": "entity-uuid-1",
      "target": "entity-uuid-2",
      "relation": "implements|uses|mentions|derives_from",
      "confidence": "EXTRACTED|INFERRED|AMBIGUOUS",
      "confidence_score": 0.85
    }
  ]
}
```

### Auto-Sync

Every successful ingestion automatically triggers graph rebuild:

```python
# In worker.py
g = get_graphify_service()
result = await g.run_graphify(
    corpus_dir=Path(settings.wiki_path) / "raw",
    update=True,  # Incremental rebuild
)
# Reload graph in sync service
sync = get_graph_sync_service()
sync.load_graph()
```

---

## Deployment & Infrastructure

### Server Specifications

| Attribute | Value |
|-----------|-------|
| Provider | Hetzner Cloud |
| Instance | CX23 (ARM64 / x86_64) |
| Cost | ~$5/month |
| Location | Helsinki, Finland |
| OS | Ubuntu 24.04 LTS |
| RAM | 4 GB |
| Storage | 40 GB SSD |

### Services Architecture

```
┌─────────────────────────────────────────────┐
│              Hetzner CX23 VPS               │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  Caddy (ports 80/443)               │   │
│  │  - HTTPS termination                │   │
│  │  - Basic auth: jsong / password     │   │
│  │  - Auto Let's Encrypt               │   │
│  └──────────────┬──────────────────────┘   │
│                 │                           │
│                 ▼                           │
│  ┌─────────────────────────────────────┐   │
│  │  Uvicorn (port 8080, localhost)     │   │
│  │  - FastAPI application              │   │
│  │  - 1-2 workers                      │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  UFW Firewall                       │   │
│  │  - Deny all incoming                │   │
│  │  - Allow 22 (SSH from my IP)        │   │
│  │  - Allow 80/443 (world)             │   │
│  │  - Allow 8080 (my IP only)          │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### Caddy Configuration

```caddyfile
# /etc/caddy/Caddyfile
wiki.ai-biz.app {
    basicauth {
        jsong $2a$14$.bxXwsjbPdWt6/A8d.TzuOjLYCpl2VHpibrXLZi5BjwUtJ22rS4d.
    }
    reverse_proxy 127.0.0.1:8080
}
```

**Password generation:**
```bash
caddy hash-password --plaintext 'your-password'
```

### Systemd Service

```ini
# /etc/systemd/system/llm-wiki.service
[Unit]
Description=LLM Wiki FastAPI Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/llm-wiki-system
ExecStart=/root/llm-wiki-system/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Firewall (UFW)

```bash
# Default deny
ufw default deny incoming
ufw default allow outgoing

# SSH (essential)
ufw allow 22/tcp

# Web (through Caddy)
ufw allow 80/tcp
ufw allow 443/tcp

# Direct API access (YOUR_IP only)
ufw allow from YOUR_IP to any port 8080 proto tcp

# Enable
ufw --force enable
```

---

## Configuration Reference

### Hermes Environment (`~/.hermes/.env`)

API keys stored separate from app configuration:

```bash
# OpenRouter (recommended)
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxx

# Or native Kimi
KIMI_API_KEY=sk-kimi-xxxxxxxxxx
```

### Environment Variables

Prefix: `LLM_WIKI_`

| Variable | Default | Description |
|----------|---------|-------------|
| `WIKI_PATH` | See config.py | Obsidian vault path |
| `WEB_HOST` | `0.0.0.0` | Bind address |
| `WEB_PORT` | `8080` | Port |
| `LLM_MODEL` | `kimi-k2.5` | Model ID |
| `LLM_PROVIDER` | `openrouter` | Provider |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | API endpoint |
| `LLM_API_KEY` | From `~/.hermes/.env` | Auth token |
| `GRAPHIFY_ENABLED` | `true` | Enable graph |
| `GRAPHIFY_MODE` | `standard` | `standard` or `deep` |
| `GRAPHIFY_TIMEOUT_DEFAULT` | `10` | General ops timeout |
| `GRAPHIFY_TIMEOUT_QUERY` | `30` | Graph query timeout |
| `GRAPHIFY_TIMEOUT_INGEST` | `300` | Full rebuild timeout |

---

## API Reference

### Ingest Endpoints

**POST** `/api/ingest/url`
```json
// Request
{ "url": "https://example.com/article" }

// Response
{ "job_id": "uuid", "status": "queued" }
```

**POST** `/api/ingest/upload`
```http
Content-Type: multipart/form-data
file: <binary>

// Response
{ "job_id": "uuid", "status": "queued" }
```

**GET** `/api/status/{job_id}`
```json
{
  "job_id": "uuid",
  "status": "done|failed|running|queued",
  "message": "Human-readable status",
  "result": { "title": "...", "slug": "..." }
}
```

### Wiki Browser Endpoints

**GET** `/api/overview`
Returns `overview.md` rendered as HTML.

**GET** `/api/log?page=1`
Returns `log.md` paginated (50 entries/page) as HTML.

**GET** `/api/recent`
Returns last 10 ingestion jobs.
```json
{
  "jobs": [
    { "job_id": "...", "status": "done", "title": "...", "date": "..." }
  ]
}
```

**GET** `/api/pages`
Lists all wiki pages.
```json
{
  "pages": [
    { "path": "concepts/agentic-ai.md", "title": "Agentic AI", "folder": "concepts" }
  ]
}
```

**GET** `/api/pages/{path}`
Returns specific page as rendered HTML.
```json
{ "html": "<h1>...</h1>", "title": "Page Title", "path": "concepts/..." }
```

**GET** `/api/search?q=query`
Full-text search across all wiki pages.
```json
{
  "query": "agentic",
  "results": [
    { "path": "...", "title": "...", "snippet": "..." }
  ]
}
```

### Graph Endpoints

**GET** `/api/graph/stats`
```json
{
  "node_count": 150,
  "edge_count": 423,
  "community_count": 12,
  "god_nodes": [{ "label": "AI", "degree": 45 }]
}
```

**GET** `/api/graph/full`
Returns complete graph JSON (nodes + edges) for D3 rendering.

**GET** `/api/graph/query?q=...`&`dfs=true|false`
Natural language graph query with optional DFS traversal.
```json
{ "query": "what connects AI to agents?", "result": "..." }
```

---

## Security Considerations

### Authentication

- **Caddy Basic Auth** — Username/password for all access
- **No session management** — Credentials checked on every request
- **HTTPS only** — TLS 1.3 enforced by Caddy

### Network Security

- **Port 8080 restricted** — Only MY_IP can access directly
- **Public access via 443** — Caddy proxy with auth required
- **No CORS headers** — SPA and API on same origin
- **No API rate limiting** — UFW provides basic protection

### Data Security

- **Local storage only** — No cloud dependencies
- **API keys in ~/.hermes/.env** — Outside app directory
- **File permissions** — 600 for sensitive files
- **No user data collection** — Content stays on server

### Recommendations

1. **Rotate API keys** monthly
2. **Monitor Caddy logs** for brute force attempts
3. **Keep system updated** — `apt update && apt upgrade`
4. **Backup wiki directory** — `rsync` to offsite location
5. **Consider fail2ban** for SSH protection

---

## Development Methodology

### Hermes Agent-Driven Development

This entire system was built through conversational AI agents without manual code editing:

**Development Workflow:**
1. User describes requirements in natural language
2. Hermes agent generates implementation plan
3. Agent writes all code files
4. Agent deploys to server
5. Agent debugs issues
6. Agent generates documentation (this file)

**Key Capabilities Demonstrated:**
- Full-stack web application design
- System architecture decisions
- Async Python programming
- Frontend SPA development
- Linux server administration
- Reverse proxy configuration
- Knowledge graph integration
- API design and documentation

### Iteration History

| Phase | Focus | Key Decisions |
|-------|-------|---------------|
| 1 | Core Wiki | FastAPI + file-based queue + basic wiki structure |
| 2 | Ingestion | LLM pipeline with Kimi-2.5 + cross-linking |
| 3 | Wiki Browser | Client-side routing + sidebar navigation |
| 4 | Graphify | Knowledge graph integration + D3 visualization |
| 5 | Production | Caddy HTTPS + Basic Auth + UFW firewall |

---

## Future Enhancements

### Planned Features

1. **Semantic Search** — Vector embeddings for similarity queries
2. **Plugin System** — Custom extractors for proprietary formats
3. **Collaborative Editing** — Real-time multi-user support
4. **Mobile App** — React Native wrapper
5. **AI Chat Interface** — Conversational query mode
6. **Backup Sync** — Automatic Git or S3 backups

### Performance Optimizations

1. **Redis Queue** — Replace file-based queue at scale
2. **CDN** — Static asset caching
3. **Graph Database** — Neo4j for complex queries
4. **Incremental Indexing** — Background index updates

---

## Appendix A: Troubleshooting

### Common Issues

| Symptom | Solution |
|---------|----------|
| Server won't start | Check `python -c "from backend.main import app"` |
| 401 from LLM | Verify API key in `~/.hermes/.env` |
| Pages not found | Check `wiki_path` includes `/wiki/` subdirectory |
| Graph not rendering | Check browser console for D3 errors |
| Caddy won't start | Verify DNS A record points to server IP |

### Debug Commands

```bash
# Test API directly (localhost only)
curl http://localhost:8080/api/status/{job_id}

# Check running processes
ps aux | grep -E "uvicorn|caddy"

# View logs
journalctl -u caddy -f
journalctl -u llm-wiki -f

# Test Graphify directly
python -m graphify ~/Documents/Obsidian\ Vault/LLM-Wiki/wiki --output-dir /tmp/test
```

---

## Appendix B: References

- **FastAPI**: https://fastapi.tiangolo.com
- **Graphify**: https://github.com/safishamsi/graphify
- **Karpathy LLM Wiki Pattern**: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- **Hermes Agent Framework**: Internal tooling
- **Caddy Server**: https://caddyserver.com
- **D3.js**: https://d3js.org

---

**Document Version**: 1.0  
**Last Updated**: April 20, 2025  
**Author**: Hermes AI Agent (autonomous development)  
**Maintainer**: Jaehee Song (jsong@koreatous.com)
