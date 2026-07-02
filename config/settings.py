"""
Application settings and configuration constants.

Provides centralized configuration for paths, database defaults, UI dimensions,
and test parameters. Automatically creates necessary directories.
"""
import os
import sys

BASE_DIR = (
    os.path.dirname(sys.executable)
    if getattr(sys, 'frozen', False)
    else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

ASSETS_DIR = os.path.join(BASE_DIR, 'assets')

TEST_DATA_DIR = os.path.join(DATA_DIR, 'test_history')
os.makedirs(TEST_DATA_DIR, exist_ok=True)

DEFAULT_DB = {
    'host': 'localhost',
    'port': 3306,
    'user': '',
    'password': '',
    'dbname': '',
}

APP_TITLE = "Referee Earnings Tracker"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

DEFAULT_TEST_QUESTIONS = 30
TEST_MODES = ['random', 'by_rule', 'unanswered', 'wrong_answers']
