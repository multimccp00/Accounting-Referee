"""
Mobile app using plain Kivy (no KivyMD) for reliable Android builds.
Handball-themed UI with a slide-out hamburger drawer.
Shares data models and backend logic with the Tkinter version.
"""
import os
import random
import sys
from pathlib import Path
from datetime import date
import json

from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.game_tracking.manager import GameDataManager

# --- Handball-themed palette ---
# Court blue background, teal court-line accent, referee-yellow for actions.
C_BG        = (0.06, 0.10, 0.17, 1)   # deep court navy
C_BG2       = (0.09, 0.14, 0.22, 1)   # slightly lighter panel
C_SURFACE   = (0.12, 0.18, 0.28, 1)   # card surface
C_SURFACE_2 = (0.16, 0.23, 0.34, 1)   # raised / selected
C_PRIMARY   = (0.00, 0.65, 0.69, 1)   # teal (court lines)
C_PRIMARY_DK= (0.00, 0.47, 0.51, 1)
C_YELLOW    = (0.98, 0.78, 0.12, 1)   # referee yellow card
C_YELLOW_DK = (0.85, 0.64, 0.05, 1)
C_TEXT      = (0.96, 0.97, 0.98, 1)
C_TEXT_2    = (0.62, 0.70, 0.80, 1)
C_GREEN     = (0.18, 0.71, 0.42, 1)
C_RED       = (0.91, 0.30, 0.31, 1)
C_LINE      = (0.20, 0.30, 0.42, 1)   # subtle border line
C_SCRIM     = (0, 0, 0, 0.55)


def _load_db_config():
    """Read DB_CONFIG from db_connection.py.

    On desktop it's at the project root; inside the Android APK the bundled
    files live next to the app's main.py. Try importing it directly first
    (it's on sys.path in the APK), then fall back to scanning likely paths.
    """
    # 1) Direct import — works in the APK where db_connection.py is on sys.path.
    try:
        import db_connection
        cfg = getattr(db_connection, 'DB_CONFIG', None)
        if isinstance(cfg, dict) and cfg.get('host'):
            return cfg
    except Exception:
        pass

    # 2) Scan candidate locations by file path (desktop + Android variants).
    import importlib.util
    candidates = [
        Path(__file__).parent.parent.parent / 'db_connection.py',   # desktop root
        Path(__file__).parent.parent / 'db_connection.py',
        Path(__file__).parent / 'db_connection.py',
    ]
    # Android: the app dir (where main.py entry point lives)
    try:
        android_app = os.environ.get('ANDROID_APP_PATH') or os.getcwd()
        candidates.append(Path(android_app) / 'db_connection.py')
    except Exception:
        pass
    for cfg_file in candidates:
        try:
            if cfg_file.exists():
                spec = importlib.util.spec_from_file_location('db_connection', str(cfg_file))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                cfg = getattr(mod, 'DB_CONFIG', None)
                if isinstance(cfg, dict) and cfg.get('host'):
                    return cfg
        except Exception:
            continue
    return None


def load_handball_dataset(json_path):
    """Load the pre-built handball dataset from JSON (no PDF deps)."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading handball dataset: {e}")
        return {}


def label(text, color=C_TEXT, bold=False, font_size=16, halign="left", valign="middle", **kw):
    lbl = Label(text=text, color=color, bold=bold, font_size=dp(font_size),
                halign=halign, valign=valign, markup=True, **kw)
    lbl.bind(size=lambda l, s: setattr(l, 'text_size', (l.width, l.height)))
    return lbl


def wrap_label(text, color=C_TEXT, bold=False, font_size=16, **kw):
    """A label that wraps text and grows its height to fit the content."""
    lbl = Label(text=text, color=color, bold=bold, font_size=dp(font_size),
                halign="left", valign="top", markup=True, size_hint_y=None, **kw)
    # text_size width = own width, height free -> texture_size reflects wrapped height
    lbl.bind(width=lambda l, w: setattr(l, 'text_size', (w, None)))
    lbl.bind(texture_size=lambda l, ts: setattr(l, 'height', ts[1]))
    return lbl


class Card(BoxLayout):
    """Rounded surface container with an optional left accent stripe."""
    def __init__(self, bg=C_SURFACE, radius=14, border=True, accent=None, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._color = Color(*bg)
            self._rect = RoundedRectangle(radius=[radius])
            if border:
                self._bcol = Color(*C_LINE)
                self._border = Line(width=1.1)
            if accent:
                self._acol = Color(*accent)
                self._accent = RoundedRectangle(radius=[radius, 0, 0, radius])
        self._radius = radius
        self._has_border = border
        self._has_accent = accent is not None
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        if self._has_border:
            r = self._radius
            x, y, w, h = self.x, self.y, self.width, self.height
            self._border.rounded_rectangle = (x, y, w, h, r)
        if self._has_accent:
            self._accent.pos = self.pos
            self._accent.size = (dp(5), self.height)


class PrimaryButton(Button):
    """Filled rounded button."""
    def __init__(self, bg=C_YELLOW, fg=(0.08, 0.10, 0.15, 1), radius=12, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.color = fg
        self.bold = True
        self.selected = False
        self._radius = radius
        with self.canvas.before:
            self._color = Color(*bg)
            self._rect = RoundedRectangle(radius=[radius])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_bg(self, rgba):
        self._color.rgba = rgba


class OptionButton(Button):
    """Selectable answer option, left-aligned, toggles teal when chosen."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.color = C_TEXT
        self.halign = "left"
        self.valign = "middle"
        self.selected = False
        with self.canvas.before:
            self._color = Color(*C_SURFACE)
            self._rect = RoundedRectangle(radius=[10])
            self._bcol = Color(*C_LINE)
            self._border = Line(width=1.1)
        self.bind(pos=self._sync, size=self._sync, texture_size=self._fit)

    def _sync(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, 10)
        self.text_size = (self.width - dp(24), None)
        self.padding_x = dp(12)

    def _fit(self, *a):
        self.height = max(dp(50), self.texture_size[1] + dp(22))

    def set_selected(self, val):
        self.selected = val
        self._color.rgba = C_PRIMARY if val else C_SURFACE
        self._bcol.rgba = C_PRIMARY if val else C_LINE


