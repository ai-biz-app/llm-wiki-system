import os
import re
import json
import httpx
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from backend.config import get_settings
from backend.services import file_storage as fs
from backend.services import extraction


def _slugify(name: str, max_len: int = 50) -> str:
    from slugify import slugify as _sl
    return _sl(name, max_length=max_len, word_boundary=True) or "untitled"


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _wikilink_exists(wiki_path: Path, title: str) -> bool:
    # Try to find in wiki/entities/, wiki/concepts/, wiki/analyses/, wiki/sources/
    slug = _slugify(title)
    for subdir in ["entities", "concepts", "analyses", "sources"]:
        for f in (wiki_path / "wiki" / subdir).glob("*.md"):
            # Simple heuristic: check frontmatter title or filename
            content = _read_text(f)
            if f"title: \"{title}\"" in content or f"title: '{title}'" in content:
                return True
            if f.stem == slug:
                return True
    return False


async def _call_kimi(prompt: str, temperature: float = 0.3) -> str:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError(
            "No LLM API key configured. Set OPENROUTER_API_KEY or KIMI_API_KEY in ~/.hermes/.env, "
            "or set LLM_WIKI_LLM_API_KEY environment variable."
        )
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{settings.llm_base_url}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _build_prompt(source_text: str, source_meta: dict, existing_pages: list) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    meta_block = json.dumps(source_meta, indent=2)
    pages_block = "\n".join([f"- {p['type']}: {p['title']} ({p['file']})" for p in existing_pages]) or "None yet."

    prompt = f"""You are the wiki maintainer for a local Markdown knowledge base. Follow the schema in KIMI.md exactly.

TODAY'S DATE: {today}

EXISTING PAGES IN THE WIKI:
{pages_block}

SOURCE TO INGEST:
---
{source_text[:80000]}
---

SOURCE METADATA:
{meta_block}

Produce a SINGLE valid JSON object (no markdown code fences, no extra prose) with these keys:
- "source_page": object with "file_name" (YYYY-MM-DD-slug.md) and "content" (full markdown string including YAML frontmatter) for wiki/sources/
- "entities": array of objects {{ "name", "file_name" (kebab-case), "content" (full markdown with frontmatter) }} — only significant ones. If an entity already exists, merge new info and update the "updated" date.
- "concepts": array of objects {{ "name", "file_name" (kebab-case), "content" (full markdown with frontmatter) }} — only significant ones. Same merge rule.
- "analyses": array of objects {{ "title", "file_name", "content" }} — optional, only if the source warrants a comparative or deep-dive analysis.
- "log_entry": the exact markdown line to append to log.md (format: `## [YYYY-MM-DD] ingest | Title`)
- "overview_delta": brief paragraph (1-3 sentences) describing how this source changes the big picture. If it doesn't shift the overall picture, return an empty string.
- "index_entries": array of one-line strings to add under the correct section in index.md (e.g., "- [[Page Title]] — Description. (YYYY-MM-DD)")

Rules:
1. Use [[Page Title]] Obsidian wikilinks for all cross-references.
2. Every page must have YAML frontmatter with title, type, tags, created, updated.
3. If an entity or concept page already exists (check the EXISTING PAGES list), return the FULL updated content merged with the new information. Bump the "updated" date.
4. Do not create pages for passing mentions.
5. Keep source summaries objective.
6. Return ONLY the JSON object. No ```json fences.
"""
    return prompt


