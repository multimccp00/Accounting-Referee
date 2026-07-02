"""
Game data persistence and management.

Provides GameDataManager for storing and retrieving game records using either
a database (SQLite, MySQL, PostgreSQL) or JSON files as fallback.
Handles schema creation, data synchronization, and automatic migration from JSON.
"""
import json
import os
from datetime import date
from typing import List, Dict, Any

from config.settings import DATA_DIR


class GameDataManager:
    """Manages game records across multiple persistence backends.

    Supports both database (SQLite, MySQL, PostgreSQL) and JSON file storage.
    Automatically falls back to JSON if database becomes unavailable.
    Maintains a combined 'all_games.json' export for easy data access.

    Attributes:
        data_dir: Directory where JSON files are stored.
        db_path: Path to SQLite database, if using local database.
        conn: Active database connection, or None if using JSON-only mode.
        db_error: Error message if database operations failed.
    """
    def __init__(self, db_path: str = None, db_conn=None):
        """Initialize the game data manager.

        Attempts to set up database connection if provided, otherwise falls back
        to JSON-only mode. Imports any existing JSON data into the database and
        generates a combined export file.

        Args:
            db_path: Path to SQLite database file to create or open.
            db_conn: Existing database connection object (e.g., pymysql, psycopg2).
                     Ignored if db_path is also provided.
        """
        os.makedirs(DATA_DIR, exist_ok=True)
        self.data_dir = DATA_DIR
        self.db_path = db_path
        self.conn = None
        self.db_error = None

        if db_conn is not None:
            self.conn = db_conn
            self._ensure_schema()
        elif db_path:
            self._init_db(db_path)

        if self.conn:
            try:
                self.import_json_to_db()
            except Exception as e:
                print(f"Warning during JSON->DB import: {e}")
                self.db_error = str(e)
                self.conn = None

        if self.conn:
            self._dedupe_db()

        self._dump_all()

    def _init_db(self, path: str):
        """Create/open the sqlite database and ensure the table exists."""
        import sqlite3
        self.conn = sqlite3.connect(path)
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure the ``games`` table exists."""
        if self.conn is None:
            return
        if self._is_sqlite():
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
                with self.conn:
                    self.conn.execute(sql)
            else:
                cur = self.conn.cursor()
                cur.execute(sql)
                cur.close()
        except Exception as exc:
            print(f"Warning: could not create games table: {exc}")
            self.db_error = str(exc)
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            return

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
            pass

        if not self._is_sqlite():
            try:
                cur = self.conn.cursor()
                cur.execute("SHOW INDEX FROM games WHERE Non_unique = 0")
                rows = cur.fetchall()
                by_name = {}
                for r in rows:
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
                pass

    def get_season_file(self, season: str) -> str:
        return os.path.join(self.data_dir, f"games_{season.replace('/', '-')}.json")

    def _row_to_game(self, row: tuple) -> Dict[str, Any]:
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
        """Remove duplicate season/gameNumber/date rows from the database."""
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
            return 'sqlite' in self.conn.__class__.__module__

    def _dump_json(self, season: str):
        """Write the contents of the database for *season* back to JSON."""
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
        self._dump_all()

    def _dump_all(self):
        """Export every game in the database across all seasons to a single JSON file."""
        games = []
        if self.conn:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT * FROM games")
                rows = cursor.fetchall()
                cursor.close()
                games = [self._row_to_game(r) for r in rows]
            except Exception:
                pass
        else:
            # Only scan JSON files if database is unavailable
            try:
                json_files = [
                    fname for fname in os.listdir(self.data_dir)
                    if fname.startswith('games_') and fname.endswith('.json')
                ]
            except Exception:
                json_files = []

            for fname in json_files:
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
        """Copy any JSON‑stored games into the database."""
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

        def _dump(season_name):
            games = self._db_load_games(season_name)
            path = self.get_season_file(season_name)
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(games, f, indent=2)
            except Exception:
                pass

        for fname in os.listdir(self.data_dir):
            if not (fname.startswith('games_') and fname.endswith('.json')):
                continue
            season = fname[len('games_'):-5].replace('-', '/')
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
                            continue
                    except Exception:
                        pass
                else:
                    continue
            path = os.path.join(self.data_dir, fname)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    games = json.load(f)
            except Exception:
                games = []

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

            for g in games:
                try:
                    self.add_game(season, g)
                except Exception as e:
                    print(f"Warning: failed to insert game {g} ({e})")
                    if not self.conn:
                        return
            markers.add(season)
            _write_markers(markers)
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

        self._dump_json(season)

    def _json_load_games(self, season: str) -> List[Dict[str, Any]]:
        """Read season data directly from the JSON file."""
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
        """Return all games for a season."""
        if not self.conn:
            self.db_error = "no database connection"
            return self._json_load_games(season)
        try:
            games = self._db_load_games(season)
            self.db_error = None
            return games
        except Exception as exc:
            print(f"Database read error: {exc}")
            self.db_error = str(exc)
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
                self._dump_json(season)
            except Exception:
                raise
            return
        games = self.load_games(season)
        games.append(game)
        self.save_games(season, games)

    def import_excel(self, excel_path: str) -> Dict[str, Any]:
        """Import games from Excel file, adding only non-duplicate games.

        Reads games from Excel and adds them to JSON/database if they don't already exist.
        Checks for duplicates by game number + date combination.

        Args:
            excel_path: Path to the Excel file (games.xlsx)

        Returns:
            Dictionary with import results: {
                'total_in_excel': int,
                'already_existing': int,
                'added': int,
                'errors': list
            }
        """
        try:
            import openpyxl
        except ImportError:
            return {
                'total_in_excel': 0,
                'already_existing': 0,
                'added': 0,
                'errors': ['openpyxl not installed. Run: pip install openpyxl']
            }

        from datetime import datetime
        from pathlib import Path

        results = {
            'total_in_excel': 0,
            'already_existing': 0,
            'added': 0,
            'errors': []
        }

        try:
            # Load Excel
            excel_file = Path(excel_path)
            if not excel_file.exists():
                results['errors'].append(f"Excel file not found: {excel_path}")
                return results

            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active

            # Read games from Excel
            excel_games = []
            for row_num in range(4, 100):  # Start from row 4 (after headers)
                row = ws[row_num]
                game_num = row[1].value  # Column B

                if not game_num or str(game_num).lower().strip() in ['totals', 'none', '']:
                    break

                # Extract fields
                date_val = row[0].value
                if isinstance(date_val, datetime):
                    date_val = date_val.strftime('%Y-%m-%d')

                game = {
                    'season': '2025/2026',
                    'gameNumber': str(game_num),
                    'date': str(date_val) if date_val else '',
                    'location': str(row[2].value) if row[2].value else '',
                    'transportation': float(row[3].value) if row[3].value else 0.0,
                    'food': float(row[4].value) if row[4].value else 0.0,
                    'gamePayment': float(row[5].value) if row[5].value else 0.0,
                    'paidStatus': str(row[6].value) if row[6].value else '',
                    'paymentDate': None,
                    'observations': str(row[8].value) if row[8].value else None
                }

                if row[7].value:
                    payment_date = row[7].value
                    if isinstance(payment_date, datetime):
                        payment_date = payment_date.strftime('%Y-%m-%d')
                    game['paymentDate'] = str(payment_date)

                excel_games.append(game)

            results['total_in_excel'] = len(excel_games)

            # Get existing games
            all_games = self.get_all_games() or []
            existing_combos = set((str(g.get('gameNumber')), g.get('date')) for g in all_games)

            # Find games to add
            added_count = 0
            for game in excel_games:
                combo = (game['gameNumber'], game['date'])

                if combo in existing_combos:
                    results['already_existing'] += 1
                else:
                    # Add to database/JSON
                    season = game['season']
                    try:
                        self.add_game(season, game)
                        existing_combos.add(combo)
                        added_count += 1
                    except Exception as e:
                        error_msg = str(e)
                        results['errors'].append(f"Game {game['gameNumber']} ({game['date']}): {error_msg}")

            results['added'] = added_count

            if added_count > 0:
                self._dump_all()

            return results

        except Exception as exc:
            results['errors'].append(str(exc))
            return results

    def update_game(self, season: str, game_number: str, updated_game: Dict[str, Any], game_date: str = None):
        if self.conn:
            placeholder = '?' if self._is_sqlite() else '%s'
            quote = '"' if self._is_sqlite() else '`'

            if game_number is None or str(game_number).strip() == '':
                where_sql = f" WHERE season={placeholder} AND (" \
                            f"{quote}gameNumber{quote} IS NULL OR {quote}gameNumber{quote}={placeholder})"
            else:
                where_sql = f" WHERE season={placeholder} AND {quote}gameNumber{quote}={placeholder}"

            if game_date is not None:
                where_sql += f" AND {quote}date{quote}={placeholder}"

            sql = (
                f"UPDATE games SET {quote}gameNumber{quote}={placeholder}, {quote}date{quote}={placeholder}, {quote}location{quote}={placeholder}, {quote}transportation{quote}={placeholder},"
                f" {quote}food{quote}={placeholder}, {quote}gamePayment{quote}={placeholder}, {quote}paidStatus{quote}={placeholder},"
                f" {quote}paymentDate{quote}={placeholder}, {quote}observations{quote}={placeholder}"
                + where_sql
            )

            try:
                params = [
                    updated_game.get('gameNumber'),
                    updated_game.get('date'),
                    updated_game.get('location'),
                    updated_game.get('transportation', 0),
                    updated_game.get('food', 0),
                    updated_game.get('gamePayment', 0),
                    updated_game.get('paidStatus'),
                    updated_game.get('paymentDate', ''),
                    updated_game.get('observations', ''),
                    season,
                ]

                if game_number is None or str(game_number).strip() == '':
                    params.append('')
                else:
                    params.append(game_number)

                if game_date is not None:
                    params.append(game_date)
                if self._is_sqlite():
                    with self.conn:
                        cur = self.conn.execute(sql, tuple(params))
                        if cur.rowcount == 0:
                            print(f"Warning: update_game did not match row for {season}/{game_number}/{game_date}")
                else:
                    cur = self.conn.cursor()
                    cur.execute(sql, tuple(params))
                    if cur.rowcount == 0:
                        print(f"Warning: update_game did not match row for {season}/{game_number}/{game_date}")
                    self.conn.commit()
                    cur.close()
                self._dump_json(season)
            except Exception:
                raise
            return
        games = self.load_games(season)
        updated = False
        for idx, g in enumerate(games):
            if str(g.get('gameNumber', '')) == str(game_number) and (game_date is None or str(g.get('date', '')) == str(game_date)):
                games[idx] = updated_game
                updated = True
                break
        if not updated:
            print(f"Warning: update_game JSON fallback did not find game {season}/{game_number}/{game_date}")
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
                self._dump_json(season)
            except Exception as e:
                raise
            return
        games = self.load_games(season)
        games = [g for g in games if not (g['gameNumber'] == game_number and (game_date is None or g.get('date') == game_date))]
        self.save_games(season, games)

    def mark_games_paid(self, season: str, game_numbers: List[Any], payment_date: str = None):
        """Mark the specified game numbers as paid and set their payment date."""
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
                print(f"Database write error during mark_games_paid: {exc}")
                self.db_error = str(exc)
                try:
                    if self.conn:
                        self.conn.close()
                except Exception:
                    pass
                self.conn = None
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
        """Return totals for a season."""
        if not self.conn:
            self.db_error = "no database connection"
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
            return self.get_summary(season)
