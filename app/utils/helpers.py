"""
Text processing and data parsing utilities.

Provides helper functions for normalizing PDF text, cleaning question/rule text,
parsing answer keys, and detecting image file types.
"""
import re
from typing import List

RULE_REF_TOKEN_RE = re.compile(
    r"\b\d+:\d+[a-z]?\b|\bClarification\s+\d+[a-z]?\b|\bGuidelines?\b",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Remove trailing whitespace from each line and rejoin.

    Args:
        text: Multi-line string to normalize.

    Returns:
        Normalized text with trailing whitespace removed.
    """
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines)


def clean_rule_title(raw_title: str) -> str:
    """Clean rule titles by removing artifacts and normalizing whitespace.

    Args:
        raw_title: Raw rule title string (may contain encoding artifacts).

    Returns:
        Cleaned title with normalized spacing and stripped delimiters.
    """
    title = (raw_title or "").replace("�", "-")
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title


def clean_question_text(text: str) -> str:
    """Clean question text by normalizing whitespace and removing page numbers.

    PDF extraction often includes page numbers as trailing integers.
    This function removes those artifacts while preserving the question.

    Args:
        text: Raw question text from PDF.

    Returns:
        Cleaned question text without page numbers.
    """
    cleaned = " ".join((text or "").split())
    cleaned = re.sub(r"\s+\d{1,3}$", "", cleaned)
    return cleaned.strip()


def parse_answer_keys(answer_text: str) -> List[str]:
    """Extract unique answer keys (A-I) from answer text.

    Args:
        answer_text: Raw answer text containing option letters.

    Returns:
        Ordered list of unique uppercase answer keys (e.g., ['A', 'B']).
    """
    keys: List[str] = []
    for token in re.split(r"[\s,;/]+", (answer_text or "").strip()):
        uppercase_token = token.strip().upper()
        if len(uppercase_token) == 1 and "A" <= uppercase_token <= "I" and uppercase_token not in keys:
            keys.append(uppercase_token)
    return keys


def extract_rule_reference_tokens(reasoning: str) -> List[str]:
    """Extract rule reference tokens from reasoning text.

    Finds references like "2:7", "Clarification 3", or "Guidelines".

    Args:
        reasoning: Text containing rule references.

    Returns:
        List of unique rule reference tokens found in the text.
    """
    refs: List[str] = []
    for match in RULE_REF_TOKEN_RE.findall(reasoning or ""):
        token = str(match).strip()
        if token and token not in refs:
            refs.append(token)
    return refs


def image_extension_from_bytes(data: bytes, fallback_name: str = "") -> str:
    """Detect image file type from binary data and filename.

    Checks filename extension first, then inspects binary magic numbers
    to detect PNG, JPG, GIF, BMP, or WEBP formats.

    Args:
        data: Binary image data.
        fallback_name: Optional filename to check extension.

    Returns:
        File extension (e.g., '.png', '.jpg') or '.bin' if unrecognized.
    """
    name = str(fallback_name or "").lower()

    # Check filename extension first
    extension_map = {
        ".png": ".png",
        ".jpg": ".jpg",
        ".jpeg": ".jpg",
        ".gif": ".gif",
        ".bmp": ".bmp",
        ".webp": ".webp",
    }

    for ext, result in extension_map.items():
        if name.endswith(ext):
            return result

    # Check magic bytes
    magic_bytes = [
        (b"\x89PNG", ".png"),
        (b"\xff\xd8\xff", ".jpg"),
        (b"BM", ".bmp"),
    ]

    for magic, ext in magic_bytes:
        if data.startswith(magic):
            return ext

    # Special cases for GIF and WEBP
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"

    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return ".webp"

    return ".bin"
