import sys
import os
import random
import json
import time
import csv
import io
import re
import difflib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import calendar
from datetime import datetime, date
from pathlib import Path
try:
    # Works when launched as a module from project root: `python -m app.main`
    from app.data_manager import GameDataManager
except ModuleNotFoundError:
    # Works when launched directly as a script: `python app/main.py`
    from data_manager import GameDataManager

try:
    from app.handball_content import load_handball_dataset
except ModuleNotFoundError:
    from handball_content import load_handball_dataset

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

# default remote database connection details – these are merely
# placeholders.  Real credentials should be supplied via environment
# variables or a private `db_connection.py` file; the values below are not
# sensitive and are kept empty to avoid accidentally leaking secrets.
DEFAULT_DB = {
    'host': 'localhost',
    'port': 3306,
    'user': '',
    'password': '',
    'dbname': '',
}

class RefereeApp:
    def __init__(self, root, db_path: str = None, db_conn=None):
        print("[debug] RefereeApp.__init__ start")
        self.root = root
        self.root.title("Referee Earnings Tracker")
        # manager may use JSON, SQLite path, or a supplied connection object
        print("[debug] creating GameDataManager (db_path=", db_path, "db_conn=", bool(db_conn), ")")
        if db_conn is not None:
            self.manager = GameDataManager(db_conn=db_conn)
        elif db_path:
            self.manager = GameDataManager(db_path=db_path)
        else:
            self.manager = GameDataManager()
        print("[debug] manager created, conn=", getattr(self.manager, 'conn', None))

        # if we have a database connection, try a simple query now to make
        # sure the connection works; if it raises we fall back to JSON.
        if getattr(self.manager, 'conn', None) is not None:
            print("[debug] testing database connection")
            try:
                cur = self.manager.conn.cursor()
                cur.execute('SELECT 1')
                cur.fetchall()
                cur.close()
                print("[debug] db connection ok")
            except Exception as e:
                print(f"Warning: database connection is unusable ({e}); using JSON instead.")
                # replace manager with plain JSON instance
                self.manager = GameDataManager()
                print("[debug] manager replaced with JSON-only")
        print("[debug] calling get_seasons")
        self.seasons = self.get_seasons()
        print("[debug] seasons=", self.seasons)
        self.selected_season = tk.StringVar(value=self.seasons[0] if self.seasons else "2025/2026")
        self.games = []
        self.selected_total = 0.0
        self.rulebook_dataset_path = None
        self.rulebook_image_refs = []
        print("[debug] calling setup_ui")
        self.setup_ui()
        print("[debug] calling load_games")
        self.load_games()
        print("[debug] RefereeApp.__init__ done")

    def get_seasons(self):
        # retrieve list of seasons available either in JSON files or in database
        seasons = []
        if self.manager.conn:
            try:
                cursor = self.manager.conn.cursor()
                cursor.execute("SELECT DISTINCT season FROM games ORDER BY season")
                rows = cursor.fetchall()
                seasons = [r[0] for r in rows]
            except Exception as exc:
                # if the query fails we treat the database as unusable and
                # fall back to JSON.  this mirrors the strategy in
                # GameDataManager so the UI continues functioning.
                print(f"Warning: unable to fetch seasons from DB: {exc}")
                self.manager.db_error = str(exc)
                try:
                    self.manager.conn.close()
                except Exception:
                    pass
                self.manager.conn = None
        if not self.manager.conn:
            import os
            if os.path.isdir(self.manager.data_dir):
                for f in os.listdir(self.manager.data_dir):
                    if f.startswith("games_") and f.endswith(".json"):
                        s = f[6:-5].replace('-', '/')
                        seasons.append(s)
        if not seasons:
            seasons = ["2025/2026"]
        return sorted(seasons)

    def _setup_theme(self):
        # Palette inspired by the IHF PDF visuals: deep blues, aqua accents,
        # and clean neutral surfaces for readability.
        self.colors = {
            "root_bg": "#0a3150",
            "sidebar_bg": "#08304a",
            "sidebar_text": "#e9f2f8",
            "sidebar_muted": "#9dc1d5",
            "sidebar_active": "#0f4e76",
            "shell_bg": "#e8eff4",
            "surface": "#ffffff",
            "surface_alt": "#f4f8fb",
            "text_primary": "#102a43",
            "text_secondary": "#486581",
            "hero_bg": "#0f5f8f",
            "hero_sub": "#d3ebf7",
            "rulebook_bg": "#dceef9",
            "rulebook_panel": "#2e78a6",
            "ball_main": "#6db2d7",
            "ball_soft": "#b9def2",
            "accent": "#1f7a8c",
            "accent_soft": "#d8edf2",
            "success": "#2f9e44",
            "border": "#c7d4df",
            "danger": "#b42318",
        }
        self.fonts = {
            "title": ("Bahnschrift", 16, "bold"),
            "subtitle": ("Trebuchet MS", 10),
            "brand": ("Bahnschrift", 16, "bold"),
            "brand_sub": ("Trebuchet MS", 9),
            "nav": ("Trebuchet MS", 11, "bold"),
            "hero": ("Bahnschrift", 28, "bold"),
            "h2": ("Bahnschrift", 15, "bold"),
            "h3": ("Bahnschrift", 13, "bold"),
            "body": ("Trebuchet MS", 10),
            "body_bold": ("Trebuchet MS", 10, "bold"),
            "small": ("Trebuchet MS", 9),
        }

    def _configure_ttk_theme(self):
        c = self.colors
        f = self.fonts
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.root.option_add("*Font", f["body"])

        style.configure("TFrame", background=c["shell_bg"])
        style.configure("TLabel", background=c["shell_bg"], foreground=c["text_secondary"], font=f["body"])
        style.configure("TButton", font=f["body_bold"], padding=(10, 6))
        style.map(
            "TButton",
            background=[("active", c["accent_soft"]), ("pressed", c["accent_soft"])],
            foreground=[("active", c["text_primary"]), ("pressed", c["text_primary"])],
        )
        style.configure("Treeview", font=f["body"], rowheight=28, fieldbackground=c["surface"], background=c["surface"])
        style.configure("Treeview.Heading", font=f["body_bold"], background=c["surface_alt"], foreground=c["text_primary"])
        style.configure("TLabelframe", background=c["surface"], bordercolor=c["border"])
        style.configure("TLabelframe.Label", background=c["surface"], foreground=c["text_primary"], font=f["body_bold"])
        style.configure("TCombobox", fieldbackground=c["surface"], foreground=c["text_primary"])

    def setup_ui(self):
        self._setup_theme()
        self._configure_ttk_theme()
        c = self.colors
        f = self.fonts

        self.root.geometry("1360x820")
        self.root.minsize(1100, 700)
        self.root.configure(bg=c["root_bg"])

        self.test_progress = self._load_test_progress()
        stats = self.test_progress.get('stats', {})
        self.test_attempts = int(stats.get('attempts', 0) or 0)
        self.test_correct = int(stats.get('correct', 0) or 0)
        self.current_test_question = None
        self.current_test_answered = False
        self.current_test_session_id = None
        self.session_results = {}
        self.test_timer_job = None
        self.test_end_epoch = None
        self.test_total_seconds = 30 * 60
        self.max_wrong_to_pass = 5

        self.handball_dataset = None
        self.quiz_questions = []
        self._load_handball_content()

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.sidebar = tk.Frame(self.root, bg=c["sidebar_bg"], width=240)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)

        self.main_shell = tk.Frame(self.root, bg=c["shell_bg"])
        self.main_shell.grid(row=0, column=1, sticky="nsew")
        self.main_shell.grid_rowconfigure(1, weight=1)
        self.main_shell.grid_columnconfigure(0, weight=1)

        topbar = tk.Frame(self.main_shell, bg=c["surface"], height=70)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_propagate(False)

        self.page_title_var = tk.StringVar(value="Dashboard")
        tk.Label(
            topbar,
            textvariable=self.page_title_var,
            bg=c["surface"],
            fg=c["text_primary"],
            font=f["title"],
        ).pack(side="left", padx=20, pady=18)
        self.page_subtitle_var = tk.StringVar(value="Track your referee seasons, tests and progress")
        tk.Label(
            topbar,
            textvariable=self.page_subtitle_var,
            bg=c["surface"],
            fg=c["text_secondary"],
            font=f["subtitle"],
        ).pack(side="left", pady=24)

        self.page_host = tk.Frame(self.main_shell, bg=c["shell_bg"])
        self.page_host.grid(row=1, column=0, sticky="nsew")
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)

        self.pages = {
            "dashboard": tk.Frame(self.page_host, bg=c["shell_bg"]),
            "games": tk.Frame(self.page_host, bg=c["shell_bg"]),
            "tests": tk.Frame(self.page_host, bg=c["shell_bg"]),
            "rulebook": tk.Frame(self.page_host, bg=c["shell_bg"]),
            "statistics": tk.Frame(self.page_host, bg=c["shell_bg"]),
        }
        for frame in self.pages.values():
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_remove()

        self._build_sidebar()
        self._build_dashboard_page()
        self._build_games_page()
        self._build_tests_page()
        self._build_rulebook_page()
        self._build_statistics_page()

        self.show_page("dashboard")

    def _progress_file_path(self):
        return os.path.join(self.manager.data_dir, 'test_progress.json')

    def _load_test_progress(self):
        path = self._progress_file_path()
        default = {'stats': {'attempts': 0, 'correct': 0}, 'questions': {}, 'sessions': []}
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        data.setdefault('stats', {'attempts': 0, 'correct': 0})
                        data.setdefault('questions', {})
                        data.setdefault('sessions', [])
                        return data
        except Exception:
            pass
        return default

    def _save_test_progress(self):
        path = self._progress_file_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.test_progress, f, indent=2, ensure_ascii=False)

    def _stop_test_timer(self):
        if self.test_timer_job is not None:
            try:
                self.root.after_cancel(self.test_timer_job)
            except Exception:
                pass
            self.test_timer_job = None

    def _tick_test_timer(self):
        if not self.active_test_questions or self.test_end_epoch is None:
            if hasattr(self, 'test_timer_var'):
                self.test_timer_var.set("")
            self._stop_test_timer()
            return

        remaining = int(max(0, self.test_end_epoch - time.time()))
        mins = remaining // 60
        secs = remaining % 60
        self.test_timer_var.set(f"Time: {mins:02d}:{secs:02d}")

        if remaining <= 0:
            self.finish_test_session(timeout=True)
            return

        self.test_timer_job = self.root.after(1000, self._tick_test_timer)

    def _record_question_result(self, question_id: str, result: str):
        qstats = self.test_progress.setdefault('questions', {}).setdefault(
            question_id,
            {'attempts': 0, 'correct': 0, 'wrong': 0, 'unanswered': 0}
        )
        qstats['attempts'] = int(qstats.get('attempts', 0)) + 1
        if result == 'correct':
            qstats['correct'] = int(qstats.get('correct', 0)) + 1
        elif result == 'wrong':
            qstats['wrong'] = int(qstats.get('wrong', 0)) + 1
        elif result == 'unanswered':
            qstats['unanswered'] = int(qstats.get('unanswered', 0)) + 1

    def _available_unanswered_pool(self):
        pool = []
        by_q = self.test_progress.get('questions', {})
        for q in self.quiz_questions:
            qid = str(q.get('id', ''))
            qstats = by_q.get(qid, {})
            attempts = int(qstats.get('attempts', 0) or 0)
            unanswered = int(qstats.get('unanswered', 0) or 0)
            if attempts == 0 or unanswered > 0:
                pool.append(q)
        return pool

    def _available_wrong_pool(self):
        pool = []
        by_q = self.test_progress.get('questions', {})
        for q in self.quiz_questions:
            qid = str(q.get('id', ''))
            qstats = by_q.get(qid, {})
            wrong = int(qstats.get('wrong', 0) or 0)
            if wrong > 0:
                pool.append(q)
        return pool

    def _build_sidebar(self):
        c = self.colors
        f = self.fonts

        brand = tk.Frame(self.sidebar, bg=c["sidebar_bg"])
        brand.pack(fill="x", padx=18, pady=(20, 10))
        tk.Label(
            brand,
            text="REF TRACKER",
            bg=c["sidebar_bg"],
            fg=c["sidebar_text"],
            font=f["brand"],
        ).pack(anchor="w")
        tk.Label(
            brand,
            text="Games + Tests + Rules",
            bg=c["sidebar_bg"],
            fg=c["sidebar_muted"],
            font=f["brand_sub"],
        ).pack(anchor="w", pady=(2, 0))

        nav_items = [
            ("dashboard", "Profile Dashboard"),
            ("games", "List of Games"),
            ("tests", "Tests"),
            ("rulebook", "Rulebook"),
            ("statistics", "Statistics"),
        ]

        self.nav_buttons = {}
        for key, label in nav_items:
            btn = tk.Button(
                self.sidebar,
                text=label,
                anchor="w",
                relief="flat",
                bd=0,
                bg=c["sidebar_bg"],
                fg=c["sidebar_text"],
                activebackground=c["sidebar_active"],
                activeforeground=c["surface"],
                font=f["nav"],
                command=lambda k=key: self.show_page(k),
                padx=18,
                pady=10,
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[key] = btn

    def _build_dashboard_page(self):
        page = self.pages["dashboard"]
        c = self.colors
        f = self.fonts

        hero = tk.Frame(page, bg=c["hero_bg"], height=230)
        hero.pack(fill="x", padx=20, pady=(20, 10))
        hero.pack_propagate(False)

        hero_canvas = tk.Canvas(hero, bg=c["hero_bg"], highlightthickness=0)
        hero_canvas.pack(fill="both", expand=True)

        def _paint_hero_bg(_event=None):
            w = max(1, hero_canvas.winfo_width())
            h = max(1, hero_canvas.winfo_height())
            hero_canvas.delete("bg")
            # Large decorative blue balls inspired by the rulebook cover.
            hero_canvas.create_oval(w - 250, -95, w + 70, 215, fill=c["ball_main"], outline="", tags="bg")
            hero_canvas.create_oval(w - 220, -65, w + 10, 165, fill=c["ball_soft"], outline="", stipple="gray75", tags="bg")
            hero_canvas.create_oval(-85, h - 105, 120, h + 105, fill="#4e9fc9", outline="", tags="bg")
            hero_canvas.create_oval(40, h - 78, 175, h + 55, fill="#a9d5ec", outline="", stipple="gray75", tags="bg")

        hero_canvas.bind("<Configure>", _paint_hero_bg)

        hero_content = tk.Frame(hero_canvas, bg=c["hero_bg"])
        hero_canvas.create_window((0, 0), window=hero_content, anchor="nw", width=1120, height=230)

        tk.Label(
            hero_content,
            text="Your referee profile and daily challenge.",
            bg=c["hero_bg"],
            fg=c["surface"],
            font=f["hero"],
        ).pack(anchor="w", padx=30, pady=(40, 8))
        tk.Label(
            hero_content,
            text="Train smarter with tests by category and verify decisions with rule references.",
            bg=c["hero_bg"],
            fg=c["hero_sub"],
            font=f["body"],
        ).pack(anchor="w", padx=30)

        cta_row = tk.Frame(hero_content, bg=c["hero_bg"])
        cta_row.pack(anchor="w", padx=30, pady=16)
        ttk.Button(cta_row, text="Start Tests", command=lambda: self.show_page("tests")).pack(side="left", padx=(0, 8))
        ttk.Button(cta_row, text="Open Rulebook", command=lambda: self.show_page("rulebook")).pack(side="left", padx=(0, 8))
        ttk.Button(cta_row, text="View Games", command=lambda: self.show_page("games")).pack(side="left")

        cards = tk.Frame(page, bg=c["shell_bg"])
        cards.pack(fill="x", padx=20, pady=10)

        self.dashboard_tests_var = tk.StringVar(value="Tests attempted: 0")
        self.dashboard_accuracy_var = tk.StringVar(value="Accuracy: 0%")
        self.dashboard_games_var = tk.StringVar(value="Games this season: 0")

        for title, var in [
            ("Tests", self.dashboard_tests_var),
            ("Accuracy", self.dashboard_accuracy_var),
            ("Season Games", self.dashboard_games_var),
        ]:
            card = tk.Frame(cards, bg=c["surface"], bd=1, relief="solid", highlightbackground=c["border"], highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=6)
            tk.Label(card, text=title, bg=c["surface"], fg=c["text_secondary"], font=f["body_bold"]).pack(anchor="w", padx=14, pady=(12, 4))
            tk.Label(card, textvariable=var, bg=c["surface"], fg=c["text_primary"], font=f["h3"]).pack(anchor="w", padx=14, pady=(0, 14))

        qod_card = tk.Frame(page, bg=c["surface"], bd=1, relief="solid", highlightbackground=c["border"], highlightthickness=1)
        qod_card.pack(fill="both", expand=True, padx=20, pady=(8, 20))

        tk.Label(qod_card, text="Question of the Day", bg=c["surface"], fg=c["text_primary"], font=f["h2"]).pack(anchor="w", padx=14, pady=(12, 4))
        self.qod_status_var = tk.StringVar(value="")
        tk.Label(qod_card, textvariable=self.qod_status_var, bg=c["surface"], fg=c["text_secondary"], font=f["small"]).pack(anchor="w", padx=14)

        self.qod_question_var = tk.StringVar(value="No question available")
        tk.Label(
            qod_card,
            textvariable=self.qod_question_var,
            bg=c["surface"],
            fg=c["text_primary"],
            font=f["body_bold"],
            wraplength=980,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(8, 8))

        self.qod_options_frame = tk.Frame(qod_card, bg=c["surface"])
        self.qod_options_frame.pack(fill="x", padx=14)
        self.qod_option_vars = []
        self.qod_question = None

        qod_actions = tk.Frame(qod_card, bg=c["surface"])
        qod_actions.pack(fill="x", padx=14, pady=(10, 10))
        ttk.Button(qod_actions, text="Check Answer", command=self.submit_question_of_day).pack(side="left")
        ttk.Button(qod_actions, text="Open Tests", command=lambda: self.show_page("tests")).pack(side="left", padx=8)

        self.qod_feedback_var = tk.StringVar(value="")
        tk.Label(
            qod_card,
            textvariable=self.qod_feedback_var,
            bg=c["surface"],
            fg=c["text_secondary"],
            font=f["body"],
            wraplength=980,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 12))

        self.load_question_of_day()

    def _build_games_page(self):
        page = self.pages["games"]

        season_frame = ttk.Frame(page)
        season_frame.pack(fill='x', padx=12, pady=(12, 6))
        ttk.Label(season_frame, text="Season:").pack(side='left')
        self.season_combo = ttk.Combobox(season_frame, textvariable=self.selected_season, values=self.seasons, state='readonly')
        self.season_combo.pack(side='left', padx=5)
        self.season_combo.bind('<<ComboboxSelected>>', lambda e: self.load_games())

        if getattr(self.manager, 'conn', None) is not None:
            ttk.Button(season_frame, text="Test DB", command=self.test_db).pack(side='left', padx=5)

        self.summary_label = ttk.Label(page, text="")
        self.summary_label.pack(fill='x', padx=12, pady=4)
        self.selection_label = ttk.Label(page, text="")
        self.selection_label.pack(fill='x', padx=12, pady=(0, 4))
        self.backend_label = ttk.Label(page, text="", foreground="#555")
        self.backend_label.pack(fill='x', padx=12, pady=(0, 4))

        search_frame = ttk.Frame(page)
        search_frame.pack(fill='x', padx=12, pady=6)
        ttk.Label(search_frame, text="Search:").pack(side='left')
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<Return>', lambda e: self.search_games())
        ttk.Button(search_frame, text="Search", command=self.search_games).pack(side='left')
        ttk.Button(search_frame, text="Clear", command=self.load_games).pack(side='left')

        columns = ["date", "gameNumber", "location", "totalEarnings", "amountLeft", "paidStatus", "observations"]
        self.tree = ttk.Treeview(page, columns=columns, show='headings')
        self.col_headers = {col: col.capitalize() for col in columns}
        for col in columns:
            self.tree.heading(col, text=self.col_headers[col], command=lambda c=col: self.on_column_click(c))
        self.tree.pack(fill='both', expand=True, padx=12, pady=6)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.update_selection_sum())

        self.sort_column = None
        self.sort_reverse = False
        self.displayed_games = []

        btn_frame = ttk.Frame(page)
        btn_frame.pack(fill='x', padx=12, pady=(4, 12))
        ttk.Button(btn_frame, text="Add Game", command=self.add_game_dialog).pack(side='left')
        ttk.Button(btn_frame, text="Edit Game", command=self.edit_game_dialog).pack(side='left')
        ttk.Button(btn_frame, text="Delete Game", command=self.delete_game).pack(side='left')
        ttk.Button(btn_frame, text="Mark Paid", command=self.mark_selected_paid).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Import Games (CSV/XLSX)", command=self.import_games).pack(side='right', padx=(0, 8))
        ttk.Button(btn_frame, text="Export All Seasons (CSV/XLSX)", command=self.export_all_games).pack(side='right')

    def _build_tests_page(self):
        page = self.pages["tests"]
        c = self.colors
        f = self.fonts

        self.active_test_questions = []
        self.active_test_index = -1
        self.test_mode = ""
        self.test_mode_rule = ""

        self.tests_launcher = tk.Frame(page, bg=c["shell_bg"])
        self.tests_launcher.pack(fill="x", padx=16, pady=(14, 8))

        # Recommended card (style inspired by the provided layout)
        rec_card = tk.Frame(self.tests_launcher, bg=c["surface_alt"], bd=1, relief="solid", highlightbackground=c["border"], highlightthickness=1)
        rec_card.pack(fill="x", pady=(0, 12))
        rec_header = tk.Frame(rec_card, bg=c["accent"], height=50)
        rec_header.pack(fill="x")
        rec_header.pack_propagate(False)
        tk.Label(rec_header, text="Teste recomendado", bg=c["accent"], fg=c["surface"], font=f["h2"]).pack(expand=True)

        rec_body = tk.Frame(rec_card, bg=c["surface_alt"], height=54)
        rec_body.pack(fill="x")
        rec_body.pack_propagate(False)
        tk.Label(rec_body, text="RAND", bg=c["success"], fg=c["surface"], font=f["h3"], width=6).pack(side="left", fill="y")
        tk.Label(rec_body, text="Randomized test (30 questions)", bg=c["surface_alt"], fg=c["text_primary"], font=f["h3"]).pack(side="left", padx=16)
        tk.Button(
            rec_body,
            text=">",
            bg=c["success"],
            fg=c["surface"],
            relief="flat",
            font=f["h2"],
            width=3,
            command=lambda: self.start_test_session(mode="random", total=30),
        ).pack(side="right", fill="y")

        tk.Label(self.tests_launcher, text="Escolha o tipo de teste", bg=c["shell_bg"], fg=c["text_primary"], font=f["h2"]).pack(anchor="w", pady=(0, 6))

        self.test_mode_list_host = tk.Frame(self.tests_launcher, bg=c["shell_bg"])
        self.test_mode_list_host.pack(fill="x", pady=(0, 8))
        self._render_primary_test_modes()

        tk.Label(self.tests_launcher, text="Escolha a categoria de regra", bg=c["shell_bg"], fg=c["text_primary"], font=f["h3"]).pack(anchor="w", pady=(4, 6))

        self.category_list_host = tk.Frame(self.tests_launcher, bg=c["shell_bg"])
        self.category_list_host.pack(fill="x")
        self._render_test_categories()

        self.tests_exam = tk.Frame(page, bg=c["surface"], bd=1, relief="solid", highlightbackground=c["border"], highlightthickness=1)
        self.tests_exam.pack(fill="both", expand=True, padx=16, pady=(4, 14))
        self.tests_exam.pack_forget()

        top = ttk.Frame(self.tests_exam)
        top.pack(fill="x", padx=12, pady=(10, 6))
        ttk.Button(top, text="Skip", command=self.skip_test_question).pack(side="left")
        ttk.Button(top, text="Submit Answer", command=self.submit_test_answer).pack(side="left", padx=6)
        ttk.Button(top, text="Finish", command=lambda: self.finish_test_session(timeout=False)).pack(side="left", padx=6)
        self.test_status_var = tk.StringVar(value="Start a test from the categories above")
        ttk.Label(top, textvariable=self.test_status_var).pack(side="left", padx=12)

        self.test_progress_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.test_progress_var).pack(side="right")
        self.test_timer_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.test_timer_var).pack(side="right", padx=12)

        self.test_question_var = tk.StringVar(value="")
        ttk.Label(
            self.tests_exam,
            textvariable=self.test_question_var,
            wraplength=960,
            justify="left",
            font=f["body_bold"],
        ).pack(fill="x", padx=12, pady=8)

        self.test_options_frame = ttk.Frame(self.tests_exam)
        self.test_options_frame.pack(fill="both", expand=True, padx=12, pady=4)
        self.test_option_vars = []

        self.test_feedback_var = tk.StringVar(value="")
        ttk.Label(
            self.tests_exam,
            textvariable=self.test_feedback_var,
            wraplength=960,
            justify="left",
            foreground=c["text_primary"],
        ).pack(fill="x", padx=12, pady=(4, 12))

        if not self.quiz_questions:
            self.test_status_var.set("No handball dataset loaded. Build data/handball_content.json first.")

    def _render_primary_test_modes(self):
        c = self.colors
        f = self.fonts
        for w in self.test_mode_list_host.winfo_children():
            w.destroy()

        modes = [
            ("RAND", "Randomized test (30 questions)", lambda: self.start_test_session(mode="random", total=30)),
            ("NEW", "Unanswered questions", lambda: self.start_test_session(mode="unanswered", total=30)),
            ("WRONG", "Questions answered wrong", lambda: self.start_test_session(mode="wrong", total=30)),
        ]

        for code, label, action in modes:
            row = tk.Frame(self.test_mode_list_host, bg=c["surface_alt"], bd=1, relief="flat", highlightbackground=c["border"], highlightthickness=1)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=code, bg=c["success"], fg=c["surface"], font=f["body_bold"], width=8).pack(side="left", fill="y")
            tk.Label(row, text=label, bg=c["surface_alt"], fg=c["text_primary"], font=f["body"]).pack(side="left", padx=14)
            tk.Button(
                row,
                text=">",
                bg=c["success"],
                fg=c["surface"],
                relief="flat",
                font=f["h3"],
                width=3,
                command=action,
            ).pack(side="right", fill="y")

    def _render_test_categories(self):
        c = self.colors
        f = self.fonts
        for w in self.category_list_host.winfo_children():
            w.destroy()

        categories = self._get_rule_categories()
        shown = categories[:8]
        if not shown:
            shown = ["General"]

        for rule_id in shown:
            row = tk.Frame(self.category_list_host, bg=c["surface_alt"], bd=1, relief="flat", highlightbackground=c["border"], highlightthickness=1)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=rule_id, bg=c["success"], fg=c["surface"], font=f["h2"], width=6).pack(side="left", fill="y")
            tk.Label(
                row,
                text=f"Questions focused on rule {rule_id}",
                bg=c["surface_alt"],
                fg=c["text_primary"],
                font=f["body"],
            ).pack(side="left", padx=14)
            tk.Button(
                row,
                text=">",
                bg=c["success"],
                fg=c["surface"],
                relief="flat",
                font=f["h3"],
                width=3,
                command=lambda r=rule_id: self.start_test_session(mode="rule", rule=r, total=30),
            ).pack(side="right", fill="y")

    def _get_rule_categories(self):
        if not self.quiz_questions:
            return []
        categories = set()
        for q in self.quiz_questions:
            for ref in q.get("rule_references", []):
                ref_text = str(ref)
                if ":" in ref_text and ref_text[0].isdigit():
                    categories.add(ref_text.split(":", 1)[0])
        def sort_key(v):
            try:
                return (0, int(v))
            except Exception:
                return (1, v)
        return sorted(categories, key=sort_key)

    def _ordered_options(self, question: dict):
        options = list(question.get('options', []))
        # Always present options in deterministic A..Z order so only
        # question order is randomized.
        return sorted(options, key=lambda o: str(o.get('key', '')).upper())

    def start_test_session(self, mode="random", rule="", total=30):
        if not self.quiz_questions:
            self.test_status_var.set("Dataset not loaded. Build data/handball_content.json first.")
            return

        pool = list(self.quiz_questions)
        self.test_mode_rule = ""
        if mode == "rule" and rule:
            filtered = []
            for q in pool:
                refs = [str(r) for r in q.get("rule_references", [])]
                if any(r.startswith(f"{rule}:") for r in refs):
                    filtered.append(q)
            pool = filtered
            self.test_mode_rule = str(rule)
        elif mode == "unanswered":
            pool = self._available_unanswered_pool()
        elif mode == "wrong":
            pool = self._available_wrong_pool()

        if not pool:
            self.test_status_var.set("No questions available for this test mode.")
            return

        random.shuffle(pool)
        self.active_test_questions = pool[:max(1, min(total, len(pool)))]
        self.active_test_index = -1
        self.current_test_question = None
        self.current_test_answered = False
        self.test_mode = mode
        self.current_test_session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.session_results = {}
        self.test_feedback_var.set("")

        self.tests_launcher.pack_forget()
        self.tests_exam.pack(fill="both", expand=True, padx=16, pady=(4, 14))

        self._stop_test_timer()
        self.test_end_epoch = time.time() + self.test_total_seconds
        self._tick_test_timer()

        if mode == "rule":
            self.test_status_var.set(f"Rule {rule} test started with {len(self.active_test_questions)} questions")
        elif mode == "unanswered":
            self.test_status_var.set(f"Unanswered test started with {len(self.active_test_questions)} questions")
        elif mode == "wrong":
            self.test_status_var.set(f"Wrong-answers test started with {len(self.active_test_questions)} questions")
        else:
            self.test_status_var.set(f"Randomized test started with {len(self.active_test_questions)} questions")

        self.next_test_question()

    def next_test_question(self):
        if not self.active_test_questions:
            self.test_status_var.set("Start a test from the categories above")
            return

        # If user moved on without answering, mark previous as unanswered.
        if self.current_test_question is not None and not self.current_test_answered:
            qid = str(self.current_test_question.get('id', ''))
            self.session_results[qid] = 'unanswered'

        self.active_test_index += 1
        if self.active_test_index >= len(self.active_test_questions):
            self.finish_test_session(timeout=False)
            return

        self.current_test_question = self.active_test_questions[self.active_test_index]
        self.current_test_answered = False
        q = self.current_test_question
        self.test_question_var.set(f"{q.get('id', '')}: {q.get('question', '')}")
        self.test_feedback_var.set("")
        self.test_progress_var.set(f"{self.active_test_index + 1}/{len(self.active_test_questions)}")

        for w in self.test_options_frame.winfo_children():
            w.destroy()
        self.test_option_vars = []

        options = self._ordered_options(q)
        for opt in options:
            key = str(opt.get('key', '')).upper()
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(
                self.test_options_frame,
                text=f"{key}) {opt.get('text', '')}",
                variable=var,
            )
            cb.pack(anchor="w", pady=2)
            self.test_option_vars.append((key, var))

        self.test_status_var.set("Select one or more options, then click Submit Answer")

    def skip_test_question(self):
        if not self.current_test_question:
            return
        qid = str(self.current_test_question.get('id', ''))
        self.session_results[qid] = 'unanswered'
        self.current_test_answered = True
        self.next_test_question()

    def finish_test_session(self, timeout=False):
        if not self.active_test_questions:
            return

        # If current question is still open, count it as unanswered.
        if self.current_test_question is not None and not self.current_test_answered:
            qid = str(self.current_test_question.get('id', ''))
            self.session_results[qid] = 'unanswered'

        self._stop_test_timer()

        question_ids = [str(q.get('id', '')) for q in self.active_test_questions]
        for qid in question_ids:
            result = self.session_results.get(qid, 'unanswered')
            self._record_question_result(qid, result)

        answered = sum(1 for qid in question_ids if self.session_results.get(qid) in ('correct', 'wrong'))
        correct = sum(1 for qid in question_ids if self.session_results.get(qid) == 'correct')
        wrong = sum(1 for qid in question_ids if self.session_results.get(qid) == 'wrong')
        unanswered = sum(1 for qid in question_ids if self.session_results.get(qid, 'unanswered') == 'unanswered')
        passed = wrong <= self.max_wrong_to_pass
        verdict = 'PASSED' if passed else 'FAILED'

        session_entry = {
            'session_id': self.current_test_session_id,
            'timestamp': datetime.now().isoformat(),
            'mode': self.test_mode,
            'rule': self.test_mode_rule,
            'total': len(question_ids),
            'answered': answered,
            'correct': correct,
            'wrong': wrong,
            'unanswered': unanswered,
            'time_seconds': self.test_total_seconds,
            'elapsed_seconds': int(max(0, self.test_total_seconds - int(max(0, self.test_end_epoch - time.time())))) if self.test_end_epoch else 0,
            'max_wrong_to_pass': self.max_wrong_to_pass,
            'passed': passed,
            'question_ids': question_ids,
        }
        self.test_progress.setdefault('sessions', []).append(session_entry)
        self.test_progress.setdefault('stats', {})['attempts'] = int(self.test_attempts)
        self.test_progress.setdefault('stats', {})['correct'] = int(self.test_correct)
        self._save_test_progress()

        self.active_test_questions = []
        self.active_test_index = -1
        self.current_test_question = None
        self.current_test_answered = False
        self.current_test_session_id = None
        self.session_results = {}
        self.test_end_epoch = None
        self.test_timer_var.set("")

        for w in self.test_options_frame.winfo_children():
            w.destroy()
        self.test_option_vars = []

        self.test_progress_var.set("")
        if timeout:
            self.test_question_var.set("Time is up. Session ended.")
            self.test_status_var.set(
                f"Session {verdict}: {correct}/{len(question_ids)} correct | "
                f"{wrong} wrong | {unanswered} unanswered"
            )
        else:
            self.test_question_var.set("Test completed.")
            self.test_status_var.set(
                f"Session {verdict}: {correct}/{len(question_ids)} correct | "
                f"{wrong} wrong | {unanswered} unanswered"
            )

        self.test_feedback_var.set(
            f"Result: {verdict}\n"
            f"Rule to pass: wrong answers <= {self.max_wrong_to_pass}\n"
            f"Final: {wrong} wrong, {correct} correct, {unanswered} unanswered"
        )

        self.tests_exam.pack_forget()
        self.tests_launcher.pack(fill="x", padx=16, pady=(14, 8))
        self.refresh_statistics_page()

    def _build_rulebook_page(self):
        page = self.pages["rulebook"]
        c = self.colors
        f = self.fonts

        page.configure(bg=c["shell_bg"])

        row = ttk.Frame(page)
        row.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Label(row, text="Rulebook sections (PDF navigation):").pack(side="left")
        ttk.Button(row, text="Refresh Sections", command=self.search_rulebook_ui).pack(side="right")

        split = ttk.Frame(page)
        split.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        left_panel = tk.Frame(split, bg=c["shell_bg"])
        left_panel.pack(side="left", fill="y")

        self.rulebook_results_list = tk.Listbox(
            left_panel,
            width=34,
            bg=c["surface"],
            fg=c["text_primary"],
            selectbackground=c["accent_soft"],
            selectforeground=c["text_primary"],
            bd=1,
            highlightthickness=1,
            highlightbackground=c["border"],
            activestyle="none",
        )
        self.rulebook_results_list.pack(side="left", fill="y")
        rule_list_scroll = ttk.Scrollbar(left_panel, orient="vertical", command=self.rulebook_results_list.yview)
        rule_list_scroll.pack(side="left", fill="y")
        self.rulebook_results_list.configure(yscrollcommand=rule_list_scroll.set)
        self.rulebook_results_list.bind("<<ListboxSelect>>", lambda e: self.show_selected_rule_section())
        self.rulebook_results_list.bind("<MouseWheel>", self._on_rulebook_list_mousewheel)

        right = ttk.Frame(split)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        header = tk.Frame(right, bg=c["surface_alt"])
        header.pack(fill="x")

        self.rulebook_pdf_status_var = tk.StringVar(value="")
        tk.Label(
            header,
            textvariable=self.rulebook_pdf_status_var,
            bg=c["surface_alt"],
            fg=c["text_primary"],
            font=f["body_bold"],
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=6)

        controls = tk.Frame(header, bg=c["surface_alt"])
        controls.pack(side="right", padx=8, pady=4)
        ttk.Button(controls, text="Prev", command=self.prev_rulebook_page).pack(side="left", padx=2)
        ttk.Button(controls, text="Next", command=self.next_rulebook_page).pack(side="left", padx=2)
        self.rulebook_pdf_continuous_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            controls,
            text="Continuous",
            variable=self.rulebook_pdf_continuous_var,
            command=self._render_rulebook_pdf_page,
        ).pack(side="left", padx=(6, 2))
        ttk.Button(controls, text="-", width=3, command=lambda: self.change_rulebook_zoom(-0.1)).pack(side="left", padx=2)
        ttk.Button(controls, text="+", width=3, command=lambda: self.change_rulebook_zoom(0.1)).pack(side="left", padx=2)

        viewer_box = ttk.LabelFrame(right, text="Official PDF View")
        viewer_box.pack(fill="both", expand=True, pady=(8, 0))

        self.rulebook_pdf_canvas = tk.Canvas(viewer_box, bg=c["rulebook_bg"], highlightthickness=0)
        self.rulebook_pdf_canvas.pack(side="left", fill="both", expand=True)
        y_scroll = ttk.Scrollbar(viewer_box, orient="vertical", command=self.rulebook_pdf_canvas.yview)
        y_scroll.pack(side="right", fill="y")
        x_scroll = ttk.Scrollbar(right, orient="horizontal", command=self.rulebook_pdf_canvas.xview)
        x_scroll.pack(fill="x", pady=(2, 0))
        self.rulebook_pdf_canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.rulebook_pdf_canvas.bind("<MouseWheel>", self._on_rulebook_canvas_mousewheel)
        self.rulebook_pdf_canvas.bind("<Shift-MouseWheel>", self._on_rulebook_canvas_shift_mousewheel)

        self.rulebook_pdf_doc = None
        self.rulebook_pdf_path = None
        self.rulebook_pdf_page_index = 0
        self.rulebook_pdf_zoom = 1.25
        self.rulebook_pdf_photo = None
        self.rulebook_pdf_photos = []
        self.rulebook_current_section = None

        self.rulebook_results = []
        if self.handball_dataset and self.handball_dataset.get("rulebook"):
            self._load_rulebook_pdf_document()
            self.search_rulebook_ui()
        else:
            self.rulebook_pdf_status_var.set("Rulebook dataset not loaded.")

    def _build_statistics_page(self):
        page = self.pages["statistics"]
        c = self.colors
        f = self.fonts

        wrap = tk.Frame(page, bg=c["shell_bg"])
        wrap.pack(fill="both", expand=True, padx=20, pady=20)

        top_cards = tk.Frame(wrap, bg=c["shell_bg"])
        top_cards.pack(fill="x")

        self.stats_games_var = tk.StringVar(value="Games this season: 0")
        self.stats_paid_var = tk.StringVar(value="Total paid: 0.00 EUR")
        self.stats_left_var = tk.StringVar(value="Amount left: 0.00 EUR")
        self.stats_tests_var = tk.StringVar(value="Test score: 0/0")
        self.stats_accuracy_var = tk.StringVar(value="Accuracy: 0%")

        for var in [
            self.stats_games_var,
            self.stats_paid_var,
            self.stats_left_var,
            self.stats_tests_var,
            self.stats_accuracy_var,
        ]:
            card = tk.Frame(top_cards, bg=c["surface"], bd=1, relief="solid", highlightbackground=c["border"], highlightthickness=1)
            card.pack(fill="x", pady=6)
            tk.Label(card, textvariable=var, bg=c["surface"], fg=c["text_primary"], font=f["h3"]).pack(anchor="w", padx=12, pady=12)

        history_card = tk.Frame(wrap, bg=c["surface"], bd=1, relief="solid", highlightbackground=c["border"], highlightthickness=1)
        history_card.pack(fill="both", expand=True, pady=(10, 0))
        head_row = tk.Frame(history_card, bg=c["surface"])
        head_row.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(
            history_card,
            text="Recent Test Sessions (local)",
            bg=c["surface"],
            fg=c["text_primary"],
            font=f["h3"],
        ).pack(in_=head_row, side="left", anchor="w")
        ttk.Button(head_row, text="Reset Progress", command=self.reset_test_progress).pack(side="right")

        self.stats_history_text = tk.Text(history_card, wrap="word", height=12)
        self.stats_history_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def show_page(self, key: str):
        c = self.colors
        titles = {
            "dashboard": ("Profile Dashboard", "Your profile, progress and question of the day"),
            "games": ("List of Games", "Manage season matches, payments and notes"),
            "tests": ("Tests", "Run recommended tests or rule-specific tests"),
            "rulebook": ("Rulebook", "Search official rules and clarifications"),
            "statistics": ("Statistics", "Performance and earnings summary"),
        }
        for page in self.pages.values():
            page.grid_remove()
        self.pages[key].grid()

        for name, btn in self.nav_buttons.items():
            if name == key:
                btn.configure(bg=c["sidebar_active"], fg=c["surface"])
            else:
                btn.configure(bg=c["sidebar_bg"], fg=c["sidebar_text"])

        title, subtitle = titles.get(key, ("Ref Tracker", ""))
        self.page_title_var.set(title)
        self.page_subtitle_var.set(subtitle)

        self.refresh_statistics_page()

    def _load_handball_content(self):
        candidates = [
            os.path.join(self.manager.data_dir, "handball_content.json"),
            os.path.join(os.path.dirname(__file__), "..", "data", "handball_content.json"),
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "handball_content.json"),
        ]
        for path in candidates:
            try:
                norm = os.path.abspath(path)
                if os.path.exists(norm):
                    self.handball_dataset = load_handball_dataset(norm)
                    self.quiz_questions = self.handball_dataset.get("questions", [])
                    self.rulebook_dataset_path = norm
                    return
            except Exception:
                continue
        self.handball_dataset = None
        self.quiz_questions = []
        self.rulebook_dataset_path = None

    def _resolve_rulebook_image_path(self, image_ref: str):
        if not image_ref:
            return None
        p = Path(image_ref)
        if p.is_absolute() and p.exists():
            return str(p)
        if self.rulebook_dataset_path:
            base = Path(self.rulebook_dataset_path).parent
            candidate = (base / image_ref).resolve()
            if candidate.exists():
                return str(candidate)
        fallback = Path(self.manager.data_dir) / image_ref
        if fallback.exists():
            return str(fallback.resolve())
        return None

    def _resolve_rulebook_pdf_path(self):
        candidates = []

        # Prefer filename from dataset metadata when available.
        if self.handball_dataset:
            src = self.handball_dataset.get('metadata', {}).get('sources', {}).get('rulebook_pdf')
            if src:
                candidates.extend([
                    Path(self.manager.data_dir) / str(src),
                    Path(__file__).resolve().parent.parent / str(src),
                    Path(__file__).resolve().parent.parent.parent / str(src),
                ])

        # Known default name used in this project.
        default_name = "09A - Rules of the Game_Indoor Handball_E.pdf"
        candidates.extend([
            Path(self.manager.data_dir) / default_name,
            Path(__file__).resolve().parent.parent / default_name,
            Path(__file__).resolve().parent.parent.parent / default_name,
        ])

        for c in candidates:
            try:
                p = c.resolve()
            except Exception:
                p = c
            if p.exists():
                return str(p)
        return None

    def _load_rulebook_pdf_document(self):
        if not hasattr(self, 'rulebook_pdf_status_var'):
            return

        if fitz is None:
            self.rulebook_pdf_status_var.set("PDF viewer unavailable. Install PyMuPDF to view original pages.")
            return
        if Image is None or ImageTk is None:
            self.rulebook_pdf_status_var.set("PDF viewer requires Pillow. Install Pillow to display pages.")
            return

        pdf_path = self._resolve_rulebook_pdf_path()
        if not pdf_path:
            self.rulebook_pdf_status_var.set("Rulebook PDF file not found in project.")
            return

        try:
            if self.rulebook_pdf_doc is not None:
                self.rulebook_pdf_doc.close()
        except Exception:
            pass

        try:
            self.rulebook_pdf_doc = fitz.open(pdf_path)
            self.rulebook_pdf_path = pdf_path
            self.rulebook_pdf_page_index = 0
            self.rulebook_pdf_status_var.set(f"Loaded PDF: {Path(pdf_path).name}")
            self._render_rulebook_pdf_page()
        except Exception as exc:
            self.rulebook_pdf_doc = None
            self.rulebook_pdf_path = None
            self.rulebook_pdf_status_var.set(f"Failed to open PDF: {exc}")

    def _render_rulebook_pdf_page(self):
        if not hasattr(self, 'rulebook_pdf_canvas'):
            return

        self.rulebook_pdf_canvas.delete("all")
        self.rulebook_pdf_photo = None
        self.rulebook_pdf_photos = []

        if self.rulebook_pdf_doc is None:
            self.rulebook_pdf_status_var.set("PDF not loaded.")
            return

        page_count = len(self.rulebook_pdf_doc)
        if page_count == 0:
            self.rulebook_pdf_status_var.set("PDF has no pages.")
            return

        self.rulebook_pdf_page_index = max(0, min(self.rulebook_pdf_page_index, page_count - 1))
        try:
            continuous = bool(getattr(self, 'rulebook_pdf_continuous_var', None) and self.rulebook_pdf_continuous_var.get())
            canvas_w = max(1, int(self.rulebook_pdf_canvas.winfo_width()))

            # Continuous mode renders all pages of the selected section.
            if continuous and self.rulebook_current_section:
                start_page = int(self.rulebook_current_section.get('start_page', self.rulebook_pdf_page_index + 1) or 1)
                end_page = int(self.rulebook_current_section.get('end_page', start_page) or start_page)
                start_idx = max(0, min(page_count - 1, start_page - 1))
                end_idx = max(start_idx, min(page_count - 1, end_page - 1))

                y = 0
                max_w = 0
                matrix = fitz.Matrix(self.rulebook_pdf_zoom, self.rulebook_pdf_zoom)
                for idx in range(start_idx, end_idx + 1):
                    page = self.rulebook_pdf_doc.load_page(idx)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    photo = ImageTk.PhotoImage(img)
                    self.rulebook_pdf_photos.append(photo)

                    x = max(0, (canvas_w - img.width) // 2)
                    self.rulebook_pdf_canvas.create_image(x, y, anchor="nw", image=photo)
                    self.rulebook_pdf_canvas.create_text(
                        x + 10,
                        y + 12,
                        text=f"Page {idx + 1}",
                        anchor="nw",
                        fill="#0b2942",
                        font=self.fonts["small"],
                    )
                    y += img.height + 16
                    max_w = max(max_w, img.width)

                self.rulebook_pdf_canvas.configure(scrollregion=(0, 0, max(canvas_w, max_w), y))
            else:
                page = self.rulebook_pdf_doc.load_page(self.rulebook_pdf_page_index)
                matrix = fitz.Matrix(self.rulebook_pdf_zoom, self.rulebook_pdf_zoom)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                self.rulebook_pdf_photo = ImageTk.PhotoImage(img)
                self.rulebook_pdf_photos.append(self.rulebook_pdf_photo)

                x = max(0, (canvas_w - img.width) // 2)
                self.rulebook_pdf_canvas.create_image(x, 0, anchor="nw", image=self.rulebook_pdf_photo)
                self.rulebook_pdf_canvas.configure(scrollregion=(0, 0, max(canvas_w, img.width), img.height))

            section_text = ""
            if self.rulebook_current_section:
                sid = self.rulebook_current_section.get('section_id', '')
                title = self.rulebook_current_section.get('title', '')
                section_text = f" | Section {sid}: {title}"
            mode_text = "Continuous" if continuous and self.rulebook_current_section else "Single"
            self.rulebook_pdf_status_var.set(
                f"Page {self.rulebook_pdf_page_index + 1}/{page_count} | {mode_text} | Zoom {self.rulebook_pdf_zoom:.2f}x{section_text}"
            )
        except Exception as exc:
            self.rulebook_pdf_status_var.set(f"Failed rendering PDF page: {exc}")

    def _on_rulebook_canvas_mousewheel(self, event):
        if hasattr(self, 'rulebook_pdf_canvas'):
            step = -1 * int(event.delta / 120) if event.delta else 0
            if step:
                self.rulebook_pdf_canvas.yview_scroll(step, "units")
        return "break"

    def _on_rulebook_canvas_shift_mousewheel(self, event):
        if hasattr(self, 'rulebook_pdf_canvas'):
            step = -1 * int(event.delta / 120) if event.delta else 0
            if step:
                self.rulebook_pdf_canvas.xview_scroll(step, "units")
        return "break"

    def _on_rulebook_list_mousewheel(self, event):
        if hasattr(self, 'rulebook_results_list'):
            step = -1 * int(event.delta / 120) if event.delta else 0
            if step:
                self.rulebook_results_list.yview_scroll(step, "units")
        return "break"

    def prev_rulebook_page(self):
        if self.rulebook_pdf_doc is None:
            return
        self.rulebook_pdf_page_index = max(0, self.rulebook_pdf_page_index - 1)
        self._render_rulebook_pdf_page()

    def next_rulebook_page(self):
        if self.rulebook_pdf_doc is None:
            return
        self.rulebook_pdf_page_index = min(len(self.rulebook_pdf_doc) - 1, self.rulebook_pdf_page_index + 1)
        self._render_rulebook_pdf_page()

    def change_rulebook_zoom(self, delta):
        if self.rulebook_pdf_doc is None:
            return
        self.rulebook_pdf_zoom = max(0.6, min(3.0, self.rulebook_pdf_zoom + delta))
        self._render_rulebook_pdf_page()

    def submit_test_answer(self):
        if not self.current_test_question:
            self.test_status_var.set("Open a question first")
            return

        selected = sorted([k for k, v in self.test_option_vars if v.get()])
        correct = sorted([str(k).upper() for k in self.current_test_question.get('correct_options', [])])

        self.test_attempts += 1
        is_correct = set(selected) == set(correct)
        qid = str(self.current_test_question.get('id', ''))
        if is_correct:
            self.test_correct += 1
            self.session_results[qid] = 'correct'
        else:
            self.session_results[qid] = 'wrong'
        self.current_test_answered = True

        reasoning = self.current_test_question.get('reasoning', '')
        refs = ", ".join(self.current_test_question.get('rule_references', []))
        verdict = "Correct" if is_correct else "Not correct"
        self.test_feedback_var.set(
            f"{verdict}. Your answer: {', '.join(selected) or '-'} | "
            f"Expected: {', '.join(correct) or '-'}\n"
            f"Rule references: {refs or '-'}\n"
            f"Reasoning: {reasoning or '-'}"
        )
        if self.active_test_questions:
            mode_name = {
                'random': 'Randomized',
                'unanswered': 'Unanswered',
                'wrong': 'Wrong-only',
                'rule': f"Rule {self.test_mode_rule}" if self.test_mode_rule else 'Rule',
            }.get(self.test_mode, 'Test')
            self.test_status_var.set(
                f"{mode_name} | Score: {self.test_correct}/{self.test_attempts} | "
                f"Question {min(self.active_test_index + 1, len(self.active_test_questions))}/"
                f"{len(self.active_test_questions)}"
            )
        else:
            self.test_status_var.set(f"Score: {self.test_correct}/{self.test_attempts}")
        self.test_progress.setdefault('stats', {})['attempts'] = int(self.test_attempts)
        self.test_progress.setdefault('stats', {})['correct'] = int(self.test_correct)
        self._save_test_progress()
        self.refresh_statistics_page()

    def load_question_of_day(self):
        if not hasattr(self, 'qod_question_var'):
            return
        for w in self.qod_options_frame.winfo_children():
            w.destroy()
        self.qod_option_vars = []
        self.qod_feedback_var.set("")

        if not self.quiz_questions:
            self.qod_question = None
            self.qod_status_var.set("Dataset not loaded")
            self.qod_question_var.set("No question of the day available")
            return

        day_index = date.today().toordinal() % len(self.quiz_questions)
        self.qod_question = self.quiz_questions[day_index]
        q = self.qod_question
        self.qod_status_var.set(f"Question id: {q.get('id', '-')}")
        self.qod_question_var.set(q.get('question', ''))

        options = self._ordered_options(q)
        for opt in options:
            key = str(opt.get('key', '')).upper()
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(
                self.qod_options_frame,
                text=f"{key}) {opt.get('text', '')}",
                variable=var,
            )
            cb.pack(anchor="w", pady=2)
            self.qod_option_vars.append((key, var))

    def submit_question_of_day(self):
        if not self.qod_question:
            self.qod_feedback_var.set("Question of the day is not available.")
            return

        selected = sorted([k for k, v in self.qod_option_vars if v.get()])
        correct = sorted([str(k).upper() for k in self.qod_question.get('correct_options', [])])
        is_correct = set(selected) == set(correct)

        self.test_attempts += 1
        if is_correct:
            self.test_correct += 1

        refs = ", ".join(self.qod_question.get('rule_references', []))
        verdict = "Correct" if is_correct else "Not correct"
        self.qod_feedback_var.set(
            f"{verdict}. Your answer: {', '.join(selected) or '-'} | "
            f"Expected: {', '.join(correct) or '-'}\n"
            f"Rule references: {refs or '-'}"
        )
        self.refresh_statistics_page()

    def search_rulebook_ui(self):
        self.rulebook_results_list.delete(0, tk.END)
        self.rulebook_results = []

        if not self.handball_dataset:
            if hasattr(self, 'rulebook_pdf_status_var'):
                self.rulebook_pdf_status_var.set("Rulebook dataset not loaded.")
            return

        # Intentionally avoid text-search mode; navigate sections directly
        # and display the official PDF pages.
        self.rulebook_results = list(self.handball_dataset.get("rulebook", []))
        if not self.rulebook_results:
            if hasattr(self, 'rulebook_pdf_status_var'):
                self.rulebook_pdf_status_var.set("No rulebook sections available.")
            return

        for idx, section in enumerate(self.rulebook_results):
            sid = section.get("section_id", "")
            title = section.get("title", "")
            self.rulebook_results_list.insert(idx, f"{sid} - {title}")
        self.rulebook_results_list.selection_set(0)
        self.show_selected_rule_section()

    def show_selected_rule_section(self):
        if not self.rulebook_results:
            return
        sel = self.rulebook_results_list.curselection()
        if not sel:
            return
        section = self.rulebook_results[sel[0]]
        self.rulebook_current_section = section

        if self.rulebook_pdf_doc is None:
            self._load_rulebook_pdf_document()
        if self.rulebook_pdf_doc is None:
            return

        # Dataset pages are 1-based; fitz is 0-based.
        start_page = section.get('start_page')
        try:
            if isinstance(start_page, int) and start_page > 0:
                self.rulebook_pdf_page_index = start_page - 1
        except Exception:
            pass

        self._render_rulebook_pdf_page()

    def refresh_statistics_page(self):
        if not hasattr(self, 'stats_games_var'):
            return
        summary = self.manager.get_summary(self.selected_season.get())
        self.stats_games_var.set(f"Games this season: {summary.get('games_count', 0)}")
        self.stats_paid_var.set(f"Total paid: {summary.get('total_earnings', 0.0):.2f} EUR")
        self.stats_left_var.set(f"Amount left: {summary.get('amount_left', 0.0):.2f} EUR")
        self.stats_tests_var.set(f"Test score: {self.test_correct}/{self.test_attempts}")
        acc = (self.test_correct / self.test_attempts * 100.0) if self.test_attempts else 0.0
        self.stats_accuracy_var.set(f"Accuracy: {acc:.1f}%")

        if hasattr(self, 'dashboard_tests_var'):
            self.dashboard_tests_var.set(f"Tests attempted: {self.test_attempts}")
            self.dashboard_accuracy_var.set(f"Accuracy: {acc:.1f}%")
            self.dashboard_games_var.set(f"Games this season: {summary.get('games_count', 0)}")

        if hasattr(self, 'stats_history_text'):
            sessions = self.test_progress.get('sessions', [])
            self.stats_history_text.delete("1.0", tk.END)
            if not sessions:
                self.stats_history_text.insert("1.0", "No sessions saved yet.")
            else:
                recent = sessions[-12:]
                lines = []
                for s in reversed(recent):
                    mode = s.get('mode', 'random')
                    if mode == 'rule' and s.get('rule'):
                        mode = f"rule {s.get('rule')}"
                    verdict = "PASSED" if s.get('passed') else "FAILED"
                    stamp = str(s.get('timestamp', ''))[:19].replace('T', ' ')
                    elapsed = int(s.get('elapsed_seconds', 0) or 0)
                    mm = elapsed // 60
                    ss = elapsed % 60
                    lines.append(
                        f"[{stamp}] {verdict} | mode={mode} | "
                        f"score={s.get('correct', 0)}/{s.get('total', 0)} | "
                        f"wrong={s.get('wrong', 0)} | unanswered={s.get('unanswered', 0)} | "
                        f"time={mm:02d}:{ss:02d}"
                    )
                self.stats_history_text.insert("1.0", "\n".join(lines))

    def reset_test_progress(self):
        ok = messagebox.askyesno(
            "Reset Test Progress",
            "This will erase all local test history, wrong/unanswered tracking, and scores.\n\nContinue?"
        )
        if not ok:
            return

        self._stop_test_timer()
        self.test_end_epoch = None
        self.current_test_question = None
        self.current_test_answered = False
        self.current_test_session_id = None
        self.session_results = {}
        self.active_test_questions = []
        self.active_test_index = -1

        self.test_attempts = 0
        self.test_correct = 0
        self.test_progress = {'stats': {'attempts': 0, 'correct': 0}, 'questions': {}, 'sessions': []}
        self._save_test_progress()

        if hasattr(self, 'test_question_var'):
            self.test_question_var.set("Progress reset. Start a new test.")
        if hasattr(self, 'test_feedback_var'):
            self.test_feedback_var.set("")
        if hasattr(self, 'test_status_var'):
            self.test_status_var.set("Progress reset. Choose a test mode.")
        if hasattr(self, 'test_progress_var'):
            self.test_progress_var.set("")
        if hasattr(self, 'test_timer_var'):
            self.test_timer_var.set("")
        if hasattr(self, 'test_options_frame'):
            for w in self.test_options_frame.winfo_children():
                w.destroy()
            self.test_option_vars = []

        if hasattr(self, 'tests_exam') and hasattr(self, 'tests_launcher'):
            self.tests_exam.pack_forget()
            self.tests_launcher.pack(fill="x", padx=16, pady=(14, 8))

        self.refresh_statistics_page()
        messagebox.showinfo("Reset Complete", "Local test progress has been reset.")

    def open_date_picker(self, entry_widget, initial_date_str=None):
        """Open a simple date picker popup; sets selected date into the provided entry widget in YYYY-MM-DD."""
        try:
            if initial_date_str:
                cur = datetime.strptime(initial_date_str, '%Y-%m-%d').date()
            else:
                cur = date.today()
        except Exception:
            cur = date.today()
        # make picker a child of the dialog containing the entry so it receives events
        parent = entry_widget.winfo_toplevel()
        picker = tk.Toplevel(parent)
        picker.transient(parent)
        picker.title('Select date')
        # ensure picker can receive input even if parent dialog has a grab
        try:
            picker.grab_set()
        except Exception:
            pass
        # position near parent entry
        try:
            x = entry_widget.winfo_rootx()
            y = entry_widget.winfo_rooty() + entry_widget.winfo_height()
            picker.geometry(f'+{x}+{y}')
        except Exception:
            pass
        sel_year = cur.year
        sel_month = cur.month

        header = ttk.Frame(picker)
        header.pack(padx=8, pady=6)
        month_label = ttk.Label(header, text='')
        month_label.pack()

        days_frame = ttk.Frame(picker)
        days_frame.pack(padx=8, pady=4)

        def draw_calendar(year, month):
            for w in days_frame.winfo_children():
                w.destroy()
            month_label.config(text=f'{calendar.month_name[month]} {year}')
            wkdays = ['Mo','Tu','We','Th','Fr','Sa','Su']
            for i, d in enumerate(wkdays):
                ttk.Label(days_frame, text=d).grid(row=0, column=i)
            cal = calendar.monthcalendar(year, month)
            for r, week in enumerate(cal, start=1):
                for c, day in enumerate(week):
                    if day == 0:
                        ttk.Label(days_frame, text='').grid(row=r, column=c)
                    else:
                        btn = ttk.Button(days_frame, text=str(day), width=3,
                                         command=lambda d=day, y=year, m=month: select_date(y, m, d))
                        btn.grid(row=r, column=c, padx=1, pady=1)

        def select_date(y, m, d):
            # set into DateEntry if available, else into plain Entry
            if hasattr(entry_widget, 'set_date'):
                try:
                    entry_widget.set_date(date(y, m, d))
                except Exception:
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, f"{y}-{m:02d}-{d:02d}")
            else:
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, f"{y}-{m:02d}-{d:02d}")
            picker.destroy()

        def prev_month():
            nonlocal sel_year, sel_month
            sel_month -= 1
            if sel_month < 1:
                sel_month = 12
                sel_year -= 1
            draw_calendar(sel_year, sel_month)

        def next_month():
            nonlocal sel_year, sel_month
            sel_month += 1
            if sel_month > 12:
                sel_month = 1
                sel_year += 1
            draw_calendar(sel_year, sel_month)

        nav = ttk.Frame(picker)
        nav.pack(padx=8, pady=4)
        ttk.Button(nav, text='<', width=3, command=prev_month).pack(side='left')
        ttk.Button(nav, text='Today', command=lambda: select_date(date.today().year, date.today().month, date.today().day)).pack(side='left', padx=6)
        ttk.Button(nav, text='>', width=3, command=next_month).pack(side='left')

        draw_calendar(sel_year, sel_month)
        picker.focus_set()
        picker.wait_window()

    def load_games(self):
        season = self.selected_season.get()
        self.games = self.manager.load_games(season)
        # if manager reported a database error during load, notify user
        if getattr(self.manager, 'db_error', None):
            messagebox.showwarning(
                "Database Unavailable",
                f"Could not read from database; using JSON data instead.\n"
                f"({self.manager.db_error})"
            )
        # update backend status label
        if getattr(self.manager, 'conn', None):
            self.backend_label.config(text="Backend: database connection")
        else:
            self.backend_label.config(text="Backend: local JSON files")
        # default sort by date (most recent first)
        self.displayed_games = sorted(self.games, key=lambda g: g.get('date',''), reverse=True)
        self.sort_column = 'date'
        self.sort_reverse = True
        self._set_header_arrow('date', self.sort_reverse)
        self.refresh_table(self.displayed_games)
        self.update_summary()
    def refresh_table(self, games):
        # remember currently-displayed list (used for sorting)
        self.displayed_games = list(games)
        for row in self.tree.get_children():
            self.tree.delete(row)
        for g in games:
            try:
                total = float(g.get('transportation', 0)) + float(g.get('food', 0)) + float(g.get('gamePayment', 0))
            except Exception:
                total = 0.0
            # amount_paid = total if paidStatus == 'Yes' else 0.0
            amount_paid = total if str(g.get('paidStatus','')).lower() == 'yes' else 0.0
            left = 0.0 if str(g.get('paidStatus','')).lower() == 'yes' else total
            obs = g.get('observations', "")
            # show amount actually paid in the TotalEarnings column
            self.tree.insert('', 'end', values=(g.get('date',''), g.get('gameNumber',''), g.get('location',''), f"{amount_paid:.2f} €", f"{left:.2f} €", g.get('paidStatus',''), obs))
        # update selection sum in case previous selection is still valid
        self.update_selection_sum()

    def update_summary(self):
        summary = self.manager.get_summary(self.selected_season.get())
        sel = float(getattr(self, 'selected_total', 0.0) or 0.0)
        self.summary_label.config(
            text=(
                f"Total Earnings: {summary['total_earnings']:.2f} € | "
                f"Amount Left: {summary['amount_left']:.2f} € | "
                f"Selected: {sel:.2f} € | "
                f"Games: {summary['games_count']}"
            )
        )
        # secondary label no longer used for selected totals
        self.selection_label.config(text="")
        self.refresh_statistics_page()

    def search_games(self):
        query = self.search_var.get().strip()
        if not query:
            self.load_games()
            return
        games = self.manager.search_games(self.selected_season.get(), query)
        self.refresh_table(games)
        # reset sort state when search changes
        self.sort_column = None
        self.sort_reverse = False
        self._clear_header_arrows()

    # ---------- new helpers ----------------------------------------------
    def _parse_currency(self, text: str) -> float:
        try:
            return float(str(text).replace('€', '').strip())
        except Exception:
            return 0.0

    def _to_float_safe(self, value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return 0.0
        s = s.replace('€', '').replace('EUR', '').replace('eur', '').strip()
        if ',' in s and '.' in s:
            if s.rfind(',') > s.rfind('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            s = s.replace(',', '.')
        try:
            return float(s)
        except Exception:
            return 0.0

    def _canonical_import_header(self, header: str):
        if header is None:
            return None
        key = ''.join(ch for ch in str(header).strip().lower() if ch.isalnum())
        aliases = {
            'season': 'season',
            'epoca': 'season',
            'seasonname': 'season',
            'temporada': 'season',
            'date': 'date',
            'gamedate': 'date',
            'matchdate': 'date',
            'data': 'date',
            'dia': 'date',
            'gamenumber': 'gameNumber',
            'gameno': 'gameNumber',
            'matchnumber': 'gameNumber',
            'numerojogo': 'gameNumber',
            'jogo': 'gameNumber',
            'location': 'location',
            'venue': 'location',
            'local': 'location',
            'transportation': 'transportation',
            'transport': 'transportation',
            'travel': 'transportation',
            'deslocacao': 'transportation',
            'food': 'food',
            'meal': 'food',
            'alimentacao': 'food',
            'gamepayment': 'gamePayment',
            'payment': 'gamePayment',
            'fee': 'gamePayment',
            'valorjogo': 'gamePayment',
            'paidstatus': 'paidStatus',
            'status': 'paidStatus',
            'paid': 'paidStatus',
            'pago': 'paidStatus',
            'paymentdate': 'paymentDate',
            'datapagamento': 'paymentDate',
            'observations': 'observations',
            'observation': 'observations',
            'notes': 'observations',
            'note': 'observations',
            'obs': 'observations',
        }
        if key in aliases:
            return aliases.get(key)

        # Fuzzy fallback for non-standard or misspelled headers.
        best = None
        best_ratio = 0.0
        for alias_key, canonical in aliases.items():
            ratio = difflib.SequenceMatcher(None, key, alias_key).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = canonical
        if best_ratio >= 0.78:
            return best
        return None

    def _detect_header_row(self, rows):
        """Detect the most likely header row in semi-structured tables."""
        if not rows:
            return None

        scan_limit = min(20, len(rows))
        best_idx = None
        best_score = -1

        for idx in range(scan_limit):
            row = rows[idx] or []
            mapped = []
            non_empty = 0
            for cell in row:
                text = str(cell).strip() if cell is not None else ''
                if text:
                    non_empty += 1
                canon = self._canonical_import_header(text)
                if canon:
                    mapped.append(canon)

            unique_mapped = len(set(mapped))
            score = unique_mapped * 10 + min(non_empty, 8) - idx * 0.2
            if unique_mapped >= 2 and score > best_score:
                best_score = score
                best_idx = idx

        return best_idx

    def _normalize_date_safe(self, value):
        if value is None:
            return ''
        if isinstance(value, datetime):
            return value.date().isoformat()
        if hasattr(value, 'isoformat') and not isinstance(value, str):
            try:
                return value.isoformat()
            except Exception:
                pass

        s = str(value).strip()
        if not s:
            return ''

        # dd/mm/yyyy or dd-mm-yyyy
        m = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$', s)
        if m:
            d = int(m.group(1))
            mo = int(m.group(2))
            y = int(m.group(3))
            if y < 100:
                y += 2000
            try:
                return date(y, mo, d).isoformat()
            except Exception:
                return s

        # yyyy-mm-dd or yyyy/mm/dd
        m = re.match(r'^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$', s)
        if m:
            y = int(m.group(1))
            mo = int(m.group(2))
            d = int(m.group(3))
            try:
                return date(y, mo, d).isoformat()
            except Exception:
                return s

        return s

    def _looks_like_date(self, value):
        s = self._normalize_date_safe(value)
        return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', s))

    def _looks_like_game_number(self, value):
        s = str(value).strip()
        if not s:
            return False
        if re.match(r'^[A-Za-z]{0,3}\d{1,5}$', s):
            return True
        return False

    def _coerce_paid_status(self, value):
        s = str(value or '').strip().lower()
        if not s:
            return 'No'
        yes_set = {'yes', 'y', 'true', '1', 'paid', 'sim', 'pago'}
        no_set = {'no', 'n', 'false', '0', 'unpaid', 'nao', 'não'}
        if s in yes_set:
            return 'Yes'
        if s in no_set:
            return 'No'
        # Keep custom status if provided.
        return str(value).strip()

    def _infer_missing_import_fields(self, normalized: dict, raw: dict):
        candidates = []
        for k, v in raw.items():
            if str(k).startswith('_'):
                continue
            candidates.append(v)

        # infer date
        if not normalized.get('date'):
            for v in candidates:
                if self._looks_like_date(v):
                    normalized['date'] = self._normalize_date_safe(v)
                    break

        # infer game number
        if not normalized.get('gameNumber'):
            for v in candidates:
                if self._looks_like_game_number(v):
                    normalized['gameNumber'] = str(v).strip()
                    break

        # infer paid status
        if not normalized.get('paidStatus'):
            for v in candidates:
                s = str(v or '').strip().lower()
                if s in {'yes', 'no', 'paid', 'unpaid', 'sim', 'nao', 'não', 'pago'}:
                    normalized['paidStatus'] = self._coerce_paid_status(v)
                    break

        # infer monetary columns from numeric values when headers are unknown.
        numeric_values = []
        for v in candidates:
            val = self._to_float_safe(v)
            if val != 0.0:
                numeric_values.append(val)
        if numeric_values:
            if 'transportation' not in normalized:
                normalized['transportation'] = numeric_values[0] if len(numeric_values) > 0 else 0.0
            if 'food' not in normalized:
                normalized['food'] = numeric_values[1] if len(numeric_values) > 1 else 0.0
            if 'gamePayment' not in normalized:
                normalized['gamePayment'] = numeric_values[2] if len(numeric_values) > 2 else (
                    numeric_values[-1] if numeric_values else 0.0
                )

        # infer location / observations from free text
        text_values = [str(v).strip() for v in candidates if v is not None and str(v).strip()]
        long_texts = [t for t in text_values if len(t) > 10]
        medium_texts = [t for t in text_values if len(t) > 2]
        if not normalized.get('location') and medium_texts:
            normalized['location'] = medium_texts[0]
        if not normalized.get('observations') and long_texts:
            normalized['observations'] = long_texts[-1]

    def _read_import_rows(self, path: str):
        path_l = str(path).lower()
        if path_l.endswith('.csv'):
            with open(path, 'r', encoding='utf-8-sig', newline='') as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                except Exception:
                    dialect = csv.excel
                reader = csv.reader(f, dialect)
                rows = [row for row in reader if any(str(c).strip() for c in row)]

            if not rows:
                return [], []

            header_idx = self._detect_header_row(rows)
            if header_idx is None:
                # Fallback: synthetic headers when no valid header row exists.
                max_cols = max(len(r) for r in rows)
                headers = [f"col_{i+1}" for i in range(max_cols)]
                data_rows = rows
            else:
                headers = [str(h).strip() if h is not None else '' for h in rows[header_idx]]
                data_rows = rows[header_idx + 1:]

            out = []
            for r in data_rows:
                if not any(str(v).strip() for v in r):
                    continue
                row = {}
                for i, h in enumerate(headers):
                    key = h if h else f"col_{i+1}"
                    row[key] = r[i] if i < len(r) else ''
                out.append(row)
            return out, []

        if path_l.endswith('.xlsx'):
            try:
                from openpyxl import load_workbook
            except Exception as exc:
                raise RuntimeError(
                    "Excel import requires openpyxl. Install with: pip install openpyxl"
                ) from exc

            wb = load_workbook(path, data_only=True)
            all_rows = []
            sheet_hints = []
            for ws in wb.worksheets:
                values = [list(r) for r in ws.iter_rows(values_only=True)]
                if not values:
                    continue

                values = [r for r in values if any(v not in (None, '') for v in r)]
                if not values:
                    continue

                header_idx = self._detect_header_row(values)
                if header_idx is None:
                    max_cols = max(len(r) for r in values)
                    headers = [f"col_{i+1}" for i in range(max_cols)]
                    data_rows = values
                else:
                    headers = [str(h).strip() if h is not None else '' for h in values[header_idx]]
                    data_rows = values[header_idx + 1:]

                sheet_hints.append(ws.title)
                for row_vals in data_rows:
                    if row_vals is None:
                        continue
                    if not any(v not in (None, '') for v in row_vals):
                        continue
                    row = {}
                    for i, h in enumerate(headers):
                        key = h if h else f"col_{i+1}"
                        row[key] = row_vals[i] if i < len(row_vals) else ''
                    row['_sheet_title'] = ws.title
                    all_rows.append(row)
            return all_rows, sheet_hints

        raise RuntimeError("Unsupported file extension. Use .csv or .xlsx")

    def _normalize_import_game(self, raw: dict):
        normalized = {}
        for k, v in raw.items():
            canon = self._canonical_import_header(k)
            if canon:
                normalized[canon] = v

        self._infer_missing_import_fields(normalized, raw)

        season = str(normalized.get('season', '') or '').strip()
        if not season:
            sheet_title = str(raw.get('_sheet_title', '') or '').strip()
            if sheet_title and sheet_title.lower() not in ('games', 'sheet1'):
                season = sheet_title.replace('-', '/')
        if not season:
            season = self.selected_season.get().strip()

        game_number = str(normalized.get('gameNumber', '') or '').strip()
        game_date = self._normalize_date_safe(normalized.get('date', ''))
        if not game_number or not game_date:
            return None

        paid_status = self._coerce_paid_status(normalized.get('paidStatus', ''))

        return {
            'season': season,
            'date': game_date,
            'gameNumber': game_number,
            'location': str(normalized.get('location', '') or '').strip(),
            'transportation': self._to_float_safe(normalized.get('transportation', 0)),
            'food': self._to_float_safe(normalized.get('food', 0)),
            'gamePayment': self._to_float_safe(normalized.get('gamePayment', 0)),
            'paidStatus': paid_status,
            'paymentDate': str(normalized.get('paymentDate', '') or '').strip(),
            'observations': str(normalized.get('observations', '') or '').strip(),
        }

    def _show_import_preview_and_confirm(self, path: str, raw_rows, season_to_rows: dict, skipped: int) -> bool:
        """Show inferred mapping and sample rows before committing import."""
        all_headers = []
        for row in raw_rows:
            for h in row.keys():
                if str(h).startswith('_'):
                    continue
                if h not in all_headers:
                    all_headers.append(h)

        mapped = []
        unknown = []
        for h in all_headers:
            canon = self._canonical_import_header(h)
            if canon:
                mapped.append((str(h), canon))
            else:
                unknown.append(str(h))

        parsed_rows = []
        for season, rows in season_to_rows.items():
            for r in rows:
                parsed_rows.append(r)

        lines = []
        lines.append(f"File: {path}")
        lines.append(f"Raw rows: {len(raw_rows)}")
        lines.append(f"Valid parsed rows: {len(parsed_rows)}")
        lines.append(f"Skipped rows: {skipped}")
        lines.append("")
        lines.append("Detected Column Mapping:")
        if mapped:
            for src, dst in mapped:
                lines.append(f"- {src} -> {dst}")
        else:
            lines.append("- No explicit mappings detected; value inference will be used.")
        if unknown:
            lines.append("")
            lines.append("Unmapped Source Columns:")
            for h in unknown[:20]:
                lines.append(f"- {h}")

        lines.append("")
        lines.append("Rows per Season:")
        for season in sorted(season_to_rows.keys()):
            lines.append(f"- {season}: {len(season_to_rows[season])}")

        lines.append("")
        lines.append("Sample Parsed Rows:")
        for idx, row in enumerate(parsed_rows[:12], start=1):
            lines.append(
                f"{idx}. {row.get('season','')} | {row.get('date','')} | #{row.get('gameNumber','')} | "
                f"{row.get('location','')} | pay={row.get('gamePayment',0):.2f} | "
                f"trans={row.get('transportation',0):.2f} | food={row.get('food',0):.2f} | "
                f"status={row.get('paidStatus','')}"
            )

        dlg = tk.Toplevel(self.root)
        dlg.title("Import Preview")
        dlg.geometry("980x620")
        dlg.minsize(840, 520)
        dlg.transient(self.root)
        dlg.grab_set()

        c = self.colors
        f = self.fonts

        wrap = tk.Frame(dlg, bg=c["surface"])
        wrap.pack(fill="both", expand=True)

        tk.Label(
            wrap,
            text="Review detected mapping and sample rows before import",
            bg=c["surface"],
            fg=c["text_primary"],
            font=f["h3"],
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 6))

        txt = tk.Text(wrap, wrap="word")
        txt.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        ybar = ttk.Scrollbar(txt, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=ybar.set)
        ybar.pack(side="right", fill="y")
        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")

        decision = {"ok": False}

        def _confirm():
            decision["ok"] = True
            dlg.destroy()

        def _cancel():
            decision["ok"] = False
            dlg.destroy()

        actions = ttk.Frame(wrap)
        actions.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(actions, text="Cancel", command=_cancel).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Import Now", command=_confirm).pack(side="right")

        dlg.wait_window()
        return decision["ok"]

    def import_games(self):
        path = filedialog.askopenfilename(
            title="Import games",
            filetypes=[
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx"),
            ],
        )
        if not path:
            return

        try:
            rows, _sheet_hints = self._read_import_rows(path)
        except Exception as exc:
            messagebox.showerror("Import", f"Failed to read file:\n{exc}")
            return

        if not rows:
            messagebox.showinfo("Import", "No rows found to import.")
            return

        season_to_rows = {}
        skipped = 0
        for raw in rows:
            game = self._normalize_import_game(raw)
            if not game:
                skipped += 1
                continue
            season_to_rows.setdefault(game['season'], []).append(game)

        if not season_to_rows:
            messagebox.showwarning("Import", "No valid rows found. Ensure each row has date and gameNumber.")
            return

        ok = self._show_import_preview_and_confirm(path, rows, season_to_rows, skipped)
        if not ok:
            return

        added = 0
        updated = 0
        failed = []

        try:
            for season, import_rows in season_to_rows.items():
                current = list(self.manager.load_games(season))
                idx_by_key = {}
                for idx, g in enumerate(current):
                    key = (str(g.get('gameNumber', '')).strip(), str(g.get('date', '')).strip())
                    idx_by_key[key] = idx

                for game in import_rows:
                    key = (str(game.get('gameNumber', '')).strip(), str(game.get('date', '')).strip())
                    if key in idx_by_key:
                        current[idx_by_key[key]] = game
                        updated += 1
                    else:
                        idx_by_key[key] = len(current)
                        current.append(game)
                        added += 1

                try:
                    self.manager.save_games(season, current)
                except Exception as save_exc:
                    error_msg = str(save_exc)
                    if 'UNIQUE' in error_msg or 'constraint' in error_msg.lower():
                        failed.append(f"Constraint violation (may have duplicate game numbers): {error_msg}")
                    else:
                        raise
        except Exception as exc:
            messagebox.showerror("Import", f"Failed while importing games:\n{exc}")
            return

        self.seasons = self.get_seasons()
        self.season_combo['values'] = self.seasons
        if self.selected_season.get() not in self.seasons and self.seasons:
            self.selected_season.set(self.seasons[0])

        self.load_games()
        msg = f"Imported from: {path}\n\nAdded: {added}\nUpdated: {updated}\nSkipped: {skipped}"
        if failed:
            msg += f"\n\nErrors ({len(failed)}):\n" + "\n".join(failed)
            messagebox.showwarning("Import Complete", msg)
        else:
            messagebox.showinfo("Import Complete", msg)

    def update_selection_sum(self):
        """Recalculate and display the total of the currently selected games."""
        total = 0.0
        for iid in self.tree.selection():
            vals = self.tree.item(iid).get('values', [])
            if len(vals) >= 5:
                # selected total should represent full game value (paid + left)
                total += self._parse_currency(vals[3]) + self._parse_currency(vals[4])
        self.selected_total = total
        self.update_summary()

    def mark_selected_paid(self):
        """Set paid status for all selected games, using today's date."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Mark Paid", "Select one or more games first.")
            return
        season = self.selected_season.get()
        today_str = date.today().isoformat()
        game_keys = [
            (self.tree.item(i)['values'][1], self.tree.item(i)['values'][0])
            for i in sel
        ]
        # ask for confirmation
        if not messagebox.askyesno("Mark Paid", f"Mark {len(game_keys)} game(s) as paid today ({today_str})?"):
            return

        # perform update and handle any errors / fallbacks
        try:
            self.manager.mark_games_paid(season, game_keys, today_str)
        except Exception as exc:
            # unexpected failure (e.g. JSON write also failed).  surface error
            messagebox.showerror("Mark Paid", f"Error marking games paid:\n{exc}")
        finally:
            # re‑load games so UI reflects whatever backend is now active
            self.load_games()

        # if the database became unusable during the update, let the user know
        if getattr(self.manager, 'db_error', None) and not getattr(self.manager, 'conn', None):
            messagebox.showwarning(
                "Database Unavailable",
                f"The database connection was lost; the application is now using local JSON files instead.\n({self.manager.db_error})"
            )

    def add_game_dialog(self):
        self.game_dialog(mode='add')

    def _clear_header_arrows(self):
        for col, label in self.col_headers.items():
            self.tree.heading(col, text=label)

    def _set_header_arrow(self, col, reverse):
        # show arrow for sorted column
        arrow = ' ▲' if not reverse else ' ▼'
        for c, label in self.col_headers.items():
            text = label + (arrow if c == col else '')
            self.tree.heading(c, text=text)

    def on_column_click(self, col):
        # toggle sort direction
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        # compute key function
        def key_fn(g):
            try:
                if col == 'date':
                    return datetime.strptime(g.get('date','0001-01-01'), '%Y-%m-%d')
                if col == 'gameNumber':
                    try:
                        return int(g.get('gameNumber'))
                    except Exception:
                        return g.get('gameNumber','')
                if col == 'location':
                    return g.get('location','').lower()
                if col == 'totalEarnings':
                    return float(g.get('transportation',0)) + float(g.get('food',0)) + float(g.get('gamePayment',0))
                if col == 'amountLeft':
                    total = float(g.get('transportation',0)) + float(g.get('food',0)) + float(g.get('gamePayment',0))
                    return 0.0 if g.get('paidStatus','').lower() == 'yes' else total
                if col == 'paidStatus':
                    return g.get('paidStatus','').lower()
                if col == 'observations':
                    return g.get('observations','').lower()
            except Exception:
                return ''
        # sort displayed games and refresh
        try:
            sorted_games = sorted(self.displayed_games, key=key_fn, reverse=self.sort_reverse)
        except Exception:
            sorted_games = list(self.displayed_games)
        self._set_header_arrow(col, self.sort_reverse)
        self.refresh_table(sorted_games)

    def edit_game_dialog(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Edit Game", "Select a game to edit.")
            return
        values = self.tree.item(selected[0])['values']
        game_date = values[0]
        game_number = values[1]
        season = self.selected_season.get()
        games = self.manager.load_games(season)
        # Find the game by game number and all fields
        for g in games:
            if str(g['gameNumber']) == str(game_number) and str(g.get('date','')) == str(game_date):
                self.game_dialog(mode='edit', game=g)
                return
        messagebox.showerror("Edit Game", "No matching game found to edit.")

    def test_db(self):
        """Run a trivial query to verify the database connection.

        If the connection works we show an info box; if not, an error box
        will display the exception message.  This can be useful when running
        the app against a remote server to immediately surface connection
        problems.
        """
        if not getattr(self.manager, 'conn', None):
            messagebox.showinfo("Database Test", "No database connection in use.")
            return
        try:
            cur = self.manager.conn.cursor()
            # simple query; most backends support "SELECT 1" or variant
            cur.execute("SELECT 1")
            cur.fetchall()
            cur.close()
            messagebox.showinfo("Database Test", "Connection OK")
        except Exception as e:
            messagebox.showerror("Database Test", f"Error executing test query:\n{e}")

    def delete_game(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Delete Game", "Select a game to delete.")
            return
        values = self.tree.item(selected[0])['values']
        game_date = values[0]
        game_number = values[1]
        self.manager.delete_game(self.selected_season.get(), game_number, game_date)
        self.load_games()

    def export_all_games(self):
        rows = []
        season_rows = {}
        for season in self.get_seasons():
            try:
                season_games = self.manager.load_games(season)
            except Exception:
                season_games = []
            season_rows[season] = []
            for g in season_games:
                row = {
                    'season': season,
                    'date': g.get('date', ''),
                    'gameNumber': g.get('gameNumber', ''),
                    'location': g.get('location', ''),
                    'transportation': g.get('transportation', 0),
                    'food': g.get('food', 0),
                    'gamePayment': g.get('gamePayment', 0),
                    'paidStatus': g.get('paidStatus', ''),
                    'paymentDate': g.get('paymentDate', ''),
                    'observations': g.get('observations', ''),
                }
                rows.append(row)
                season_rows[season].append(row)

        if not rows:
            messagebox.showinfo("Export", "No games found to export.")
            return

        path = filedialog.asksaveasfilename(
            title="Export all games",
            defaultextension=".csv",
            filetypes=[
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx"),
            ],
        )
        if not path:
            return

        headers = [
            'season', 'date', 'gameNumber', 'location', 'transportation',
            'food', 'gamePayment', 'paidStatus', 'paymentDate', 'observations'
        ]

        try:
            if path.lower().endswith('.csv'):
                with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(rows)
            elif path.lower().endswith('.xlsx'):
                try:
                    from openpyxl import Workbook
                    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
                    from openpyxl.utils import get_column_letter
                except Exception:
                    messagebox.showerror(
                        "Export",
                        "Excel export requires openpyxl.\nInstall with: pip install openpyxl\nOr export as CSV instead."
                    )
                    return

                wb = Workbook()

                # remove default sheet; we'll create one tab per season
                default_ws = wb.active
                wb.remove(default_ws)

                title_fill = PatternFill(fill_type="solid", fgColor="1F4E78")
                header_fill = PatternFill(fill_type="solid", fgColor="D9EAF7")
                stripe_fill = PatternFill(fill_type="solid", fgColor="F7FBFF")
                title_font = Font(color="FFFFFF", bold=True, size=13)
                header_font = Font(color="1F2937", bold=True)
                thin_border = Border(
                    left=Side(style="thin", color="D1D5DB"),
                    right=Side(style="thin", color="D1D5DB"),
                    top=Side(style="thin", color="D1D5DB"),
                    bottom=Side(style="thin", color="D1D5DB"),
                )
                currency_fmt = '#,##0.00'
                date_fmt = 'yyyy-mm-dd'

                sheet_headers = [
                    'date', 'gameNumber', 'location', 'transportation',
                    'food', 'gamePayment', 'paidStatus', 'paymentDate', 'observations'
                ]

                def safe_sheet_title(base_title, existing_titles):
                    invalid = '[]:*?/\\'
                    cleaned = ''.join('-' if ch in invalid else ch for ch in str(base_title))
                    cleaned = cleaned.strip() or 'Season'
                    cleaned = cleaned[:31]
                    if cleaned not in existing_titles:
                        return cleaned

                    idx = 2
                    while True:
                        suffix = f" ({idx})"
                        candidate = f"{cleaned[:31-len(suffix)]}{suffix}"
                        if candidate not in existing_titles:
                            return candidate
                        idx += 1

                for season, season_data in season_rows.items():
                    if not season_data:
                        continue

                    ws_title = safe_sheet_title(season.replace('/', '-'), set(wb.sheetnames))
                    ws = wb.create_sheet(title=ws_title)

                    col_count = len(sheet_headers)
                    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=col_count)
                    ws.cell(row=1, column=1, value=f"Referee Games - Season {season}")

                    for col in range(1, col_count + 1):
                        cell = ws.cell(row=1, column=col)
                        cell.fill = title_fill
                        cell.font = title_font
                        cell.alignment = Alignment(horizontal='left', vertical='center')

                    ws.row_dimensions[1].height = 28

                    for col, key in enumerate(sheet_headers, start=1):
                        header_cell = ws.cell(row=3, column=col, value=key)
                        header_cell.fill = header_fill
                        header_cell.font = header_font
                        header_cell.alignment = Alignment(horizontal='center', vertical='center')
                        header_cell.border = thin_border

                    data_start = 4
                    for row_idx, item in enumerate(season_data, start=data_start):
                        values = [item.get(h, '') for h in sheet_headers]
                        for col_idx, value in enumerate(values, start=1):
                            cell = ws.cell(row=row_idx, column=col_idx, value=value)
                            cell.border = thin_border
                            if row_idx % 2 == 0:
                                cell.fill = stripe_fill

                            key = sheet_headers[col_idx - 1]
                            if key in ('transportation', 'food', 'gamePayment'):
                                cell.number_format = currency_fmt
                                cell.alignment = Alignment(horizontal='right', vertical='center')
                            elif key in ('date', 'paymentDate'):
                                cell.number_format = date_fmt
                                cell.alignment = Alignment(horizontal='center', vertical='center')
                            else:
                                cell.alignment = Alignment(horizontal='left', vertical='center')

                    total_row = data_start + len(season_data)
                    ws.cell(row=total_row, column=1, value='Totals').font = Font(bold=True, color='1F2937')
                    ws.cell(row=total_row, column=1).fill = header_fill
                    ws.cell(row=total_row, column=1).border = thin_border

                    for money_col_idx in (4, 5, 6):
                        col_letter = get_column_letter(money_col_idx)
                        total_cell = ws.cell(
                            row=total_row,
                            column=money_col_idx,
                            value=f"=SUM({col_letter}{data_start}:{col_letter}{total_row-1})"
                        )
                        total_cell.font = Font(bold=True, color='1F2937')
                        total_cell.fill = header_fill
                        total_cell.border = thin_border
                        total_cell.number_format = currency_fmt
                        total_cell.alignment = Alignment(horizontal='right', vertical='center')

                    for col_idx in range(2, col_count + 1):
                        c = ws.cell(row=total_row, column=col_idx)
                        if c.value is None:
                            c.fill = header_fill
                            c.border = thin_border

                    ws.freeze_panes = 'A4'
                    ws.auto_filter.ref = f"A3:{get_column_letter(col_count)}{total_row-1}"

                    widths = {
                        1: 14,
                        2: 14,
                        3: 28,
                        4: 16,
                        5: 12,
                        6: 14,
                        7: 14,
                        8: 14,
                        9: 42,
                    }
                    for col_idx, width in widths.items():
                        ws.column_dimensions[get_column_letter(col_idx)].width = width

                if not wb.sheetnames:
                    ws = wb.create_sheet(title='Games')
                    ws.append(headers)

                wb.save(path)
            else:
                messagebox.showerror("Export", "Unsupported file extension. Use .csv or .xlsx")
                return

            messagebox.showinfo("Export", f"Exported {len(rows)} games to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export", f"Failed to export games:\n{exc}")

    def game_dialog(self, mode='add', game=None):
        dlg = tk.Toplevel(self.root)
        dlg.geometry("500x420")
        dlg.minsize(420, 320)
        dlg.resizable(True, True)
        # Content frame (no scrolling) — keep layout simple and predictable
        content_frame = ttk.Frame(dlg)
        content_frame.pack(fill='both', expand=True, padx=8, pady=8)
        dlg.title("Add Game" if mode=='add' else "Edit Game")
        # allow the second column (inputs) to expand
        content_frame.columnconfigure(1, weight=1)
        fields = [
            ("Date", "date"),
            ("Game Number", "gameNumber"),
            ("Location", "location"),
            ("Transportation Payment", "transportation"),
            ("Food Payment", "food"),
            ("Game Payment", "gamePayment"),
            ("Paid Status", "paidStatus"),
            ("Payment Date", "paymentDate"),
            ("Season", "season"),
            ("Observations", "observations")
        ]
        entries = {}
        # remember original identifiers when editing
        original_game_number = game.get('gameNumber') if game else None
        original_game_date = game.get('date') if game else None
        original_season = game.get('season') if game else None
        # Import DateEntry from tkcalendar
        try:
            from tkcalendar import DateEntry
        except ImportError:
            # tkcalendar not available — fall back to manual date entry
            DateEntry = None
        # Collect all unique locations from all games
        all_locations = set()
        for s in self.seasons:
            for g in self.manager.load_games(s):
                if g.get('location'):
                    all_locations.add(g['location'])
        location_list = sorted(all_locations)
        for idx, (label, key) in enumerate(fields):
            ttk.Label(content_frame, text=label).grid(row=idx, column=0, sticky='w', padx=5, pady=2)
            val = game.get(key, "") if game else ""
            if key == "date" and DateEntry:
                entry = DateEntry(content_frame, date_pattern='yyyy-mm-dd')
                if val:
                    entry.set_date(val)
                # always show small calendar button (works with DateEntry or Entry)
                cal_btn = ttk.Button(content_frame, text='📅', width=3, command=lambda e_key=entry, v=val: self.open_date_picker(e_key, v))
                cal_btn.grid(row=idx, column=2, padx=2, pady=2)
            elif key == "date":
                entry = ttk.Entry(content_frame, width=25)
                if val:
                    entry.insert(0, str(val))
                # add a small calendar button to open a simple date-picker popup
                cal_btn = ttk.Button(content_frame, text='📅', width=3, command=lambda e_key=entry, v=val: self.open_date_picker(e_key, v))
                cal_btn.grid(row=idx, column=2, padx=2, pady=2)
                entry_placeholder = ttk.Label(content_frame, text="Format: YYYY-MM-DD", foreground="gray")
                entry_placeholder.grid(row=idx, column=3, padx=5, pady=2)
            elif key == "location":
                entry = ttk.Combobox(content_frame, values=location_list, state='normal', width=25)
                entry.set(val if val else (location_list[0] if location_list else ""))
            elif key in ["transportation", "food", "gamePayment"]:
                entry = ttk.Entry(content_frame, width=20)
                entry.insert(0, str(val) if val else "0")
            elif key == "paidStatus":
                entry = ttk.Combobox(content_frame, values=["Yes", "No"], state='readonly', width=8)
                entry.set(val if val else "No")
            elif key == "season":
                # allow typing a new season, not just existing ones
                entry = ttk.Combobox(content_frame, values=self.seasons, state='normal', width=18)
                entry.set(val if val else self.selected_season.get())
            elif key == "observations":
                entry = tk.Text(content_frame, height=4, width=40, relief='sunken', borderwidth=1, bg='white')
                if val:
                    entry.insert('1.0', str(val))
                # make observations visually prominent
                entry.configure(highlightthickness=1, highlightbackground='#999')
            else:
                entry = ttk.Entry(content_frame, width=25)
                entry.insert(0, str(val) if val else "")
            entry.grid(row=idx, column=1, padx=5, pady=2)
            entries[key] = entry
        

        def on_submit():
            try:
                # DateEntry returns a datetime.date, convert to string
                date_val = entries['date'].get()
                if DateEntry and isinstance(entries['date'], DateEntry):
                    date_val = entries['date'].get_date().strftime('%Y-%m-%d')
                # validate date format (YYYY-MM-DD)
                from datetime import datetime
                try:
                    datetime.strptime(date_val, '%Y-%m-%d')
                except Exception:
                    messagebox.showerror('Input Error', 'Date must be in YYYY-MM-DD format')
                    return
                def parse_decimal(val):
                    val = val.replace(',', '').replace(' ', '')
                    return float(val)
                game_data = {
                    'date': date_val,
                    'gameNumber': entries['gameNumber'].get(),
                    'location': entries['location'].get(),
                    'transportation': parse_decimal(entries['transportation'].get()),
                    'food': parse_decimal(entries['food'].get()),
                    'gamePayment': parse_decimal(entries['gamePayment'].get()),
                    'paidStatus': entries['paidStatus'].get(),
                    'paymentDate': entries['paymentDate'].get(),
                    'season': entries['season'].get(),
                    'observations': entries['observations'].get('1.0', 'end').strip() if 'observations' in entries else ""
                }
            except Exception as e:
                messagebox.showerror("Input Error", f"Invalid input: {e}\nPlease enter only numbers for payment fields.")
                return
            if mode == 'add':
                self.manager.add_game(game_data['season'], game_data)
            else:
                # update existing game — use the original game number/season to find the record
                if original_game_number is None:
                    # fallback: update by new gameNumber
                    self.manager.update_game(game_data['season'], game_data['gameNumber'], game_data, game_data.get('date'))
                else:
                    # same season -> update in place
                    if original_season == game_data['season']:
                        self.manager.update_game(original_season, original_game_number, game_data, original_game_date)
                    else:
                        # moved to a different season: delete from old and add to new
                        self.manager.delete_game(original_season, original_game_number, original_game_date)
                        self.manager.add_game(game_data['season'], game_data)
            dlg.destroy()
            self.seasons = self.get_seasons()
            self.season_combo['values'] = self.seasons
            self.load_games()

        # Add an inline Save button inside the content area for visibility
        save_button = ttk.Button(content_frame, text="Save", command=on_submit)
        save_button.grid(row=len(fields)+1, column=0, columnspan=2, pady=8)
        save_button.focus_set()
        # keyboard shortcut
        dlg.bind('<Control-s>', lambda e: on_submit())
        # helper note (visible)
        ttk.Label(content_frame, text="Tip: press Ctrl+S or click Save to store changes.", foreground="#555").grid(row=len(fields)+2, column=0, columnspan=2, pady=(2,8))

        # (previously debug print removed)
        # Ensure dialog is focused and on top
        dlg.lift()
        dlg.focus_force()

        dlg.transient(self.root)
        dlg.grab_set()
        dlg.wait_window()

if __name__ == "__main__":
    # debug logging to console so we can see where execution reaches
    print("[debug] starting app.main __main__")
    import argparse, os
    parser = argparse.ArgumentParser(description="Referee earnings tracker")
    parser.add_argument('--db', help='database path or URL to use (optional). If omitted a JSON backend is used. Can also be set via REF_DB_PATH env var.')
    args = parser.parse_args()
    db_path = args.db or os.environ.get('REF_DB_PATH')

    db_conn = None
    db_error_msg = None

    # determine connection parameters (env vars or optional private
    # config file override defaults)
    cfg = DEFAULT_DB.copy()
    # look for a local configuration file that is gitignored
    try:
        # this module should define a dictionary named DB_CONFIG
        from db_connection import DB_CONFIG
        if isinstance(DB_CONFIG, dict):
            cfg.update(DB_CONFIG)
    except Exception:
        # when launched via `python app/main.py`, project root may not be in
        # sys.path. Try loading db_connection.py directly from project root.
        try:
            import importlib.util
            from pathlib import Path

            cfg_file = Path(__file__).resolve().parent.parent / 'db_connection.py'
            if cfg_file.exists():
                spec = importlib.util.spec_from_file_location('db_connection', str(cfg_file))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    private_cfg = getattr(mod, 'DB_CONFIG', None)
                    if isinstance(private_cfg, dict):
                        cfg.update(private_cfg)
        except Exception:
            # no file or invalid contents; ignore
            pass
    # environment variables take highest precedence
    if os.environ.get('DB_HOST'):
        cfg['host'] = os.environ.get('DB_HOST')
        cfg['port'] = int(os.environ.get('DB_PORT', cfg['port']))
        cfg['user'] = os.environ.get('DB_USER', cfg['user'])
        cfg['password'] = os.environ.get('DB_PASS', cfg['password'])
        cfg['dbname'] = os.environ.get('DB_NAME', cfg['dbname'])

    # If we already computed a db_error_msg earlier (from URL
    # processing), we only surface it as a dialog if the user explicitly
    # supplied a `--db`/REF_DB_PATH value.  Placeholder/default configs will
    # silently fall back to JSON.
    if db_error_msg and db_path:
        messagebox.showwarning("Database", db_error_msg + ".\nUsing JSON fallback.")

    # if a --db URL was provided, that takes precedence; otherwise try the
    # configured host/port/user/password pair (defaulting to DEFAULT_DB).
    if db_path:
        try:
            if any(db_path.startswith(s) for s in ('postgres://', 'postgresql://')):
                import psycopg2
                db_conn = psycopg2.connect(db_path)
            elif db_path.startswith('mysql://'):
                from urllib.parse import urlparse
                try:
                    import pymysql
                except ImportError:
                    print("Error: pymysql library not installed.\n"
                          "Install it with `pip install pymysql` or use the provided "
                          "requirements.txt file.")
                    sys.exit(1)
                parsed = urlparse(db_path)
                user = parsed.username or ''
                password = parsed.password or ''
                host = parsed.hostname or 'localhost'
                port = parsed.port or 3306
                dbname = parsed.path.lstrip('/')
                db_conn = pymysql.connect(host=host, user=user,
                                          password=password, port=port,
                                          db=dbname)
            # else: sqlite filename; GameDataManager will open it itself
        except Exception as exc:  # network errors, auth failures, etc.
            print(f"Warning: failed to open database connection ({exc}).")
            print("Continuing with JSON backend instead.")
            db_conn = None
            db_path = None
    else:
        # no URL supplied – attempt general DB connection using cfg
        # only try to connect if the configuration appears to contain real
        # credentials rather than the placeholder strings that ship with the
        # example config file.  this avoids popping up a blocking warning for
        # users who haven't set up a database.
        def _cfg_looks_valid(c):
            # require non-empty host/user/password/dbname and reject values
            # that start with '<' (the templated placeholders).
            return (c.get('host') and not str(c.get('host')).startswith('<')
                    and c.get('user') and not str(c.get('user')).startswith('<')
                    and c.get('password') and not str(c.get('password')).startswith('<')
                    and c.get('dbname') and not str(c.get('dbname')).startswith('<'))

        if _cfg_looks_valid(cfg):
            try:
                import pymysql
                db_conn = pymysql.connect(
                    host=cfg['host'], port=cfg['port'],
                    user=cfg['user'], password=cfg['password'],
                    db=cfg['dbname'], connect_timeout=5
                )
            except Exception as exc:
                db_error_msg = f"Could not open default database ({exc})"
                print("Warning: ", db_error_msg)
        else:
            # skip connection attempt; user is probably using JSON backend
            db_conn = None

    try:
        # create TK root and show any initial warning/info message
        print("[debug] creating Tk root")
        root = tk.Tk()
        print("[debug] root created")
        # Only display the warning popup if the user explicitly asked for a
        # database.  Otherwise the error has already been printed and we silently
        # continue with JSON storage.
        if db_error_msg and db_path:
            print("[debug] showing db error popup")
            messagebox.showwarning("Database", db_error_msg + ".\nUsing JSON fallback.")
        # no 'connected' popup; backend_label will show status
        print("[debug] instantiating RefereeApp")
        app = RefereeApp(root, db_path=db_path, db_conn=db_conn)
        print("[debug] entering mainloop")
        root.mainloop()
        print("[debug] mainloop exited")
    except Exception as e:
        # ensure any exception is printed; otherwise the process may silently
        # exit and the prompt will return leaving the user confused.
        import traceback
        print("[error] unhandled exception in main:")
        traceback.print_exc()
        sys.exit(1)