class GameRow(Button):
    """A tappable game card showing two lines of info with an accent stripe."""
    def __init__(self, game, accent, amount, paid, on_tap=None, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.size_hint_y = None
        self.height = dp(76)
        self.text = ''
        if on_tap:
            self.bind(on_release=lambda x: on_tap())
        line1 = f"Game {game.get('gameNumber','-')}  -  {game.get('location','-')}"
        line2 = f"{game.get('date','-')}    {amount:.2f} EUR    {'Paid' if paid else 'Unpaid'}"
        with self.canvas.before:
            self._c = Color(*C_SURFACE)
            self._rect = RoundedRectangle(radius=[12])
            self._bc = Color(*C_LINE)
            self._border = Line(width=1.1)
            self._ac = Color(*accent)
            self._accent = RoundedRectangle(radius=[12, 0, 0, 12])
        # Two text labels drawn as children
        self._l1 = Label(text=line1, color=C_TEXT, bold=True, font_size=dp(15),
                         halign="left", valign="middle", markup=True)
        self._l2 = Label(text=line2, color=C_TEXT_2, font_size=dp(12),
                         halign="left", valign="middle")
        self.add_widget(self._l1)
        self.add_widget(self._l2)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *a):
        self._rect.pos = self.pos; self._rect.size = self.size
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, 12)
        self._accent.pos = self.pos; self._accent.size = (dp(5), self.height)
        px = self.x + dp(16)
        self._l1.text_size = (self.width - dp(28), None)
        self._l2.text_size = (self.width - dp(28), None)
        self._l1.pos = (px, self.y + self.height/2 - dp(2))
        self._l1.size = (self.width - dp(28), dp(24))
        self._l2.pos = (px, self.y + self.height/2 - dp(26))
        self._l2.size = (self.width - dp(28), dp(20))


class RuleRow(Button):
    """A tappable rulebook entry: section id + title with an accent stripe."""
    def __init__(self, rule, on_tap=None, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.size_hint_y = None
        self.height = dp(52)
        self.text = ''
        if on_tap:
            self.bind(on_release=lambda x: on_tap())
        txt = f"{rule.get('section_id','-')}   {rule.get('title','-')}"
        with self.canvas.before:
            self._c = Color(*C_SURFACE)
            self._rect = RoundedRectangle(radius=[12])
            self._bc = Color(*C_LINE)
            self._border = Line(width=1.1)
            self._ac = Color(*C_PRIMARY)
            self._accent = RoundedRectangle(radius=[12, 0, 0, 12])
        self._lbl = Label(text=txt, color=C_TEXT, bold=True, font_size=dp(14),
                          halign="left", valign="middle", markup=True)
        self.add_widget(self._lbl)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *a):
        self._rect.pos = self.pos; self._rect.size = self.size
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, 12)
        self._accent.pos = self.pos; self._accent.size = (dp(5), self.height)
        self._lbl.text_size = (self.width - dp(28), None)
        self._lbl.pos = (self.x + dp(16), self.y)
        self._lbl.size = (self.width - dp(28), self.height)


class PickerField(Button):
    """A button that opens a centered modal scroll-list to pick a value.

    Replaces Kivy's Spinner, whose dropdown mispositions on Android. The modal
    is always centered on screen, so it's never disconnected from the control.
    """
    def __init__(self, values, value=None, title="Select", **kwargs):
        super().__init__(**kwargs)
        self.values = list(values)
        self.title = title
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.color = C_TEXT
        self.text = value if value in self.values else (self.values[0] if self.values else "")
        with self.canvas.before:
            self._c = Color(*C_SURFACE)
            self._rect = RoundedRectangle(radius=[8])
            self._bc = Color(*C_LINE)
            self._bd = Line(width=1.1)
        self.bind(pos=self._sync, size=self._sync)
        self.bind(on_release=lambda x: self._open())

    def _sync(self, *a):
        self._rect.pos = self.pos; self._rect.size = self.size
        self._bd.rounded_rectangle = (self.x, self.y, self.width, self.height, 8)

    def _open(self):
        modal = ModalView(size_hint=(0.7, 0.7), background_color=(0, 0, 0, 0.6))
        box = BoxLayout(orientation="vertical")
        with box.canvas.before:
            Color(*C_BG2)
            r = RoundedRectangle(radius=[14])
        box.bind(pos=lambda *a: setattr(r, 'pos', box.pos), size=lambda *a: setattr(r, 'size', box.size))
        hdr = Label(text=f"[b]{self.title}[/b]", markup=True, color=C_TEXT,
                    size_hint_y=None, height=dp(46), font_size=dp(17))
        box.add_widget(hdr)
        sv = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(2), padding=dp(6))
        grid.bind(minimum_height=grid.setter("height"))
        for v in self.values:
            sel = (v == self.text)
            item = Button(text=v, size_hint_y=None, height=dp(46), font_size=dp(16),
                          background_normal='', background_down='',
                          background_color=(C_PRIMARY if sel else (0, 0, 0, 0)),
                          color=C_TEXT)
            def pick(_b, val=v):
                self.text = val
                modal.dismiss()
            item.bind(on_release=pick)
            grid.add_widget(item)
        sv.add_widget(grid)
        box.add_widget(sv)
        modal.add_widget(box)
        modal.open()


class RootScreen(Screen):
    pass


