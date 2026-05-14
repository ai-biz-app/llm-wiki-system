# LLM Wiki System

> **A web-based implementation of the Karpathy LLM Wiki pattern** — persistent, LLM-maintained markdown knowledge bases as an alternative to RAG.

---

## What This Is

The LLM Wiki System is a **local-first, AI-native knowledge management platform** that ingests content from URLs and files, synthesizes it into structured markdown via LLM (Kimi-2.5 via OpenRouter), and surfaces it through a web interface with an interactive knowledge graph.

It implements Andrej Karpathy's [LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): instead of treating LLMs as ephemeral query engines (RAG), you treat them as **persistent knowledge base maintainers**. The LLM reads sources, writes structured markdown, cross-links concepts, and maintains an index — just like a human wiki editor, but automated and always available.

### Core Philosophy

| Traditional RAG | LLM Wiki |
|-----------------|----------|
| Ephemeral — answers generated on-the-fly from chunks | Persistent — knowledge is written, stored, and versioned |
| No cross-source synthesis | Explicit entity/concept extraction with relationships |
| No memory between sessions | Growing, linked knowledge base over time |
| Chunks lose context | Full articles with structure, hierarchy, and narrative |
| Black-box retrieval | Transparent, human-readable, Obsidian-compatible markdown |

The wiki is not a database the LLM queries. **The wiki IS the product.** The LLM is the maintainer.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CLIENT (Browser)                                                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Ingest Portal   │  │ Wiki Browser    │  │ Knowledge Graph │              │
│  │ (URL / File)    │  │ (Search + Tree) │  │ (D3.js + Filters│              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
└───────────┼────────────────────┼────────────────────┼────────────────────────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  REVERSE PROXY (Caddy) — HTTPS + Basic Auth                                │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FASTAPI APPLICATION (Port 8080)                                             │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Ingest API   │  │ Wiki Browser │  │ Graph API    │  │ Job Queue       │ │
│  │ /api/ingest  │  │ /api/pages   │  │ /api/graph   │  │ JSON-lines      │ │
│  │ /api/upload  │  │ /api/search  │  │ /api/graph/  │  │ async worker    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ SERVICE LAYER                                                          ││
│  │  • Extraction (URL, PDF, DOCX, TXT, MD)                               ││
│  │  • Ingestion (LLM synthesis pipeline with cross-linking)              ││
│  │  • Markdown Rendering (Obsidian-compatible wiki links)                ││
│  │  • Graphify Integration (Knowledge graph generation)                  ││
│  │  • Graph Sync (Cross-reference injection into wiki pages)             ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DATA LAYER (Local Filesystem)                                               │
│                                                                              │
│  ~/Documents/Obsidian Vault/LLM-Wiki/                                        │
│  ├── SCHEMA.md          # Wiki schema & conventions                          │
│  ├── index.md           # Master page index                                  │
│  ├── log.md             # Chronological action log                           │
│  ├── overview.md        # High-level topical overview                        │
│  ├── raw/               # Layer 1: Immutable sources                         │
│  │   ├── sources/       # Original text, articles, PDFs                     │
│  │   └── assets/        # Images, media                                      │
│  ├── wiki/              # Layer 2: LLM-synthesized markdown                  │
│  │   ├── sources/       # Source summaries                                   │
│  │   ├── entities/      # People, organizations, products                   │
│  │   ├── concepts/      # Topics, ideas, methodologies                       │
│  │   └── analyses/      # Deep dives, comparisons, syntheses                │
│  └── graphify-out/      # Layer 3: Knowledge graph outputs                   │
│      ├── graph.json     # Network data (nodes + edges)                       │
│      ├── graph.html     # Standalone visualization                           │
│      └── obsidian/      # Obsidian-compatible vault export                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The Ingestion Pipeline

When you submit a URL or upload a file, this happens:

```
1. EXTRACT
   URL → httpx + BeautifulSoup → plain text
   PDF → PyMuPDF (fitz) → text
   DOCX → python-docx → text
   TXT/MD → read directly

2. CONTEXTUALIZE
   Collect existing wiki pages for cross-linking awareness
   Read SCHEMA.md for formatting conventions

3. SYNTHESIZE (LLM)
   Build structured prompt with:
   • Schema guidelines
   • Existing pages (for cross-links)
   • Source text (first 80KB)
   • Metadata (date, source type, URL)

   LLM returns JSON:
   {
     "source_page": "# ...",      // New/updated source summary
     "entities": [...],           // People, orgs, products
     "concepts": [...],           // Topics, ideas
     "analyses": [...],           // Deep dives
     "log_entry": "...",          // Chronological log line
     "index_entries": [...]       // Index updates
   }

4. WRITE
   Save raw source to raw/sources/
   Write synthesized pages to wiki/{entities,concepts,analyses}/
   Update index.md, log.md, overview.md

5. GRAPH
   Trigger Graphify rebuild (incremental)
   Extract entities/relationships from all wiki pages
   Build network graph with confidence scoring
   Generate Obsidian-compatible export
```

---

## Key Features

### Ingest Portal
- **URL ingestion** — Paste any URL; the system fetches, extracts text, and synthesizes
- **File upload** — Drag-and-drop PDF, DOCX, TXT, or MD files
- **Job queue** — Async processing with status polling; no Redis required (JSON-lines file queue)
- **Job filters** — Filter by name, date, and status

### Wiki Browser
- **Folder tree** — Collapsible sidebar with alphabetical sorting
- **Full-text search** — Backend-powered search with snippet extraction
- **Breadcrumbs** — Path-based navigation with clickable segments
- **WikiLink support** — `[[Page Title]]` links rewritten for SPA routing
- **Obsidian-compatible** — Open the wiki directory directly in Obsidian

### Knowledge Graph
- **Force-directed visualization** — D3.js with zoom, pan, and drag
- **Community detection** — Nodes colored by detected community clusters
- **Confidence levels** — Edges labeled EXTRACTED (green), INFERRED (yellow), AMBIGUOUS (red)
- **Collapsible sidebar controls** — Search, filters (community + confidence + "good nodes"), path finding, NL query
- **Node details** — Click any node to see properties, connections, incoming/outgoing relationships
- **Path finding** — BFS shortest path between two nodes
- **Natural language queries** — Ask the graph questions in plain English

### Design
- **Linear-inspired UI** — Dark-mode-native design system with Inter typography, semi-transparent borders, and indigo-violet accents
- **Responsive** — Works on desktop and mobile

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Backend | FastAPI + Uvicorn | Async web framework |
| LLM | Kimi-2.5 via OpenRouter | Content synthesis |
| Queue | JSON-lines file queue | Async job processing (no Redis) |
| Extraction | httpx, bs4, PyMuPDF, python-docx | Multi-format text extraction |
| Graph | Graphify + D3.js v7 | Knowledge graph engine + visualization |
| Frontend | Vanilla JS SPA | No build step, client-side routing |
| Design | Linear design system | Inter font, dark native, premium feel |
| Hosting | Hetzner CX23 ($5/mo) | Ubuntu 24.04 VPS |
| Proxy | Caddy | HTTPS + Basic Auth + Reverse proxy |
| Firewall | UFW | IP-based access control |

---

## Quick Start

```bash
git clone https://github.com/ai-biz-app/llm-wiki-system.git
cd llm-wiki-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set API key in ~/.hermes/.env:
# OPENROUTER_API_KEY=sk-or-v1-...
# Or: KIMI_API_KEY=...

python -m backend.main
```

Server starts on `http://0.0.0.0:8080`.

---

## Configuration

Environment variables (prefix with `LLM_WIKI_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `WIKI_PATH` | `~/Documents/Obsidian Vault/LLM-Wiki` | Wiki root directory |
| `WEB_HOST` | `0.0.0.0` | Bind address |
| `WEB_PORT` | `8080` | Port |
| `LLM_MODEL` | `kimi-k2.5` | Model ID |
| `LLM_PROVIDER` | `openrouter` | Provider |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | API endpoint |
| `LLM_API_KEY` | (from `~/.hermes/.env`) | Auth token |
| `GRAPHIFY_ENABLED` | `true` | Enable knowledge graph |
| `GRAPHIFY_TIMEOUT_DEFAULT` | `10` | General ops timeout (seconds) |
| `GRAPHIFY_TIMEOUT_QUERY` | `30` | Graph query timeout |
| `GRAPHIFY_TIMEOUT_INGEST` | `300` | Full rebuild timeout |

---

## Security

**By default, the server binds to `0.0.0.0` with no built-in authentication.**

**Recommended setup:**

1. Run behind Caddy (or Nginx) with Basic Auth and HTTPS
2. Restrict port 8080 to your IP via firewall:
   ```bash
   ufw allow from YOUR_IP to any port 8080
   ```
3. Or use an SSH tunnel instead of exposing the port:
   ```bash
   ssh -L 8080:localhost:8080 your-server-ip
   ```

API keys are read from `~/.hermes/.env` (outside the app directory) and never committed.

---

## API Endpoints

### Ingestion
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ingest/url` | POST | Ingest from URL |
| `/api/ingest/upload` | POST | Ingest from file upload |
| `/api/status/{job_id}` | GET | Check job status |
| `/api/recent` | GET | List recent jobs |

### Wiki Browser
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pages` | GET | List all wiki pages |
| `/api/pages/{path}` | GET | Get specific page as HTML |
| `/api/search?q=...` | GET | Full-text search |
| `/api/overview` | GET | Overview page as HTML |
| `/api/log?page=1` | GET | Log page (paginated) |

### Knowledge Graph
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/graph/stats` | GET | Node/edge/community counts |
| `/api/graph/full` | GET | Complete graph JSON for D3 |
| `/api/graph/query?q=...` | GET | Natural language graph query |

---

## Graph Confidence Model

The knowledge graph uses a three-tier confidence system:

| Level | Color | Meaning |
|-------|-------|---------|
| **EXTRACTED** | Green | Directly verified from source text |
| **INFERRED** | Yellow | Probable relationship derived by LLM |
| **AMBIGUOUS** | Red | Uncertain — needs human review |

The "Good nodes only" filter shows only **EXTRACTED** nodes that have at least one connection, filtering out isolated or uncertain entities.

---

## Impact: Why This Matters

1. **Own your knowledge** — Everything lives in plain markdown files you control. No vendor lock-in, no API quotas for reading your own notes.

2. **Cross-source synthesis** — Unlike RAG, which retrieves chunks from individual documents, the wiki actively synthesizes across sources. When you ingest two papers on agentic AI, the LLM creates concept pages that link both, with analyses comparing them.

3. **Compounding value** — Each ingestion makes the wiki smarter. The LLM cross-links new content with existing pages, updates the index, and maintains a chronological log. Your knowledge base grows more valuable over time.

4. **Human + AI hybrid** — The wiki is readable and editable by humans (Obsidian-compatible) while being maintainable by AI. You can open any page, edit it, and the next ingestion will respect your changes.

5. **Graph-native** — Entities and relationships are first-class. The knowledge graph isn't an afterthought — it's generated automatically from every page, with confidence scoring and community detection.

---

## Development

This system was built autonomously by [Hermes AI agents](https://github.com/hermes-agent) with no manual code editing. The entire stack — backend architecture, frontend SPA, D3 visualization, Linux deployment, Caddy configuration, and documentation — was generated through conversational AI.

**Repository:** [github.com/ai-biz-app/llm-wiki-system](https://github.com/ai-biz-app/llm-wiki-system)  
**Maintainer:** Jaehee Song (jsong@koreatous.com)  
**License:** MIT
