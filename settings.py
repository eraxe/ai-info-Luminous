#!/usr/bin/env python3
"""
Luminous AI — Settings Section
SettingsApp: reads/writes settings.json next to main.py.
Also exposes SettingsManager for use by other sections.
"""
import tkinter as tk
import json
import os
import sys
import platform
from pathlib import Path

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

_APP_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
_SETTINGS_PATH = _APP_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "save_data_path": "",
    "last_campaign": "",
    "readonly_mode": False,
    "ui_font_family": "Segoe UI",
    "ui_font_size": 10,
    "theme": "dark",
}


# ---------------------------------------------------------------------------
# SettingsManager — lightweight, importable, no tkinter required
# ---------------------------------------------------------------------------

class SettingsManager:
    """Read/write settings.json. Import this from any section module."""

    def __init__(self, path: Path = _SETTINGS_PATH):
        self._path = path
        self._data: dict = {}
        self.load()

    # ---- public API ----

    def load(self) -> dict:
        """Load settings from disk; fill missing keys with defaults."""
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                self._data = {}
        except Exception:
            self._data = {}
        # fill defaults without overwriting existing keys
        for k, v in DEFAULT_SETTINGS.items():
            self._data.setdefault(k, v)
        return self._data

    def save(self) -> bool:
        """Persist current settings to disk. Returns True on success."""
        try:
            tmp = str(self._path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, str(self._path))
            return True
        except Exception:
            return False

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value

    def set_many(self, updates: dict) -> None:
        self._data.update(updates)

    def save_data_path(self) -> str:
        return self._data.get("save_data_path", "")

    def last_campaign(self) -> str:
        return self._data.get("last_campaign", "")

    def readonly_mode(self) -> bool:
        return bool(self._data.get("readonly_mode", False))

    def set_save_data_path(self, path: str) -> None:
        self._data["save_data_path"] = path

    def set_last_campaign(self, campaign_id: str) -> None:
        self._data["last_campaign"] = campaign_id

    def set_readonly_mode(self, value: bool) -> None:
        self._data["readonly_mode"] = bool(value)

    def all(self) -> dict:
        return dict(self._data)


# Module-level singleton — import and use directly from other modules:
#   from settings import settings_manager
settings_manager = SettingsManager()


# ---------------------------------------------------------------------------
# Shared widget helpers (no ttk)
# ---------------------------------------------------------------------------

class FlatButton(tk.Label):
    def __init__(self, parent, text="", command=None,
                 bg=C["surface2"], fg=C["fg"],
                 hover_bg=C["surface3"], hover_fg=C["accent"],
                 font=("Segoe UI", 9), padx=12, pady=6, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font,
                         padx=padx, pady=pady, cursor="hand2", **kw)
        self._bg, self._fg = bg, fg
        self._hbg, self._hfg = hover_bg, hover_fg
        self._cmd = command
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _=None): self.config(bg=self._hbg, fg=self._hfg)
    def _on_leave(self, _=None): self.config(bg=self._bg, fg=self._fg)
    def _on_click(self, _=None):
        self._on_enter()
        if self._cmd:
            self.after(50, self._cmd)


class AccentButton(FlatButton):
    def __init__(self, parent, text="", command=None, **kw):
        super().__init__(parent, text=text, command=command,
                         bg=C["accent"], fg="#ffffff",
                         hover_bg="#9580ff", hover_fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), **kw)


def _mk_entry(parent, textvariable=None, width=32, show=None):
    """Plain-tk styled entry (no ttk)."""
    e = tk.Entry(parent, textvariable=textvariable, width=width,
                 bg=C["surface2"], fg=C["fg"], insertbackground=C["accent"],
                 selectbackground=C["accent"], selectforeground="#fff",
                 relief="flat", borderwidth=0,
                 highlightthickness=1, highlightbackground=C["border"],
                 highlightcolor=C["accent"],
                 font=("Segoe UI", 9))
    if show:
        e.config(show=show)
    return e


