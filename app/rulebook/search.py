"""
Rulebook search functionality.

Provides comprehensive search across rulebook sections with ranking,
keyword extraction, and relevance scoring.
"""
import re
from typing import Any, Dict, List, Set, Tuple


def extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    """Extract significant keywords from rule content.

    Filters out common stop words and very short terms, keeps meaningful terms.

    Args:
        text: Rule content text.
        max_keywords: Maximum keywords to extract.

    Returns:
        List of significant keywords, sorted by relevance.
    """
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "is", "are", "be", "was", "were", "have", "has",
        "do", "does", "did", "will", "would", "should", "could", "may", "must",
        "can", "this", "that", "these", "those", "which", "what", "who", "when",
        "where", "why", "how", "as", "if", "from", "up", "about", "through",
        "rule", "section", "article", "player", "team", "game", "ball", "court"
    }

    # Extract words (4+ chars), convert to lowercase, remove stop words
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    keywords = [w for w in set(words) if w not in stop_words]

    # Sort by frequency in original text (higher frequency = more relevant)
    keywords.sort(key=lambda w: text.lower().count(w), reverse=True)
    return keywords[:max_keywords]


def calculate_relevance_score(section: Dict[str, Any], query: str,
                             question_count: int) -> float:
    """Calculate relevance score for a rule section relative to search query.

    Scoring: title match (high), keyword match (high), content match (medium),
    question frequency (medium bonus), difficulty (slight boost for highly-tested rules).

    Args:
        section: Rule section from dataset.
        query: Normalized (lowercased, stripped) search query.
        question_count: Number of questions referencing this rule (for boost).

    Returns:
        Relevance score (higher = more relevant).
    """
    score = 0.0
    title = str(section.get("title", "")).lower()
    content = str(section.get("content", "")).lower()
    difficulty = str(section.get("difficulty", "")).lower()

    # Title match is highest priority
    if query in title:
        score += 100.0
    elif query.startswith(title) or title.startswith(query):
        score += 80.0

    # Keyword match in title
    keywords = extract_keywords(content)
    if any(query in kw or kw in query for kw in keywords):
        score += 60.0

    # Content match
    content_count = content.count(query)
    score += content_count * 10.0

    # Question frequency bonus (rules tested more = higher priority)
    score += question_count * 3.0

    # Difficulty boost: Hard rules tested more = more important
    if difficulty == "hard":
        score += 15.0
    elif difficulty == "medium":
        score += 5.0

    return score


def search_rulebook(dataset: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
    """Search rulebook sections by keyword with relevance ranking.

    Performs case-insensitive search across titles, keywords, and content.
    Results are ranked by relevance (title matches first, then keyword matches,
    then content matches). Includes metadata for relevance display.

    Args:
        dataset: Complete handball dataset with rulebook sections and questions.
        query: Search query string (will be stripped and lowercased).

    Returns:
        List of matching rule sections sorted by relevance, with relevance metadata.
    """
    normalized_query = query.lower().strip()
    if not normalized_query:
        return []

    # Search and score all sections
    matches_with_scores: List[Tuple[Dict[str, Any], float]] = []
    for section in dataset.get("rulebook", []):
        # Use pre-computed metadata if available (from enrich_rules_with_metadata)
        question_count = section.get("question_count", 0)

        # Try to match the query
        title = str(section.get("title", "")).lower()
        content = str(section.get("content", "")).lower()
        keywords = extract_keywords(content)

        # Check if query matches title, keywords, or content
        title_match = normalized_query in title
        keyword_match = any(normalized_query in kw or kw in normalized_query for kw in keywords)
        content_match = normalized_query in content

        if not (title_match or keyword_match or content_match):
            continue

        # Calculate relevance score
        score = calculate_relevance_score(section, normalized_query, question_count)

        # Create enriched result with metadata
        enriched_section = section.copy()
        enriched_section["_relevance_score"] = score
        enriched_section["_question_count"] = question_count
        enriched_section["_keywords"] = keywords
        enriched_section["_preview"] = (content[:150] + "...") if len(content) > 150 else content

        matches_with_scores.append((enriched_section, score))

    # Sort by relevance score (descending)
    matches_with_scores.sort(key=lambda x: x[1], reverse=True)
    return [section for section, _ in matches_with_scores]
