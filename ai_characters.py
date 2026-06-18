#!/usr/bin/env python3
"""
Luminous AI — AI Characters Section
Full NPCViewerApp. Launched from main.py hub.
"""
import sys
import os

# --- surfaced import error ---
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, scrolledtext, messagebox, font as tkfont
    import json
    import platform
    import subprocess
    from datetime import datetime
    from pathlib import Path
    from jsonTemplate import TEMPLATES, TABS, TAG_CONFIG, KNOWN_KEYS, RenderContext
except Exception as _import_err:
    import tkinter as _tk
    import tkinter.messagebox as _mb
    _r = _tk.Tk()
    _r.withdraw()
    _mb.showerror("Import Error", f"ai_characters.py failed to load:\n\n{_import_err}")
    _r.destroy()
    sys.exit(1)

C = {
    "bg":        "#0d0f14",
    "surface":   "#13161e",
    "surface2":  "#1a1e29",
    "surface3":  "#212537",
    "fg":        "#e2e8f0",
    "fg_dim":    "#7b879e",
    "fg_muted":  "#445069",
    "accent":    "#7c6af7",
    "accent2":   "#38bdf8",
    "accent3":   "#f59e0b",
    "green":     "#22d3a0",
    "red":       "#f87171",
    "border":    "#252a38",
    "scrollbar": "#2a2f42",
}


class Icons:
    FOLDER   = "\u2b21"
    REFRESH  = "\u21ba"
    BOOKMARK = "\u25c8"
    SETTINGS = "\u25c9"
    SEARCH   = "\u2315"
    COLLAPSE = "\u2039"
    COPY     = "\u2398"
    EXPORT   = "\u2197"
    PIN      = "\u2295"
    TRASH    = "\u2298"


class FlatButton(tk.Label):
    def __init__(self, parent, text="", command=None, bg=C["surface2"], fg=C["fg"],
                 hover_bg=C["surface3"], hover_fg=C["accent"], font=("Segoe UI", 9),
                 padx=12, pady=6, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady,
                         cursor="hand2", **kw)
        self._bg = bg
        self._fg = fg
        self._hbg = hover_bg
        self._hfg = hover_fg
        self._cmd = command
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _=None):
        self.config(bg=self._hbg, fg=self._hfg)

    def _on_leave(self, _=None):
        self.config(bg=self._bg, fg=self._fg)

    def _on_click(self, _=None):
        self._on_enter()
        if self._cmd:
            self.after(50, self._cmd)


class AccentButton(FlatButton):
    def __init__(self, parent, text="", command=None, **kw):
        super().__init__(parent, text=text, command=command, bg=C["accent"], fg="#ffffff",
                         hover_bg="#9580ff", hover_fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), **kw)


class SidebarItem(tk.Frame):
    def __init__(self, parent, icon="", label="", command=None,
                 ui_font="Segoe UI", ui_size=9, **kw):
        super().__init__(parent, bg=C["surface"], cursor="hand2", **kw)
        self._cmd = command
        self._active = False
        self._indicator = tk.Frame(self, bg=C["surface"], width=3)
        self._indicator.pack(side=tk.LEFT, fill=tk.Y)
        inner = tk.Frame(self, bg=C["surface"])
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 10), pady=6)
        self._icon_lbl = tk.Label(inner, text=icon, bg=C["surface"], fg=C["fg_dim"],
                                  font=(ui_font, ui_size + 1))
        self._icon_lbl.pack(side=tk.LEFT)
        self._text_lbl = tk.Label(inner, text=label, bg=C["surface"], fg=C["fg_dim"],
                                  font=(ui_font, ui_size), anchor="w")
        self._text_lbl.pack(side=tk.LEFT, padx=(6, 0))
        for w in (self, inner, self._icon_lbl, self._text_lbl):
            w.bind("<Enter>", self._hover_on)
            w.bind("<Leave>", self._hover_off)
            w.bind("<Button-1>", self._click)

    def _hover_on(self, _=None):
        if not self._active:
            for w in (self, self._icon_lbl, self._text_lbl):
                w.config(bg=C["surface2"])
            self.winfo_children()[1].config(bg=C["surface2"])

    def _hover_off(self, _=None):
        if not self._active:
            for w in (self, self._icon_lbl, self._text_lbl):
                w.config(bg=C["surface"])
            self.winfo_children()[1].config(bg=C["surface"])

    def _click(self, _=None):
        if self._cmd:
            self._cmd()

    def set_active(self, active: bool):
        self._active = active
        bg = C["surface3"] if active else C["surface"]
        fg_icon = C["accent"] if active else C["fg_dim"]
        fg_text = C["fg"] if active else C["fg_dim"]
        ind = C["accent"] if active else C["surface"]
        for w in (self, self._icon_lbl, self._text_lbl):
            w.config(bg=bg)
        self.winfo_children()[1].config(bg=bg)
        self._icon_lbl.config(fg=fg_icon)
        self._text_lbl.config(fg=fg_text)
        self._indicator.config(bg=ind)


