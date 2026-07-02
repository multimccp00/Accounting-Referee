"""
Handball content parser.

Parses questions, answers, and rules from PDF text using regex patterns
tailored to IHF (International Handball Federation) document formats.
"""
import re
import hashlib
from typing import Any, Dict, List, Optional
from pathlib import Path

from app.models.question import ParsedQuestion, ParsedAnswer
from app.utils.helpers import (
    normalize_text, clean_rule_title, clean_question_text,
    parse_answer_keys, extract_rule_reference_tokens, image_extension_from_bytes
)
from app.utils.pdf import extract_pdf_text

QUESTION_ID_PATTERN = r"(?:SAR\d+|(?:\d+\.)+\d+|\d{1,4})"

QUESTION_LINE_RE = re.compile(
    rf"^\s*(?:Q(?:uestion)?\s*)?({QUESTION_ID_PATTERN})\s*[\).:-]\s*(.*)$",
    re.IGNORECASE,
)
COMPACT_ANSWER_LINE_RE = re.compile(
    rf"^\s*({QUESTION_ID_PATTERN})\)\s*([A-Za-z](?:\s*,\s*[A-Za-z])*)\s+(.+)$",
    re.IGNORECASE,
)
ANSWER_TOKEN_RE = re.compile(
    r"(?i)\b(?:answer|correct(?:\s+answer)?)\b\s*[:\-]?\s*([A-D]|True|False|Yes|No|\d+)"
)
RULE_HEADING_RE = re.compile(
    r"^\s*(?:Rule|Law|Article|Art\.)\s+([\dA-Za-z][\dA-Za-z.\-]*)\s*[:\-]?\s*(.*)$",
    re.IGNORECASE,
)

OPTION_LINE_RE = re.compile(r"^\s*([A-Ia-i])\s*[\).:-]\s*(.+)$")

# Compiled regex patterns for rulebook parsing (used in parse_rulebook_text)
RULE_TOC_FULL_RE = re.compile(r"^\s*Rule\s+(\d{1,2})\s*[\-–−]?\s*(.*?)\s+(\d{1,3})\s*$", re.IGNORECASE)
RULE_TOC_START_RE = re.compile(r"^\s*Rule\s+(\d{1,2})\s*[\-–−]?\s*(.*?)\s*$", re.IGNORECASE)
TRAILING_PAGE_RE = re.compile(r"^(.*?)\s+(\d{1,3})\s*$")
ROMAN_TOC_RE = re.compile(r"^\s*((?:I|II|III|IV|V))\.\s+(.*?)\s+(\d{1,3})\s*$", re.IGNORECASE)
PAGE_HEADER_RE = re.compile(r"^\s*(\d{1,3})\s+IX\.\s+Rules of the Game", re.IGNORECASE)


def split_numbered_blocks(text: str) -> List[Dict[str, Any]]:
    """Split text into numbered blocks based on question ID patterns.

    Args:
        text: Raw text containing numbered questions or items.

    Returns:
        List of blocks, each with 'id' and 'lines' keys.
    """
    blocks: List[Dict[str, Any]] = []
    current_id: Optional[str] = None
    current_lines: List[str] = []

    for raw_line in normalize_text(text).splitlines():
        line = raw_line.strip()
        if not line:
            if current_id is not None:
                current_lines.append("")
            continue

        match = QUESTION_LINE_RE.match(line)
        if match:
            if current_id is not None:
                blocks.append({"id": current_id, "lines": current_lines})
            current_id = match.group(1)
            first_line = match.group(2).strip()
            current_lines = [first_line] if first_line else []
            continue

        if current_id is not None:
            current_lines.append(line)

    if current_id is not None:
        blocks.append({"id": current_id, "lines": current_lines})

    return blocks


def parse_questions_text(text: str) -> List[ParsedQuestion]:
    """Parse questions and options from PDF text.

    Handles page-break artifacts (synthetic questions with just page numbers)
    by merging them with preceding questions when appropriate.

    Args:
        text: Raw question text from PDF.

    Returns:
        List of ParsedQuestion objects with IDs, text, and options.
    """
    parsed: List[ParsedQuestion] = []
    for block in split_numbered_blocks(text):
        question_lines: List[str] = []
        options: List[Dict[str, str]] = []

        for line in block["lines"]:
            opt = OPTION_LINE_RE.match(line)
            if opt:
                options.append({"key": opt.group(1).upper(), "text": opt.group(2).strip()})
            elif line:
                question_lines.append(line)

        question_text = clean_question_text(" ".join([line for line in question_lines if line]))
        if not question_text and options:
            question_text = "(question text unavailable in source PDF)"

        parsed.append(
            ParsedQuestion(
                question_id=str(block["id"]),
                question=question_text,
                options=options,
            )
        )

    # Merge page-break continuation blocks
    merged: List[ParsedQuestion] = []
    for q in parsed:
        if merged:
            prev = merged[-1]
            is_page_artifact = ("." not in q.question_id and len(q.question_id) <= 3)
            if is_page_artifact and not prev.options and q.options:
                prev.question = clean_question_text(f"{prev.question} {q.question}")
                prev.options = q.options
                continue
        merged.append(q)
    return merged


