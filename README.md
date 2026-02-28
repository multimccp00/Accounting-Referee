# Referee Earnings Tracker (Accounting_Referee)

A compact Python desktop app for referees to record and track match earnings by season. Data is stored locally in JSON files — private by default and excluded from Git.

Short description
- Track games, payments (transport, food, match fee), paid status and observations — organized by season.

Key features
- Add / edit / delete games with date, game number, location, payments, paid status and notes
- Season-based organization and filtering (e.g. 2024/2025, 2025/2026)
- Search and sort by Date, Game Number, Location, Amount Paid and more
- Summary per season showing amount paid and outstanding balances
- A single combined JSON snapshot (`data/all_games.json`) is maintained and updated on every change, providing an easy way to export or review all games regardless of backend.
  When the app is built into an executable (via PyInstaller or similar) the
  `data/` directory is created next to the executable, and all JSON files are
  written there.  This ensures your data persists between updates; the
  executable bundle itself is read‑only, so nothing is stored inside the
  package.
- When a database connection is in use the manager will automatically **deduplicate** rows that share the same season and game number; the schema enforces a unique constraint so duplicates cannot reoccur.
- Local JSON files exist as a **write‑through backup only** (data folder is gitignored for privacy).  The database is always used for reads/writes; JSON files are updated after each change but never read by the application except during the initial one‑time migration step.

Quick start
1. Create a virtual environment (recommended):
   - python -m venv .venv
   - source .venv/Scripts/activate   (Windows) or source .venv/bin/activate (macOS / Linux)
2. Install dependencies (optional frontend and any database backends):
   - A rich date-picker (optional): `pip install tkcalendar`
   - For PostgreSQL support: `pip install psycopg2-binary`
   - For MySQL/MariaDB support: `pip install pymysql`
   - Alternatively you can install everything at once with:
     ```bash
     pip install -r requirements.txt
     ```
3. Run the app:
   - python -m app.main
   - to use an SQLite file instead of JSON, either set the `REF_DB_PATH` environment variable or pass `--db path/to/dbfile.sqlite` on the command line.  A simple schema will be created automatically if the file does not already exist.
   - you can also point at a remote PostgreSQL or MySQL/MariaDB server by providing a suitably formatted URL.  Replace the placeholder values with your own credentials and host information.
     *PostgreSQL example:*  
     ```bash
     python -m app.main --db postgresql://<user>:<password>@<host>:<port>/<database>
     ```
     *MySQL example:*  
     ```bash
     python -m app.main --db mysql://<user>:<password>@<host>:<port>/<database>
     ```
     (install the appropriate driver – `psycopg2-binary` or `pymysql` – as
     noted in the requirements.)
   - if you have an existing DB‑API connection object you can pass it
     programmatically when embedding the application; the manager will use
     it directly and assumes your schema is already created.
   - **the repository does not contain any usable database credentials.**
     you must supply your own via command line, environment variables, or
     the gitignored `db_connection.py` file described below.
   - note: a blank/template `db_connection.py` (with '<your-...>' values) is
     intentionally ignored at startup.  the app will not attempt to connect
     using those placeholders and will silently fall back to the JSON backend
     instead of showing a popup error.  remove or populate the file if you
     intend to use a real database.
   - if you have an existing DB‑API connection object you can pass it
     programmatically when embedding the application; the manager will use
     it directly and assumes your schema is already created.
   - **storing credentials out of source control:**
     create a file called `db_connection.py` next to the main script and
     populate it with a `DB_CONFIG` dictionary.  A sample (`db_connection.example.py`)
     is included.  The real file is ignored by Git through `.gitignore`, so
     you can keep sensitive information private.
   - alternatively the connection can be configured entirely via environment
     variables (useful for deployment).  Set `DB_HOST`, `DB_PORT` (defaults to
     3306), `DB_USER`, `DB_PASS` and `DB_NAME` (defaults to
     `referee_accounting`).  Example:
     ```bash
     export DB_HOST=<your-db-host>
     export DB_USER=<your-user>
     export DB_PASS=<your-password>
     export DB_NAME=<your-database>
     python -m app.main
     ```
     The app will attempt to open a MySQL connection using those values; if
     the connection fails it will fall back to the JSON backend and display a
     warning on startup.

     When a database connection is successfully established, the manager will
     also look at any existing `games_<season>.json` files in the `data/`
     directory and import them into the database automatically (each season is
     imported only once).  After a season has been migrated the JSON file is
     **never read again** – the database is treated as the authoritative
     source and deletions or edits in the UI will not be overwritten by the
     backup.  The original JSON files remain on disk purely so you still have
     a copy if the database is lost or corrupted.

Usage notes
- The app displays `Amount Paid` (only recorded payments) and `Amount Left` (outstanding due) per game.
- Observations/notes are stored with each game and shown in the table.
- All data is stored under the `data/` folder as JSON files (one file per season).

Privacy & GitHub
- The `data/` directory is listed in `.gitignore` — your game data will not be included when you push this repo to GitHub.

Contributing
- Bug reports and feature requests are welcome. Open an issue or submit a PR.

Suggested Topics / Tags
- python, tkinter, desktop-app, referee, accounting, json

License
- MIT License — see the `LICENSE` file (or add one if needed).

Contact
- Create issues on the repository or reach out to the project owner.
