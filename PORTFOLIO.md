# Portfolio Project Write-up — Referee Tracker

**Project name:**
Referee Tracker

**One-line pitch:**
A cross-platform app that lets handball referees track their game earnings and study for certification exams, keeping the same data in sync between a desktop app and a native Android phone app.

**The problem / why I built it:**
Handball referees juggle two separate needs — tracking their games, payments, and travel costs, and studying a large official rulebook to pass certification exams. No single tool did both, and nothing let a referee manage that data on both a computer and a phone from one shared source of truth. I built Referee Tracker to combine earnings tracking and exam prep in one app that works wherever the referee is.

**What I actually built (main features):**
- Game & earnings tracking — add/edit/delete games with transportation, food, and match-fee costs, paid/unpaid status, seasonal summaries, and Excel import
- Exam prep engine — a 400-question quiz bank with timed test variants (30/15/5 questions), a post-test review that marks the correct answer green and your wrong pick red, and a daily "Question of the Day"
- In-app rulebook — browse rule sections and open the official IHF rulebook PDF directly on the device
- Native Android app — a handball-themed, Material-style UI with hamburger navigation and full feature parity, packaged as an installable APK
- Shared live database — a MySQL backend so edits on the phone and the desktop sync to the same data
- Desktop app — a full Tkinter build for managing everything on a computer

**Tech stack:**
Python · Tkinter (desktop UI) · Kivy (Android UI) · MySQL via PyMySQL (with SQLite/JSON fallback) · PyMuPDF & Pillow (PDF/image handling) · openpyxl (Excel import) · buildozer + python-for-android on WSL2/Ubuntu (Android build pipeline) · pyjnius + Android FileProvider (native PDF opening)

**My role:**
Solo developer, built with AI pair-programming assistance. I owned the full scope — product design, desktop and mobile UIs, database architecture, and the Android build/release pipeline — using AI to accelerate implementation and debugging.

**Status:**
Working prototype in personal use. The desktop app runs, the APK installs and runs on real Android phones, and both read/write the same live MySQL database. Not yet published to an app store.

**Links:**
- GitHub: https://github.com/multimccp00/Accounting-Referee
  (Note: currently reflects the earlier desktop version; mobile code + a portfolio README still to be committed.)

**Anything notable — hard problems solved / what I'm proud of:**
- Diagnosed a mobile app crash down to the *emulator's* graphics layer (a BlueStacks OpenGL/EGL incompatibility) rather than the app itself — verified by getting it running cleanly on a standards-compliant Android emulator with GPU passthrough
- Migrated the mobile UI from KivyMD to plain Kivy to fix an Android-only startup crash (KivyMD reading the window before it existed), then hand-built a themed Material-style interface (custom cards, drawer, buttons, and a centered date-picker to replace the broken native dropdown)
- Solved Android's FileProvider/manifest requirements to open a bundled PDF in the device's native viewer (patched the python-for-android manifest template so the `<provider>` landed inside `<application>`)
- Architected a single MySQL database shared live between a desktop and a mobile client, with graceful SQLite/JSON fallback when offline
- Set up the full Android build pipeline from scratch on Windows via WSL2 (SDK/NDK, buildozer, signing) and produced a working installable APK

**Images / screenshots (in the `portfolio/` folder):**
- 01_dashboard.png — Dashboard with earnings KPI cards (games this season, total paid, amount left, test accuracy)
- 02_navigation_drawer.png — Slide-out hamburger navigation menu
- 03_games.png — Games list with color-coded paid/unpaid cards (live DB data)
- 04_add_game_form.png — Add/edit game form
- 05_date_picker.png — Custom centered date-picker modal
- 06_tests_menu.png — Test setup with 30/15/5-question length selector
- 07_test_question.png — Live timed test question with countdown
- 08_review.png — Post-test review: correct answer in green, wrong pick in red (recommended hero image)
- 09_rulebook.png — Rulebook section list
- 10_rulebook_pdf.png — Official IHF rulebook PDF rendered on the device

---

## Short "featured card" version (for a portfolio grid/tile)

Referee Tracker — a cross-platform Python app for handball referees that combines game-earnings tracking with a 400-question, timed certification exam trainer. Built a Tkinter desktop app and a native Kivy Android app (packaged to APK) sharing one live MySQL database, plus an in-app IHF rulebook PDF viewer.