def parse_answers_text(text: str) -> Dict[str, ParsedAnswer]:
    """Parse answers and reasoning from PDF text.

    Supports both compact format (e.g., "2.14) b, c, d 2:9, Clarification 3")
    and prose format with explicit "Answer:" lines.

    Args:
        text: Raw answer text from PDF.

    Returns:
        Dictionary mapping question IDs to ParsedAnswer objects.
    """
    parsed: Dict[str, ParsedAnswer] = {}

    # Common IHF format in the answers PDF
    for raw_line in normalize_text(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        compact = COMPACT_ANSWER_LINE_RE.match(line)
        if compact:
            qid = compact.group(1).strip()
            answer = ", ".join([token.strip().upper() for token in compact.group(2).split(",")])
            refs = compact.group(3).strip()
            parsed[qid] = ParsedAnswer(
                question_id=qid,
                answer=answer,
                reasoning=refs,
            )

    # Fallback for prose-style documents
    for block in split_numbered_blocks(text):
        lines = [line for line in block["lines"] if line]
        raw_joined = "\n".join(lines)
        detected_answer = ""
        reasoning_lines: List[str] = []

        for line in lines:
            match = ANSWER_TOKEN_RE.search(line)
            if match and not detected_answer:
                detected_answer = match.group(1).strip()
                cleaned = ANSWER_TOKEN_RE.sub("", line).strip(" :-")
                if cleaned:
                    reasoning_lines.append(cleaned)
                continue
            if not detected_answer and len(line) == 1 and line.upper() in {"A", "B", "C", "D"}:
                detected_answer = line.upper()
                continue
            reasoning_lines.append(line)

        if not detected_answer:
            first_token = re.match(r"^\s*([A-D])\b", raw_joined, re.IGNORECASE)
            if first_token:
                detected_answer = first_token.group(1).upper()

        block_id = str(block["id"])
        if block_id not in parsed:
            parsed[block_id] = ParsedAnswer(
                question_id=block_id,
                answer=detected_answer,
                reasoning="\n".join(reasoning_lines).strip(),
            )
    return parsed


def parse_rulebook_text(text: str) -> List[Dict[str, Any]]:
    """Parse rule sections from PDF text.

    Extracts rules by either parsing table of contents and page ranges,
    or by finding explicit rule headings and collecting their content.

    Args:
        text: Raw rulebook text from PDF.

    Returns:
        List of rule sections, each with 'section_id', 'title', and 'content'.
    """
    lines = normalize_text(text).splitlines()


    toc_entries: List[Dict[str, Any]] = []
    seen_ids = set()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        m_rule_full = RULE_TOC_FULL_RE.match(line)
        if m_rule_full:
            sid = m_rule_full.group(1).strip()
            title = clean_rule_title(m_rule_full.group(2)) or f"Rule {sid}"
            page = int(m_rule_full.group(3))
            if sid not in seen_ids:
                toc_entries.append({"section_id": sid, "title": title, "start_page": page})
                seen_ids.add(sid)
            i += 1
            continue

        m_rule_start = RULE_TOC_START_RE.match(line)
        if m_rule_start:
            sid = m_rule_start.group(1).strip()
            title_parts = [m_rule_start.group(2).strip()]
            page = None

            lookahead = i + 1
            while lookahead < len(lines) and lookahead <= i + 3:
                nxt = lines[lookahead].strip()
                if not nxt:
                    lookahead += 1
                    continue
                tail = TRAILING_PAGE_RE.match(nxt)
                if tail:
                    title_chunk = tail.group(1).strip()
                    if title_chunk:
                        title_parts.append(title_chunk)
                    page = int(tail.group(2))
                    break
                if RULE_TOC_START_RE.match(nxt) or ROMAN_TOC_RE.match(nxt):
                    break
                title_parts.append(nxt)
                lookahead += 1

            if page is not None and sid not in seen_ids:
                title = clean_rule_title(" ".join([p for p in title_parts if p])) or f"Rule {sid}"
                toc_entries.append({"section_id": sid, "title": title, "start_page": page})
                seen_ids.add(sid)

            i += 1
            continue

        m_roman = ROMAN_TOC_RE.match(line)
        if m_roman:
            sid = m_roman.group(1).upper()
            title = clean_rule_title(m_roman.group(2)) or sid
            page = int(m_roman.group(3))
            if sid not in seen_ids:
                toc_entries.append({"section_id": sid, "title": title, "start_page": page})
                seen_ids.add(sid)
            i += 1
            continue

        i += 1

    if not toc_entries:
        # Fallback for plain text inputs
        sections_plain: List[Dict[str, Any]] = []
        current_id: Optional[str] = None
        current_title = ""
        current_lines: List[str] = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if current_id is not None:
                    current_lines.append("")
                continue

            heading = RULE_HEADING_RE.match(line)
            if heading:
                tail = heading.group(2).strip()
                if re.match(r"^\d+\s*[:.]", tail):
                    if current_id is not None:
                        current_lines.append(line)
                    continue

                if current_id is not None:
                    sections_plain.append(
                        {
                            "section_id": current_id,
                            "title": current_title,
                            "content": "\n".join(current_lines).strip(),
                        }
                    )
                current_id = heading.group(1).strip()
                current_title = clean_rule_title(tail) or f"Rule {current_id}"
                current_lines = []
                continue

            if current_id is not None:
                current_lines.append(line)

        if current_id is not None:
            sections_plain.append(
                {
                    "section_id": current_id,
                    "title": current_title,
                    "content": "\n".join(current_lines).strip(),
                }
            )

        sections_plain = [s for s in sections_plain if s.get("content")]
        if sections_plain:
            return sections_plain

        fallback_content = normalize_text(text).strip()
        if fallback_content:
            return [
                {
                    "section_id": "all",
                    "title": "Complete Rulebook",
                    "content": fallback_content,
                }
            ]
        return []

    toc_entries.sort(key=lambda e: e["start_page"])

    line_pages: List[Optional[int]] = []
    current_page: Optional[int] = None
    for raw_line in lines:
        hdr = PAGE_HEADER_RE.match(raw_line.strip())
        if hdr:
            current_page = int(hdr.group(1))
        line_pages.append(current_page)

    max_page = max([p for p in line_pages if p is not None], default=toc_entries[-1]["start_page"])
    start_pages = sorted({e["start_page"] for e in toc_entries})

    sections: List[Dict[str, Any]] = []
    for idx, entry in enumerate(toc_entries):
        start_page = entry["start_page"]
        next_greater = next((p for p in start_pages if p > start_page), None)
        end_page = (next_greater - 1) if next_greater is not None else max_page

        content_lines: List[str] = []
        for raw_line, page in zip(lines, line_pages):
            if page is None or page < start_page or page > end_page:
                continue

            line = raw_line.strip()
            if not line:
                continue
            if PAGE_HEADER_RE.match(line):
                continue
            if re.match(r"^\s*__+\s*$", line):
                continue
            if re.match(r"^\s*1\s+MARCH\s+2025\s*$", line, re.IGNORECASE):
                continue

            content_lines.append(line)

        content = "\n".join(content_lines).strip()
        sections.append(
            {
                "section_id": entry["section_id"],
                "title": entry["title"],
                "content": content,
                "start_page": start_page,
                "end_page": end_page,
            }
        )

    return sections


def extract_rulebook_images(
    rulebook_pdf: str,
    rules: List[Dict[str, Any]],
    output_dir: Path,
    relative_to: Optional[Path] = None,
) -> Dict[str, List[str]]:
    """Extract embedded images from rulebook PDF pages.

    Maps images to their corresponding rule sections based on page ranges.
    Deduplicates images by SHA1 hash to avoid storing duplicate images.

    Args:
        rulebook_pdf: Path to the rulebook PDF file.
        rules: List of rule sections with 'start_page' and 'end_page'.
        output_dir: Directory where extracted images will be saved.
        relative_to: Base directory for relative path calculation.

    Returns:
        Dictionary mapping section IDs to lists of image file paths.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError(
            "Missing dependency pypdf. Install with: pip install pypdf"
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(rulebook_pdf))
    rel_base = relative_to or output_dir.parent

    image_map: Dict[str, List[str]] = {}
    seen_hashes: set = set()

    for section in rules:
        sid = str(section.get("section_id", "")).strip()
        start_page = section.get("start_page")
        end_page = section.get("end_page")
        if not sid or not isinstance(start_page, int) or not isinstance(end_page, int):
            continue

        paths: List[str] = []
        for page_num in range(start_page, end_page + 1):
            idx = page_num - 1
            if idx < 0 or idx >= len(reader.pages):
                continue

            page = reader.pages[idx]
            images = list(getattr(page, "images", []) or [])
            for img_idx, img in enumerate(images, start=1):
                data = getattr(img, "data", None)
                if not isinstance(data, (bytes, bytearray)) or not data:
                    continue

                digest = hashlib.sha1(bytes(data)).hexdigest()
                if digest in seen_hashes:
                    continue
                seen_hashes.add(digest)

                ext = image_extension_from_bytes(bytes(data), str(getattr(img, "name", "")))
                out_name = f"section_{sid}_p{page_num}_{img_idx}_{digest[:8]}{ext}"
                out_path = output_dir / out_name

                with out_path.open("wb") as handle:
                    handle.write(bytes(data))

                try:
                    rel_path = out_path.relative_to(rel_base)
                    paths.append(str(rel_path).replace("\\", "/"))
                except ValueError:
                    paths.append(str(out_path))

        if paths:
            image_map[sid] = paths

    return image_map
