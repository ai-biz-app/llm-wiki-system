import re
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.toc import TocExtension
from markdown.extensions.tables import TableExtension
from pathlib import Path


def strip_frontmatter(md_content: str) -> str:
    """Remove YAML frontmatter from markdown content."""
    if md_content.startswith("---"):
        parts = md_content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return md_content


def extract_title(md_content: str, default: str = "Untitled") -> str:
    """Extract title from H1 or frontmatter."""
    # Frontmatter title
    m = re.search(r'^title:\s*(.+)$', md_content, re.MULTILINE)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    # H1 heading
    m = re.search(r'^#\s+(.+)$', md_content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return default


def build_wiki_index(wiki_dir: Path) -> dict:
    """Build a mapping of slug -> relative path for all .md files in wiki."""
    index = {}
    wiki_root = wiki_dir / "wiki"
    if not wiki_root.exists():
        return index
    for md_file in wiki_root.rglob("*.md"):
        rel = md_file.relative_to(wiki_root).as_posix()
        slug = rel.replace(".md", "").replace(" ", "-").replace("_", "-").lower()
        # Also index just the filename
        name_slug = md_file.stem.replace(" ", "-").replace("_", "-").lower()
        index[slug] = rel
        index[name_slug] = rel
        # Index folder/name combinations
        if "/" in slug:
            index[slug.split("/")[-1]] = rel
    return index


def rewrite_wiki_links(md_content: str, wiki_dir: Path, current_path: str = "") -> str:
    """
    Rewrite Obsidian [[...]] links and relative .md links to /wiki/... paths.
    """
    index = build_wiki_index(wiki_dir)
    current_folder = Path(current_path).parent.as_posix() if "/" in current_path else ""

    def resolve_link(link_text: str) -> str:
        # Handle Obsidian aliases: [[Target|Display]]
        target = link_text.split("|")[0].strip()
        target_slug = target.replace(" ", "-").replace("_", "-").lower()
        # Try exact match in index
        if target_slug in index:
            return "/wiki/" + index[target_slug].replace(".md", "")
        # Try fuzzy: look for any path containing the slug
        for slug, rel in index.items():
            if target_slug in slug or slug in target_slug:
                return "/wiki/" + rel.replace(".md", "")
        # Fallback: create a dashed slug
        return "/wiki/" + target_slug

    # Replace [[...]] links
    def obsidian_repl(m):
        inner = m.group(1)
        href = resolve_link(inner)
        display = inner.split("|")[1].strip() if "|" in inner else inner.strip()
        return f'[{display}]({href})'

    md_content = re.sub(r'\[\[([^\]]+)\]\]', obsidian_repl, md_content)

    # Replace relative .md links
    def md_link_repl(m):
        prefix = m.group(1)
        href = m.group(2)
        suffix = m.group(3)
        if href.startswith("http://") or href.startswith("https://") or href.startswith("#"):
            return m.group(0)
        if href.endswith(".md"):
            # Resolve relative to current file
            if current_folder and not href.startswith("/"):
                resolved = (Path(current_folder) / href).as_posix()
            else:
                resolved = href.lstrip("/")
            clean = resolved.replace(".md", "")
            return f'{prefix}/wiki/{clean}{suffix}'
        return m.group(0)

    md_content = re.sub(r'(\[.*?\]\()([^)]+)(\))', md_link_repl, md_content)

    return md_content


def md_to_html(md_content: str, wiki_dir: Path = None, current_path: str = "") -> str:
    """Convert markdown to HTML with syntax highlighting and wiki link rewriting."""
    if wiki_dir:
        md_content = rewrite_wiki_links(md_content, wiki_dir, current_path)
    md = markdown.Markdown(
        extensions=[
            CodeHiliteExtension(css_class="highlight", guess_lang=False),
            TocExtension(),
            TableExtension(),
            "fenced_code",
        ]
    )
    html = md.convert(strip_frontmatter(md_content))
    return html


def parse_log_entries(md_content: str):
    """
    Parse log.md into individual entries.
    Entries start with '## [YYYY-MM-DD] ...'
    Returns list of dicts with date, type, title, html.
    """
    # Split on '## [' but keep the delimiter
    pattern = r'^(##\s+\[\d{4}-\d{2}-\d{2}\]\s+)'
    parts = re.split(pattern, md_content, flags=re.MULTILINE)

    entries = []
    current_header = ""
    for part in parts:
        if not part.strip():
            continue
        if re.match(r'^##\s+\[\d{4}-\d{2}-\d{2}\]\s+', part):
            current_header = part.strip()
        elif current_header:
            full_entry = current_header + part
            # Extract date and type
            m = re.match(r'^##\s+\[(\d{4}-\d{2}-\d{2})\]\s+(\w+)\s+\|\s+(.*)', current_header)
            if m:
                date_str, entry_type, title = m.groups()
                entries.append({
                    "date": date_str,
                    "type": entry_type,
                    "title": title.strip(),
                    "html": md_to_html(full_entry),
                })
            current_header = ""
    return entries


def paginate_log(md_content: str, page: int = 1, per_page: int = 50) -> dict:
    """Parse log.md and return paginated HTML."""
    entries = parse_log_entries(md_content)
    # Reverse chronological
    entries.reverse()

    total = len(entries)
    pages = max(1, (total + per_page - 1) // per_page) if total > 0 else 1
    page = max(1, min(page, pages))

    start = (page - 1) * per_page
    end = start + per_page
    page_entries = entries[start:end]

    html = "\n<hr>\n".join([e["html"] for e in page_entries])
    return {
        "html": html,
        "total_entries": total,
        "page": page,
        "pages": pages,
    }
