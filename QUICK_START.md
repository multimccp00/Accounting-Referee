# Quick Start - New Rulebook Features

## Two Simple Changes

### 1. Cleaner Index
```
Before: "4 - The Team, Substitutions, Equipment, Player Injuries [Hard] (108 q)"
After:  "4 - The Team, Substitutions, Equipment, Player Injuries"
```
✅ Removed difficulty tags
✅ Removed question counts
✅ Cleaner index display

### 2. Text View (New Feature)
Toggle between PDF and extracted text content:
- **PDF Mode**: Original rulebook pages (default)
- **Text Mode**: Extracted text + images (new)

---

## How to Use

### Start App
```bash
python app/main.py
```

### Navigate to Rulebook
- Click "Rulebook" tab on left

### View a Rule
1. Click any rule in the index
2. Metadata shows in info bar (difficulty, questions)

### Switch View Modes
- **Click "PDF"** → See original PDF pages
- **Click "Text"** → See extracted text with images

### Test Review Workflow
1. Review a test question
2. Find the referenced rule in rulebook index
3. Click rule, then click "Text"
4. Read extracted content
5. Copy text for notes
6. Switch back to PDF to see original formatting

---

## What Changed

| Item | Before | After | Status |
|------|--------|-------|--------|
| Index Display | With metadata | Clean format | ✅ |
| View Modes | PDF only | PDF + Text | ✅ |
| Text Content | N/A | Extracted + searchable | ✅ |
| Images | PDF only | Text view embedded | ✅ |
| Features | Maintained | All + new features | ✅ |

---

## UI Controls

### View Mode Buttons (Top Right)
```
┌─────────────────────────┐
│ [PDF] [Text] | Buttons  │
└─────────────────────────┘
     Toggles between views
```

### Index View
```
Left Panel: Rule Index
  I - Foreword
  1 - Playing Court
  2 - Playing Time...
  3 - The Ball
  ...
  (Clean list, no metadata)
```

### Text View
```
Right Panel: Extracted Content
  [Title and Rule ID]
  ─────────────────
  [Full text content]
  [Embedded images]
  [Scrollable area]
```

### PDF View
```
Right Panel: PDF Pages
  [Original PDF pages]
  [Prev/Next buttons]
  [Zoom controls]
  [Continuous mode]
```

---

## Tips & Tricks

### For Test Review
1. Have test open in one window
2. Have rulebook in another
3. When question references a rule, click it
4. Toggle to Text mode
5. Copy relevant text to notepad
6. Keep both windows visible for reference

### For Studying
1. Use Text mode to read rules without PDF app
2. Copy text into study guide
3. Take notes with text visible
4. Switch to PDF to see original formatting
5. Use images in text view for context

### For Quick Reference
1. Use clean index to find rules quickly
2. Click rule name for instant reference
3. Info bar shows difficulty (how important)
4. Metadata helps prioritize study time

---

## Features

### Available Now
- ✅ Toggle PDF/Text views
- ✅ Text extraction for all 23 rules
- ✅ 30 embedded images
- ✅ Auto-scaling images
- ✅ Copy text support
- ✅ Full scrolling
- ✅ Continuous mode
- ✅ Info bar metadata

### Works Like Before
- ✅ PDF view unchanged
- ✅ Search functionality intact
- ✅ Index navigation works
- ✅ All controls responsive

---

## Data Available

### Per Rule
- Full extracted text (847-10,000+ characters)
- Difficulty classification (Hard/Medium/Easy/Untested)
- Test question count (0-166 questions)
- Extracted keywords (for searches)
- Associated images (where available)

### Overall
- 23 rules with text content
- 30 extracted images
- 400 test questions indexed
- Full-text searchable content

---

## Keyboard Shortcuts

| Action | Control |
|--------|---------|
| Toggle modes | Click PDF/Text buttons |
| Navigate rules | Click in index list |
| Scroll text | Mouse wheel |
| Select text | Click and drag |
| Copy text | Ctrl+C (standard) |

---

## Troubleshooting

### Text view shows slowly
- Large rules (10,000+ chars) take 200-500ms to render
- This is normal and only happens first time
- Switch back to PDF while it loads

### Images not showing
- They load on first use then cache
- Check `data/rulebook_images/` directory exists
- Image path shown if loading fails

### Can't copy text from PDF
- Switch to Text mode - text is fully copyable there
- PDF mode is images only (original formatting)

### Index shows metadata
- Refresh page with F5 or restart app
- Should show clean "ID - Title" format

---

## Getting Help

See detailed docs:
- `TEXT_VIEW_FEATURE.md` - Text view guide
- `RECENT_CHANGES.md` - What changed details
- `DEPLOYMENT_READY.md` - Full deployment info

---

## Done!

Everything is ready to use. Start the app and try the new features!

```bash
python app/main.py
```

Then go to the **Rulebook** tab and toggle between **PDF** and **Text** modes.

Happy studying! 📖
