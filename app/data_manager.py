import json
import os
import sys
from datetime import date
from typing import List, Dict, Any

# determine where to write persistent JSON data.  When running
# normally we keep a `data/` directory alongside the Python package; when
# the application is frozen by PyInstaller or a similar bundler we want to
# write next to the executable so the user can find the files and they are
# preserved across upgrades.
if getattr(sys, 'frozen', False):
    # running as a bundle (PyInstaller, cx_Freeze, etc.)
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(__file__)
DATA_DIR = os.path.join(base_dir, '..', 'data')

class GameDataManager:
    def __init__(self, db_path: str = None, db_conn=None):
        # persistent directory for the JSON files
        os.makedirs(DATA_DIR, exist_ok=True)
        self.data_dir = DATA_DIR

        # one of db_path (string) or db_conn (existing connection) may be
        # supplied.  db_conn can be any DB‑API connection object such as
        # a psycopg2 connection pointed at a remote server.
        self.db_path = db_path
        self.conn = None
        if db_conn is not None:
            # use provided connection and ensure the expected table exists
            self.conn = db_conn
            self._ensure_schema()
        elif db_path:
            self._init_db(db_path)

        # if we have a connection and there are existing JSON files, import
        # them into the database so that subsequent operations read from the
        # database instead of the files.  We only import seasons that have
        # not already been populated to avoid duplicates.
        if self.conn:
            try:
                self.import_json_to_db()
            except Exception as e:
                # import failures shouldn't stop the rest of the app; the
                # connection may have been closed by the underlying driver.
                print(f"Warning during JSON->DB import: {e}")
                self.db_error = str(e)
                self.conn = None
        # remove any accidental duplicates that might already be present.
        # this is defensive (e.g. if the same JSON was imported twice or a
        # manual script inserted duplicate rows).
        if self.conn:
            self._dedupe_db()
        # always make sure the combined export exists, even if we're in
        # JSON‑only mode or the import step did nothing.
        self._dump_all()

    def _init_db(self, path: str):
        """Create/open the sqlite database and ensure the table exists."""
        import sqlite3
        self.conn = sqlite3.connect(path)
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure the ``games`` table exists.

        When using SQLite the table is created with a simple schema; when using
        another backend (MySQL, Postgres, etc.) a slightly different DDL is
        issued so that the SQL is compatible.  Any errors are logged rather
        than raised so that the application can continue operating using JSON
        if the database is not usable.
        """
        if self.conn is None:
            return
        if self._is_sqlite():
            # include a uniqueness constraint so that the combination of
            # season+gameNumber+date cannot be inserted twice.  this stops an
            # identical game from appearing twice even if add_game is called
            # repeatedly or an import is run more than once.  we also add
            # paymentDate/observations columns so the UI can track when a game
            # was paid and any notes.
            sql = (
                """CREATE TABLE IF NOT EXISTS games (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        season TEXT NOT NULL,
                        gameNumber TEXT,
                        date TEXT,
                        location TEXT,
                        transportation REAL,
                        food REAL,
                        gamePayment REAL,
                        paidStatus TEXT,
                        paymentDate TEXT,
                        observations TEXT,
                        UNIQUE(season, gameNumber, date)
                    )"""
            )
        else:
            # generic SQL that should work on MySQL/Postgres; add the same
            # uniqueness constraint so the combination of
            # season+gameNumber+date cannot be duplicated.  add
            # paymentDate/observations while we're here.
            sql = (
                """CREATE TABLE IF NOT EXISTS games (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        season VARCHAR(255) NOT NULL,
                        gameNumber VARCHAR(255),
                        date VARCHAR(255),
                        location VARCHAR(255),
                        transportation DOUBLE,
                        food DOUBLE,
                        gamePayment DOUBLE,
                        paidStatus VARCHAR(50),
                        paymentDate VARCHAR(255),
                        observations TEXT,
                        UNIQUE(season, gameNumber, date)
                    )"""
            )
        try:
            if self._is_sqlite():
                # sqlite connection supports context manager that commits
                with self.conn:
                    self.conn.execute(sql)
            else:
                # other adapters (e.g. pymysql) will close the connection if
                # used as a context manager, so use a cursor instead.
                cur = self.conn.cursor()
                cur.execute(sql)
                cur.close()
        except Exception as exc:
            # log failure, mark connection unusable, and propagate state
            print(f"Warning: could not create games table: {exc}")
            self.db_error = str(exc)
            # drop the connection so callers fall back to JSON
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            return

        # after ensuring table exists, add any missing columns from older
        # installations.  create-table above will not modify an existing table,
        # so we may need to ALTER it.  we check for paymentDate/observations
        # because those were added later.
        try:
            cur = self.conn.cursor()
            existing = []
            if self._is_sqlite():
                cur.execute("PRAGMA table_info(games)")
                existing = [r[1] for r in cur.fetchall()]
            else:
                cur.execute("SHOW COLUMNS FROM games")
                existing = [r[0] for r in cur.fetchall()]
            if 'paymentDate' not in existing:
                try:
                    cur.execute("ALTER TABLE games ADD COLUMN paymentDate TEXT")
                except Exception:
                    pass
            if 'observations' not in existing:
                try:
                    cur.execute("ALTER TABLE games ADD COLUMN observations TEXT")
                except Exception:
                    pass
            if not self._is_sqlite():
                self.conn.commit()
            cur.close()
        except Exception:
            # non-fatal; table may already be up-to-date or access denied
            pass

        # Ensure existing non-sqlite databases have the expected unique
        # index shape (season, gameNumber, date). Older installations used
        # (season, gameNumber), which blocks same gameNumber on different
        # dates.
        if not self._is_sqlite():
            try:
                cur = self.conn.cursor()
                cur.execute("SHOW INDEX FROM games WHERE Non_unique = 0")
                rows = cur.fetchall()
                by_name = {}
                for r in rows:
                    # MySQL SHOW INDEX columns:
                    # 2=Key_name, 3=Seq_in_index, 4=Column_name
                    key_name = r[2]
                    seq = int(r[3])
                    col = r[4]
                    by_name.setdefault(key_name, {})[seq] = col

                needs_new = True
                drop_candidates = []
                for key_name, seq_map in by_name.items():
                    cols = [seq_map[s] for s in sorted(seq_map.keys())]
                    if cols == ['season', 'gameNumber', 'date']:
                        needs_new = False
                    elif cols == ['season', 'gameNumber']:
                        drop_candidates.append(key_name)

                for key_name in drop_candidates:
                    if key_name != 'PRIMARY':
                        cur.execute(f"ALTER TABLE games DROP INDEX {key_name}")

                if needs_new:
                    cur.execute(
                        "ALTER TABLE games ADD UNIQUE INDEX uniq_season_game_date (season, gameNumber, date)"
                    )
                self.conn.commit()
                cur.close()
            except Exception:
                # Non-fatal migration safety: if index alteration fails, app
                # still runs and existing behavior is preserved.
                pass

    def get_season_file(self, season: str) -> str:
        return os.path.join(self.data_dir, f"games_{season.replace('/', '-')}.json")

    # ------ database helpers ------------------------------------------------
    def _row_to_game(self, row: tuple) -> Dict[str, Any]:
        # row order must match the SELECT statement used below
        # support new paymentDate/observations columns if they exist
        if len(row) >= 11:
            _, season, gameNumber, date, location, transportation, food, gamePayment, paidStatus, paymentDate, observations = row
            return {
                'season': season,
                'gameNumber': gameNumber,
                'date': date,
                'location': location,
                'transportation': transportation,
                'food': food,
                'gamePayment': gamePayment,
                'paidStatus': paidStatus,
                'paymentDate': paymentDate,
                'observations': observations,
            }
        else:
            _, season, gameNumber, date, location, transportation, food, gamePayment, paidStatus = row
            return {
                'season': season,
                'gameNumber': gameNumber,
                'date': date,
                'location': location,
                'transportation': transportation,
                'food': food,
                'gamePayment': gamePayment,
                'paidStatus': paidStatus,
            }

    def _dedupe_db(self):
        """Remove duplicate season/gameNumber/date rows from the database.

        The table has a unique index, but duplicates may already exist if the
        database was written to manually or imported twice.  This method keeps
        the first row encountered and deletes the rest.
        """
        if not self.conn:
            return
        cursor = self.conn.cursor()
        placeholder = '?' if self._is_sqlite() else '%s'
        cursor.execute(f"SELECT id, season, gameNumber, date FROM games")
        seen = set()
        to_delete = []
        for _id, season, gameNumber, game_date in cursor.fetchall():
            key = (season, gameNumber, game_date)
            if key in seen:
                to_delete.append(_id)
            else:
                seen.add(key)
        for _id in to_delete:
            try:
                if self._is_sqlite():
                    with self.conn:
                        self.conn.execute("DELETE FROM games WHERE id=?", (_id,))
                else:
                    cur2 = self.conn.cursor()
                    cur2.execute("DELETE FROM games WHERE id=%s", (_id,))
                    self.conn.commit()
                    cur2.close()
            except Exception:
                pass
        cursor.close()

    def _is_sqlite(self) -> bool:
        """Return True if the current connection is an sqlite3 connection."""
        if self.conn is None:
            return False
        try:
            import sqlite3
            return isinstance(self.conn, sqlite3.Connection)
        except Exception:
            # fallback: inspect module name
            return 'sqlite' in self.conn.__class__.__module__

    def _dump_json(self, season: str):
        """Write the contents of the database for *season* back to JSON.

        Used as a backup when the database is the primary store.  This keeps
        the per‑season JSON files in sync so they reflect the last known good
        state.  After writing the season file we also update the combined
        export (`all_games.json`).
        """
        try:
            games = self._db_load_games(season)
        except Exception:
            return
        path = self.get_season_file(season)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(games, f, indent=2)
        except Exception:
            pass
        # update aggregate file as well
        self._dump_all()

    def _dump_all(self):
        """Export every game in the database across all seasons to a single
        JSON file (`all_games.json`) in the data directory.

        This is what the UI uses when you ask for "a json file with all the
        games" on startup; the file is updated on every write as a snapshot of
        the current database state.
        """
        # build a list of all games regardless of backend.  When using
        # the database we pull every row; otherwise we merge JSON files.
        games = []
        if self.conn:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT * FROM games")
                rows = cursor.fetchall()
                cursor.close()
                games = [self._row_to_game(r) for r in rows]
            except Exception:
                # couldn't read from DB, leave games empty
                pass
        else:
            # scan json season files
            for fname in os.listdir(self.data_dir):
                if not (fname.startswith('games_') and fname.endswith('.json')):
                    continue
                path = os.path.join(self.data_dir, fname)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        season_games = json.load(f)
                        if isinstance(season_games, list):
                            games.extend(season_games)
                except Exception:
                    continue
        path = os.path.join(self.data_dir, 'all_games.json')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(games, f, indent=2)
        except Exception:
            pass

    def import_json_to_db(self):
        """Copy any JSON‑stored games into the database.

        After migrating seasons we regenerate the combined backup as well.

        We maintain a separate small file listing seasons we've already
        processed so that once a season has been migrated we never re‑apply
        the JSON even if the database becomes empty again (e.g. records were
        deleted).  The JSON files themselves are left untouched for backup.
        """
        import os, json

        # helper to read/write marker file
        def _read_markers():
            marker_path = os.path.join(self.data_dir, 'imported_seasons.json')
            if os.path.exists(marker_path):
                try:
                    with open(marker_path, 'r', encoding='utf-8') as mf:
                        return set(json.load(mf))
                except Exception:
                    return set()
            return set()

        def _write_markers(seasons):
            marker_path = os.path.join(self.data_dir, 'imported_seasons.json')
            try:
                with open(marker_path, 'w', encoding='utf-8') as mf:
                    json.dump(sorted(list(seasons)), mf)
            except Exception:
                pass

        markers = _read_markers()
        # helper to create/update JSON backup from current DB state
        def _dump(season_name):
            games = self._db_load_games(season_name)
            path = self.get_season_file(season_name)
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(games, f, indent=2)
            except Exception:
                pass
        # iterate JSON files

        for fname in os.listdir(self.data_dir):
            if not (fname.startswith('games_') and fname.endswith('.json')):
                continue
            season = fname[len('games_'):-5].replace('-', '/')
            # if we’ve previously marked this season imported, double-check that
            # the current database actually contains rows for it.  markers live in
            # a global file and are not tied to a specific backend, so switching
            # from SQLite to MySQL (for example) would otherwise prevent any
            # data being migrated.  In such cases we re-import the season.
            if season in markers:
                if self.conn:
                    try:
                        placeholder = '?' if self._is_sqlite() else '%s'
                        cur = self.conn.cursor()
                        cur.execute(
                            f"SELECT COUNT(*) FROM games WHERE season={placeholder}",
                            (season,)
                        )
                        row = cur.fetchone()
                        cur.close()
                        if row and row[0] > 0:
                            # data is already present; skip import
                            continue
                        # otherwise fall through and re-import below
                    except Exception:
                        # if the query fails for any reason treat as not
                        # imported so we attempt the migration
                        pass
                else:
                    # no connection: nothing to import now, just skip
                    continue
            # load JSON content
            path = os.path.join(self.data_dir, fname)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    games = json.load(f)
            except Exception:
                games = []

            # delete any existing rows for this season before re-inserting
            try:
                placeholder = '?' if self._is_sqlite() else '%s'
                del_sql = f"DELETE FROM games WHERE season={placeholder}"
                if self._is_sqlite():
                    with self.conn:
                        self.conn.execute(del_sql, (season,))
                else:
                    cur = self.conn.cursor()
                    cur.execute(del_sql, (season,))
                    self.conn.commit()
                    cur.close()
            except Exception as e:
                print(f"Warning: could not clear season {season} ({e})")
                # continue anyway, inserts may still work

            for g in games:
                try:
                    self.add_game(season, g)
                except Exception as e:
                    print(f"Warning: failed to insert game {g} ({e})")
                    if not self.conn:
                        return
            markers.add(season)
            _write_markers(markers)
        # after import of each season update combined dump
        self._dump_all()

    def _db_load_games(self, season: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        placeholder = '?' if self._is_sqlite() else '%s'
        cursor.execute(
            f"SELECT * FROM games WHERE season = {placeholder}",
            (season,)
        )
        rows = cursor.fetchall()
        return [self._row_to_game(r) for r in rows]

    def _db_save_games(self, season: str, games: List[Dict[str, Any]]):
        # crude implementation: delete and re-insert
        placeholder = '?' if self._is_sqlite() else '%s'
        delete_sql = f"DELETE FROM games WHERE season = {placeholder}"
        insert_sql = (
            "INSERT INTO games(season,gameNumber,date,location,"
            "transportation,food,gamePayment,paidStatus,paymentDate,observations) VALUES (" +
            ",".join([placeholder]*10) + ")"
        )
        if self._is_sqlite():
            with self.conn:
                cur = self.conn.cursor()
                cur.execute(delete_sql, (season,))
                for g in games:
                    cur.execute(insert_sql, (
                        season,
                        g.get('gameNumber'),
                        g.get('date'),
                        g.get('location'),
                        g.get('transportation', 0),
                        g.get('food', 0),
                        g.get('gamePayment', 0),
                        g.get('paidStatus'),
                        g.get('paymentDate',''),
                        g.get('observations',''),
                    ))
            # keep JSON backup in sync even when DB is primary
            self._dump_json(season)
            return

        cur = self.conn.cursor()
        try:
            cur.execute(delete_sql, (season,))
            for g in games:
                cur.execute(insert_sql, (
                    season,
                    g.get('gameNumber'),
                    g.get('date'),
                    g.get('location'),
                    g.get('transportation', 0),
                    g.get('food', 0),
                    g.get('gamePayment', 0),
                    g.get('paidStatus'),
                    g.get('paymentDate',''),
                    g.get('observations',''),
                ))
            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise
        finally:
            cur.close()

        # keep JSON backup in sync even when DB is primary
        self._dump_json(season)

    # helpers for JSON fallback ------------------------------------------------
    def _json_load_games(self, season: str) -> List[Dict[str, Any]]:
        """Read season data directly from the JSON file.

        This is used when the database is unavailable so that the UI can still
        display existing games and the user can continue working.  The JSON
        files are always kept up to date by the write–through logic in
        ``save_games``/``_dump_json`` so using them as a fallback is safe.
        """
        path = self.get_season_file(season)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                games = json.load(f)
                if isinstance(games, list):
                    return games
        except Exception:
            pass
        return []

    def load_games(self, season: str) -> List[Dict[str, Any]]:
        """Return all games for a season.

        When a database connection is present we read from it; if any error
        occurs the connection is discarded and we fall back to reading the
        appropriate JSON file so that the rest of the application continues to
        work.  ``self.db_error`` is set to a human‑readable message in either
        case so the UI can display a warning.
        """
        if not self.conn:
            # already in JSON mode
            self.db_error = "no database connection"
            return self._json_load_games(season)
        try:
            games = self._db_load_games(season)
            self.db_error = None
            return games
        except Exception as exc:
            print(f"Database read error: {exc}")
            self.db_error = str(exc)
            # the connection appears to be unusable; drop it so callers reuse
            # the reliable JSON backend from this point forward.
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            return self._json_load_games(season)

    def save_games(self, season: str, games: List[Dict[str, Any]]):
        if self.conn:
            return self._db_save_games(season, games)
        file_path = self.get_season_file(season)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(games, f, indent=2)
        # even in JSON‑only mode we still write the consolidated export so
        # the user always has a single file with every game.
        self._dump_all()

    def add_game(self, season: str, game: Dict[str, Any]):
        if self.conn:
            placeholder = '?' if self._is_sqlite() else '%s'
            sql = (
                """INSERT INTO games(season,gameNumber,date,location,""" +
                "transportation,food,gamePayment,paidStatus,paymentDate,observations) VALUES (" +
                ",".join([placeholder]*10) + ")"
            )
            try:
                if self._is_sqlite():
                    with self.conn:
                        self.conn.execute(sql, (
                            season,
                            game.get('gameNumber'),
                            game.get('date'),
                            game.get('location'),
                            game.get('transportation', 0),
                            game.get('food', 0),
                            game.get('gamePayment', 0),
                            game.get('paidStatus'),
                            game.get('paymentDate',''),
                            game.get('observations',''),
                        ))
                else:
                    cur = self.conn.cursor()
                    cur.execute(sql, (
                        season,
                        game.get('gameNumber'),
                        game.get('date'),
                        game.get('location'),
                        game.get('transportation', 0),
                        game.get('food', 0),
                        game.get('gamePayment', 0),
                        game.get('paidStatus'),
                        game.get('paymentDate',''),
                        game.get('observations',''),
                    ))
                    self.conn.commit()
                    cur.close()
                    # update JSON backup for this season and aggregate file
                self._dump_json(season)
            except Exception:
                # if insert fails we leave connection open but propagate error
                raise
            return
        games = self.load_games(season)
        games.append(game)
        self.save_games(season, games)

    def update_game(self, season: str, game_number: str, updated_game: Dict[str, Any], game_date: str = None):
        if self.conn:
            placeholder = '?' if self._is_sqlite() else '%s'
            where_sql = " WHERE season=" + placeholder + " AND gameNumber=" + placeholder
            if game_date is not None:
                where_sql += " AND date=" + placeholder
            sql = (
                """UPDATE games SET date=""" + placeholder + ", location=" + placeholder + ", transportation=" + placeholder +
                ", food=" + placeholder + ", gamePayment=" + placeholder + ", paidStatus=" + placeholder +
                ", paymentDate=" + placeholder + ", observations=" + placeholder +
                where_sql
            )
            try:
                params = [
                    updated_game.get('date'),
                    updated_game.get('location'),
                    updated_game.get('transportation', 0),
                    updated_game.get('food', 0),
                    updated_game.get('gamePayment', 0),
                    updated_game.get('paidStatus'),
                    updated_game.get('paymentDate',''),
                    updated_game.get('observations',''),
                    season,
                    game_number,
                ]
                if game_date is not None:
                    params.append(game_date)
                if self._is_sqlite():
                    with self.conn:
                        self.conn.execute(sql, tuple(params))
                else:
                    cur = self.conn.cursor()
                    cur.execute(sql, tuple(params))
                    self.conn.commit()
                    cur.close()
                self._dump_json(season)
            except Exception:
                raise
            return
        games = self.load_games(season)
        for idx, g in enumerate(games):
            if g['gameNumber'] == game_number and (game_date is None or g.get('date') == game_date):
                games[idx] = updated_game
                break
        self.save_games(season, games)

    def delete_game(self, season: str, game_number: str, game_date: str = None):
        if self.conn:
            placeholder = '?' if self._is_sqlite() else '%s'
            sql = f"DELETE FROM games WHERE season={placeholder} AND gameNumber={placeholder}"
            params = [season, game_number]
            if game_date is not None:
                sql += f" AND date={placeholder}"
                params.append(game_date)
            try:
                if self._is_sqlite():
                    with self.conn:
                        self.conn.execute(sql, tuple(params))
                else:
                    cur = self.conn.cursor()
                    cur.execute(sql, tuple(params))
                    self.conn.commit()
                    cur.close()
                # update backups
                self._dump_json(season)
            except Exception as e:
                raise
            return
        games = self.load_games(season)
        games = [g for g in games if not (g['gameNumber'] == game_number and (game_date is None or g.get('date') == game_date))]
        self.save_games(season, games)

    def mark_games_paid(self, season: str, game_numbers: List[Any], payment_date: str = None):
        """Mark the specified game numbers as paid and set their payment date.

        This works whether we're using a database or plain JSON.  In DB mode we
        load the games, modify the entries and then call ``save_games`` which
        will overwrite the season.  ``payment_date`` should be an ISO-formatted
        string (YYYY-MM-DD).
        """
        effective_payment_date = payment_date or date.today().isoformat()
        games = self.load_games(season)
        changed = False
        targets_numbers = set()
        targets_pairs = set()
        for n in game_numbers:
            if isinstance(n, (tuple, list)) and len(n) >= 2:
                targets_pairs.add((str(n[0]), str(n[1])))
            elif isinstance(n, dict) and 'gameNumber' in n and 'date' in n:
                targets_pairs.add((str(n.get('gameNumber')), str(n.get('date'))))
            else:
                targets_numbers.add(str(n))
        for g in games:
            game_key = (str(g.get('gameNumber')), str(g.get('date')))
            should_update = (game_key in targets_pairs) or (str(g.get('gameNumber')) in targets_numbers)
            if should_update:
                if str(g.get('paidStatus','')).lower() != 'yes':
                    g['paidStatus'] = 'Yes'
                    changed = True
                g['paymentDate'] = effective_payment_date
                changed = True
        if changed:
            try:
                self.save_games(season, games)
            except Exception as exc:
                # if writing to the database failed for any reason, drop the
                # connection and fall back to JSON storage so the update isn't
                # lost.  ``save_games`` will raise again if the JSON write also
                # fails, which is fine since something is very wrong at that
                # point.
                print(f"Database write error during mark_games_paid: {exc}")
                self.db_error = str(exc)
                try:
                    if self.conn:
                        self.conn.close()
                except Exception:
                    pass
                self.conn = None
                # re‑attempt using JSON backend
                self.save_games(season, games)

    def search_games(self, season: str, query: str) -> List[Dict[str, Any]]:
        if self.conn:
            cursor = self.conn.cursor()
            like = f"%{query}%"
            placeholder = '?' if self._is_sqlite() else '%s'
            cursor.execute(
                f"""SELECT * FROM games WHERE season={placeholder} AND
                   (gameNumber LIKE {placeholder} OR location LIKE {placeholder} OR date LIKE {placeholder})""",
                (season, like, like, like)
            )
            return [self._row_to_game(r) for r in cursor.fetchall()]
        games = self.load_games(season)
        query = query.lower()
        return [g for g in games if query in g['gameNumber'].lower() or query in g['location'].lower() or query in g['date'].lower()]

    def get_summary(self, season: str) -> Dict[str, Any]:
        """Return totals for a season.

        Works against either the database or the JSON files.  If the database is
        unavailable we recompute the summary from the JSON fallback.  Any error
        encountered reading the database causes the connection to be dropped so
        subsequent calls don’t repeatedly fail.
        """
        if not self.conn:
            self.db_error = "no database connection"
            # compute from JSON instead of returning zeros
            games = self._json_load_games(season)
            total_paid = 0.0
            total_due_left = 0.0
            for g in games:
                try:
                    total = float(g.get('transportation', 0)) + float(g.get('food', 0)) + float(g.get('gamePayment', 0))
                except Exception:
                    total = 0.0
                if str(g.get('paidStatus','')).lower() == 'yes':
                    total_paid += total
                else:
                    total_due_left += total
            return {'total_earnings': total_paid, 'amount_left': total_due_left, 'games_count': len(games)}
        try:
            cursor = self.conn.cursor()
            placeholder = '?' if self._is_sqlite() else '%s'
            cursor.execute(
                f"""SELECT transportation, food, gamePayment, paidStatus
                       FROM games WHERE season={placeholder}""",
                (season,)
            )
            total_paid = 0.0
            total_due_left = 0.0
            rows = cursor.fetchall()
            for trans, food, pay, paid in rows:
                total = float(trans or 0) + float(food or 0) + float(pay or 0)
                if (paid or "").lower() == 'yes':
                    total_paid += total
                else:
                    total_due_left += total
            games_count = len(rows)
            self.db_error = None
            return {
                'total_earnings': total_paid,
                'amount_left': total_due_left,
                'games_count': games_count
            }
        except Exception as exc:
            print(f"Database summary error: {exc}")
            self.db_error = str(exc)
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            # fall back to JSON summary
            return self.get_summary(season)
