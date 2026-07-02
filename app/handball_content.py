import json
import re
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


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
RULE_REF_TOKEN_RE = re.compile(
    r"\b\d+:\d+[a-z]?\b|\bClarification\s+\d+[a-z]?\b|\bGuidelines?\b",
    re.IGNORECASE,
)

# The IHF catalogue uses options beyond D in some questions (e.g. E/F/G).
OPTION_LINE_RE = re.compile(r"^\s*([A-Ia-i])\s*[\).:-]\s*(.+)$")


@dataclass
class ParsedQuestion:
    question_id: str
    question: str
    options: List[Dict[str, str]]


@dataclass
class ParsedAnswer:
    question_id: str
    answer: str
    reasoning: str


def _parse_answer_keys(answer_text: str) -> List[str]:
    keys: List[str] = []
    for token in re.split(r"[\s,;/]+", (answer_text or "").strip()):
        tok = token.strip().upper()
        if len(tok) == 1 and "A" <= tok <= "I" and tok not in keys:
            keys.append(tok)
    return keys


def _extract_rule_reference_tokens(reasoning: str) -> List[str]:
    refs: List[str] = []
    for match in RULE_REF_TOKEN_RE.findall(reasoning or ""):
        token = str(match).strip()
        if token and token not in refs:
            refs.append(token)
    return refs


