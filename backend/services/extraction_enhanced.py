"""
Enhanced extraction service supporting multimodal inputs.
Extends the existing extraction.py with image, video, audio, and code support.
"""

import asyncio
import io
import logging
import mimetypes
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# MIME type to category mapping
MIME_CATEGORIES = {
    # Documents
    "text/plain": "doc",
    "text/markdown": "doc",
    "text/x-markdown": "doc",
    "application/pdf": "doc",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "doc",
    # Code
    "text/x-python": "code",
    "application/javascript": "code",
    "text/javascript": "code",
    "text/typescript": "code",
    # Images
    "image/png": "image",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/webp": "image",
    "image/gif": "image",
    # Video
    "video/mp4": "video",
    "video/quicktime": "video",
    "video/x-matroska": "video",
    "video/webm": "video",
    "video/x-msvideo": "video",
    "video/x-m4v": "video",
    # Audio
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/x-wav": "audio",
    "audio/mp4": "audio",
    "audio/ogg": "audio",
}

# File extension to category mapping
EXT_CATEGORIES = {
    # Documents
    ".txt": "doc",
    ".md": "doc",
    ".markdown": "doc",
    ".pdf": "doc",
    ".docx": "doc",
    ".doc": "doc",
    # Code
    ".py": "code",
    ".js": "code",
    ".mjs": "code",
    ".jsx": "code",
    ".ts": "code",
    ".tsx": "code",
    ".go": "code",
    ".rs": "code",
    ".java": "code",
    ".c": "code",
    ".cpp": "code",
    ".cc": "code",
    ".h": "code",
    ".hpp": "code",
    ".rb": "code",
    ".cs": "code",
    ".kt": "code",
    ".scala": "code",
    ".php": "code",
    ".swift": "code",
    ".lua": "code",
    ".zig": "code",
    ".ps1": "code",
    ".ex": "code",
    ".exs": "code",
    ".m": "code",
    ".mm": "code",
    ".jl": "code",
    ".vue": "code",
    ".svelte": "code",
    ".dart": "code",
    # Images
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    # Video
    ".mp4": "video",
    ".mov": "video",
    ".mkv": "video",
    ".webm": "video",
    ".avi": "video",
    ".m4v": "video",
    # Audio
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".ogg": "audio",
}


def get_file_category(file_path: Path) -> str:
    """Determine file category based on extension and mime type."""
    ext = file_path.suffix.lower()

    # Check extension first
    if ext in EXT_CATEGORIES:
        return EXT_CATEGORIES[ext]

    # Try mime type detection
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        # Check exact match
        if mime_type in MIME_CATEGORIES:
            return MIME_CATEGORIES[mime_type]

        # Check prefix match
        category = mime_type.split("/")[0]
        if category in ["image", "video", "audio", "text"]:
            return category

    return "unknown"


def extract_text_from_doc(file_bytes: bytes, ext: str) -> str:
    """Extract text from document files (txt, md, pdf, docx)."""
    ext = ext.lower().lstrip(".")

    if ext in ("txt", "md", "markdown"):
        return file_bytes.decode("utf-8", errors="ignore")

    if ext == "pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n\n".join([p.get_text() for p in doc])
            doc.close()
            return text
        except ImportError:
            logger.warning("PyMuPDF not installed. PDF extraction skipped.")
            return ""
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""

    if ext in ("docx", "doc"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            return "\n\n".join([p.text for p in doc.paragraphs])
        except ImportError:
            logger.warning("python-docx not installed. DOCX extraction skipped.")
            return ""
        except Exception as e:
            logger.error(f"DOCX extraction error: {e}")
            return ""

    return ""


def save_code_file(file_bytes: bytes, filename: str, dest_dir: Path) -> Path:
    """Save code file to destination and return path."""
    dest_path = dest_dir / filename
    dest_path.write_bytes(file_bytes)
    return dest_path


def save_media_file(file_bytes: bytes, filename: str, dest_dir: Path) -> Path:
    """Save media file (image/video/audio) to assets directory."""
    dest_path = dest_dir / filename
    dest_path.write_bytes(file_bytes)
    return dest_path


async def transcribe_audio(
    audio_path: Path,
    model: str = "base",
    domain_prompt: Optional[str] = None,
) -> Optional[str]:
    """
    Transcribe audio/video file using faster-whisper.

    Args:
        audio_path: Path to audio/video file
        model: Whisper model size (tiny, base, small, medium, large)
        domain_prompt: Optional domain-aware prompt for better accuracy

    Returns:
        Transcribed text or None on error
    """
    try:
        from faster_whisper import WhisperModel

        logger.info(f"Transcribing {audio_path} with model {model}")

        # Load model
        whisper_model = WhisperModel(model, device="cpu", compute_type="int8")

        # Prepare prompt
        initial_prompt = domain_prompt or "This is a technical discussion about software engineering and AI."

        # Transcribe
        segments, info = whisper_model.transcribe(
            str(audio_path),
            initial_prompt=initial_prompt,
            condition_on_previous_text=True,
        )

        # Collect text
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text)

        return " ".join(text_parts)

    except ImportError:
        logger.warning("faster-whisper not installed. Audio transcription skipped.")
        return None
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return None


