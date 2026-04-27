import io
import httpx
from pathlib import Path


def extract_text_from_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        texts = []
        for page in doc:
            texts.append(page.get_text())
        return "\n\n".join(texts)
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")


def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        raise RuntimeError(f"DOCX extraction failed: {e}")


def extract_text_from_md(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore")


async def extract_text_from_url(url: str) -> str:
    """Fetch URL and return plain text. Tries Firecrawl-like extraction first,
    then falls back to raw HTML -> simple text extraction."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(str(url), headers=headers)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "").lower()

        if "application/pdf" in content_type:
            return extract_text_from_pdf(resp.content)

        html = resp.text
        # Simple HTML-to-text fallback
        text = _html_to_text(html)
        return text


def _html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except ImportError:
        # Very naive fallback
        import re
        text = re.sub(r"<[^>]+>", "", html)
        return text


def extract_text(file_bytes: bytes, ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext == "txt":
        return extract_text_from_txt(file_bytes)
    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    if ext == "docx":
        return extract_text_from_docx(file_bytes)
    if ext in ("md", "markdown"):
        return extract_text_from_md(file_bytes)
    raise ValueError(f"Unsupported file extension: .{ext}")
