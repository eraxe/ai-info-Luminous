#!/usr/bin/env python3
"""
Luminous AI — AI Characters Section
NPCViewerApp launched from main.py hub.
"""
import sys
import os

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, scrolledtext, messagebox, font as tkfont
    import json
    import re
    from pathlib import Path
    from jsonTemplate import (
        TEMPLATES, TABS, TAG_CONFIG, KNOWN_KEYS, RenderContext,
        TabDef, SubTabDef,
    )
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

# Colour lookup used by TAG_CONFIG fg keys
_TAG_FG = {
    "accent":  C["accent"],
    "accent2": C["accent2"],
    "accent3": C["accent3"],
    "fg":      C["fg"],
    "fg_dim":  C["fg_dim"],
    "fg_muted":C["fg_muted"],
    "green":   C["green"],
    "red":     C["red"],
    "border":  C["border"],
    "surface2":C["surface2"],
    "surface3":C["surface3"],
}


class Icons:
    FOLDER   = "\u2b21"
    REFRESH  = "\u21ba"
    BOOKMARK = "\u25c8"
    SEARCH   = "\u2315"
    COPY     = "\u2398"
    EXPORT   = "\u2197"


class FlatButton(tk.Label):
    def __init__(self, parent, text="", command=None, bg=C["surface2"], fg=C["fg"],
                 hover_bg=C["surface3"], hover_fg=C["accent"], font=("Segoe UI", 9),
                 padx=12, pady=6, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font,
                         padx=padx, pady=pady, cursor="hand2", **kw)
        self._bg, self._fg, self._hbg, self._hfg = bg, fg, hover_bg, hover_fg
        self._cmd = command
        self.bind("<Enter>",    lambda _: self.config(bg=self._hbg, fg=self._hfg))
        self.bind("<Leave>",    lambda _: self.config(bg=self._bg,  fg=self._fg))
        self.bind("<Button-1>", lambda _: self.after(50, self._cmd) if self._cmd else None)


class AccentButton(FlatButton):
    def __init__(self, parent, text="", command=None, **kw):
        super().__init__(parent, text=text, command=command,
                         bg=C["accent"], fg="#ffffff",
                         hover_bg="#9580ff", hover_fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), **kw)


class SidebarItem(tk.Frame):
    def __init__(self, parent, icon="", label="", command=None, **kw):
        super().__init__(parent, bg=C["surface"], cursor="hand2", **kw)
        self._cmd     = command
        self._active  = False
        self._ind     = tk.Frame(self, bg=C["surface"], width=3)
        self._ind.pack(side=tk.LEFT, fill=tk.Y)
        inner = tk.Frame(self, bg=C["surface"])
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 10), pady=6)
        self._icon_lbl = tk.Label(inner, text=icon, bg=C["surface"], fg=C["fg_dim"],
                                  font=("Segoe UI", 10))
        self._icon_lbl.pack(side=tk.LEFT)
        self._text_lbl = tk.Label(inner, text=label, bg=C["surface"], fg=C["fg_dim"],
                                  font=("Segoe UI", 9), anchor="w")
        self._text_lbl.pack(side=tk.LEFT, padx=(6, 0))
        for w in (self, inner, self._icon_lbl, self._text_lbl):
            w.bind("<Enter>",    self._hover_on)
            w.bind("<Leave>",    self._hover_off)
            w.bind("<Button-1>", self._click)

    def _all_widgets(self):
        return (self, self._icon_lbl, self._text_lbl, self.winfo_children()[1])

    def _hover_on(self, _=None):
        if not self._active:
            for w in self._all_widgets():
                w.config(bg=C["surface2"])

    def _hover_off(self, _=None):
        if not self._active:
            for w in self._all_widgets():
                w.config(bg=C["surface"])

    def _click(self, _=None):
        if self._cmd:
            self._cmd()

    def set_active(self, active: bool):
        self._active = active
        bg   = C["surface3"] if active else C["surface"]
        ind  = C["accent"]   if active else C["surface"]
        fi   = C["accent"]   if active else C["fg_dim"]
        ft   = C["fg"]       if active else C["fg_dim"]
        for w in self._all_widgets():
            w.config(bg=bg)
        self._icon_lbl.config(fg=fi)
        self._text_lbl.config(fg=ft)
        self._ind.config(bg=ind)


class StatusBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["surface"], height=26, **kw)
        self.pack_propagate(False)
        self._dot = tk.Label(self, text="\u25cf", bg=C["surface"], fg=C["green"],
                             font=("Segoe UI", 8))
        self._dot.pack(side=tk.LEFT, padx=(10, 4))
        self._msg = tk.Label(self, text="Ready", bg=C["surface"], fg=C["fg_dim"],
                             font=("Segoe UI", 9), anchor="w")
        self._msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._right = tk.Label(self, text="", bg=C["surface"], fg=C["fg_muted"],
                               font=("Segoe UI", 8))
        self._right.pack(side=tk.RIGHT, padx=10)
        self._timer = None

    def set(self, msg, level="ok", right=""):
        color = {"ok": C["green"], "warn": C["accent3"],
                 "error": C["red"], "info": C["accent2"]}.get(level, C["green"])
        self._dot.config(fg=color)
        self._msg.config(text=msg, fg=C["fg"])
        self._right.config(text=right)
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(5000,
                                 lambda: self._msg.config(text="Ready", fg=C["fg_dim"]))


class CustomTitleBar(tk.Frame):
    def __init__(self, parent, app, title=""):
        super().__init__(parent, bg=C["bg"], height=36)
        self.pack_propagate(False)
        self.app  = app
        self.root = app.root
        self.bind("<ButtonPress-1>",  self.start_move)
        self.bind("<B1-Motion>",      self.do_move)
        self.bind("<Double-Button-1>", lambda e: self.toggle_max())

        back = tk.Label(self, text="\u2b21 Hub", bg=C["bg"], fg=C["fg_muted"],
                        font=("Segoe UI", 8), padx=10, pady=6, cursor="hand2")
        back.pack(side=tk.LEFT)
        back.bind("<Enter>",    lambda e: back.config(fg=C["accent"]))
        back.bind("<Leave>",    lambda e: back.config(fg=C["fg_muted"]))
        back.bind("<Button-1>", lambda e: app.back_to_hub())

        tk.Frame(self, bg=C["border"], width=1).pack(
            side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=6)

        lbl = tk.Label(self, text=f" {title}", bg=C["bg"], fg=C["fg_dim"],
                       font=("Segoe UI", 9, "bold"))
        lbl.pack(side=tk.LEFT, padx=4)
        lbl.bind("<ButtonPress-1>",  self.start_move)
        lbl.bind("<B1-Motion>",      self.do_move)
        lbl.bind("<Double-Button-1>", lambda e: self.toggle_max())

        btns = tk.Frame(self, bg=C["bg"])
        btns.pack(side=tk.RIGHT, fill=tk.Y)
        FlatButton(btns, text="\u2014", command=self.min_app,
                   bg=C["bg"], hover_bg=C["surface3"], padx=14).pack(side=tk.LEFT, fill=tk.Y)
        self.max_btn = FlatButton(btns, text="\u2610", command=self.toggle_max,
                                  bg=C["bg"], hover_bg=C["surface3"], padx=14)
        self.max_btn.pack(side=tk.LEFT, fill=tk.Y)
        FlatButton(btns, text="\u2715", command=self.close_app,
                   bg=C["bg"], hover_bg=C["red"], hover_fg="#fff", padx=14
                   ).pack(side=tk.LEFT, fill=tk.Y)
        self._is_max = False

    def start_move(self, event):
        if not self._is_max:
            self.root.x, self.root.y = event.x, event.y

    def do_move(self, event):
        if not self._is_max:
            x = self.root.winfo_x() + event.x - self.root.x
            y = self.root.winfo_y() + event.y - self.root.y
            self.root.geometry(f"+{x}+{y}")

    def min_app(self):    self.app.minimize()

    def toggle_max(self):
        if self._is_max:
            if hasattr(self, "_normal_geo"):
                self.root.geometry(self._normal_geo)
            self._is_max = False
            self.max_btn.config(text="\u2610")
            self.app.grip.place(relx=1.0, rely=1.0, anchor="se")
        else:
            self._normal_geo = self.root.geometry()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self._is_max = True
            self.max_btn.config(text="\u2750")
            self.app.grip.place_forget()

    def close_app(self):
        handler = self.root.protocol("WM_DELETE_WINDOW")
        if handler:
            self.root.tk.call(handler)
        else:
            self.app.back_to_hub()


# ---------------------------------------------------------------------------
# NPCViewerApp
# ---------------------------------------------------------------------------