def _section_label(parent, text):
    tk.Label(parent, text=text, bg=C["surface"], fg=C["fg_muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(16, 4), padx=16)


# ---------------------------------------------------------------------------
# CustomTitleBar (section variant with Hub back button)
# ---------------------------------------------------------------------------

class CustomTitleBar(tk.Frame):
    def __init__(self, parent, app, title=""):
        super().__init__(parent, bg=C["bg"], height=36)
        self.pack_propagate(False)
        self.app = app
        self.root = app.root
        self._is_max = False
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<B1-Motion>", self._do_move)

        back = tk.Label(self, text="\u2b21 Hub", bg=C["bg"], fg=C["fg_muted"],
                        font=("Segoe UI", 8), padx=10, pady=6, cursor="hand2")
        back.pack(side=tk.LEFT)
        back.bind("<Enter>", lambda e: back.config(fg=C["accent"]))
        back.bind("<Leave>", lambda e: back.config(fg=C["fg_muted"]))
        back.bind("<Button-1>", lambda e: app.back_to_hub())

        tk.Frame(self, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=6)

        lbl = tk.Label(self, text=f" {title}", bg=C["bg"], fg=C["fg_dim"],
                       font=("Segoe UI", 9, "bold"))
        lbl.pack(side=tk.LEFT, padx=4)
        lbl.bind("<ButtonPress-1>", self._start_move)
        lbl.bind("<B1-Motion>", self._do_move)

        btns = tk.Frame(self, bg=C["bg"])
        btns.pack(side=tk.RIGHT, fill=tk.Y)
        FlatButton(btns, text="\u2014", command=self._minimize,
                   bg=C["bg"], hover_bg=C["surface3"], padx=14).pack(side=tk.LEFT, fill=tk.Y)
        self._max_btn = FlatButton(btns, text="\u2610", command=self._toggle_max,
                                   bg=C["bg"], hover_bg=C["surface3"], padx=14)
        self._max_btn.pack(side=tk.LEFT, fill=tk.Y)
        FlatButton(btns, text="\u2715", command=lambda: self.root.event_generate("WM_DELETE_WINDOW"),
                   bg=C["bg"], hover_bg=C["red"], hover_fg="#fff", padx=14).pack(side=tk.LEFT, fill=tk.Y)

    def _start_move(self, e):
        if not self._is_max:
            self.root.x, self.root.y = e.x, e.y

    def _do_move(self, e):
        if not self._is_max:
            x = self.root.winfo_x() + e.x - self.root.x
            y = self.root.winfo_y() + e.y - self.root.y
            self.root.geometry(f"+{x}+{y}")

    def _minimize(self):
        if platform.system() == "Windows":
            self.root.overrideredirect(False)
            self.root.iconify()
            self.root.bind("<Map>", lambda e: (
                self.root.overrideredirect(True), self.root.unbind("<Map>")))
        else:
            self.root.iconify()

    def _toggle_max(self):
        if self._is_max:
            self.root.geometry(self._norm_geo)
            self._is_max = False
            self._max_btn.config(text="\u2610")
        else:
            self._norm_geo = self.root.geometry()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self._is_max = True
            self._max_btn.config(text="\u2750")


# ---------------------------------------------------------------------------
# StatusBar
# ---------------------------------------------------------------------------

class StatusBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["surface"], height=26, **kw)
        self.pack_propagate(False)
        self._dot = tk.Label(self, text="\u25cf", bg=C["surface"], fg=C["green"],
                             font=("Segoe UI", 9))
        self._dot.pack(side=tk.LEFT, padx=(10, 4))
        self._msg = tk.Label(self, text="Ready", bg=C["surface"], fg=C["fg_dim"],
                             font=("Segoe UI", 9), anchor="w")
        self._msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._timer = None

    def set(self, msg, level="ok"):
        color = {"ok": C["green"], "warn": C["accent3"],
                 "error": C["red"], "info": C["accent2"]}.get(level, C["green"])
        self._dot.config(fg=color)
        self._msg.config(text=msg, fg=C["fg"])
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(5000, lambda: self._msg.config(text="Ready", fg=C["fg_dim"]))


# ---------------------------------------------------------------------------
# SettingsApp
# ---------------------------------------------------------------------------

class SettingsApp:
    """Full settings UI section. Launched from main.py hub."""

    def __init__(self, root: tk.Toplevel, on_close=None):
        self.root = root
        self.on_close = on_close
        self.sm = SettingsManager()  # fresh load

        root.title("Settings")
        root.overrideredirect(True)
        root.geometry("680x560")
        root.minsize(560, 440)
        root.configure(bg=C["border"])
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = 680, 560
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        root.protocol("WM_DELETE_WINDOW", self._on_destroy)

        self._frame = tk.Frame(root, bg=C["bg"],
                               highlightbackground=C["border"], highlightthickness=1)
        self._frame.pack(fill=tk.BOTH, expand=True)

        self._build_ui()

    # ---- hub integration ----

    def back_to_hub(self):
        self.sm.load()  # discard unsaved changes
        self._on_destroy()

    def _on_destroy(self):
        self.root.destroy()
        if self.on_close:
            self.on_close()

    # ---- UI ----

    def _build_ui(self):
        bar = CustomTitleBar(self._frame, self, "Settings")
        bar.pack(fill=tk.X)

        body = tk.Frame(self._frame, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        # ---- scrollable content ----
        canvas = tk.Canvas(body, bg=C["bg"], highlightthickness=0, bd=0)
        sb = tk.Scrollbar(body, orient="vertical", command=canvas.yview,
                          bg=C["scrollbar"], troughcolor=C["bg"], width=6)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=C["bg"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        self._build_content(inner)

        # ---- status + buttons at bottom ----
        foot = tk.Frame(self._frame, bg=C["surface"])
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Frame(foot, bg=C["border"], height=1).pack(fill=tk.X)
        btn_row = tk.Frame(foot, bg=C["surface"])
        btn_row.pack(fill=tk.X, padx=20, pady=10)
        AccentButton(btn_row, text="Save Settings", command=self._save).pack(side=tk.LEFT)
        FlatButton(btn_row, text="Reset Defaults", command=self._reset,
                   bg=C["surface2"], fg=C["fg_dim"],
                   hover_bg=C["surface3"], hover_fg=C["accent3"],
                   padx=10).pack(side=tk.LEFT, padx=8)

        self.status = StatusBar(self._frame)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_content(self, parent):
        uf, us = "Segoe UI", 9

        # ---- PATHS ----
        _section_label(parent, "PATHS")
        path_frame = tk.Frame(parent, bg=C["surface"], pady=2)
        path_frame.pack(fill=tk.X, padx=16, pady=(0, 4))
        path_frame.columnconfigure(1, weight=1)

        tk.Label(path_frame, text="save_data folder", bg=C["surface"], fg=C["fg_dim"],
                 font=(uf, us)).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        self._path_var = tk.StringVar(value=self.sm.save_data_path())
        path_entry = _mk_entry(path_frame, textvariable=self._path_var, width=48)
        path_entry.grid(row=0, column=1, sticky="ew", pady=4)
        FlatButton(path_frame, text="Browse\u2026", command=self._browse_save_data,
                   bg=C["surface2"], fg=C["accent2"], font=(uf, us - 1),
                   padx=8, pady=4).grid(row=0, column=2, padx=(6, 0), pady=4)

        hint = tk.Label(parent, text="  Point to the AI Influence save_data folder (contains campaign subfolders).",
                        bg=C["bg"], fg=C["fg_muted"], font=(uf, us - 1), anchor="w")
        hint.pack(fill=tk.X, padx=16, pady=(0, 8))

        # ---- BEHAVIOR ----
        _section_label(parent, "BEHAVIOR")
        row_ro = tk.Frame(parent, bg=C["bg"])
        row_ro.pack(fill=tk.X, padx=24, pady=2)
        self._readonly_var = tk.BooleanVar(value=self.sm.readonly_mode())
        self._mk_checkbox(row_ro, "Read-only mode (disables all file writes)",
                          self._readonly_var)

        # ---- LAST CAMPAIGN (info only) ----
        _section_label(parent, "SESSION")
        lc_frame = tk.Frame(parent, bg=C["surface"], pady=2)
        lc_frame.pack(fill=tk.X, padx=16, pady=(0, 4))
        lc_frame.columnconfigure(1, weight=1)
        tk.Label(lc_frame, text="Last campaign", bg=C["surface"], fg=C["fg_dim"],
                 font=(uf, us)).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        self._last_campaign_var = tk.StringVar(value=self.sm.last_campaign())
        lc_e = _mk_entry(lc_frame, textvariable=self._last_campaign_var, width=36)
        lc_e.config(state="readonly")
        lc_e.grid(row=0, column=1, sticky="ew", pady=4)
        FlatButton(lc_frame, text="Clear", command=self._clear_last_campaign,
                   bg=C["surface2"], fg=C["fg_muted"], font=(uf, us - 1),
                   padx=8, pady=4).grid(row=0, column=2, padx=(6, 0), pady=4)

        # ---- APPEARANCE ----
        _section_label(parent, "APPEARANCE")
        ui_frame = tk.Frame(parent, bg=C["surface"], pady=4)
        ui_frame.pack(fill=tk.X, padx=16, pady=(0, 16))
        ui_frame.columnconfigure(1, weight=1)

        tk.Label(ui_frame, text="UI font family", bg=C["surface"], fg=C["fg_dim"],
                 font=(uf, us)).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        self._font_var = tk.StringVar(value=self.sm.get("ui_font_family", "Segoe UI"))
        _mk_entry(ui_frame, textvariable=self._font_var, width=24).grid(
            row=0, column=1, sticky="w", pady=4)

        tk.Label(ui_frame, text="UI font size", bg=C["surface"], fg=C["fg_dim"],
                 font=(uf, us)).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)
        self._font_size_var = tk.IntVar(value=self.sm.get("ui_font_size", 10))
        sz_entry = _mk_entry(ui_frame, textvariable=self._font_size_var, width=6)
        sz_entry.grid(row=1, column=1, sticky="w", pady=4)

    def _mk_checkbox(self, parent, label, var):
        row = tk.Frame(parent, bg=C["bg"], cursor="hand2")
        row.pack(anchor="w", pady=2)
        box = tk.Canvas(row, width=16, height=16, bg=C["bg"],
                        highlightthickness=1, highlightbackground=C["border"],
                        cursor="hand2")
        box.pack(side=tk.LEFT)
        dot = [None]

        def _draw():
            box.delete("all")
            if var.get():
                box.create_rectangle(3, 3, 13, 13, fill=C["accent"], outline="")

        def _toggle(_=None):
            var.set(not var.get())
            _draw()

        box.bind("<Button-1>", _toggle)
        _draw()
        lbl = tk.Label(row, text=label, bg=C["bg"], fg=C["fg"],
                       font=("Segoe UI", 9), cursor="hand2")
        lbl.pack(side=tk.LEFT, padx=(6, 0))
        lbl.bind("<Button-1>", _toggle)
        var.trace_add("write", lambda *_: _draw())

    def _browse_save_data(self):
        from tkinter import filedialog
        current = self._path_var.get() or str(Path.home())
        d = filedialog.askdirectory(initialdir=current, title="Select save_data folder")
        if d:
            self._path_var.set(d)

    def _clear_last_campaign(self):
        self._last_campaign_var.set("")
        self.sm.set_last_campaign("")
        self.sm.save()
        self.status.set("Last campaign cleared", "ok")

    def _save(self):
        self.sm.set_save_data_path(self._path_var.get().strip())
        self.sm.set_readonly_mode(self._readonly_var.get())
        self.sm.set("ui_font_family", self._font_var.get().strip() or "Segoe UI")
        try:
            self.sm.set("ui_font_size", int(self._font_size_var.get()))
        except (ValueError, tk.TclError):
            pass
        if self.sm.save():
            self.status.set("Settings saved \u2713", "ok")
        else:
            self.status.set("Failed to save settings", "error")

    def _reset(self):
        for k, v in DEFAULT_SETTINGS.items():
            self.sm.set(k, v)
        self._path_var.set("")
        self._readonly_var.set(False)
        self._font_var.set("Segoe UI")
        self._font_size_var.set(10)
        self.status.set("Defaults restored (not saved)", "warn")


def main():
    root = tk.Tk()
    root.withdraw()
    app = SettingsApp(root)
    root.update_idletasks()
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
