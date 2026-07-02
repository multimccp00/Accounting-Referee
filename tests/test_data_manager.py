import pytest
import pymysql
from datetime import date
from app.game_tracking.manager import GameDataManager


def test_json_fallback_when_db_read_fails(tmp_path, monkeypatch):
    # create a manager pointing at a temporary data directory
    mgr = GameDataManager()
    # ensure there's a season file
    season_file = tmp_path / "games_2025-2026.json"
    season_file.write_text("[]")  # empty list
    mgr.data_dir = str(tmp_path)

    # simulate a connection that raises an error when executing any query
    class BadCursor:
        def execute(self, *args, **kwargs):
            raise pymysql.err.OperationalError(0, "")

        def fetchall(self):
            return []

        def close(self):
            pass

    class BadConn:
        def cursor(self):
            return BadCursor()

        def close(self):
            pass

    mgr.conn = BadConn()

    # load_games should not crash and should read from JSON
    games = mgr.load_games("2025/2026")
    assert games == []
    assert mgr.conn is None  # connection should be dropped
    assert mgr.db_error.startswith("(0,")

    # summary should compute using JSON (empty list -> zero values)
    summary = mgr.get_summary("2025/2026")
    assert summary == {'total_earnings': 0.0, 'amount_left': 0.0, 'games_count': 0}


def test_mark_games_paid_uses_json_on_write_error(tmp_path, monkeypatch):
    mgr = GameDataManager()
    mgr.data_dir = str(tmp_path)
    # create some JSON data
    mgr.save_games("2025/2026", [{
        "season": "2025/2026",
        "gameNumber": "1",
        "transportation": 10,
        "food": 0,
        "gamePayment": 20,
        "paidStatus": "No",
    }])

    # first mark should succeed in JSON mode
    mgr.mark_games_paid("2025/2026", ["1"], "2026-03-03")
    assert mgr.load_games("2025/2026")[0]['paidStatus'] == 'Yes'

    # now simulate a write failure by forcing save_games to raise
    def bad_save(season, games):
        raise pymysql.err.OperationalError(0, "write failed")

    monkeypatch.setattr(mgr, 'save_games', bad_save)
    # restore connection to hit error path
    mgr.conn = object()
    # calling mark_games_paid should drop conn and still raise due to JSON save
    with pytest.raises(pymysql.err.OperationalError):
        mgr.mark_games_paid("2025/2026", ["1"], "2026-03-04")


def test_mark_selected_paid_shows_warning_for_db_loss(tmp_path, monkeypatch):
    # create a minimal app instance and simulate DB failure during mark
    import tkinter as tk
    from app.ui.app import RefereeApp

    root = tk.Tk()
    root.withdraw()
    app = RefereeApp(root)
    # prepare one game in JSON so selection is meaningful
    app.manager.data_dir = str(tmp_path)
    app.manager.save_games("2025/2026", [{
        "season": "2025/2026",
        "gameNumber": "1",
        "transportation": 5,
        "food": 0,
        "gamePayment": 10,
        "paidStatus": "No",
    }])
    app.selected_season.set("2025/2026")
    app.load_games()

    # patch the manager to raise on mark_games_paid and then drop connection
    def bad_mark(season, nums, date):
        app.manager.conn = None
        app.manager.db_error = "simulated failure"
        raise pymysql.err.OperationalError(0, "boom")
    monkeypatch.setattr(app.manager, 'mark_games_paid', bad_mark)

    # record messagebox calls and skip confirmation dialog
    called = {'warn': False, 'err': False}
    monkeypatch.setattr('tkinter.messagebox.showwarning', lambda *args, **kwargs: called.update(warn=True))
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *args, **kwargs: called.update(err=True))
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *args, **kwargs: True)

    # also patch the existing tree widget so selection returns one item
    # and item() returns our test game number.  keep the real widget so
    # load_games/refresh_table can still manipulate headings etc.
    orig_tree = app.tree
    orig_tree.selection = lambda: ['id']
    orig_tree.item = lambda iid: {'values': [None, '1']}

    # call method under test
    app.mark_selected_paid()
    assert called['err'] is True
    # after failure load_games should have been invoked and backend_label updated
    assert 'JSON' in app.backend_label.cget('text')
    root.destroy()


def test_db_save_games_non_sqlite_commits_without_context_manager(monkeypatch):
    mgr = GameDataManager()

    class FakeCursor:
        def __init__(self):
            self.executed = []
            self.closed = False

        def execute(self, sql, params=None):
            self.executed.append((sql, params))

        def close(self):
            self.closed = True

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.commits = 0
            self.rollbacks = 0

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

    fake_conn = FakeConn()
    mgr.conn = fake_conn
    dump_called = {'count': 0}

    # force non-sqlite branch explicitly
    monkeypatch.setattr(mgr, '_is_sqlite', lambda: False)
    monkeypatch.setattr(mgr, '_dump_json', lambda season: dump_called.__setitem__('count', dump_called['count'] + 1))

    games = [
        {
            'season': '2025/2026',
            'gameNumber': '123',
            'date': '2026-03-03',
            'location': 'TEST',
            'transportation': 1,
            'food': 2,
            'gamePayment': 3,
            'paidStatus': 'No',
            'paymentDate': '',
            'observations': ''
        }
    ]

    mgr._db_save_games('2025/2026', games)

    assert fake_conn.commits == 1
    assert fake_conn.rollbacks == 0
    assert fake_conn.cursor_obj.closed is True
    assert len(fake_conn.cursor_obj.executed) == 2
    assert dump_called['count'] == 1


