# LLM Wiki System

A local-first, LLM-maintained markdown knowledge base with a web ingestion interface.

## Architecture

- **Backend**: FastAPI + Uvicorn
- **Frontend**: Vanilla HTML/JS (single-page app)
- **LLM**: Kimi-2.5 via OpenRouter
- **Storage**: Local markdown files in your Obsidian vault

## Quick Start

```bash
cd /root/llm-wiki-system
source venv/bin/activate
python -m backend.main
```

The server will start on `http://0.0.0.0:8080`.

## Environment Variables

You can override defaults via environment variables (all prefixed with `LLM_WIKI_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_WIKI_WIKI_PATH` | `/root/Documents/Obsidian Vault/LLM-Wiki` | Path to your wiki root |
| `LLM_WIKI_WEB_HOST` | `0.0.0.0` | Host to bind |
| `LLM_WIKI_WEB_PORT` | `8080` | Port to bind |
| `LLM_WIKI_LLM_API_KEY` | (from `~/.hermes/.env`) | OpenRouter or Kimi API key |
| `LLM_WIKI_LLM_MODEL` | `kimi-k2.5` | Model ID |
| `LLM_WIKI_LLM_BASE_URL` | `https://openrouter.ai/api/v1` | API base URL |

## Security Warning

By default, the server binds to `0.0.0.0` (all interfaces). **There is no built-in authentication.**

If this machine has a public IP, anyone who can reach port 8080 can upload files and trigger ingestion.

Recommended protections:
1. Run behind a reverse proxy (Nginx/Caddy) with Basic Auth and HTTPS
2. Use a firewall to restrict port 8080 to your IP only
3. Or use an SSH tunnel instead of exposing the port publicly:
   ```bash
   ssh -L 8080:localhost:8080 your-server-ip
   ```
   Then access via `http://localhost:8080` on your local machine.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI (ingest form) |
| `/overview` | GET | Web UI (overview viewer) |
| `/log` | GET | Web UI (log viewer) |
| `/api/ingest/url` | POST | Ingest from URL |
| `/api/ingest/upload` | POST | Ingest from file upload |
| `/api/status/{job_id}` | GET | Check ingestion job status |
| `/api/overview` | GET | Get `overview.md` as HTML |
| `/api/log` | GET | Get `log.md` as HTML (paginated) |
| `/api/recent` | GET | List recent ingestion jobs |