class StatusBar(tk.Frame):
    def __init__(self, parent, ui_font, ui_size, **kw):
        super().__init__(parent, bg=C["surface"], height=26, **kw)
        self.pack_propagate(False)
        self._dot = tk.Label(self, text="\u25cf", bg=C["surface"], fg=C["green"],
                             font=(ui_font, ui_size - 1))
        self._dot.pack(side=tk.LEFT, padx=(10, 4))
        self._msg = tk.Label(self, text="Ready", bg=C["surface"], fg=C["fg_dim"],
                             font=(ui_font, ui_size), anchor="w")
        self._msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._right = tk.Label(self, text="", bg=C["surface"], fg=C["fg_muted"],
                               font=(ui_font, ui_size - 1))
        self._right.pack(side=tk.RIGHT, padx=10)
        self._timer = None

    def set(self, msg, level="ok", right=""):
        color = {"ok": C["green"], "warn": C["accent3"], "error": C["red"],
                 "info": C["accent2"]}.get(level, C["green"])
        self._dot.config(fg=color)
        self._msg.config(text=msg, fg=C["fg"])
        self._right.config(text=right)
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(5000, lambda: self._msg.config(text="Ready", fg=C["fg_dim"]))


class CustomTitleBar(tk.Frame):
    def __init__(self, parent, app, title=""):
        super().__init__(parent, bg=C["bg"], height=36)
        self.pack_propagate(False)
        self.app = app
        self.root = app.root
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)
        self.bind("<Double-Button-1>", lambda e: self.toggle_max())

        back = tk.Label(self, text="\u2b21 Hub", bg=C["bg"], fg=C["fg_muted"],
                        font=("Segoe UI", 8), padx=10, pady=6, cursor="hand2")
        back.pack(side=tk.LEFT)
        back.bind("<Enter>", lambda e: back.config(fg=C["accent"]))
        back.bind("<Leave>", lambda e: back.config(fg=C["fg_muted"]))
        back.bind("<Button-1>", lambda e: app.back_to_hub())

        tk.Frame(self, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=6)

        self.lbl = tk.Label(self, text=f" {title}", bg=C["bg"], fg=C["fg_dim"],
                            font=("Segoe UI", 9, "bold"))
        self.lbl.pack(side=tk.LEFT, padx=4)
        self.lbl.bind("<ButtonPress-1>", self.start_move)
        self.lbl.bind("<B1-Motion>", self.do_move)
        self.lbl.bind("<Double-Button-1>", lambda e: self.toggle_max())

        btns = tk.Frame(self, bg=C["bg"])
        btns.pack(side=tk.RIGHT, fill=tk.Y)
        FlatButton(btns, text="\u2014", command=self.min_app, bg=C["bg"],
                   hover_bg=C["surface3"], padx=14).pack(side=tk.LEFT, fill=tk.Y)
        self.max_btn = FlatButton(btns, text="\u2610", command=self.toggle_max,
                                  bg=C["bg"], hover_bg=C["surface3"], padx=14)
        self.max_btn.pack(side=tk.LEFT, fill=tk.Y)
        FlatButton(btns, text="\u2715", command=self.close_app, bg=C["bg"],
                   hover_bg=C["red"], hover_fg="#fff", padx=14).pack(side=tk.LEFT, fill=tk.Y)
        self._is_max = False

    def start_move(self, event):
        if self._is_max:
            return
        self.root.x = event.x
        self.root.y = event.y

    def do_move(self, event):
        if self._is_max:
            return
        x = self.root.winfo_x() + event.x - self.root.x
        y = self.root.winfo_y() + event.y - self.root.y
        self.root.geometry(f"+{x}+{y}")

    def min_app(self):
        self.app.minimize()

    def toggle_max(self):
        if self._is_max:
            if hasattr(self, "_normal_geo"):
                self.root.geometry(self._normal_geo)
            self._is_max = False
            self.max_btn.config(text="\u2610")
            self.app.grip.place(relx=1.0, rely=1.0, anchor="se")
        else:
            self._normal_geo = self.root.geometry()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self._is_max = True
            self.max_btn.config(text="\u2750")
            self.app.grip.place_forget()

    def close_app(self):
        # WM_DELETE_WINDOW is a protocol, not a Tk event — call the handler directly
        handler = self.root.protocol("WM_DELETE_WINDOW")
        if handler:
            self.root.tk.call(handler)
        else:
            self.app.back_to_hub()

