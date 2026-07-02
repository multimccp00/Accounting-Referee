# Rulebook Improvements Summary

## Overview
The rulebook feature has been significantly improved to address navigation, search, and discoverability issues. All changes maintain backward compatibility with existing data while adding rich metadata and intelligent ranking.

---

## Improvements Made

### 1. **Intelligent Search with Relevance Ranking**
**File**: `app/rulebook/search.py`

**Changes**:
- Replaced simple substring matching with multi-factor relevance scoring
- Search now ranks results by:
  - Title matches (highest priority)
  - Keyword matches (extracted from rule content)
  - Content matches (with frequency counting)
  - Question frequency (rules tested more = higher rank)
  - Difficulty level (hard rules boost relevance)

**Implementation Details**:
- `extract_keywords()`: Extracts 5 most significant keywords from each rule, filtering out common stop words
- `calculate_relevance_score()`: Computes normalized relevance score (0-∞)
- Results are automatically sorted by relevance, best matches first

**User Benefit**: 
- Search results are ordered by usefulness, not alphabetically
- Most relevant rules appear first without user having to scroll

---

### 2. **Rule Difficulty Tagging**
**Files**: `app/rulebook/content.py`

**Changes**:
- New function `enrich_rules_with_metadata()` analyzes question frequency
- Automatically tags each rule with difficulty level:
  - **Hard**: 6+ test questions reference this rule
  - **Medium**: 3-5 test questions reference this rule
  - **Easy**: 0-2 test questions reference this rule
  - **Untested**: No test questions reference this rule

- Metadata is computed during dataset build and stored in `handball_content.json`
- Updated `build_handball_dataset()` to call enrichment function

**User Benefit**:
- Referees can instantly see which rules are critical (Hard = heavily tested)
- Helps prioritize study time on high-impact rules

---

### 3. **Enhanced Search Result Display**
**Files**: `app/ui/app.py` → `search_rulebook_ui()` method

**Changes**:
- Search results now display:
  - Rule ID and title
  - Difficulty level in brackets (e.g., "[Hard]")
  - Question count in parentheses (e.g., "(108 q)")
  
Example: `4 - The Team, Substitutions, Equipment, Player Injuries [Hard] (108 q)`

**User Benefit**:
- At a glance, users see which rules are most important
- Helps context-aware browsing of results

---

### 4. **Rule Information Sidebar**
**Files**: `app/ui/app.py`

**Changes**:
- New `_update_rule_info_status()` method displays rule metadata
- Info bar shows:
  - Difficulty level
  - Number of test questions covering this rule
  - Top 3 extracted keywords from rule content

**UI Location**: 
- Appears above the PDF viewer in the rulebook page
- Auto-updates when user selects a different rule from search results

**User Benefit**:
- Quick context about the rule's importance and key concepts
- Helps users understand at a glance if this is a critical rule to learn

---

### 5. **Keyword Extraction & Indexing**
**File**: `app/rulebook/search.py` → `extract_keywords()` function

**Changes**:
- Automatically extracts 5 most significant keywords from each rule
- Filters out 50+ common stop words (the, a, and, rule, player, etc.)
- Sorts keywords by frequency in original content

**Implementation**:
- Regex-based word extraction (4+ character words)
- Stop word filtering
- Frequency-based ranking

**User Benefit**:
- Helps understand rule scope at a glance
- Keywords appear in the info sidebar for context
- Improves search accuracy (keyword matches boost relevance)

---

## Data Structure Changes

### Rule Object Now Includes:
```json
{
  "section_id": "4",
  "title": "The Team, Substitutions, Equipment, Player Injuries",
  "content": "...",
  "start_page": 12,
  "end_page": 15,
  "images": ["..."],
  
  // NEW FIELDS:
  "difficulty": "Hard",
  "question_count": 108
}
```

### Search Result Object Now Includes:
```json
{
  // All original fields plus:
  "_relevance_score": 185.5,
  "_question_count": 108,
  "_keywords": ["team", "substitution", "player", "equipment", "position"],
  "_preview": "First 150 characters of rule content..."
}
```

---

## Testing Notes

### Search Functionality
- Tested with multiple queries: "goal", "substitute", "rule 2"
- Results properly ranked by relevance
- Difficulty tags appear correctly in UI
- Keywords extracted appropriately

### Performance
- Search completes instantly on 23-rule, 400-question dataset
- Keyword extraction computed once during dataset build
- No runtime performance impact on search UI

### Backward Compatibility
- Existing `handball_content.json` can be updated by running:
  ```bash
  python scripts/build_handball_json.py \
    --questions "9434_IHF Catalogue of Rules Questions_v2_23-5-19_EN.pdf" \
    --answers "9434_IHF Catalogue of Rules Questions_Answers_v2_23-5-19_EN1.pdf" \
    --rulebook "09A - Rules of the Game_Indoor Handball_E.pdf"
  ```
- Old code continues to work with new data (graceful degradation)

---

## Future Enhancements (Not Implemented)

These features were identified as improvements but not yet implemented:

1. **Question-to-Rule Linking in Tests** 
   - During tests, show related rules for each question
   - Allow jumping from test feedback to relevant rule sections

2. **Rule Difficulty Filter**
   - Filter search results by difficulty level
   - "Show only Hard rules" toggle

3. **Rule Index/TOC Sidebar**
   - Left sidebar with full rule list
   - Quick jump navigation to any rule
   - Visual indicator of difficulty levels

4. **Content Preview in Search**
   - Show first 150 chars of rule content in search results
   - Helps users decide if result is relevant without opening PDF

5. **Rule Bookmarks**
   - Mark important rules for quick access
   - Personal study list

---

## Files Modified

1. **app/rulebook/search.py**
   - Rewrote search engine with intelligent ranking
   - Added keyword extraction

2. **app/rulebook/content.py**
   - Added `enrich_rules_with_metadata()` function
   - Updated `build_handball_dataset()` to enrich rules

3. **app/ui/app.py**
   - Added Dict, Any imports for type hints
   - Updated `search_rulebook_ui()` to display difficulty and question count
   - Added `_update_rule_info_status()` method
   - Added info bar to rulebook page with `rulebook_info_var`
   - Updated `show_selected_rule_section()` to call info update

4. **data/handball_content.json**
   - Rebuilt with new metadata fields (difficulty, question_count)
   - Metadata computed from test question references

---

## Summary

The rulebook is now significantly more usable:

✅ Search results are intelligently ranked by relevance  
✅ Rules are tagged with difficulty based on test frequency  
✅ Users can see which rules are critical at a glance  
✅ Keywords help understand rule scope  
✅ Information sidebar provides context before opening PDF  
✅ Fully backward compatible with existing code  

The improvements directly address the identified gap: **"Rulebook Navigation is Fragmented"** by making rules discoverable, prioritizing important rules, and providing context-aware information display.
