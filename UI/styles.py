import tkinter as tk
from tkinter import ttk

#  Colors (will update with cirius branding)
BG = "#f4f5f3"              # main background
SURFACE = "#ffffff"         # panels
BORDER = "#dcded9"          # lighter borders
BORDER_STRONG = "#b9bcb4"   # borders
TEXT = "#1e211d"            # main text
TEXT_SECONDARY = "#5b5f57"  # labels
TEXT_MUTED = "#8c8f86"      # disabled text

ACCENT = "#2b5f4c"          # primary buttons, links
ACCENT_HOVER = "#234c3d"

DANGER = "#a3352b"          # high severity
DANGER_BG = "#f8e9e7"
WARNING = "#8a5a10"         # medium severity / alerts
WARNING_BG = "#faf0dc"
SUCCESS = "#3a6b3f"         # low severity / good status
SUCCESS_BG = "#eaf1e8"

# Fonts
FONT_FAMILY = "Segoe UI"
FONT_BODY = (FONT_FAMILY, 10)
FONT_LABEL = (FONT_FAMILY, 9)
FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 10)
FONT_MONO = ("Consolas", 10)


def apply_theme(root: tk.Tk) -> None:
    root.configure(bg=BG)

    style = ttk.Style(root)
    
    style.theme_use("clam")

    style.configure("App.TFrame", background=BG)
    style.configure("Card.TFrame", background=SURFACE, relief="flat")
    style.configure("TLabel", background=BG, foreground=TEXT, font=FONT_BODY)
    style.configure("Card.TLabel", background=SURFACE, foreground=TEXT, font=FONT_BODY)
    style.configure("Muted.TLabel", background=SURFACE, foreground=TEXT_SECONDARY, font=FONT_LABEL)
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=FONT_TITLE)
    style.configure("CardTitle.TLabel", background=SURFACE, foreground=TEXT, font=FONT_TITLE)

    style.configure("Primary.TButton", background=ACCENT, foreground="white",
                    font=FONT_BODY, padding=8)
    style.map("Primary.TButton", background=[("active", ACCENT_HOVER)])

    style.configure("Secondary.TButton", background=SURFACE, foreground=TEXT,
                    font=FONT_LABEL, padding=6)

    style.configure("TEntry", padding=6)
    style.configure("TCombobox", padding=6)