def extract_pdf_text(pdf_path: str) -> str:
    """Read text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError(
            "Missing dependency pypdf. Install with: pip install pypdf"
        ) from exc

    reader = PdfReader(pdf_path)
    pages: List[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines)


def _clean_rule_title(raw_title: str) -> str:
    title = (raw_title or "").replace("�", "-")
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title


def _clean_question_text(text: str) -> str:
    s = " ".join((text or "").split())
    # PDF page numbers are often captured as trailing standalone integers.
    s = re.sub(r"\s+\d{1,3}$", "", s)
    return s.strip()


def _split_numbered_blocks(text: str) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    current_id: Optional[str] = None
    current_lines: List[str] = []

    for raw_line in _normalize_text(text).splitlines():
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
    parsed: List[ParsedQuestion] = []
    for block in _split_numbered_blocks(text):
        question_lines: List[str] = []
        options: List[Dict[str, str]] = []

        for line in block["lines"]:
            opt = OPTION_LINE_RE.match(line)
            if opt:
                options.append({"key": opt.group(1).upper(), "text": opt.group(2).strip()})
            elif line:
                question_lines.append(line)

        question_text = _clean_question_text(" ".join([line for line in question_lines if line]))
        if not question_text and options:
            question_text = "(question text unavailable in source PDF)"

        parsed.append(
            ParsedQuestion(
                question_id=str(block["id"]),
                question=question_text,
                options=options,
            )
        )

    # Merge page-break continuation blocks. In the IHF PDFs, a page number
    # can be parsed as a synthetic question id (e.g. "5", "17", "31"), while
    # the preceding real question (e.g. "2.29") may lose its options.
    merged: List[ParsedQuestion] = []
    for q in parsed:
        if merged:
            prev = merged[-1]
            is_page_artifact = ("." not in q.question_id and len(q.question_id) <= 3)
            if is_page_artifact and not prev.options and q.options:
                prev.question = _clean_question_text(f"{prev.question} {q.question}")
                prev.options = q.options
                continue
        merged.append(q)
    return merged


def parse_answers_text(text: str) -> Dict[str, ParsedAnswer]:
    parsed: Dict[str, ParsedAnswer] = {}

    # Common IHF format in the answers PDF:
    # 2.14) b, c, d 2:9, Clarification 3
    for raw_line in _normalize_text(text).splitlines():
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

    # Fallback for prose-style documents where each numbered block includes
    # explicit "Answer:" text and narrative reasoning.
    for block in _split_numbered_blocks(text):
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
    lines = _normalize_text(text).splitlines()

    # Build section index from table-of-contents style lines, e.g.
    # "Rule 1 ... 4" and "II. Clarifications to the Rules ... 54".
    rule_toc_full_re = re.compile(r"^\s*Rule\s+(\d{1,2})\s*[\-–�]?\s*(.*?)\s+(\d{1,3})\s*$", re.IGNORECASE)
    rule_toc_start_re = re.compile(r"^\s*Rule\s+(\d{1,2})\s*[\-–�]?\s*(.*?)\s*$", re.IGNORECASE)
    trailing_page_re = re.compile(r"^(.*?)\s+(\d{1,3})\s*$")
    roman_toc_re = re.compile(r"^\s*((?:I|II|III|IV|V))\.\s+(.*?)\s+(\d{1,3})\s*$", re.IGNORECASE)
    page_header_re = re.compile(r"^\s*(\d{1,3})\s+IX\.\s+Rules of the Game", re.IGNORECASE)

    toc_entries: List[Dict[str, Any]] = []
    seen_ids = set()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        m_rule_full = rule_toc_full_re.match(line)
        if m_rule_full:
            sid = m_rule_full.group(1).strip()
            title = _clean_rule_title(m_rule_full.group(2)) or f"Rule {sid}"
            page = int(m_rule_full.group(3))
            if sid not in seen_ids:
                toc_entries.append({"section_id": sid, "title": title, "start_page": page})
                seen_ids.add(sid)
            i += 1
            continue

        m_rule_start = rule_toc_start_re.match(line)
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
                tail = trailing_page_re.match(nxt)
                if tail:
                    title_chunk = tail.group(1).strip()
                    if title_chunk:
                        title_parts.append(title_chunk)
                    page = int(tail.group(2))
                    break
                # stop if we hit another TOC heading before finding page number
                if rule_toc_start_re.match(nxt) or roman_toc_re.match(nxt):
                    break
                title_parts.append(nxt)
                lookahead += 1

            if page is not None and sid not in seen_ids:
                title = _clean_rule_title(" ".join([p for p in title_parts if p])) or f"Rule {sid}"
                toc_entries.append({"section_id": sid, "title": title, "start_page": page})
                seen_ids.add(sid)

            i += 1
            continue

        m_roman = roman_toc_re.match(line)
        if m_roman:
            sid = m_roman.group(1).upper()
            title = _clean_rule_title(m_roman.group(2)) or sid
            page = int(m_roman.group(3))
            if sid not in seen_ids:
                toc_entries.append({"section_id": sid, "title": title, "start_page": page})
                seen_ids.add(sid)
            i += 1
            continue

        i += 1

    if not toc_entries:
        # Fallback for plain text inputs (e.g. tests) that already contain
        # explicit "Rule X ..." heading lines but no page headers.
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
                # Ignore inline references such as "Rule 8:5 ...".
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
                current_title = _clean_rule_title(tail) or f"Rule {current_id}"
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

        fallback_content = _normalize_text(text).strip()
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

    # Tag each line with the PDF page number inferred from page headers.
    line_pages: List[Optional[int]] = []
    current_page: Optional[int] = None
    for raw_line in lines:
        hdr = page_header_re.match(raw_line.strip())
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
            if page_header_re.match(line):
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


def _image_extension_from_bytes(data: bytes, fallback_name: str = "") -> str:
    name = str(fallback_name or "").lower()
    if name.endswith(".png"):
        return ".png"
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        return ".jpg"
    if name.endswith(".gif"):
        return ".gif"
    if name.endswith(".bmp"):
        return ".bmp"
    if name.endswith(".webp"):
        return ".webp"

    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"BM"):
        return ".bmp"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return ".webp"
    return ".bin"


def extract_rulebook_images(
    rulebook_pdf: str,
    rules: List[Dict[str, Any]],
    output_dir: Path,
    relative_to: Optional[Path] = None,
) -> Dict[str, List[str]]:
    """Extract embedded images from rulebook pages and map them to sections."""
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

                ext = _image_extension_from_bytes(bytes(data), str(getattr(img, "name", "")))
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


def merge_questions_and_answers(
    questions: List[ParsedQuestion], answers: Dict[str, ParsedAnswer]
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for q in questions:
        ans = answers.get(q.question_id)
        answer_text = ans.answer if ans else ""
        correct_options = _parse_answer_keys(answer_text)
        option_keys = [opt.get("key", "") for opt in q.options]
        invalid_answer_keys = [k for k in correct_options if k not in option_keys]
        rule_refs = _extract_rule_reference_tokens(ans.reasoning if ans else "")
        merged.append(
            {
                "id": q.question_id,
                "question": q.question,
                "options": q.options,
                # Keep original answer string for traceability to source PDF.
                "answer": answer_text,
                # Order-independent answer keys; use this for quiz evaluation.
                "correct_options": correct_options,
                "reasoning": ans.reasoning if ans else "",
                "rule_references": rule_refs,
                # Useful validation flags for cleaning noisy OCR/PDF extraction.
                "invalid_answer_keys": invalid_answer_keys,
            }
        )
    return merged


def audit_dataset(dataset: Dict[str, Any]) -> Dict[str, Any]:
    questions = dataset.get("questions", [])
    rulebook = dataset.get("rulebook", [])

    ids_seen = set()
    duplicate_ids: List[str] = []
    missing_answers: List[str] = []
    invalid_key_questions: List[str] = []
    unresolved_rule_refs: List[str] = []

    available_rule_sections = {str(s.get("section_id", "")).strip() for s in rulebook}

    for q in questions:
        qid = str(q.get("id", "")).strip()
        if qid in ids_seen:
            duplicate_ids.append(qid)
        ids_seen.add(qid)

        if not q.get("correct_options"):
            missing_answers.append(qid)

        if q.get("invalid_answer_keys"):
            invalid_key_questions.append(qid)

        for ref in q.get("rule_references", []):
            # For references like "2:7", we verify top-level rule section "2" exists.
            token = str(ref)
            if ":" in token and token[0].isdigit():
                top_rule = token.split(":", 1)[0]
                if top_rule not in available_rule_sections:
                    unresolved_rule_refs.append(f"{qid}:{token}")

    return {
        "total_questions": len(questions),
        "duplicate_ids": sorted(list(set(duplicate_ids))),
        "missing_answers": sorted(list(set(missing_answers))),
        "questions_with_invalid_answer_keys": sorted(list(set(invalid_key_questions))),
        "unresolved_rule_references": sorted(list(set(unresolved_rule_refs))),
    }


def build_handball_dataset(
    questions_pdf: str,
    answers_pdf: str,
    rulebook_pdf: str,
    output_json: str,
    source_language: str = "pt",
) -> Dict[str, Any]:
    question_text = extract_pdf_text(questions_pdf)
    answer_text = extract_pdf_text(answers_pdf)
    rulebook_text = extract_pdf_text(rulebook_pdf)

    parsed_questions = parse_questions_text(question_text)
    parsed_answers = parse_answers_text(answer_text)
    rules = parse_rulebook_text(rulebook_text)
    merged_questions = merge_questions_and_answers(parsed_questions, parsed_answers)

    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    images_output_dir = output_path.parent / "rulebook_images"
    section_images = extract_rulebook_images(
        rulebook_pdf=rulebook_pdf,
        rules=rules,
        output_dir=images_output_dir,
        relative_to=output_path.parent,
    )
    for section in rules:
        sid = str(section.get("section_id", "")).strip()
        section["images"] = section_images.get(sid, [])

    dataset = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_language": source_language,
            "sources": {
                "questions_pdf": str(Path(questions_pdf).name),
                "answers_pdf": str(Path(answers_pdf).name),
                "rulebook_pdf": str(Path(rulebook_pdf).name),
            },
            "counts": {
                "questions": len(merged_questions),
                "answered_questions": sum(1 for q in merged_questions if q.get("answer")),
                "rule_sections": len(rules),
                "rulebook_images": sum(len(s.get("images", [])) for s in rules),
            },
        },
        "questions": merged_questions,
        "rulebook": rules,
    }

    dataset["integrity"] = audit_dataset(dataset)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(dataset, handle, indent=2, ensure_ascii=False)

    return dataset


def load_handball_dataset(json_path: str) -> Dict[str, Any]:
    with Path(json_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def search_rulebook(dataset: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
    """Simple substring search in rulebook sections."""
    q = query.lower().strip()
    if not q:
        return []
    matches: List[Dict[str, Any]] = []
    for section in dataset.get("rulebook", []):
        title = str(section.get("title", ""))
        content = str(section.get("content", ""))
        if q in title.lower() or q in content.lower():
            matches.append(section)
    return matches
