#!/usr/bin/env python3
"""
Luminous AI — Settings Section
"""
import tkinter as tk
from tkinter import ttk, filedialog, font as tkfont
import platform
import json
import os
from pathlib import Path

C = {
    "bg":       "#0d0f14",
    "surface":  "#13161e",
    "surface2": "#1a1e29",
    "surface3": "#212537",
    "fg":       "#e2e8f0",
    "fg_dim":   "#7b879e",
    "fg_muted": "#445069",
    "accent":   "#7c6af7",
    "accent2":  "#38bdf8",
    "accent3":  "#f59e0b",
    "green":    "#22d3a0",
    "red":      "#f87171",
    "border":   "#252a38",
    "scrollbar":"#2a2f42",
}

DEFAULT_SETTINGS = {
    "default_json_dir":       "",
    "auto_load_last":         True,
    "ui_font_family":         "Segoe UI",
    "ui_font_size":           10,
    "content_font_family":    "Segoe UI",
    "content_font_size":      11,
    "code_font_family":       "Consolas",
    "code_font_size":         10,
    "autosave_delay_ms":      1000,
    "edit_mode_enabled":      False,
}


def get_config_path() -> Path:
    p = Path.home() / ".luminous_ai"
    p.mkdir(exist_ok=True)
    return p / "settings.json"


def load_settings() -> dict:
    cfg = dict(DEFAULT_SETTINGS)
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg.update(saved)
        except Exception:
            pass
    return cfg


def save_settings(data: dict):
    try:
        with open(get_config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


class CustomTitleBar(tk.Frame):
    def __init__(self, parent, root, title=""):
        super().__init__(parent, bg=C["bg"], height=36)
        self.pack_propagate(False)
        self._root = root
        self._is_max = False
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<B1-Motion>", self._do_move)
        lbl = tk.Label(self, text=f" {title}", bg=C["bg"], fg=C["fg_dim"],
                       font=("Segoe UI", 9, "bold"))
        lbl.pack(side=tk.LEFT, padx=12)
        lbl.bind("<ButtonPress-1>", self._start_move)
        lbl.bind("<B1-Motion>", self._do_move)
        btns = tk.Frame(self, bg=C["bg"])
        btns.pack(side=tk.RIGHT, fill=tk.Y)
        self._mk_btn(btns, "\u2014", self._minimize, C["bg"])
        self._max_btn = self._mk_btn(btns, "\u2610", self._toggle_max, C["bg"])
        self._mk_btn(btns, "\u2715", root.destroy, C["bg"], hover_bg=C["red"])

    def _mk_btn(self, parent, text, cmd, bg, hover_bg=None):
        hbg = hover_bg or C["surface3"]
        lbl = tk.Label(parent, text=text, bg=bg, fg=C["fg"],
                       font=("Segoe UI", 9), padx=14, pady=6, cursor="hand2")
        lbl.pack(side=tk.LEFT, fill=tk.Y)
        lbl.bind("<Enter>", lambda e: lbl.config(bg=hbg))
        lbl.bind("<Leave>", lambda e: lbl.config(bg=bg))
        lbl.bind("<Button-1>", lambda e: cmd())
        return lbl

    def _start_move(self, e):
        if not self._is_max:
            self._root.x, self._root.y = e.x, e.y

    def _do_move(self, e):
        if not self._is_max:
            x = self._root.winfo_x() + e.x - self._root.x
            y = self._root.winfo_y() + e.y - self._root.y
            self._root.geometry(f"+{x}+{y}")

    def _minimize(self):
        if platform.system() == "Windows":
            self._root.overrideredirect(False)
            self._root.iconify()
            self._root.bind("<Map>", lambda e: (
                self._root.overrideredirect(True), self._root.unbind("<Map>")))
        else:
            self._root.iconify()

    def _toggle_max(self):
        if self._is_max:
            self._root.geometry(self._norm_geo)
            self._is_max = False
            self._max_btn.config(text="\u2610")
        else:
            self._norm_geo = self._root.geometry()
            sw, sh = self._root.winfo_screenwidth(), self._root.winfo_screenheight()
            self._root.geometry(f"{sw}x{sh}+0+0")
            self._is_max = True
            self._max_btn.config(text="\u2750")


class ScrollableFrame(tk.Frame):
    """Vertically scrollable container."""
    def __init__(self, parent, bg=C["bg"], **kw):
        outer = tk.Frame(parent, bg=bg)
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, bg=bg, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                          bg=C["scrollbar"], troughcolor=C["bg"], width=6)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        super().__init__(canvas, bg=bg, **kw)
        self._win_id = canvas.create_window((0, 0), window=self, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self._win_id, width=e.width))
        self.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))


