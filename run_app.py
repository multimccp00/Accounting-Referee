#!/usr/bin/env python
"""
Quick launcher to choose between Tkinter desktop and Kivy mobile versions.
"""
import sys
from pathlib import Path

def main():
    print("\n" + "="*50)
    print("REFEREE TRACKER - App Launcher")
    print("="*50 + "\n")

    print("Choose which version to run:\n")
    print("1. Tkinter Desktop (traditional UI)")
    print("2. Kivy Mobile (Material Design - test on desktop)")
    print("3. Exit\n")

    choice = input("Enter your choice (1-3): ").strip()

    if choice == "1":
        print("\nLaunching Tkinter Desktop version...")
        from app.ui.app import RefereeApp
        import tkinter as tk
        root = tk.Tk()
        app = RefereeApp(root)
        app.pack(fill="both", expand=True)
        root.mainloop()

    elif choice == "2":
        print("\nLaunching Kivy Mobile version...")
        from app.mobile.main import RefereeApp
        RefereeApp().run()

    elif choice == "3":
        print("Goodbye!")
        sys.exit(0)
    else:
        print("Invalid choice. Please try again.")
        main()

if __name__ == "__main__":
    main()
