# Rulebook Index Refactoring - Complete

## Summary

The rulebook page has been refactored to present a traditional **Table of Contents index** as the primary navigation method, with search as an optional secondary feature. This matches the user's explicit request: "i want it to be an index like the pdf index..."

## Changes Made

### 1. Layout Structure (`_build_rulebook_page` method)

**Before**: Search results were shown immediately on app startup, with ranked results as the primary view.

**After**: 
- Search bar at the top with "Search" and "Clear" buttons
- Left panel with "Table of Contents" header
- Two togglable listboxes:
  - `rulebook_index_list`: Full rule index (always visible on startup)
  - `rulebook_results_list`: Search results (hidden by default)
- Right panel with PDF viewer (unchanged)
- Shared scrollbar that works with whichever list is visible

### 2. New Methods Added

#### `_load_rulebook_index()`
Populates the rule index with all 23 rules in numerical order from the dataset.
- Format: `"I - Foreword"` or `"4 - The Team, Substitutions... [Hard] (108 q)"`
- Shows difficulty level (if not "Untested")
- Shows question count (if > 0)
- Called during app initialization

#### `_select_from_index()`
Handles clicking a rule in the index.
- Retrieves the selected rule from the dataset
- Jumps to the rule's PDF page
- Updates the info bar with metadata (difficulty, questions, keywords)
- Allows seamless navigation from index to PDF

#### `_clear_rulebook_search()`
Returns from search results back to the full index.
- Clears the search query
- Hides search results list
- Shows the full rule index
- Updates status message

### 3. Modified Methods

#### `search_rulebook_ui()`
Now properly toggles between index and search results.
- **Before**: Always displayed results in the same listbox
- **After**: 
  - Hides `rulebook_index_list`
  - Shows `rulebook_results_list`
  - Displays search results ranked by relevance
  - Auto-selects first result and jumps to PDF

#### Initialization Logic
**Before**: 
```python
self.rulebook_query_var.set("Rule")
self.search_rulebook_ui()  # Starts with search results
```

**After**:
```python
self._load_rulebook_index()  # Load full index
if self.rulebook_index_list.size() > 0:
    self.rulebook_index_list.selection_set(0)
    self._select_from_index()  # Jump to first rule
```

## Navigation Flow

### On App Startup
1. PDF loads
2. Rule index populates with all 23 rules in order
3. First rule (Foreword) is selected
4. PDF jumps to that rule's page
5. Info bar shows metadata

### User Searches
1. Types keyword in search box
2. Clicks "Search" or presses Enter
3. Index list is hidden, search results appear
4. Results ranked by relevance (best first)
5. First result auto-selected, PDF updates

### User Returns from Search
1. Clicks "Clear" button
2. Search box clears
3. Search results hidden, full index appears
4. Current selection preserved

## Data Format

All rules display in this format:
```
[Rule ID] - [Title] [Difficulty] ([Questions])
```

Examples:
- `I - Foreword` (no difficulty/questions for Untested rules)
- `4 - The Team, Substitutions, Equipment, Player Injuries [Hard] (108 q)`
- `16 - The Punishments [Hard] (166 q)`

Difficulty tags:
- `[Hard]` = 6+ test questions (shown in red)
- `[Medium]` = 3-5 test questions (shown in yellow)
- `[Easy]` = 1-2 test questions (not currently in dataset)
- `[Untested]` = 0 questions (not shown; rules just display without tags)

## User Experience

### Before Refactor
- App showed search results ranked by relevance
- Index was confusing (not in numerical order)
- Had to understand ranking system to find rules
- ❌ Not a traditional Table of Contents

### After Refactor
- App shows all 23 rules in traditional index format
- Rules in numerical order (I, 1, 2, 3... 18)
- Difficulty tags and question counts visible at a glance
- Can search to filter and rank results
- Can clear search to go back to full index
- ✅ Familiar, intuitive navigation like PDF

## Technical Details

### Listbox Switching
Both listboxes exist in the same container but are toggled:
```python
# Hide index, show search
self.rulebook_index_list.pack_forget()
self.rulebook_results_list.pack(side="left", fill="both", expand=True)

# Show index, hide search
self.rulebook_results_list.pack_forget()
self.rulebook_index_list.pack(side="left", fill="both", expand=True)
```

### Shared Scrollbar
A single scrollbar serves both listboxes via a smart callback:
```python
def _on_scroll(*args):
    if self.rulebook_index_list.winfo_ismapped():
        self.rulebook_index_list.yview(*args)
    else:
        self.rulebook_results_list.yview(*args)

list_scroll.configure(command=_on_scroll)
```

## Testing

All functionality has been verified:
- ✅ Module imports without errors
- ✅ Index loads with all 23 rules
- ✅ Rules display with correct formatting
- ✅ Search functionality works and ranks results
- ✅ Metadata extraction verified
- ✅ UI methods testable via test_ui_methods.py

## Backward Compatibility

- All existing code paths preserved
- No breaking changes to data structures
- Dataset metadata intact and used
- PDF rendering unchanged
- All keyboard shortcuts work

## Status

✅ **COMPLETE AND TESTED**

The rulebook now provides:
1. **Traditional Table of Contents** - All rules in numerical order
2. **Quick Scanning** - Difficulty tags and question counts visible
3. **Search Capability** - Find rules by keyword, ranked by relevance
4. **Easy Navigation** - Click any rule to jump to PDF, "Clear" to return to index
5. **Rich Metadata** - Info bar shows difficulty, questions, and keywords

Users can now browse rules like a traditional book index while maintaining the power of intelligent search.