def test_mark_games_paid_targets_by_number_and_date():
    mgr = GameDataManager()
    # force JSON mode for deterministic in-memory-like behavior
    mgr.conn = None
    season = '2025/2026'

    mgr.save_games(season, [
        {
            'season': season,
            'gameNumber': '999',
            'date': '2026-01-01',
            'location': 'A',
            'transportation': 0,
            'food': 0,
            'gamePayment': 10,
            'paidStatus': 'No',
            'paymentDate': ''
        },
        {
            'season': season,
            'gameNumber': '999',
            'date': '2026-01-08',
            'location': 'B',
            'transportation': 0,
            'food': 0,
            'gamePayment': 12,
            'paidStatus': 'No',
            'paymentDate': ''
        }
    ])

    # Mark only one of the duplicate-number games by using (number, date)
    mgr.mark_games_paid(season, [('999', '2026-01-08')], '2026-03-03')
    games = mgr.load_games(season)

    by_date = {g['date']: g for g in games if g.get('gameNumber') == '999'}
    assert by_date['2026-01-01']['paidStatus'] == 'No'
    assert by_date['2026-01-08']['paidStatus'] == 'Yes'


def test_mark_games_paid_defaults_payment_date_to_today():
    mgr = GameDataManager()
    mgr.conn = None
    season = '2025/2026'
    today = date.today().isoformat()

    mgr.save_games(season, [
        {
            'season': season,
            'gameNumber': '111',
            'date': '2026-02-01',
            'location': 'T',
            'transportation': 0,
            'food': 0,
            'gamePayment': 10,
            'paidStatus': 'No',
            'paymentDate': None,
            'observations': ''
        }
    ])

    mgr.mark_games_paid(season, [('111', '2026-02-01')], None)
    game = mgr.load_games(season)[0]
    assert game['paidStatus'] == 'Yes'
    assert game['paymentDate'] == today


def test_update_game_json_handles_string_int_match(tmp_path):
    mgr = GameDataManager()
    mgr.data_dir = str(tmp_path)
    mgr.conn = None

    # legacy JSON may store gameNumber as int; ensure update still works
    mgr.save_games('2025/2026', [{
        'season': '2025/2026',
        'gameNumber': 1,
        'date': '2026-03-22',
        'location': 'A',
        'transportation': 10,
        'food': 5,
        'gamePayment': 20,
        'paidStatus': 'No',
        'paymentDate': '',
        'observations': ''
    }])

    mgr.update_game('2025/2026', '1', {
        'season': '2025/2026',
        'gameNumber': '1',
        'date': '2026-03-23',
        'location': 'B',
        'transportation': 10,
        'food': 5,
        'gamePayment': 20,
        'paidStatus': 'No',
        'paymentDate': '',
        'observations': ''
    }, '2026-03-22')

    updated = mgr.load_games('2025/2026')[0]
    assert updated['date'] == '2026-03-23'
    assert updated['location'] == 'B'


def test_update_game_sql_null_game_number_matches_blank_key(tmp_path):
    db_path = tmp_path / 'test.db'
    mgr = GameDataManager(db_path=str(db_path))
    # Ensure DB begins empty (the app imports repo JSON by default to non-temp data dir)
    if mgr.conn:
        cur = mgr.conn.cursor()
        cur.execute("DELETE FROM games")
        if not mgr._is_sqlite():
            mgr.conn.commit()
        cur.close()

    # insert a row without gameNumber (NULL in DB)
    mgr.add_game('2025/2026', {
        'season': '2025/2026',
        'gameNumber': None,
        'date': '2026-03-20',
        'location': 'Home',
        'transportation': 0,
        'food': 0,
        'gamePayment': 10,
        'paidStatus': 'No',
        'paymentDate': '',
        'observations': ''
    })

    # update via empty key path (UI that loads empty string)
    mgr.update_game('2025/2026', '', {
        'season': '2025/2026',
        'gameNumber': '123',
        'date': '2026-03-20',
        'location': 'Away',
        'transportation': 0,
        'food': 0,
        'gamePayment': 10,
        'paidStatus': 'Yes',
        'paymentDate': '2026-03-21',
        'observations': 'updated'
    }, '2026-03-20')

    games = mgr.load_games('2025/2026')
    assert len(games) == 1
    assert games[0]['gameNumber'] == '123'
    assert games[0]['location'] == 'Away'
    assert games[0]['paidStatus'] == 'Yes'