async def extract_text_from_url(url: str) -> Tuple[str, str]:
    """
    Extract text from URL with improved type detection.

    Returns:
        Tuple of (text_content, content_type)
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        resp = await client.get(str(url), headers=headers)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").lower()

        # PDF
        if "application/pdf" in content_type:
            return extract_text_from_doc(resp.content, "pdf"), "pdf"

        # Video/audio - can't extract directly from URL, would need download

        # HTML
        if "text/html" in content_type:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True), "html"

        # Plain text
        if "text/plain" in content_type:
            return resp.text, "txt"

        # Default: try HTML parsing
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True), "html"


async def handle_multimodal_upload(
    file_bytes: bytes,
    filename: str,
    wiki_raw_dir: Path,
    whisper_model: str = "base",
) -> Dict[str, Any]:
    """
    Handle multimodal file upload and extract/process accordingly.

    Args:
        file_bytes: Raw file bytes
        filename: Original filename
        wiki_raw_dir: Base wiki raw directory
        whisper_model: Whisper model for audio/video transcription

    Returns:
        Dict with extraction results
    """
    file_path = Path(filename)
    category = get_file_category(file_path)
    ext = file_path.suffix.lower()

    result = {
        "filename": filename,
        "category": category,
        "saved_path": None,
        "extracted_text": None,
        "transcript_path": None,
        "error": None,
    }

    try:
        if category == "doc":
            # Documents: extract text, save to raw/sources/
            dest_dir = wiki_raw_dir / "sources"
            dest_dir.mkdir(parents=True, exist_ok=True)

            saved_path = dest_dir / filename
            saved_path.write_bytes(file_bytes)
            result["saved_path"] = str(saved_path.relative_to(wiki_raw_dir))

            # Extract text
            text = extract_text_from_doc(file_bytes, ext.lstrip("."))
            result["extracted_text"] = text

        elif category == "code":
            # Code: save to raw/code/ for graphify AST extraction
            dest_dir = wiki_raw_dir / "code"
            dest_dir.mkdir(parents=True, exist_ok=True)

            saved_path = save_code_file(file_bytes, filename, dest_dir)
            result["saved_path"] = str(saved_path.relative_to(wiki_raw_dir))
            result["extracted_text"] = file_bytes.decode("utf-8", errors="ignore")

        elif category == "image":
            # Images: save to raw/assets/
            dest_dir = wiki_raw_dir / "assets"
            dest_dir.mkdir(parents=True, exist_ok=True)

            saved_path = save_media_file(file_bytes, filename, dest_dir)
            result["saved_path"] = str(saved_path.relative_to(wiki_raw_dir))
            # Image extraction is handled by graphify (Claude vision)

        elif category in ("video", "audio"):
            # Video/Audio: save to raw/assets/, then transcribe
            dest_dir = wiki_raw_dir / "assets"
            dest_dir.mkdir(parents=True, exist_ok=True)

            saved_path = save_media_file(file_bytes, filename, dest_dir)
            result["saved_path"] = str(saved_path.relative_to(wiki_raw_dir))

            # Transcribe
            transcript = await transcribe_audio(saved_path, model=whisper_model)
            if transcript:
                # Save transcript alongside media file
                transcript_filename = f"{file_path.stem}.transcript.txt"
                transcript_path = dest_dir / transcript_filename
                transcript_path.write_text(transcript, encoding="utf-8")
                result["transcript_path"] = str(transcript_path.relative_to(wiki_raw_dir))
                result["extracted_text"] = transcript

        else:
            # Unknown type: save to raw/sources/ as binary
            dest_dir = wiki_raw_dir / "sources"
            dest_dir.mkdir(parents=True, exist_ok=True)

            saved_path = dest_dir / filename
            saved_path.write_bytes(file_bytes)
            result["saved_path"] = str(saved_path.relative_to(wiki_raw_dir))

    except Exception as e:
        logger.exception(f"Error handling upload: {filename}")
        result["error"] = str(e)

    return result


# Backwards compatibility: keep existing functions
async def extract_text(file_bytes: bytes, ext: str) -> str:
    """Legacy text extraction function."""
    return extract_text_from_doc(file_bytes, ext)
