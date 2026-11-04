"""Dark theme for the Anthem window.

Tkinter's native Windows theme cannot be recoloured - the widgets are drawn
by the OS. Switching to 'clam' gives up the native look but makes every
part themeable, which is the trade that lets this look like a music tool
rather than a 1998 settings dialog.
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# One place to change the look.
BG = "#14141c"          # window
PANEL = "#1c1c28"       # cards
PANEL_HI = "#22222f"    # hovered / raised
FIELD = "#101017"       # entries and text areas
BORDER = "#2e2e3e"
TEXT = "#e6e6f0"
MUTED = "#8b8ba3"
ACCENT = "#7b61ff"
ACCENT_HI = "#9280ff"
ACCENT_DIM = "#4a3bad"
OK = "#4ade80"
WARN = "#fbbf24"
BAD = "#f87171"

UI_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"


def fonts():
    """Font set, falling back if Segoe UI is missing."""
    families = set(tkfont.families())
    ui = UI_FAMILY if UI_FAMILY in families else "Helvetica"
    mono = MONO_FAMILY if MONO_FAMILY in families else "Courier"
    return {
        "ui": (ui, 10),
        "ui_bold": (ui, 10, "bold"),
        "small": (ui, 9),
        "label": (ui, 9, "bold"),
        "title": (ui, 20, "bold"),
        "subtitle": (ui, 10),
        "button": (ui, 10, "bold"),
        "mono": (mono, 9),
        "lyrics": (mono, 11),
    }


def apply(root):
    """Paint the whole application. Returns the font set."""
    font = fonts()
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(bg=BG)
    # The combobox popup is a classic Tk listbox, not a ttk widget, so it
    # has to be recoloured through the option database.
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", font["ui"])

    style.configure(".", background=BG, foreground=TEXT,
                    fieldbackground=FIELD, font=font["ui"],
                    borderwidth=0, focuscolor=ACCENT)

    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("Header.TFrame", background=PANEL)

    style.configure("TLabel", background=BG, foreground=TEXT,
                    font=font["ui"])
    style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
    style.configure("Muted.TLabel", background=PANEL, foreground=MUTED,
                    font=font["small"])
    style.configure("MutedBg.TLabel", background=BG, foreground=MUTED,
                    font=font["small"])
    style.configure("Section.TLabel", background=PANEL, foreground=MUTED,
                    font=font["label"])
    style.configure("Title.TLabel", background=PANEL, foreground=TEXT,
                    font=font["title"])
    style.configure("Subtitle.TLabel", background=PANEL, foreground=MUTED,
                    font=font["subtitle"])
    style.configure("Status.TLabel", background=BG, foreground=MUTED,
                    font=font["ui"])
    style.configure("Good.TLabel", background=BG, foreground=OK,
                    font=font["ui"])
    style.configure("Warn.TLabel", background=BG, foreground=WARN,
                    font=font["ui"])
    style.configure("Bad.TLabel", background=BG, foreground=BAD,
                    font=font["ui"])

    # -- entries -------------------------------------------------------
    for name in ("TEntry",):
        style.configure(name, fieldbackground=FIELD, foreground=TEXT,
                        insertcolor=TEXT, bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER,
                        borderwidth=1, relief="flat", padding=6)
        style.map(name,
                  bordercolor=[("focus", ACCENT)],
                  lightcolor=[("focus", ACCENT)],
                  darkcolor=[("focus", ACCENT)])

    # -- combobox ------------------------------------------------------
    style.configure("TCombobox", fieldbackground=FIELD, background=FIELD,
                    foreground=TEXT, arrowcolor=MUTED, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, borderwidth=1,
                    relief="flat", padding=5, arrowsize=14)
    style.map("TCombobox",
              fieldbackground=[("readonly", FIELD), ("disabled", PANEL)],
              foreground=[("disabled", MUTED)],
              bordercolor=[("focus", ACCENT), ("hover", ACCENT_DIM)],
              lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)],
              arrowcolor=[("hover", TEXT)],
              selectbackground=[("readonly", FIELD)],
              selectforeground=[("readonly", TEXT)])

    # -- buttons -------------------------------------------------------
    style.configure("TButton", background=PANEL_HI, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=PANEL_HI,
                    darkcolor=PANEL_HI, borderwidth=1, relief="flat",
                    padding=(14, 7), font=font["ui"])
    style.map("TButton",
              background=[("pressed", PANEL), ("active", "#2c2c3c"),
                          ("disabled", PANEL)],
              foreground=[("disabled", MUTED)],
              bordercolor=[("active", ACCENT_DIM)])

    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                    borderwidth=0, relief="flat", padding=(22, 10),
                    font=font["button"])
    style.map("Accent.TButton",
              background=[("pressed", ACCENT_DIM), ("active", ACCENT_HI),
                          ("disabled", "#2a2a38")],
              foreground=[("disabled", MUTED)],
              lightcolor=[("active", ACCENT_HI)],
              darkcolor=[("active", ACCENT_HI)])

    # -- checkbutton ---------------------------------------------------
    # clam names these indicatorbackground/indicatorforeground. The 'alt'
    # and 'default' themes call the box colour 'indicatorcolor', and setting
    # that name here silently does nothing - the box then renders white with
    # a black tick, which reads as broken rather than ticked.
    style.configure("TCheckbutton", background=PANEL, foreground=TEXT,
                    indicatorbackground=FIELD, indicatorforeground=TEXT,
                    indicatorrelief="flat", bordercolor=BORDER,
                    focuscolor=PANEL, padding=4, font=font["ui"])
    style.map("TCheckbutton",
              background=[("active", PANEL)],
              indicatorbackground=[("selected", ACCENT),
                                   ("pressed", ACCENT_DIM),
                                   ("!selected", FIELD)],
              indicatorforeground=[("selected", "#ffffff")],
              bordercolor=[("selected", ACCENT), ("active", ACCENT_DIM)],
              foreground=[("disabled", MUTED)])

    style.configure("Bg.TCheckbutton", background=BG, focuscolor=BG,
                    indicatorbackground=FIELD, indicatorforeground=TEXT)
    style.map("Bg.TCheckbutton",
              background=[("active", BG)],
              indicatorbackground=[("selected", ACCENT),
                                   ("pressed", ACCENT_DIM),
                                   ("!selected", FIELD)],
              indicatorforeground=[("selected", "#ffffff")],
              bordercolor=[("selected", ACCENT)])

    # -- progress ------------------------------------------------------
    style.configure("Thin.Horizontal.TProgressbar",
                    background=ACCENT, troughcolor=FIELD,
                    bordercolor=FIELD, lightcolor=ACCENT,
                    darkcolor=ACCENT, borderwidth=0, thickness=4)

    # -- scrollbar -----------------------------------------------------
    style.configure("Vertical.TScrollbar", background=PANEL_HI,
                    troughcolor=PANEL, bordercolor=PANEL,
                    arrowcolor=MUTED, borderwidth=0, relief="flat",
                    width=12)
    style.map("Vertical.TScrollbar",
              background=[("active", "#3a3a4e"), ("pressed", ACCENT_DIM)])

    style.configure("TSeparator", background=BORDER)

    return font


def card(parent, title=None, **kwargs):
    """A padded panel with an optional heading.

    Returns (outer, content). Place `outer` with grid or pack; lay widgets
    out inside `content` however you like. The heading lives in a separate
    frame so callers are free to use grid without colliding with it.
    """
    outer = tk.Frame(parent, bg=BORDER, bd=0, highlightthickness=0)
    inner = ttk.Frame(outer, style="Panel.TFrame",
                      padding=kwargs.pop("padding", 14))
    # 1px of the darker outer frame shows through as a hairline border.
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    if title:
        ttk.Label(inner, text=title.upper(), style="Section.TLabel").pack(
            anchor="w", pady=(0, 10))
    content = ttk.Frame(inner, style="Panel.TFrame")
    content.pack(fill="both", expand=True)
    return outer, content


def style_text(widget, font_tuple, muted_insert=False):
    """Recolour a plain tk.Text, which ttk cannot theme."""
    widget.configure(
        bg=FIELD, fg=TEXT, insertbackground=MUTED if muted_insert else TEXT,
        selectbackground=ACCENT_DIM, selectforeground="#ffffff",
        relief="flat", borderwidth=0, highlightthickness=1,
        highlightbackground=BORDER, highlightcolor=BORDER,
        font=font_tuple, padx=12, pady=10, wrap="word",
    )
