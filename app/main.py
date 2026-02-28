import sys
import tkinter as tk
from tkinter import ttk, messagebox
import calendar
from datetime import datetime, date
from app.data_manager import GameDataManager

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
        self.root = root
        self.root.title("Referee Earnings Tracker")
        # manager may use JSON, SQLite path, or a supplied connection object
        if db_conn is not None:
            self.manager = GameDataManager(db_conn=db_conn)
        elif db_path:
            self.manager = GameDataManager(db_path=db_path)
        else:
            self.manager = GameDataManager()

        # if we have a database connection, try a simple query now to make
        # sure the connection works; if it raises we fall back to JSON.
        if getattr(self.manager, 'conn', None) is not None:
            try:
                cur = self.manager.conn.cursor()
                cur.execute('SELECT 1')
                cur.fetchall()
                cur.close()
            except Exception as e:
                print(f"Warning: database connection is unusable ({e}); using JSON instead.")
                # replace manager with plain JSON instance
                self.manager = GameDataManager()
        self.seasons = self.get_seasons()
        self.selected_season = tk.StringVar(value=self.seasons[0] if self.seasons else "2025/2026")
        self.games = []
        self.setup_ui()
        self.load_games()

    def get_seasons(self):
        # retrieve list of seasons available either in JSON files or in database
        seasons = []
        if self.manager.conn:
            cursor = self.manager.conn.cursor()
            cursor.execute("SELECT DISTINCT season FROM games ORDER BY season")
            rows = cursor.fetchall()
            seasons = [r[0] for r in rows]
        else:
            import os
            if os.path.isdir(self.manager.data_dir):
                for f in os.listdir(self.manager.data_dir):
                    if f.startswith("games_") and f.endswith(".json"):
                        s = f[6:-5].replace('-', '/')
                        seasons.append(s)
        if not seasons:
            seasons = ["2025/2026"]
        return sorted(seasons)

    def setup_ui(self):
        # Season selector
        season_frame = ttk.Frame(self.root)
        season_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(season_frame, text="Season:").pack(side='left')
        self.season_combo = ttk.Combobox(season_frame, textvariable=self.selected_season, values=self.seasons, state='readonly')
        self.season_combo.pack(side='left', padx=5)
        self.season_combo.bind('<<ComboboxSelected>>', lambda e: self.load_games())

        # optionally show a small test-connection button if a database is in use
        if getattr(self.manager, 'conn', None) is not None:
            ttk.Button(season_frame, text="Test DB", command=self.test_db).pack(side='left', padx=5)

        # Summary
        self.summary_label = ttk.Label(self.root, text="")
        self.summary_label.pack(fill='x', padx=10, pady=5)
        # backend status label (shows whether using DB or JSON)
        self.backend_label = ttk.Label(self.root, text="", foreground="#555")
        self.backend_label.pack(fill='x', padx=10, pady=(0,5))

        # Search
        search_frame = ttk.Frame(self.root)
        search_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(search_frame, text="Search:").pack(side='left')
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<Return>', lambda e: self.search_games())
        ttk.Button(search_frame, text="Search", command=self.search_games).pack(side='left')
        ttk.Button(search_frame, text="Clear", command=self.load_games).pack(side='left')

        # Table
        columns = ["date", "gameNumber", "location", "totalEarnings", "amountLeft", "paidStatus", "observations"]
        self.tree = ttk.Treeview(self.root, columns=columns, show='headings')
        # store human labels and attach clickable headers for sorting
        self.col_headers = {col: col.capitalize() for col in columns}
        for col in columns:
            self.tree.heading(col, text=self.col_headers[col], command=lambda c=col: self.on_column_click(c))
        self.tree.pack(fill='both', expand=True, padx=10, pady=5)
        # sorting state
        self.sort_column = None
        self.sort_reverse = False
        self.displayed_games = []

        # Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(btn_frame, text="Add Game", command=self.add_game_dialog).pack(side='left')
        ttk.Button(btn_frame, text="Edit Game", command=self.edit_game_dialog).pack(side='left')
        ttk.Button(btn_frame, text="Delete Game", command=self.delete_game).pack(side='left')

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

    def update_summary(self):
        summary = self.manager.get_summary(self.selected_season.get())
        self.summary_label.config(text=f"Total Earnings: {summary['total_earnings']:.2f} € | Amount Left: {summary['amount_left']:.2f} € | Games: {summary['games_count']}")

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
        game_number = values[1]
        season = self.selected_season.get()
        games = self.manager.load_games(season)
        # Find the game by game number and all fields
        for g in games:
            if str(g['gameNumber']) == str(game_number):
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
        game_number = values[1]
        self.manager.delete_game(self.selected_season.get(), game_number)
        self.load_games()

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
                    self.manager.update_game(game_data['season'], game_data['gameNumber'], game_data)
                else:
                    # same season -> update in place
                    if original_season == game_data['season']:
                        self.manager.update_game(original_season, original_game_number, game_data)
                    else:
                        # moved to a different season: delete from old and add to new
                        self.manager.delete_game(original_season, original_game_number)
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

    # create TK root and show any initial warning/info message
    root = tk.Tk()
    # Only display the warning popup if the user explicitly asked for a
    # database.  Otherwise the error has already been printed and we silently
    # continue with JSON storage.
    if db_error_msg and db_path:
        messagebox.showwarning("Database", db_error_msg + ".\nUsing JSON fallback.")
    # no 'connected' popup; backend_label will show status
    app = RefereeApp(root, db_path=db_path, db_conn=db_conn)
    root.mainloop()