class RefereeApp(App):
    def build(self):
        if Window is not None:
            try:
                Window.clearcolor = C_BG
            except Exception:
                pass

        self.season = "2025/2026"
        # Connect to the SAME MySQL server the desktop app uses, so games
        # added/edited on the phone update the shared database. Falls back to
        # local JSON only if the server is unreachable.
        self.manager_db = self._connect_db()
        dataset_path = str(Path(__file__).parent.parent.parent / "data" / "handball_content.json")
        self.handball_dataset = load_handball_dataset(dataset_path)
        self.quiz_questions = self.handball_dataset.get("questions", []) if self.handball_dataset else []

        self.test_progress = {'stats': {'attempts': 0, 'correct': 0}, 'sessions': [], 'qod_cache': {}, 'questions': {}}
        self._load_test_progress()
        self.test_attempts = int(self.test_progress.get('stats', {}).get('attempts', 0))
        self.test_correct = int(self.test_progress.get('stats', {}).get('correct', 0))

        self.current_test_questions = []
        self.current_test_index = 0
        self.current_test_question = None
        self.session_results = {}
        self.session_answers = {}
        self._test_finished = True
        self._test_timer_ev = None
        self.qod_question = None

        # Root is a FloatLayout so the drawer can overlay the screens.
        self.root_layout = FloatLayout()

        self.sm = ScreenManager()
        self.sm.size_hint = (1, 1)
        for name in ["Home", "Games", "Tests", "TestTaking", "Review", "QOD", "Rulebook", "Stats", "GameForm", "RuleView"]:
            self.sm.add_widget(RootScreen(name=name))
        self.root_layout.add_widget(self.sm)

        self._build_drawer()

        self._render_home()
        self._render_games()
        self._render_tests()
        self._render_rulebook()
        self._render_stats()
        self._build_test_taking_screen()
        self._build_qod_screen()
        self.sm.current = "Home"
        return self.root_layout

    # ---------------- Drawer ----------------
    def _build_drawer(self):
        # Scrim (tap to close). Built once, but ONLY added to the layout while
        # the drawer is open — a permanently-present full-screen widget (even
        # disabled/transparent) swallows touches meant for the content behind it.
        self.scrim = Button(background_normal='', background_down='',
                            background_color=C_SCRIM, size_hint=(1, 1))
        self.scrim.bind(on_release=lambda x: self.close_drawer())

        # Drawer panel. Also only added to the layout while open.
        self.drawer_w = dp(280)
        self.drawer = BoxLayout(orientation="vertical", size_hint=(None, 1),
                                pos_hint={"x": 0, "top": 1}, width=self.drawer_w)
        with self.drawer.canvas.before:
            Color(*C_BG2)
            self._drawer_bg = Rectangle()
        self.drawer.bind(pos=self._sync_drawer_bg, size=self._sync_drawer_bg)

        # Drawer header
        header = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(120), padding=dp(18))
        with header.canvas.before:
            Color(*C_PRIMARY_DK)
            self._dh_bg = Rectangle()
        header.bind(pos=lambda *a: setattr(self._dh_bg, 'pos', header.pos),
                    size=lambda *a: setattr(self._dh_bg, 'size', header.size))
        header.add_widget(label("[b]Referee[/b]", font_size=24, size_hint_y=None, height=dp(34)))
        header.add_widget(label("Handball Tracker", color=C_TEXT_2, font_size=13, size_hint_y=None, height=dp(20)))
        self.drawer.add_widget(header)

        items = [("Dashboard", "Home"), ("Games", "Games"), ("Tests", "Tests"),
                 ("Question of the Day", "QOD"), ("Rulebook", "Rulebook"), ("Statistics", "Stats")]
        menu = BoxLayout(orientation="vertical", padding=(dp(10), dp(10)), spacing=dp(4))
        for text, target in items:
            b = Button(text=text, halign="left", valign="middle",
                       background_normal='', background_down='',
                       background_color=(0, 0, 0, 0), color=C_TEXT,
                       size_hint_y=None, height=dp(50), font_size=dp(16))
            b.bind(size=lambda l, s: setattr(l, 'text_size', (l.width - dp(20), l.height)))
            b.bind(on_release=lambda x, t=target: self._drawer_nav(t))
            b.padding_x = dp(14)
            menu.add_widget(b)
        menu.add_widget(Widget())  # filler
        self.drawer.add_widget(menu)
        # NOTE: scrim and drawer are NOT added here. They're added to the layout
        # only while open (see open_drawer) so they never block content touches.
        self._drawer_open = False

    def _sync_drawer_bg(self, *a):
        self._drawer_bg.pos = self.drawer.pos
        self._drawer_bg.size = self.drawer.size

    def toggle_drawer(self):
        if self._drawer_open:
            self.close_drawer()
        else:
            self.open_drawer()

    def open_drawer(self):
        if self._drawer_open:
            return
        self._drawer_open = True
        # Add scrim first (behind), then drawer (in front), on top of the screens.
        self.root_layout.add_widget(self.scrim)
        self.root_layout.add_widget(self.drawer)
        # Slide in from the left.
        self.drawer.x = -self.drawer_w
        Animation(x=0, d=0.18, t="out_quad").start(self.drawer)

    def close_drawer(self):
        if not self._drawer_open:
            return
        self._drawer_open = False
        anim = Animation(x=-self.drawer_w, d=0.16, t="out_quad")
        anim.bind(on_complete=lambda *a: self._remove_drawer_widgets())
        anim.start(self.drawer)

    def _remove_drawer_widgets(self):
        if self.drawer.parent:
            self.root_layout.remove_widget(self.drawer)
        if self.scrim.parent:
            self.root_layout.remove_widget(self.scrim)

    def _drawer_nav(self, target):
        self.close_drawer()
        self.go(target)

    # ---------------- chrome ----------------
    def _topbar(self, title):
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(58), padding=(dp(6), 0))
        with bar.canvas.before:
            Color(*C_PRIMARY_DK)
            rect = Rectangle()
        bar.bind(pos=lambda *a: setattr(rect, 'pos', bar.pos), size=lambda *a: setattr(rect, 'size', bar.size))
        # Draw a 3-line "hamburger" icon with graphics (no font glyph dependency).
        # Use LOCAL line objects per topbar — using self.* would make all screens
        # share the same 3 lines, so only the last-built topbar would render them.
        burger = Button(background_normal='', background_down='',
                        background_color=(0, 0, 0, 0),
                        size_hint_x=None, width=dp(52))
        with burger.canvas.after:
            Color(*C_TEXT)
            bl1 = Line(width=dp(1.4))
            bl2 = Line(width=dp(1.4))
            bl3 = Line(width=dp(1.4))
        def _draw_burger(*a):
            cx, cy = burger.center_x, burger.center_y
            w = dp(20); gap = dp(6)
            bl1.points = [cx - w/2, cy + gap, cx + w/2, cy + gap]
            bl2.points = [cx - w/2, cy,       cx + w/2, cy]
            bl3.points = [cx - w/2, cy - gap, cx + w/2, cy - gap]
        burger.bind(pos=_draw_burger, size=_draw_burger)
        burger.bind(on_release=lambda x: self.toggle_drawer())
        bar.add_widget(burger)
        bar.add_widget(label(f"[b]{title}[/b]", font_size=20, halign="left"))
        return bar

    def _scaffold(self, title):
        root = BoxLayout(orientation="vertical")
        root.add_widget(self._topbar(title))
        scroll = ScrollView()
        content = GridLayout(cols=1, spacing=dp(12), size_hint_y=None, padding=dp(16))
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        root.add_widget(scroll)
        return root, content

    def _kpi(self, title, value, accent=C_PRIMARY):
        card = Card(orientation="vertical", size_hint_y=None, height=dp(96),
                    padding=(dp(18), dp(14)), spacing=dp(4), accent=accent)
        card.add_widget(label(title.upper(), color=C_TEXT_2, font_size=12, bold=True,
                              size_hint_y=None, height=dp(20)))
        card.add_widget(label(str(value), bold=True, font_size=26, size_hint_y=None, height=dp(42)))
        return card

    def _clear(self, name):
        scr = self.sm.get_screen(name)
        scr.clear_widgets()
        return scr

    # ---------------- screens ----------------
    def _render_home(self):
        scr = self._clear("Home")
        root, content = self._scaffold("Dashboard")
        s = self.manager_db.get_summary(self.season)
        content.add_widget(label("[b]This Season[/b]", font_size=18, size_hint_y=None, height=dp(28)))
        content.add_widget(self._kpi("Games this season", s.get('games_count', 0), C_PRIMARY))
        content.add_widget(self._kpi("Total paid", f"{s.get('total_earnings', 0):.2f} EUR", C_GREEN))
        content.add_widget(self._kpi("Amount left", f"{s.get('amount_left', 0):.2f} EUR", C_YELLOW))
        acc = (self.test_correct / self.test_attempts * 100) if self.test_attempts else 0
        content.add_widget(self._kpi("Test accuracy", f"{acc:.0f}%  ({self.test_correct}/{self.test_attempts})", C_PRIMARY))
        b = PrimaryButton(text="Question of the Day", size_hint_y=None, height=dp(52), font_size=dp(16))
        b.bind(on_release=lambda x: self.go("QOD"))
        content.add_widget(b)
        scr.add_widget(root)

    def _render_games(self):
        scr = self._clear("Games")
        root, content = self._scaffold(f"Games {self.season}")
        add = PrimaryButton(text="+  Add Game", bg=C_PRIMARY, fg=C_TEXT,
                            size_hint_y=None, height=dp(50), font_size=dp(16))
        add.bind(on_release=lambda x: self.open_game_form(None))
        content.add_widget(add)
        games = self.manager_db.load_games(self.season) or []
        if not games:
            content.add_widget(label("No games yet - tap 'Add Game'", color=C_TEXT_2, size_hint_y=None, height=dp(40)))
        for g in reversed(games):
            amount = (g.get('transportation', 0) or 0) + (g.get('food', 0) or 0) + (g.get('gamePayment', 0) or 0)
            paid = str(g.get('paidStatus', 'No')).lower() in ('yes', 'true', '1')
            accent = C_GREEN if paid else C_YELLOW
            # Tappable card -> edit
            row = GameRow(g, accent, amount, paid, on_tap=lambda gg=g: self.open_game_form(gg))
            content.add_widget(row)
        scr.add_widget(root)

    # ---------------- Game add/edit form ----------------
    def _field(self, parent, caption, value):
        parent.add_widget(label(caption, color=C_TEXT_2, font_size=12, bold=True,
                                size_hint_y=None, height=dp(20)))
        ti = TextInput(text=str(value), multiline=False, size_hint_y=None, height=dp(44),
                       background_color=C_SURFACE, foreground_color=C_TEXT, cursor_color=C_YELLOW,
                       padding=(dp(10), dp(11)))
        parent.add_widget(ti)
        return ti

    def open_game_form(self, game):
        """Open the add (game=None) or edit (game=dict) form."""
        self._editing_game = game
        scr = self._clear("GameForm")
        is_edit = game is not None
        root = BoxLayout(orientation="vertical")
        root.add_widget(self._topbar("Edit Game" if is_edit else "Add Game"))
        scroll = ScrollView()
        form = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=dp(16))
        form.bind(minimum_height=form.setter("height"))

        g = game or {}
        self._f_number = self._field(form, "GAME NUMBER", g.get('gameNumber', ''))
        self._f_location = self._field(form, "LOCATION", g.get('location', ''))

        # Scrollable date picker (Y / M / D spinners)
        form.add_widget(label("DATE", color=C_TEXT_2, font_size=12, bold=True, size_hint_y=None, height=dp(20)))
        drow = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(46))
        cur = str(g.get('date', '')) or date.today().isoformat()
        try:
            yy, mm, dd = cur.split('-')[:3]
        except Exception:
            t = date.today(); yy, mm, dd = str(t.year), f"{t.month:02d}", f"{t.day:02d}"
        years = [str(y) for y in range(2023, 2031)]
        months = [f"{m:02d}" for m in range(1, 13)]
        days = [f"{d:02d}" for d in range(1, 32)]
        self._f_year = PickerField(years, value=(yy if yy in years else years[-1]),
                                   title="Year", size_hint_y=None, height=dp(46), font_size=dp(16))
        self._f_month = PickerField(months, value=(mm if mm in months else months[0]),
                                    title="Month", size_hint_y=None, height=dp(46), font_size=dp(16))
        self._f_day = PickerField(days, value=(dd if dd in days else days[0]),
                                  title="Day", size_hint_y=None, height=dp(46), font_size=dp(16))
        drow.add_widget(self._f_year); drow.add_widget(self._f_month); drow.add_widget(self._f_day)
        form.add_widget(drow)

        self._f_transport = self._field(form, "TRANSPORTATION (EUR)", g.get('transportation', 0) or 0)
        self._f_food = self._field(form, "FOOD (EUR)", g.get('food', 0) or 0)
        self._f_payment = self._field(form, "GAME PAYMENT (EUR)", g.get('gamePayment', 0) or 0)

        # Paid toggle
        paid = str(g.get('paidStatus', 'No')).lower() in ('yes', 'true', '1')
        self._f_paid = PrimaryButton(text="Paid: YES" if paid else "Paid: NO",
                                     bg=C_GREEN if paid else C_SURFACE_2, fg=C_TEXT,
                                     size_hint_y=None, height=dp(46))
        self._f_paid.paid = paid
        def toggle_paid(x):
            self._f_paid.paid = not self._f_paid.paid
            self._f_paid.text = "Paid: YES" if self._f_paid.paid else "Paid: NO"
            self._f_paid.set_bg(C_GREEN if self._f_paid.paid else C_SURFACE_2)
        self._f_paid.bind(on_release=toggle_paid)
        form.add_widget(label("PAYMENT STATUS", color=C_TEXT_2, font_size=12, bold=True, size_hint_y=None, height=dp(20)))
        form.add_widget(self._f_paid)

        # Action buttons
        save = PrimaryButton(text="Save", bg=C_PRIMARY, fg=C_TEXT, size_hint_y=None, height=dp(50))
        save.bind(on_release=lambda x: self._save_game())
        form.add_widget(save)
        if is_edit:
            dele = PrimaryButton(text="Delete Game", bg=C_RED, fg=C_TEXT, size_hint_y=None, height=dp(46))
            dele.bind(on_release=lambda x: self._delete_game())
            form.add_widget(dele)
        cancel = PrimaryButton(text="Cancel", bg=C_SURFACE_2, fg=C_TEXT, size_hint_y=None, height=dp(46))
        cancel.bind(on_release=lambda x: self.go("Games"))
        form.add_widget(cancel)

        scroll.add_widget(form)
        root.add_widget(scroll)
        scr.add_widget(root)
        self.sm.current = "GameForm"

    def _form_float(self, ti):
        try:
            return float(str(ti.text).replace(',', '.').strip() or 0)
        except Exception:
            return 0.0

    def _save_game(self):
        date_str = f"{self._f_year.text}-{self._f_month.text}-{self._f_day.text}"
        new_game = {
            'season': self.season,
            'gameNumber': self._f_number.text.strip(),
            'date': date_str,
            'location': self._f_location.text.strip(),
            'transportation': self._form_float(self._f_transport),
            'food': self._form_float(self._f_food),
            'gamePayment': self._form_float(self._f_payment),
            'paidStatus': 'Yes' if self._f_paid.paid else 'No',
            'paymentDate': date.today().isoformat() if self._f_paid.paid else None,
            'observations': (self._editing_game or {}).get('observations'),
        }
        try:
            if self._editing_game:
                old = self._editing_game
                self.manager_db.update_game(self.season, old.get('gameNumber'),
                                            new_game, old.get('date'))
            else:
                self.manager_db.add_game(self.season, new_game)
        except Exception as e:
            print(f"save_game error: {e}")
        self._editing_game = None
        self._render_games()
        self.go("Games")

    def _delete_game(self):
        g = self._editing_game
        if g:
            try:
                self.manager_db.delete_game(self.season, g.get('gameNumber'), g.get('date'))
            except Exception as e:
                print(f"delete_game error: {e}")
        self._editing_game = None
        self._render_games()
        self.go("Games")

    # Available test lengths: (questions, minutes)
    TEST_VARIANTS = [(30, 30), (15, 15), (5, 5)]

    def _render_tests(self):
        scr = self._clear("Tests")
        root, content = self._scaffold("Tests")

        # 1) Length selector — highlight the chosen one.
        self._selected_variant = getattr(self, '_selected_variant', self.TEST_VARIANTS[0])
        content.add_widget(label("Length", color=C_TEXT_2, font_size=13, bold=True,
                                 size_hint_y=None, height=dp(22)))
        len_row = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(52))
        self._variant_btns = []
        for (q, m) in self.TEST_VARIANTS:
            chosen = (q, m) == self._selected_variant
            b = PrimaryButton(text=f"{q}Q / {m}m",
                              bg=C_PRIMARY if chosen else C_SURFACE_2, fg=C_TEXT,
                              size_hint_y=None, height=dp(48), font_size=dp(15))
            b.variant = (q, m)
            b.bind(on_release=lambda x, v=(q, m): self._select_variant(v))
            len_row.add_widget(b)
            self._variant_btns.append(b)
        content.add_widget(len_row)

        # 2) Mode buttons — start a test of the selected length.
        content.add_widget(label("Start", color=C_TEXT_2, font_size=13, bold=True,
                                 size_hint_y=None, height=dp(22)))
        for txt, mode, bg in [("Random Test", "random", C_YELLOW),
                              ("Unanswered Questions", "unanswered", C_PRIMARY),
                              ("Wrong Answers", "wrong", C_RED)]:
            fg = (0.08, 0.10, 0.15, 1) if bg is C_YELLOW else C_TEXT
            b = PrimaryButton(text=txt, bg=bg, fg=fg, size_hint_y=None, height=dp(54), font_size=dp(16))
            b.bind(on_release=lambda x, m=mode: self.start_test(m))
            content.add_widget(b)
        scr.add_widget(root)

    def _select_variant(self, variant):
        self._selected_variant = variant
        for b in self._variant_btns:
            b.set_bg(C_PRIMARY if b.variant == variant else C_SURFACE_2)

    def _render_rulebook(self):
        scr = self._clear("Rulebook")
        root, content = self._scaffold("Rulebook")
        # Open the full PDF
        openbtn = PrimaryButton(text="Open Rulebook PDF", bg=C_PRIMARY, fg=C_TEXT,
                                size_hint_y=None, height=dp(50), font_size=dp(16))
        openbtn.bind(on_release=lambda x: self.open_rulebook_pdf())
        content.add_widget(openbtn)
        content.add_widget(label("Tap a rule to open the PDF at that section:",
                                 color=C_TEXT_2, font_size=13, size_hint_y=None, height=dp(26)))
        for rule in (self.handball_dataset.get("rulebook", []) if self.handball_dataset else []):
            page = rule.get('start_page')
            btn = RuleRow(rule, on_tap=lambda p=page: self.open_rulebook_pdf(p))
            content.add_widget(btn)
        scr.add_widget(root)

    def _rulebook_pdf_path(self):
        """Locate the bundled rulebook PDF (desktop path or APK app dir)."""
        names = ["09A - Rules of the Game_Indoor Handball_E.pdf"]
        roots = [
            Path(__file__).parent.parent.parent,           # desktop project root
            Path(os.environ.get('ANDROID_APP_PATH', os.getcwd())),  # APK app dir
            Path(os.getcwd()),
        ]
        for r in roots:
            for n in names:
                p = r / n
                if p.exists():
                    return str(p)
        return None

    def open_rulebook_pdf(self, page=None):
        """Open the rulebook PDF in the device's native viewer (Android),
        or the OS default app on desktop.

        Android approach (no FileProvider): copy the bundled PDF into the public
        Downloads folder, then launch an ACTION_VIEW intent. Simple and avoids
        manifest/FileProvider configuration entirely.
        """
        path = self._rulebook_pdf_path()
        if not path:
            self._toast("Rulebook PDF not found")
            return
        try:
            from jnius import autoclass
            import shutil
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            File = autoclass('java.io.File')
            FileProvider = autoclass('androidx.core.content.FileProvider')
            activity = PythonActivity.mActivity

            # Copy the bundled PDF into the app's external files dir (covered by
            # provider_paths.xml <external-files-path>), then share via FileProvider.
            ext_dir = activity.getExternalFilesDir(None).getAbsolutePath()
            dest = os.path.join(ext_dir, "rulebook.pdf")
            if not os.path.exists(dest) or os.path.getsize(dest) != os.path.getsize(path):
                shutil.copyfile(path, dest)

            jfile = File(dest)
            authority = activity.getPackageName() + ".fileprovider"
            uri = FileProvider.getUriForFile(activity, authority, jfile)

            intent = Intent(Intent.ACTION_VIEW)
            intent.setDataAndType(uri, "application/pdf")
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            activity.startActivity(intent)
            return
        except Exception as e:
            print(f"Android PDF open failed ({e}); trying desktop opener")
        # Desktop fallback
        try:
            import subprocess, sys as _sys
            if _sys.platform.startswith('win'):
                os.startfile(path)  # type: ignore
            elif _sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            print(f"PDF open failed: {e}")

    def _toast(self, msg):
        print(msg)
        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Toast = autoclass('android.widget.Toast')
            String = autoclass('java.lang.String')
            activity = PythonActivity.mActivity
            context = activity.getApplicationContext()
            jmsg = cast('java.lang.CharSequence', String(msg))
            def _show():
                Toast.makeText(context, jmsg, Toast.LENGTH_SHORT).show()
            activity.runOnUiThread(_show)
        except Exception as e:
            print(f"toast failed: {e}")

    def _render_stats(self):
        scr = self._clear("Stats")
        root, content = self._scaffold("Statistics")
        acc = (self.test_correct / self.test_attempts * 100) if self.test_attempts else 0
        content.add_widget(self._kpi("Tests attempted", self.test_attempts, C_PRIMARY))
        content.add_widget(self._kpi("Correct answers", self.test_correct, C_GREEN))
        content.add_widget(self._kpi("Accuracy", f"{acc:.1f}%", C_YELLOW))
        scr.add_widget(root)

    def _build_test_taking_screen(self):
        scr = self.sm.get_screen("TestTaking")
        root = BoxLayout(orientation="vertical")
        # Top bar with a countdown timer on the right
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(58), padding=(dp(12), 0))
        with bar.canvas.before:
            Color(*C_PRIMARY_DK)
            trect = Rectangle()
        bar.bind(pos=lambda *a: setattr(trect, 'pos', bar.pos), size=lambda *a: setattr(trect, 'size', bar.size))
        bar.add_widget(label("[b]Test[/b]", font_size=20, halign="left"))
        self.tt_timer = label("30:00", font_size=18, bold=True, halign="right",
                              size_hint_x=None, width=dp(80))
        bar.add_widget(self.tt_timer)
        root.add_widget(bar)

        scroll = ScrollView()
        content = GridLayout(cols=1, spacing=dp(12), size_hint_y=None, padding=dp(16))
        content.bind(minimum_height=content.setter("height"))
        self.tt_qcard = Card(orientation="vertical", size_hint_y=None, padding=dp(16), accent=C_YELLOW)
        self.tt_question = wrap_label("", bold=True, font_size=17)
        self.tt_qcard.bind(minimum_height=self.tt_qcard.setter('height'))
        self.tt_qcard.add_widget(self.tt_question)
        content.add_widget(self.tt_qcard)
        self.tt_options = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.tt_options.bind(minimum_height=self.tt_options.setter("height"))
        content.add_widget(self.tt_options)
        scroll.add_widget(content)
        root.add_widget(scroll)
        btns = GridLayout(cols=3, size_hint_y=None, height=dp(60), spacing=dp(8), padding=dp(8))
        sb = PrimaryButton(text="Submit", bg=C_GREEN, fg=C_TEXT, font_size=dp(15)); sb.bind(on_release=lambda x: self.submit_test_answer())
        kb = PrimaryButton(text="Skip", bg=C_SURFACE_2, fg=C_TEXT, font_size=dp(15)); kb.bind(on_release=lambda x: self.next_test_question())
        fb = PrimaryButton(text="Finish", bg=C_RED, fg=C_TEXT, font_size=dp(15)); fb.bind(on_release=lambda x: self.finish_test())
        btns.add_widget(sb); btns.add_widget(kb); btns.add_widget(fb)
        root.add_widget(btns)
        scr.add_widget(root)
        self.tt_option_btns = []

    def _build_qod_screen(self):
        scr = self.sm.get_screen("QOD")
        root = BoxLayout(orientation="vertical")
        root.add_widget(self._topbar("Question of the Day"))
        scroll = ScrollView()
        content = GridLayout(cols=1, spacing=dp(12), size_hint_y=None, padding=dp(16))
        content.bind(minimum_height=content.setter("height"))
        self.qod_qcard = Card(orientation="vertical", size_hint_y=None, padding=dp(16), accent=C_YELLOW)
        self.qod_question_label = wrap_label("", bold=True, font_size=17)
        self.qod_qcard.bind(minimum_height=self.qod_qcard.setter('height'))
        self.qod_qcard.add_widget(self.qod_question_label)
        content.add_widget(self.qod_qcard)
        self.qod_options = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.qod_options.bind(minimum_height=self.qod_options.setter("height"))
        content.add_widget(self.qod_options)
        self.qod_feedback_label = label("", color=C_YELLOW, font_size=14, size_hint_y=None)
        self.qod_feedback_label.bind(texture_size=lambda l, s: setattr(l, 'height', max(dp(10), s[1] + dp(8))))
        content.add_widget(self.qod_feedback_label)
        sb = PrimaryButton(text="Submit Answer", bg=C_GREEN, fg=C_TEXT, size_hint_y=None, height=dp(52))
        sb.bind(on_release=lambda x: self.submit_qod_answer())
        content.add_widget(sb)
        scroll.add_widget(content)
        root.add_widget(scroll)
        scr.add_widget(root)
        self.qod_option_btns = []

    # ---------------- navigation ----------------
    def go(self, name):
        if name == "QOD":
            self.load_question_of_day()
            self.load_qod_ui()
        if name == "Home":
            self._render_home()
        if name == "Stats":
            self._render_stats()
        if name == "Games":
            self._render_games()
        self.sm.current = name

    # ---------------- options ----------------
    def _make_option(self, key, text):
        b = OptionButton(text=f"{key})  {text}", size_hint_y=None)
        b.key = key
        b.bind(on_release=lambda x: x.set_selected(not x.selected))
        return b

    # ---------------- Question of the Day ----------------
    def load_question_of_day(self):
        if not self.quiz_questions:
            return
        today = date.today().isoformat()
        cache = self.test_progress.get('qod_cache', {})
        if cache.get('date') == today and cache.get('question_id'):
            qid = cache['question_id']
            self.qod_question = next((q for q in self.quiz_questions if str(q.get('id')) == str(qid)), None)
            if not self.qod_question:
                self.qod_question = random.choice(self.quiz_questions)
        else:
            self.qod_question = random.choice(self.quiz_questions)
            self.test_progress['qod_cache'] = {'date': today, 'question_id': str(self.qod_question.get('id', ''))}
            self._save_test_progress()

    def load_qod_ui(self):
        if not self.qod_question:
            self.qod_question_label.text = "No question available"
            return
        self.qod_question_label.text = self.qod_question.get('question', '')
        self.qod_feedback_label.text = ""
        self.qod_options.clear_widgets()
        self.qod_option_btns = []
        for opt in sorted(self.qod_question.get('options', []), key=lambda o: str(o.get('key', '')).upper()):
            b = self._make_option(str(opt.get('key', '')).upper(), opt.get('text', ''))
            self.qod_options.add_widget(b)
            self.qod_option_btns.append(b)

    def submit_qod_answer(self):
        if not self.qod_question:
            return
        selected = sorted([b.key for b in self.qod_option_btns if b.selected])
        correct = sorted([str(k).upper() for k in self.qod_question.get('correct_options', [])])
        is_correct = set(selected) == set(correct)
        self.test_attempts += 1
        if is_correct:
            self.test_correct += 1
        self._persist_stats()
        verdict = "[color=2EB56A]Correct![/color]" if is_correct else "[color=E84D4F]Not correct[/color]"
        self.qod_feedback_label.text = f"{verdict}   Your answer: {', '.join(selected) or '-'}  |  Expected: {', '.join(correct) or '-'}"

    # ---------------- Tests ----------------
    def start_test(self, mode):
        if not self.quiz_questions:
            return
        # Use the length the user selected on the Tests screen (default 30/30).
        size, minutes = getattr(self, '_selected_variant', (30, 30))
        answered = self.test_progress.get('questions', {})
        if mode == "unanswered":
            pool = [q for q in self.quiz_questions if str(q.get('id')) not in answered]
        elif mode == "wrong":
            pool = [q for q in self.quiz_questions if answered.get(str(q.get('id'))) == 'wrong']
        else:
            pool = list(self.quiz_questions)
        if not pool:
            pool = list(self.quiz_questions)
        self.current_test_questions = random.sample(pool, min(size, len(pool)))
        self.current_test_index = 0
        self.session_results = {}
        # Store the user's selected answer keys per question id (for review).
        self.session_answers = {}
        self._test_finished = False
        # Start the countdown timer for the selected duration.
        self._test_remaining = minutes * 60
        self._update_timer_label()
        from kivy.clock import Clock
        if getattr(self, '_test_timer_ev', None):
            self._test_timer_ev.cancel()
        self._test_timer_ev = Clock.schedule_interval(self._tick_timer, 1)
        self.sm.current = "TestTaking"
        self.show_test_question()

    def _update_timer_label(self):
        m, s = divmod(max(0, self._test_remaining), 60)
        self.tt_timer.text = f"{m:02d}:{s:02d}"
        self.tt_timer.color = C_RED if self._test_remaining <= 60 else C_TEXT

    def _tick_timer(self, dt):
        self._test_remaining -= 1
        self._update_timer_label()
        if self._test_remaining <= 0:
            self.finish_test(timed_out=True)
            return False

    def show_test_question(self):
        if self.current_test_index >= len(self.current_test_questions):
            self.finish_test()
            return
        q = self.current_test_questions[self.current_test_index]
        self.current_test_question = q
        self.tt_question.text = f"[color=F9C71F]Q{self.current_test_index + 1}/{len(self.current_test_questions)}[/color]\n{q.get('question', '')}"
        self.tt_options.clear_widgets()
        self.tt_option_btns = []
        # Pre-select any previously chosen answers (so going back keeps them).
        prev = set(self.session_answers.get(str(q.get('id', '')), []))
        for opt in sorted(q.get('options', []), key=lambda o: str(o.get('key', '')).upper()):
            k = str(opt.get('key', '')).upper()
            b = self._make_option(k, opt.get('text', ''))
            if k in prev:
                b.set_selected(True)
            self.tt_options.add_widget(b)
            self.tt_option_btns.append(b)

    def _record_current(self):
        """Save selection + correctness for the current question."""
        q = self.current_test_question
        if not q:
            return
        qid = str(q.get('id', ''))
        selected = sorted([b.key for b in self.tt_option_btns if b.selected])
        correct = sorted([str(k).upper() for k in q.get('correct_options', [])])
        self.session_answers[qid] = selected
        self.session_results[qid] = 'correct' if set(selected) == set(correct) else 'wrong'

    def submit_test_answer(self):
        if not self.current_test_question:
            return
        self._record_current()
        self.next_test_question()

    def next_test_question(self):
        # Record current selection even on skip, then advance.
        if self.current_test_question:
            self._record_current()
        self.current_test_index += 1
        self.show_test_question()

    def finish_test(self, timed_out=False):
        if self._test_finished:
            return
        self._test_finished = True
        # Record the question currently on screen.
        if self.current_test_index < len(self.current_test_questions):
            self._record_current()
        if getattr(self, '_test_timer_ev', None):
            self._test_timer_ev.cancel()
            self._test_timer_ev = None
        # Persist per-question correct/wrong and overall stats.
        for qid, result in self.session_results.items():
            self.test_progress.setdefault('questions', {})[qid] = result
            self.test_attempts += 1
            if result == 'correct':
                self.test_correct += 1
        self._persist_stats()
        self._review_index = 0
        self._build_review(timed_out)
        self.sm.current = "Review"

    # ---------------- Review ----------------
    def _build_review(self, timed_out=False):
        scr = self._clear("Review")
        root = BoxLayout(orientation="vertical")
        root.add_widget(self._topbar("Review"))

        correct = sum(1 for r in self.session_results.values() if r == 'correct')
        total = len(self.current_test_questions)
        head_txt = f"[b]{correct}/{total} correct[/b]"
        if timed_out:
            head_txt += "   [color=E84D4F](time up)[/color]"
        root.add_widget(label(head_txt, font_size=16, size_hint_y=None, height=dp(34),
                              halign="center"))

        self.rv_scroll = ScrollView()
        self.rv_content = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(14))
        self.rv_content.bind(minimum_height=self.rv_content.setter("height"))
        self.rv_scroll.add_widget(self.rv_content)
        root.add_widget(self.rv_scroll)

        nav = GridLayout(cols=3, size_hint_y=None, height=dp(56), spacing=dp(8), padding=dp(8))
        prevb = PrimaryButton(text="< Prev", bg=C_SURFACE_2, fg=C_TEXT, font_size=dp(14))
        prevb.bind(on_release=lambda x: self._review_step(-1))
        self.rv_counter = PrimaryButton(text="", bg=C_PRIMARY_DK, fg=C_TEXT, font_size=dp(14))
        nextb = PrimaryButton(text="Next >", bg=C_SURFACE_2, fg=C_TEXT, font_size=dp(14))
        nextb.bind(on_release=lambda x: self._review_step(1))
        nav.add_widget(prevb); nav.add_widget(self.rv_counter); nav.add_widget(nextb)
        root.add_widget(nav)

        done = PrimaryButton(text="Back to Tests", bg=C_PRIMARY, fg=C_TEXT, size_hint_y=None, height=dp(48))
        done.bind(on_release=lambda x: self.go("Tests"))
        root.add_widget(done)

        scr.add_widget(root)
        self._render_review_question()

    def _review_step(self, delta):
        n = len(self.current_test_questions)
        self._review_index = max(0, min(n - 1, self._review_index + delta))
        self._render_review_question()

    def _render_review_question(self):
        self.rv_content.clear_widgets()
        n = len(self.current_test_questions)
        i = self._review_index
        q = self.current_test_questions[i]
        qid = str(q.get('id', ''))
        self.rv_counter.text = f"{i + 1} / {n}"
        chosen = set(self.session_answers.get(qid, []))
        correct = set(str(k).upper() for k in q.get('correct_options', []))

        # Question card
        qcard = Card(orientation="vertical", size_hint_y=None, padding=dp(14), accent=C_YELLOW)
        qcard.bind(minimum_height=qcard.setter('height'))
        verdict = "[color=2EB56A]Correct[/color]" if self.session_results.get(qid) == 'correct' else "[color=E84D4F]Wrong[/color]"
        qcard.add_widget(wrap_label(f"[color=F9C71F]Q{i+1}[/color]  {verdict}\n{q.get('question','')}",
                                    bold=True, font_size=16))
        self.rv_content.add_widget(qcard)

        # Options colored: green = correct (always); red = wrong pick by user
        for opt in sorted(q.get('options', []), key=lambda o: str(o.get('key', '')).upper()):
            k = str(opt.get('key', '')).upper()
            is_correct = k in correct
            is_chosen = k in chosen
            if is_correct:
                bg = C_GREEN            # the right answer is always green
            elif is_chosen:
                bg = C_RED              # user picked this and it's wrong
            else:
                bg = C_SURFACE
            mark = ""
            if is_correct:
                mark = "  [b](correct)[/b]"
            elif is_chosen:
                mark = "  [b](your answer)[/b]"
            row = Card(orientation="vertical", size_hint_y=None, padding=(dp(12), dp(8)),
                       bg=bg, border=False)
            row.bind(minimum_height=row.setter('height'))
            fg = C_TEXT
            row.add_widget(wrap_label(f"{k})  {opt.get('text','')}{mark}", font_size=14, color=fg))
            self.rv_content.add_widget(row)

    # ---------------- persistence ----------------
    def _persist_stats(self):
        self.test_progress.setdefault('stats', {})['attempts'] = int(self.test_attempts)
        self.test_progress.setdefault('stats', {})['correct'] = int(self.test_correct)
        self._save_test_progress()

    def _connect_db(self):
        """Open a pymysql connection to the shared server; fall back to JSON."""
        cfg = _load_db_config()
        if not cfg or not cfg.get('host'):
            print("No DB config found; using local JSON.")
            return GameDataManager()
        try:
            import pymysql
            conn = pymysql.connect(
                host=cfg.get('host'),
                port=int(cfg.get('port', 3306)),
                user=cfg.get('user', ''),
                password=cfg.get('password', ''),
                db=cfg.get('dbname', ''),
                connect_timeout=8,
            )
            self.db_status = f"Connected to {cfg.get('host')}"
            print(self.db_status)
            return GameDataManager(db_conn=conn)
        except Exception as e:
            self.db_status = f"DB unreachable ({e}); using local data"
            print(self.db_status)
            return GameDataManager()

    def _progress_path(self):
        try:
            base = self.user_data_dir
        except Exception:
            base = str(Path(__file__).parent.parent.parent / "data")
        return Path(base) / "test_progress.json"

    def _load_test_progress(self):
        try:
            p = self._progress_path()
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    self.test_progress = json.load(f)
        except Exception as e:
            print(f"Error loading test progress: {e}")

    def _save_test_progress(self):
        try:
            p = self._progress_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(self.test_progress, f, indent=2)
        except Exception as e:
            print(f"Error saving test progress: {e}")


if __name__ == "__main__":
    RefereeApp().run()
