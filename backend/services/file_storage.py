import uuid
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse


def ensure_wiki_dirs(wiki_path: Path):
    """Ensure all required wiki subdirectories exist under wiki/."""
    for subdir in ["sources", "entities", "concepts", "analyses"]:
        (wiki_path / "wiki" / subdir).mkdir(parents=True, exist_ok=True)


def make_slug(text: str, max_len: int = 50) -> str:
    """Create a URL-safe slug from text."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text).strip('-')
    return text[:max_len].strip('-')


def url_to_filename(url: str) -> str:
    """Generate a filename stub from a URL."""
    parsed = urlparse(str(url))
    domain = parsed.netloc.replace("www.", "")
    path = parsed.path.strip('/').replace('/', '-')
    base = f"{domain}-{path}" if path else domain
    return make_slug(base, max_len=50)


def save_uploaded_file(file_bytes: bytes, filename: str, dest_dir: Path) -> Path:
    """Save uploaded file to destination directory."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = make_slug(Path(filename).stem) + Path(filename).suffix
    today = datetime.now().strftime("%Y-%m-%d")
    dest_path = dest_dir / f"{today}-{safe_name}"
    counter = 1
    while dest_path.exists():
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        dest_path = dest_dir / f"{today}-{make_slug(stem)}-{counter}{suffix}"
        counter += 1
    with open(dest_path, "wb") as f:
        f.write(file_bytes)
    return dest_path


def save_text_as_md(text: str, slug: str, dest_dir: Path) -> Path:
    """Save text content as a markdown file."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    dest_path = dest_dir / f"{today}-{slug}.md"
    counter = 1
    while dest_path.exists():
        dest_path = dest_dir / f"{today}-{slug}-{counter}.md"
        counter += 1
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(text)
    return dest_path