def _parse_json_from_response(text: str) -> dict:
    original = text
    text = text.strip()
    # Try to extract JSON from markdown fences
    if "```json" in text:
        text = text.split("```json", 1)[1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    text = text.strip()
    # Fallback: find outermost braces
    if not text.startswith("{"):
        start = text.find("{")
        if start != -1:
            end = text.rfind("}")
            if end != -1:
                text = text[start:end+1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Save raw response for debugging
        debug_path = Path("/tmp/llm_wiki_debug_response.json")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(original)
        raise RuntimeError(f"JSON parse failed: {e}. Raw response saved to {debug_path}") from e


def _collect_existing_pages(wiki_path: Path) -> list:
    pages = []
    for subdir in ["sources", "entities", "concepts", "analyses"]:
        for f in (wiki_path / "wiki" / subdir).glob("*.md"):
            content = _read_text(f)
            title = None
            m = re.search(r'^title:\s*["\'](.+?)["\']\s*$', content, re.MULTILINE)
            if m:
                title = m.group(1)
            else:
                title = f.stem.replace("-", " ").title()
            t = "source" if subdir == "sources" else ("entity" if subdir == "entities" else ("concept" if subdir == "concepts" else "analysis"))
            pages.append({"type": t, "title": title, "file": str(f.relative_to(wiki_path / "wiki")), "path": str(f)})
    return pages


def _update_index(wiki_path: Path, new_entries: list):
    index_path = wiki_path / "wiki" / "index.md"
    text = _read_text(index_path)
    # Simple append strategy: add entries right before a blank line or at the end
    if not text.endswith("\n"):
        text += "\n"
    for entry in new_entries:
        # Prevent duplicates
        if entry in text:
            continue
        text += f"{entry}\n"
    _write_text(index_path, text)


def _update_log(wiki_path: Path, log_entry: str):
    log_path = wiki_path / "wiki" / "log.md"
    text = _read_text(log_path)
    if not text.endswith("\n"):
        text += "\n"
    text += f"{log_entry}\n\n"
    _write_text(log_path, text)


def _update_overview(wiki_path: Path, delta: str):
    if not delta or not delta.strip():
        return
    overview_path = wiki_path / "wiki" / "overview.md"
    text = _read_text(overview_path)
    today = datetime.now().strftime("%Y-%m-%d")
    # Append a small section
    addition = f"\n## Update ({today})\n\n{delta.strip()}\n"
    if not text.endswith("\n"):
        text += "\n"
    text += addition
    # Bump updated date in frontmatter
    text = re.sub(r"updated:\s*\d{4}-\d{2}-\d{2}", f"updated: {today}", text)
    text = re.sub(r"source_count:\s*\d+", lambda m: f"source_count: {int(m.group(0).split(':')[1].strip()) + 1}", text)
    _write_text(overview_path, text)


def _bump_source_count_index(wiki_path: Path):
    index_path = wiki_path / "wiki" / "index.md"
    text = _read_text(index_path)
    m = re.search(r"source_count:\s*(\d+)", text)
    if m:
        new_count = int(m.group(1)) + 1
        text = re.sub(r"source_count:\s*\d+", f"source_count: {new_count}", text)
        _write_text(index_path, text)


async def run_ingestion(
    job_id: str,
    payload: dict,
    progress: Callable[[str, Optional[str]], None]
) -> None:
    """
    payload keys:
      - source_type: "url" | "upload"
      - raw_path: path to raw source file on disk
      - extracted_text: extracted plain text
      - meta: dict with url, author, title, etc.
    """
    settings = get_settings()
    wiki_path = Path(settings.wiki_path).expanduser().resolve()
    fs.ensure_wiki_dirs(wiki_path)

    progress("running", "Reading existing wiki pages...")
    existing_pages = _collect_existing_pages(wiki_path)

    progress("running", "Building LLM prompt...")
    prompt = _build_prompt(payload["extracted_text"], payload.get("meta", {}), existing_pages)

    progress("running", "Calling Kimi-2.5 for analysis...")
    response_text = await _call_kimi(prompt)

    progress("running", "Parsing LLM response...")
    data = _parse_json_from_response(response_text)

    progress("running", "Writing source page...")
    sp = data.get("source_page", {})
    if sp and sp.get("content"):
        _write_text(wiki_path / "wiki" / "sources" / sp["file_name"], sp["content"])

    progress("running", "Writing entity pages...")
    for ent in data.get("entities", []):
        if ent.get("content"):
            _write_text(wiki_path / "wiki" / "entities" / ent["file_name"], ent["content"])

    progress("running", "Writing concept pages...")
    for conc in data.get("concepts", []):
        if conc.get("content"):
            _write_text(wiki_path / "wiki" / "concepts" / conc["file_name"], conc["content"])

    progress("running", "Writing analyses...")
    for ana in data.get("analyses", []):
        if ana.get("content"):
            _write_text(wiki_path / "wiki" / "analyses" / ana["file_name"], ana["content"])

    progress("running", "Updating index and log...")
    _update_index(wiki_path, data.get("index_entries", []))
    if data.get("log_entry"):
        _update_log(wiki_path, data["log_entry"])
    if data.get("overview_delta"):
        _update_overview(wiki_path, data["overview_delta"])
    _bump_source_count_index(wiki_path)

    progress("done", "Ingestion complete")