class FlatButton(tk.Label):
    def __init__(self, parent, text="", command=None, bg=C["surface2"], fg=C["fg"],
                 hover_bg=C["surface3"], hover_fg=C["accent"],
                 font=("Segoe UI", 9), padx=12, pady=6, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font,
                         padx=padx, pady=pady, cursor="hand2", **kw)
        self._bg, self._fg, self._hbg, self._hfg = bg, fg, hover_bg, hover_fg
        self._cmd = command
        self.bind("<Enter>", lambda _: self.config(bg=self._hbg, fg=self._hfg))
        self.bind("<Leave>", lambda _: self.config(bg=self._bg, fg=self._fg))
        self.bind("<Button-1>", lambda _: self._cmd() if self._cmd else None)


class AccentButton(FlatButton):
    def __init__(self, parent, text="", command=None, **kw):
        super().__init__(parent, text=text, command=command,
                         bg=C["accent"], fg="#ffffff",
                         hover_bg="#9580ff", hover_fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), **kw)


class StatusBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=C["surface"], height=26)
        self.pack_propagate(False)
        self._dot = tk.Label(self, text="\u25cf", bg=C["surface"], fg=C["green"],
                             font=("Segoe UI", 8))
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


class SettingsApp:
    def __init__(self, root: tk.Tk, on_close=None):
        self.root = root
        self._on_close = on_close
        self._cfg = load_settings()

        root.overrideredirect(True)
        root.configure(bg=C["bg"])
        root.geometry("820x680")
        root.resizable(True, True)
        root.minsize(640, 480)
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"820x680+{(sw-820)//2}+{(sh-680)//2}")

        self._setup_styles()
        self._build_ui()

    # ------------------------------------------------------------------ styles
    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        uf = (self._cfg["ui_font_family"], self._cfg["ui_font_size"])
        s.configure("TEntry", fieldbackground=C["surface2"], foreground=C["fg"],
                    insertcolor=C["accent"], borderwidth=0, padding=(8, 6), font=uf)
        s.configure("TScrollbar", background=C["scrollbar"], troughcolor=C["bg"],
                    borderwidth=0, arrowsize=0)
        s.configure("TCheckbutton", background=C["surface"], foreground=C["fg"], font=uf)
        s.map("TCheckbutton", background=[("active", C["surface2"])])
        s.configure("TScale", background=C["surface2"], troughcolor=C["surface3"], borderwidth=0)
        s.configure("TCombobox", fieldbackground=C["surface2"], background=C["surface2"],
                    foreground=C["fg"], borderwidth=0, font=uf)
        s.map("TCombobox", fieldbackground=[("readonly", C["surface2"])],
              selectbackground=[("readonly", C["accent"])])

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        bar = CustomTitleBar(self.root, self.root, title="Luminous AI \u2014 Settings")
        bar.pack(fill=tk.X)

        # nav row
        nav = tk.Frame(self.root, bg=C["bg"])
        nav.pack(fill=tk.X, padx=20, pady=(8, 0))
        back = tk.Label(nav, text="\u2190 Back to Hub", bg=C["bg"], fg=C["fg_dim"],
                        font=("Segoe UI", 9), cursor="hand2")
        back.pack(side=tk.LEFT)
        back.bind("<Enter>", lambda e: back.config(fg=C["accent"]))
        back.bind("<Leave>", lambda e: back.config(fg=C["fg_dim"]))
        back.bind("<Button-1>", lambda e: self._back_to_hub())

        # header
        hdr = tk.Frame(self.root, bg=C["bg"])
        hdr.pack(fill=tk.X, padx=32, pady=(12, 4))
        tk.Label(hdr, text="Settings", bg=C["bg"], fg=C["fg"],
                 font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)
        tk.Label(hdr, text="Persistent config: ~/.luminous_ai/settings.json",
                 bg=C["bg"], fg=C["fg_muted"],
                 font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(16, 0), pady=(6, 0))

        tk.Frame(self.root, bg=C["border"], height=1).pack(fill=tk.X, padx=32, pady=(6, 0))

        # scrollable body
        scroll = ScrollableFrame(self.root, bg=C["bg"])
        body = scroll

        # --- section helpers ---
        def section(txt):
            f = tk.Frame(body, bg=C["bg"])
            f.pack(fill=tk.X, padx=32, pady=(20, 6))
            tk.Label(f, text=txt, bg=C["bg"], fg=C["fg_muted"],
                     font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
            tk.Frame(f, bg=C["border"], height=1).pack(side=tk.LEFT, fill=tk.X,
                                                         expand=True, padx=(10, 0))

        def card():
            f = tk.Frame(body, bg=C["surface"],
                         highlightbackground=C["border"], highlightthickness=1)
            f.pack(fill=tk.X, padx=32, pady=3)
            return f

        def row_2col(parent, label, widget_factory):
            r = tk.Frame(parent, bg=C["surface"])
            r.pack(fill=tk.X, padx=20, pady=8)
            tk.Label(r, text=label, bg=C["surface"], fg=C["fg"],
                     font=("Segoe UI", 9)).pack(side=tk.LEFT)
            widget_factory(r)

        # ---- GENERAL ----
        section("GENERAL")
        c1 = card()

        # default JSON directory
        dir_row = tk.Frame(c1, bg=C["surface"])
        dir_row.pack(fill=tk.X, padx=20, pady=(14, 6))
        tk.Label(dir_row, text="Default JSON Directory", bg=C["surface"], fg=C["fg"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self._dir_var = tk.StringVar(value=self._cfg.get("default_json_dir", ""))
        dir_entry = ttk.Entry(dir_row, textvariable=self._dir_var, style="TEntry", width=32)
        dir_entry.pack(side=tk.LEFT, padx=(12, 6), expand=True, fill=tk.X)
        FlatButton(dir_row, text="\u2b21 Browse", command=self._browse_dir,
                   bg=C["surface2"], fg=C["accent2"],
                   font=("Segoe UI", 9), padx=10, pady=4).pack(side=tk.LEFT)

        # auto-load
        self._auto_var = tk.BooleanVar(value=self._cfg.get("auto_load_last", True))
        al_row = tk.Frame(c1, bg=C["surface"])
        al_row.pack(fill=tk.X, padx=20, pady=(0, 14))
        ttk.Checkbutton(al_row, text="Auto-load last opened file on startup",
                        variable=self._auto_var,
                        style="TCheckbutton").pack(side=tk.LEFT)

        # ---- FONTS ----
        section("FONTS")
        all_fonts = [f for f in sorted(set(tkfont.families())) if not f.startswith("@")]

        def font_card(label, hint, fkey, skey):
            fc = card()
            lf = tk.Frame(fc, bg=C["surface"])
            lf.pack(fill=tk.X, padx=20, pady=(12, 4))
            tk.Label(lf, text=label, bg=C["surface"], fg=C["fg"],
                     font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
            tk.Label(lf, text=hint, bg=C["surface"], fg=C["fg_muted"],
                     font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(8, 0))
            rf = tk.Frame(fc, bg=C["surface2"], pady=6)
            rf.pack(fill=tk.X, padx=20, pady=(0, 12))
            ff_var = tk.StringVar(value=self._cfg.get(fkey, "Segoe UI"))
            fs_var = tk.IntVar(value=self._cfg.get(skey, 10))
            size_lbl = tk.Label(rf, text=f"{fs_var.get()}pt",
                                bg=C["surface2"], fg=C["accent"],
                                font=("Segoe UI", 9, "bold"), width=5)
            ttk.Combobox(rf, textvariable=ff_var, values=all_fonts,
                         state="readonly", width=22).pack(side=tk.LEFT, padx=(12, 6))
            ttk.Scale(rf, from_=8, to=32, variable=fs_var, orient=tk.HORIZONTAL, length=160,
                      command=lambda v: size_lbl.config(
                          text=f"{int(float(v))}pt")).pack(side=tk.LEFT, padx=(0, 6))
            size_lbl.pack(side=tk.LEFT)
            return ff_var, fs_var

        self._ui_ff, self._ui_fs = font_card(
            "UI Font", "(requires restart)", "ui_font_family", "ui_font_size")
        self._c_ff, self._c_fs = font_card(
            "Content Font", "prose, logs", "content_font_family", "content_font_size")
        self._k_ff, self._k_fs = font_card(
            "Code Font", "JSON, stats", "code_font_family", "code_font_size")

        # ---- BEHAVIOUR ----
        section("BEHAVIOUR")
        bc = card()

        delay_row = tk.Frame(bc, bg=C["surface"])
        delay_row.pack(fill=tk.X, padx=20, pady=(14, 6))
        tk.Label(delay_row, text="Autosave Delay (ms)", bg=C["surface"], fg=C["fg"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self._delay_var = tk.StringVar(value=str(self._cfg.get("autosave_delay_ms", 1000)))
        ttk.Entry(delay_row, textvariable=self._delay_var,
                  style="TEntry", width=8).pack(side=tk.RIGHT, padx=(0, 12))

        self._edit_var = tk.BooleanVar(value=self._cfg.get("edit_mode_enabled", False))
        ec = tk.Frame(bc, bg=C["surface"],
                      highlightbackground=C["red"], highlightthickness=1)
        ec.pack(fill=tk.X, padx=20, pady=(4, 14))
        ei = tk.Frame(ec, bg=C["surface"])
        ei.pack(fill=tk.X, padx=16, pady=12)
        tk.Label(ei, text="\u26a0  Edit mode directly modifies JSON files on disk.",
                 bg=C["surface"], fg=C["red"],
                 font=("Segoe UI", 9, "bold"),
                 wraplength=640, justify="left").pack(anchor="w")
        tk.Label(ei, text="Changes are autosaved immediately. Ensure you have backups.",
                 bg=C["surface"], fg=C["fg_dim"],
                 font=("Segoe UI", 8), wraplength=640,
                 justify="left").pack(anchor="w", pady=(2, 8))
        ttk.Checkbutton(ei, text="Enable Edit Mode (EXPERIMENTAL)",
                        variable=self._edit_var,
                        style="TCheckbutton").pack(anchor="w")

        # spacer
        tk.Frame(body, bg=C["bg"], height=16).pack()

        # ---- footer buttons ----
        foot = tk.Frame(self.root, bg=C["surface"],
                        highlightbackground=C["border"], highlightthickness=1)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        btn_row = tk.Frame(foot, bg=C["surface"])
        btn_row.pack(fill=tk.X, padx=32, pady=10)
        AccentButton(btn_row, text="\u2713  Save Settings",
                     command=self._save, padx=16, pady=6).pack(side=tk.LEFT)
        FlatButton(btn_row, text="Reset to Defaults",
                   command=self._reset,
                   bg=C["surface2"], fg=C["fg_dim"],
                   hover_bg=C["surface3"], hover_fg=C["red"],
                   padx=12, pady=6).pack(side=tk.LEFT, padx=8)

        self._status = StatusBar(self.root)
        self._status.pack(fill=tk.X, side=tk.BOTTOM)

    # ------------------------------------------------------------------ actions
    def _browse_dir(self):
        current = self._dir_var.get()
        init = current if current and os.path.isdir(current) else str(Path.home())
        d = filedialog.askdirectory(initialdir=init)
        if d:
            self._dir_var.set(d)

    def _collect(self) -> dict:
        try:
            delay = int(self._delay_var.get())
        except ValueError:
            delay = 1000
        return {
            "default_json_dir":    self._dir_var.get().strip(),
            "auto_load_last":      self._auto_var.get(),
            "ui_font_family":      self._ui_ff.get(),
            "ui_font_size":        int(self._ui_fs.get()),
            "content_font_family": self._c_ff.get(),
            "content_font_size":   int(self._c_fs.get()),
            "code_font_family":    self._k_ff.get(),
            "code_font_size":      int(self._k_fs.get()),
            "autosave_delay_ms":   delay,
            "edit_mode_enabled":   self._edit_var.get(),
        }

    def _save(self):
        data = self._collect()
        save_settings(data)
        self._cfg = data
        self._status.set("Settings saved \u2713", "ok")

    def _reset(self):
        save_settings(dict(DEFAULT_SETTINGS))
        self._status.set("Reset to defaults \u2014 reopen Settings to see changes", "info")

    def _back_to_hub(self):
        if self._on_close:
            self._on_close()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    SettingsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