class NPCViewerApp:
    """
    NPC / character JSON viewer.
    Called by main.py hub:  NPCViewerApp(toplevel, on_close=callback)
    TABS is list[TabDef]; each TabDef may have subtabs: list[SubTabDef].
    Templates render into a scrolledtext widget using TAG_CONFIG colour tags.
    """

    FONT      = "Segoe UI"
    FONT_MONO = "Consolas"
    FONT_SIZE = 9

    def __init__(self, root: tk.Toplevel, on_close=None):
        self.root      = root
        self._on_close = on_close

        self._char_dir:    Path | None = None
        self._all_files:   list[Path]  = []
        self._shown_files: list[Path]  = []
        self._current_file: Path | None = None
        self._current_data: dict        = {}
        self._search_var = tk.StringVar()
        self._render_ctx = RenderContext()

        # active tab / subtab — stored as TabDef / SubTabDef objects
        self._active_tab:    TabDef    | None = TABS[0] if TABS else None
        self._active_subtab: SubTabDef | None = (
            TABS[0].subtabs[0] if TABS and TABS[0].subtabs else None
        )

        root.overrideredirect(True)
        root.configure(bg=C["bg"])
        root.geometry("1120x700")
        root.resizable(True, True)
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"1120x700+{(sw - 1120)//2}+{(sh - 700)//2}")
        root.protocol("WM_DELETE_WINDOW", self.back_to_hub)
        root.minsize(760, 480)

        self._build_ui()
        self.status.set("Ready — open a folder to load characters", "info")

    # ------------------------------------------------------------------
    # UI BUILD
    # ------------------------------------------------------------------

    def _build_ui(self):
        # title bar
        self.title_bar = CustomTitleBar(self.root, self, title="AI Characters")
        self.title_bar.pack(fill=tk.X)

        # resize grip
        self.grip = tk.Label(self.root, text="\u22f1", bg=C["bg"],
                             fg=C["fg_muted"], font=(self.FONT, 10), cursor="size_nw_se")
        self.grip.place(relx=1.0, rely=1.0, anchor="se")
        self.grip.bind("<ButtonPress-1>", self._resize_start)
        self.grip.bind("<B1-Motion>",     self._resize_drag)

        # toolbar
        tb = tk.Frame(self.root, bg=C["surface"], height=38)
        tb.pack(fill=tk.X)
        tb.pack_propagate(False)
        FlatButton(tb, text=f"{Icons.FOLDER} Open Folder",
                   command=self._open_folder, padx=14).pack(side=tk.LEFT, padx=(8, 2), pady=4)
        FlatButton(tb, text=f"{Icons.REFRESH} Refresh",
                   command=self._refresh,     padx=10).pack(side=tk.LEFT, padx=2, pady=4)
        FlatButton(tb, text=f"{Icons.EXPORT} Export JSON",
                   command=self._export_json, padx=10).pack(side=tk.LEFT, padx=2, pady=4)
        AccentButton(tb, text=f"{Icons.COPY} Copy JSON",
                     command=self._copy_json, padx=10).pack(side=tk.LEFT, padx=2, pady=4)

        sf = tk.Frame(tb, bg=C["surface2"],
                      highlightbackground=C["border"], highlightthickness=1)
        sf.pack(side=tk.RIGHT, padx=10, pady=6, ipady=1)
        tk.Label(sf, text=Icons.SEARCH, bg=C["surface2"], fg=C["fg_dim"],
                 font=(self.FONT, 9), padx=6).pack(side=tk.LEFT)
        self._search_entry = tk.Entry(sf, textvariable=self._search_var,
                                      bg=C["surface2"], fg=C["fg"],
                                      insertbackground=C["fg"],
                                      relief=tk.FLAT, width=22,
                                      font=(self.FONT, self.FONT_SIZE))
        self._search_entry.pack(side=tk.LEFT, pady=2, padx=(0, 6))
        self._search_var.trace_add("write", lambda *_: self._filter_list())

        tk.Frame(self.root, bg=C["border"], height=1).pack(fill=tk.X)

        # body: sidebar | divider | right panel
        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        # sidebar
        sidebar = tk.Frame(body, bg=C["surface"], width=210)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        hdr = tk.Frame(sidebar, bg=C["surface"])
        hdr.pack(fill=tk.X, padx=10, pady=(10, 4))
        tk.Label(hdr, text="CHARACTERS", bg=C["surface"], fg=C["fg_muted"],
                 font=(self.FONT, 7, "bold")).pack(side=tk.LEFT)
        self._count_lbl = tk.Label(hdr, text="0", bg=C["surface"],
                                   fg=C["accent"], font=(self.FONT, 7, "bold"))
        self._count_lbl.pack(side=tk.RIGHT)

        lc = tk.Frame(sidebar, bg=C["surface"])
        lc.pack(fill=tk.BOTH, expand=True)
        self._list_canvas = tk.Canvas(lc, bg=C["surface"], highlightthickness=0, bd=0)
        lsb = tk.Scrollbar(lc, orient=tk.VERTICAL, command=self._list_canvas.yview)
        self._list_canvas.configure(yscrollcommand=lsb.set)
        lsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._list_frame = tk.Frame(self._list_canvas, bg=C["surface"])
        self._lcw = self._list_canvas.create_window((0, 0), window=self._list_frame, anchor="nw")
        self._list_frame.bind("<Configure>",
            lambda _: self._list_canvas.configure(
                scrollregion=self._list_canvas.bbox("all")))
        self._list_canvas.bind("<Configure>",
            lambda e: self._list_canvas.itemconfig(self._lcw, width=e.width))
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._list_canvas.bind(ev, self._list_scroll)

        self._sidebar_items: list[SidebarItem] = []
        self._active_idx: int | None = None

        tk.Frame(body, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        # right panel
        right = tk.Frame(body, bg=C["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # tab bar (TabDef objects)
        self._tab_bar = tk.Frame(right, bg=C["surface"], height=34)
        self._tab_bar.pack(fill=tk.X)
        self._tab_bar.pack_propagate(False)
        self._tab_btns: dict[str, tk.Label] = {}   # key -> Label
        for td in TABS:
            self._make_tab_btn(td)

        # subtab bar  (shown only when active tab has subtabs)
        self._subtab_bar = tk.Frame(right, bg=C["surface2"], height=28)
        self._subtab_btns: dict[str, tk.Label] = {}
        self._refresh_subtab_bar()

        tk.Frame(right, bg=C["border"], height=1).pack(fill=tk.X)

        # scrolled text detail view
        self._text = scrolledtext.ScrolledText(
            right,
            bg=C["bg"], fg=C["fg"],
            insertbackground=C["fg"],
            selectbackground=C["surface3"],
            relief=tk.FLAT, bd=0,
            wrap=tk.WORD,
            padx=18, pady=12,
            font=(self.FONT, self.FONT_SIZE),
            state="disabled",
        )
        self._text.pack(fill=tk.BOTH, expand=True)
        self._configure_tags()

        # status bar
        self.status = StatusBar(self.root)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

        self._show_empty_prompt()

    # ------------------------------------------------------------------
    # TAG CONFIGURATION  (maps TAG_CONFIG dicts → Text widget tags)
    # ------------------------------------------------------------------

    def _configure_tags(self):
        base_font  = tkfont.Font(family=self.FONT,      size=self.FONT_SIZE)
        mono_font  = tkfont.Font(family=self.FONT_MONO, size=self.FONT_SIZE)
        for tag, cfg in TAG_CONFIG.items():
            delta     = cfg.get("font_delta", 0)
            weight    = cfg.get("weight", "normal")
            fg_key    = cfg.get("fg", "fg")
            fg        = _TAG_FG.get(fg_key, C["fg"])
            bg_key    = cfg.get("bg")
            bg        = _TAG_FG.get(bg_key, C["bg"]) if bg_key else C["bg"]
            use_mono  = cfg.get("use_code_font", False)
            size      = self.FONT_SIZE + delta
            if use_mono:
                fnt = tkfont.Font(family=self.FONT_MONO, size=size, weight=weight)
            elif weight == "italic":
                fnt = tkfont.Font(family=self.FONT, size=size,
                                  weight="normal", slant="italic")
            else:
                fnt = tkfont.Font(family=self.FONT, size=size, weight=weight)
            kw = dict(font=fnt, foreground=fg, background=bg)
            if "spacing1" in cfg: kw["spacing1"] = cfg["spacing1"]
            if "spacing3" in cfg: kw["spacing3"] = cfg["spacing3"]
            if "lmargin1" in cfg: kw["lmargin1"] = cfg["lmargin1"]
            if "lmargin2" in cfg: kw["lmargin2"] = cfg["lmargin2"]
            self._text.tag_configure(tag, **kw)

    # ------------------------------------------------------------------
    # TAB & SUBTAB BAR
    # ------------------------------------------------------------------

    def _make_tab_btn(self, td: TabDef):
        is_active = (self._active_tab and td.key == self._active_tab.key)
        lbl = tk.Label(
            self._tab_bar,
            text=f"{td.icon} {td.label}",
            bg=C["surface"],
            fg=C["accent"] if is_active else C["fg_dim"],
            font=(self.FONT, self.FONT_SIZE,
                  "bold" if is_active else "normal"),
            padx=14, pady=8, cursor="hand2",
        )
        lbl.pack(side=tk.LEFT)
        lbl.bind("<Button-1>", lambda e, t=td: self._switch_tab(t))
        lbl.bind("<Enter>",    lambda e, b=lbl, t=td:
                 b.config(fg=C["accent"]) if self._active_tab and t.key != self._active_tab.key else None)
        lbl.bind("<Leave>",    lambda e, b=lbl, t=td:
                 b.config(fg=C["fg_dim"]) if self._active_tab and t.key != self._active_tab.key else None)
        self._tab_btns[td.key] = lbl

    def _switch_tab(self, td: TabDef):
        self._active_tab = td
        self._active_subtab = td.subtabs[0] if td.subtabs else None
        for key, btn in self._tab_btns.items():
            active = (key == td.key)
            btn.config(fg=C["accent"] if active else C["fg_dim"],
                       font=(self.FONT, self.FONT_SIZE,
                             "bold" if active else "normal"))
        self._refresh_subtab_bar()
        self._render_detail()

    def _refresh_subtab_bar(self):
        """Show/hide subtab bar and populate it for the current active tab."""
        for w in self._subtab_bar.winfo_children():
            w.destroy()
        self._subtab_btns.clear()

        td = self._active_tab
        if td and td.subtabs:
            self._subtab_bar.pack(fill=tk.X, after=self._tab_bar)
            for st in td.subtabs:
                is_active = (self._active_subtab and st.key == self._active_subtab.key)
                btn = tk.Label(
                    self._subtab_bar,
                    text=st.label,
                    bg=C["surface2"],
                    fg=C["accent"] if is_active else C["fg_dim"],
                    font=(self.FONT, 8, "bold" if is_active else "normal"),
                    padx=12, pady=5, cursor="hand2",
                )
                btn.pack(side=tk.LEFT)
                btn.bind("<Button-1>", lambda e, s=st: self._switch_subtab(s))
                btn.bind("<Enter>",    lambda e, b=btn, s=st:
                         b.config(fg=C["accent"])
                         if self._active_subtab and s.key != self._active_subtab.key else None)
                btn.bind("<Leave>",    lambda e, b=btn, s=st:
                         b.config(fg=C["fg_dim"])
                         if self._active_subtab and s.key != self._active_subtab.key else None)
                self._subtab_btns[st.key] = btn
        else:
            self._subtab_bar.pack_forget()

    def _switch_subtab(self, st: SubTabDef):
        self._active_subtab = st
        for key, btn in self._subtab_btns.items():
            active = (key == st.key)
            btn.config(fg=C["accent"] if active else C["fg_dim"],
                       font=(self.FONT, 8, "bold" if active else "normal"))
        self._render_detail()

    # ------------------------------------------------------------------
    # RESIZE GRIP
    # ------------------------------------------------------------------

    def _resize_start(self, event):
        self._rx, self._ry = event.x_root, event.y_root
        self._rw, self._rh = self.root.winfo_width(), self.root.winfo_height()

    def _resize_drag(self, event):
        nw = max(760, self._rw + event.x_root - self._rx)
        nh = max(480, self._rh + event.y_root - self._ry)
        self.root.geometry(f"{nw}x{nh}")

    # ------------------------------------------------------------------
    # SIDEBAR SCROLLING
    # ------------------------------------------------------------------

    def _list_scroll(self, event):
        d = -1 if (getattr(event, "delta", 0) > 0 or event.num == 4) else 1
        self._list_canvas.yview_scroll(d, "units")

    # ------------------------------------------------------------------
    # FILE OPERATIONS
    # ------------------------------------------------------------------

    def _open_folder(self):
        d = filedialog.askdirectory(title="Select NPC character folder")
        if d:
            self._char_dir = Path(d)
            self._load_files()

    def _load_files(self):
        if not self._char_dir:
            return
        self._all_files = sorted(self._char_dir.glob("*.json"))
        self._shown_files = list(self._all_files)
        self._rebuild_sidebar()
        n = len(self._all_files)
        self.status.set(f"Loaded {n} character{'s' if n != 1 else ''} "
                        f"from ‘{self._char_dir.name}’",
                        "ok", right=str(self._char_dir))
        if self._all_files:
            self._select(0)

    def _refresh(self):
        if self._char_dir:
            self._load_files()
            self.status.set("Refreshed", "ok")
        else:
            self.status.set("No folder open", "warn")

    # ------------------------------------------------------------------
    # SIDEBAR
    # ------------------------------------------------------------------

    def _rebuild_sidebar(self):
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._sidebar_items = []
        self._active_idx    = None
        for i, fp in enumerate(self._shown_files):
            item = SidebarItem(self._list_frame, icon=Icons.BOOKMARK,
                               label=fp.stem,
                               command=lambda idx=i: self._select(idx))
            item.pack(fill=tk.X)
            self._sidebar_items.append(item)
        self._count_lbl.config(text=str(len(self._shown_files)))

    def _filter_list(self):
        q = self._search_var.get().lower().strip()
        self._shown_files = (
            [f for f in self._all_files if q in f.stem.lower()]
            if q else list(self._all_files)
        )
        self._rebuild_sidebar()
        if self._shown_files:
            self._select(0)

    def _select(self, idx: int):
        if idx < 0 or idx >= len(self._sidebar_items):
            return
        if self._active_idx is not None:
            self._sidebar_items[self._active_idx].set_active(False)
        self._active_idx = idx
        self._sidebar_items[idx].set_active(True)
        self._load_char_file(self._shown_files[idx])

    def _load_char_file(self, fp: Path):
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._current_file = fp
            self._current_data = data
            self._render_detail()
            self.status.set(f"Loaded: {fp.name}", "ok", right=fp.name)
        except Exception as exc:
            self.status.set(f"Error: {exc}", "error")
            messagebox.showerror("Load Error", str(exc))

    # ------------------------------------------------------------------
    # DETAIL RENDERING
    # ------------------------------------------------------------------

    def _show_empty_prompt(self):
        self._text.config(state="normal")
        self._text.delete("1.0", tk.END)
        self._text.insert(tk.END, "\n\n  Open a folder to browse characters.\n", "null_val")
        self._text.insert(tk.END, "  Click \u2b21 Open Folder in the toolbar.\n", "muted")
        self._text.config(state="disabled")

    def _render_detail(self):
        if not self._current_data:
            self._show_empty_prompt()
            return

        td = self._active_tab
        if not td:
            return

        self._text.config(state="normal")
        self._text.delete("1.0", tk.END)

        # Determine which template key(s) to render
        if td.key == "raw":
            self._text.insert(tk.END,
                json.dumps(self._current_data, indent=2, ensure_ascii=False), "code")
            self._text.config(state="disabled")
            return

        if td.subtabs and self._active_subtab:
            keys = self._active_subtab.templates
        else:
            keys = td.templates

        ctx = self._render_ctx
        rendered_any = False
        for tpl_key in keys:
            tpl = TEMPLATES.get(tpl_key)
            if tpl:
                try:
                    tpl.render(self._text, self._current_data, ctx)
                    rendered_any = True
                except Exception as exc:
                    self._text.config(state="normal")
                    self._text.insert(tk.END,
                        f"\n  [Render error in '{tpl_key}': {exc}]\n", "bad")

        if not rendered_any:
            # fallback: show all data as raw JSON
            self._text.config(state="normal")
            self._text.insert(tk.END,
                json.dumps(self._current_data, indent=2, ensure_ascii=False), "code")

        self._text.config(state="disabled")

    # ------------------------------------------------------------------
    # EXPORT / COPY
    # ------------------------------------------------------------------

    def _copy_json(self):
        if not self._current_data:
            self.status.set("Nothing to copy — no character loaded", "warn")
            return
        txt = json.dumps(self._current_data, ensure_ascii=False, indent=2)
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        name = self._current_file.name if self._current_file else "?"
        self.status.set(f"Copied JSON for {name}", "ok")

    def _export_json(self):
        if not self._current_data:
            self.status.set("Nothing to export — no character loaded", "warn")
            return
        default = self._current_file.name if self._current_file else "character.json"
        out = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=default,
            title="Export Character JSON",
        )
        if not out:
            return
        try:
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(self._current_data, fh, ensure_ascii=False, indent=2)
            self.status.set(f"Exported to {Path(out).name}", "ok")
        except Exception as exc:
            self.status.set(f"Export failed: {exc}", "error")
            messagebox.showerror("Export Error", str(exc))

    # ------------------------------------------------------------------
    # HUB NAVIGATION
    # ------------------------------------------------------------------

    def back_to_hub(self):
        if self._on_close:
            self._on_close()

    def minimize(self):
        self.root.iconify()
