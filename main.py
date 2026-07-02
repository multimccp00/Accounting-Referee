#!/usr/bin/env python
"""
Referee Earnings Tracker - Entry Point

This module serves as the application entry point. It initializes and runs the GUI.
All application logic has been restructured into the app/ package.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Main entry point for the application."""
    import tkinter as tk
    from app.ui.app import RefereeApp
    from config.settings import DATA_DIR

    parser = argparse.ArgumentParser(description="Referee Earnings Tracker")
    parser.add_argument('--db', help='Database path (SQLite) or connection URL', default=None)
    args = parser.parse_args()

    # Default to SQLite database in data directory
    db_path = args.db or os.path.join(DATA_DIR, 'referee.sqlite')

    root = tk.Tk()
    app = RefereeApp(root, db_path=db_path)
    root.mainloop()


if __name__ == '__main__':
    main()
