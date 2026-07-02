"""
UI theme and styling configuration.

Configures tkinter theme and ttk styles for the application.
"""
import tkinter as tk
from tkinter import ttk


def setup_theme(root: tk.Tk):
    """Configure tkinter application theme.

    Attempts to load the Azure theme if available, otherwise uses default.

    Args:
        root: Tkinter root window.
    """
    try:
        root.tk.call("source", "theme/azure.tcl")
        root.tk.call("set_theme", "dark")
    except Exception:
        pass

    style = ttk.Style()
    style.theme_use('clam')


