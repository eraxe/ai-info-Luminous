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


# ---------------------------------------------------------------------------
# NPCViewerApp — main entry point called by main.py hub
# ---------------------------------------------------------------------------

class NPCViewerApp:
    """
    Full NPC/character JSON viewer and editor.
    Expects:  root (tk.Toplevel)  +  on_close callback from main.py hub.
    """

    UI_FONT = "Segoe UI"
    UI_SIZE = 9

    def __init__(self, root: tk.Toplevel, on_close=None):
        self.root = root
        self._on_close = on_close
        self._char_dir: Path | None = None
        self._files: list[Path] = []
        self._current_file: Path | None = None
        self._current_data: dict = {}
        self._search_var = tk.StringVar()
        self._pinned: set[str] = set()
        self._render_ctx = RenderContext()

        root.overrideredirect(True)
        root.configure(bg=C["bg"])
        root.geometry("1100x680")
        root.resizable(True, True)
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"1100x680+{(sw - 1100) // 2}+{(sh - 680) // 2}")
        root.protocol("WM_DELETE_WINDOW", self.back_to_hub)
        root.minsize(760, 480)

        self._build_ui()
        self.status.set("Ready — open a folder to load characters", "info")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Title bar
        self.title_bar = CustomTitleBar(self.root, self, title="AI Characters")
        self.title_bar.pack(fill=tk.X)

        # Resize grip
        self.grip = tk.Label(self.root, text="\u22f1", bg=C["bg"], fg=C["fg_muted"],
                             font=(self.UI_FONT, 10), cursor="size_nw_se")
        self.grip.place(relx=1.0, rely=1.0, anchor="se")
        self.grip.bind("<ButtonPress-1>", self._resize_start)
        self.grip.bind("<B1-Motion>", self._resize_drag)

        # Toolbar
        toolbar = tk.Frame(self.root, bg=C["surface"], height=38)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        FlatButton(toolbar, text=f"{Icons.FOLDER} Open Folder",
                   command=self._open_folder, padx=14).pack(side=tk.LEFT, padx=(8, 2), pady=4)
        FlatButton(toolbar, text=f"{Icons.REFRESH} Refresh",
                   command=self._refresh, padx=10).pack(side=tk.LEFT, padx=2, pady=4)
        FlatButton(toolbar, text=f"{Icons.EXPORT} Export JSON",
                   command=self._export_json, padx=10).pack(side=tk.LEFT, padx=2, pady=4)
        AccentButton(toolbar, text=f"{Icons.COPY} Copy JSON",
                     command=self._copy_json, padx=10).pack(side=tk.LEFT, padx=2, pady=4)

        # Search
        search_frame = tk.Frame(toolbar, bg=C["surface2"],
                                highlightbackground=C["border"], highlightthickness=1)
        search_frame.pack(side=tk.RIGHT, padx=10, pady=6, ipady=1)
        tk.Label(search_frame, text=Icons.SEARCH, bg=C["surface2"], fg=C["fg_dim"],
                 font=(self.UI_FONT, 9), padx=6).pack(side=tk.LEFT)
        self._search_entry = tk.Entry(search_frame, textvariable=self._search_var,
                                      bg=C["surface2"], fg=C["fg"], insertbackground=C["fg"],
                                      relief=tk.FLAT, width=22,
                                      font=(self.UI_FONT, self.UI_SIZE))
        self._search_entry.pack(side=tk.LEFT, pady=2, padx=(0, 6))
        self._search_var.trace_add("write", lambda *_: self._filter_list())

        # Divider
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill=tk.X)

        # Main pane: sidebar + content
        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        self._sidebar = tk.Frame(body, bg=C["surface"], width=220)
        self._sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self._sidebar.pack_propagate(False)

        sidebar_hdr = tk.Frame(self._sidebar, bg=C["surface"])
        sidebar_hdr.pack(fill=tk.X, padx=10, pady=(10, 4))
        tk.Label(sidebar_hdr, text="CHARACTERS", bg=C["surface"], fg=C["fg_muted"],
                 font=(self.UI_FONT, 7, "bold")).pack(side=tk.LEFT)
        self._count_lbl = tk.Label(sidebar_hdr, text="0", bg=C["surface"], fg=C["accent"],
                                   font=(self.UI_FONT, 7, "bold"))
        self._count_lbl.pack(side=tk.RIGHT)

        list_container = tk.Frame(self._sidebar, bg=C["surface"])
        list_container.pack(fill=tk.BOTH, expand=True)

        self._list_canvas = tk.Canvas(list_container, bg=C["surface"], highlightthickness=0,
                                      bd=0)
        list_sb = tk.Scrollbar(list_container, orient=tk.VERTICAL,
                               command=self._list_canvas.yview)
        self._list_canvas.configure(yscrollcommand=list_sb.set)
        list_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._list_frame = tk.Frame(self._list_canvas, bg=C["surface"])
        self._list_canvas_window = self._list_canvas.create_window(
            (0, 0), window=self._list_frame, anchor="nw")
        self._list_frame.bind("<Configure>", self._on_list_configure)
        self._list_canvas.bind("<Configure>", self._on_canvas_configure)
        self._list_canvas.bind("<MouseWheel>", self._on_list_scroll)
        self._list_canvas.bind("<Button-4>", self._on_list_scroll)
        self._list_canvas.bind("<Button-5>", self._on_list_scroll)

        self._sidebar_items: list[SidebarItem] = []
        self._active_sidebar_idx: int | None = None

        # Vertical divider
        tk.Frame(body, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Right panel: tabs + detail
        right = tk.Frame(body, bg=C["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tab bar
        self._tab_bar = tk.Frame(right, bg=C["surface"], height=34)
        self._tab_bar.pack(fill=tk.X)
        self._tab_bar.pack_propagate(False)
        self._tab_btns: dict[str, tk.Label] = {}
        self._active_tab = tk.StringVar(value=TABS[0] if TABS else "Overview")
        for tab_name in TABS:
            self._make_tab_btn(tab_name)

        tk.Frame(right, bg=C["border"], height=1).pack(fill=tk.X)

        # Detail scroll area
        detail_outer = tk.Frame(right, bg=C["bg"])
        detail_outer.pack(fill=tk.BOTH, expand=True)

        self._detail_canvas = tk.Canvas(detail_outer, bg=C["bg"], highlightthickness=0, bd=0)
        detail_sb = tk.Scrollbar(detail_outer, orient=tk.VERTICAL,
                                 command=self._detail_canvas.yview)
        self._detail_canvas.configure(yscrollcommand=detail_sb.set)
        detail_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._detail_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._detail_frame = tk.Frame(self._detail_canvas, bg=C["bg"])
        self._detail_canvas_window = self._detail_canvas.create_window(
            (0, 0), window=self._detail_frame, anchor="nw")
        self._detail_frame.bind("<Configure>", self._on_detail_configure)
        self._detail_canvas.bind("<Configure>", self._on_detail_canvas_configure)
        self._detail_canvas.bind("<MouseWheel>", self._on_detail_scroll)
        self._detail_canvas.bind("<Button-4>", self._on_detail_scroll)
        self._detail_canvas.bind("<Button-5>", self._on_detail_scroll)

        # Status bar
        self.status = StatusBar(self.root, self.UI_FONT, self.UI_SIZE)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

        self._show_empty_detail()

    def _make_tab_btn(self, name: str):
        is_first = not self._tab_btns
        btn = tk.Label(self._tab_bar, text=name, bg=C["surface"],
                       fg=C["accent"] if is_first else C["fg_dim"],
                       font=(self.UI_FONT, self.UI_SIZE,
                             "bold" if is_first else "normal"),
                       padx=16, pady=8, cursor="hand2")
        btn.pack(side=tk.LEFT)
        if is_first:
            tk.Frame(self._tab_bar, bg=C["accent"], height=2,
                     width=btn.winfo_reqwidth()).place(in_=btn, relx=0, rely=1.0, anchor="sw")
        btn.bind("<Button-1>", lambda e, n=name: self._switch_tab(n))
        btn.bind("<Enter>", lambda e, b=btn: b.config(fg=C["accent"])
                 if self._active_tab.get() != name else None)
        btn.bind("<Leave>", lambda e, b=btn, n=name:
                 b.config(fg=C["accent"] if self._active_tab.get() == n else C["fg_dim"]))
        self._tab_btns[name] = btn

    # ------------------------------------------------------------------
    # Scroll helpers
    # ------------------------------------------------------------------

    def _on_list_configure(self, _=None):
        self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._list_canvas.itemconfig(self._list_canvas_window, width=event.width)

    def _on_list_scroll(self, event):
        delta = -1 if (getattr(event, "delta", 0) > 0 or event.num == 4) else 1
        self._list_canvas.yview_scroll(delta, "units")

    def _on_detail_configure(self, _=None):
        self._detail_canvas.configure(scrollregion=self._detail_canvas.bbox("all"))

    def _on_detail_canvas_configure(self, event):
        self._detail_canvas.itemconfig(self._detail_canvas_window, width=event.width)

    def _on_detail_scroll(self, event):
        delta = -1 if (getattr(event, "delta", 0) > 0 or event.num == 4) else 1
        self._detail_canvas.yview_scroll(delta, "units")

    # ------------------------------------------------------------------
    # Resize grip
    # ------------------------------------------------------------------

    def _resize_start(self, event):
        self._rx = event.x_root
        self._ry = event.y_root
        self._rw = self.root.winfo_width()
        self._rh = self.root.winfo_height()

    def _resize_drag(self, event):
        nw = max(760, self._rw + event.x_root - self._rx)
        nh = max(480, self._rh + event.y_root - self._ry)
        self.root.geometry(f"{nw}x{nh}")

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _open_folder(self):
        d = filedialog.askdirectory(title="Select NPC character folder")
        if not d:
            return
        self._char_dir = Path(d)
        self._load_files()

    def _load_files(self):
        if not self._char_dir:
            return
        self._files = sorted(self._char_dir.glob("*.json"))
        self._rebuild_sidebar(self._files)
        count = len(self._files)
        self.status.set(f"Loaded {count} character{'s' if count != 1 else ''} "
                        f"from {self._char_dir.name}", "ok",
                        right=str(self._char_dir))
        self._count_lbl.config(text=str(count))
        if self._files:
            self._select_file(0)

    def _refresh(self):
        if self._char_dir:
            self._load_files()
            self.status.set("Refreshed", "ok")
        else:
            self.status.set("No folder open", "warn")

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _rebuild_sidebar(self, files: list[Path]):
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._sidebar_items = []
        self._active_sidebar_idx = None
        for i, fp in enumerate(files):
            item = SidebarItem(
                self._list_frame,
                icon=Icons.BOOKMARK,
                label=fp.stem,
                command=lambda idx=i: self._select_file(idx),
                ui_font=self.UI_FONT,
                ui_size=self.UI_SIZE,
            )
            item.pack(fill=tk.X)
            self._sidebar_items.append(item)

    def _filter_list(self):
        query = self._search_var.get().lower().strip()
        if not self._files:
            return
        filtered = [f for f in self._files if query in f.stem.lower()] if query else self._files
        self._rebuild_sidebar(filtered)
        self._count_lbl.config(text=str(len(filtered)))
        if filtered:
            self._select_file_by_path(filtered[0])

    def _select_file(self, idx: int):
        if idx < 0 or idx >= len(self._sidebar_items):
            return
        if self._active_sidebar_idx is not None:
            self._sidebar_items[self._active_sidebar_idx].set_active(False)
        self._active_sidebar_idx = idx
        self._sidebar_items[idx].set_active(True)
        # Map sidebar index back to actual file list via stem matching
        stem = self._sidebar_items[idx]._text_lbl.cget("text")
        match = next((f for f in self._files if f.stem == stem), None)
        if match:
            self._load_char_file(match)

    def _select_file_by_path(self, fp: Path):
        for i, item in enumerate(self._sidebar_items):
            if item._text_lbl.cget("text") == fp.stem:
                self._select_file(i)
                return

    def _load_char_file(self, fp: Path):
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._current_file = fp
            self._current_data = data
            self._render_detail()
            self.status.set(f"Loaded: {fp.name}", "ok", right=fp.name)
        except Exception as exc:
            self.status.set(f"Error loading {fp.name}: {exc}", "error")
            messagebox.showerror("Load Error", str(exc))

    # ------------------------------------------------------------------
    # Detail rendering
    # ------------------------------------------------------------------

    def _switch_tab(self, name: str):
        self._active_tab.set(name)
        for n, btn in self._tab_btns.items():
            btn.config(
                fg=C["accent"] if n == name else C["fg_dim"],
                font=(self.UI_FONT, self.UI_SIZE, "bold" if n == name else "normal"),
            )
        self._render_detail()

    def _show_empty_detail(self):
        for w in self._detail_frame.winfo_children():
            w.destroy()
        msg_frame = tk.Frame(self._detail_frame, bg=C["bg"])
        msg_frame.pack(expand=True, fill=tk.BOTH, pady=80)
        tk.Label(msg_frame, text="\u25c6", bg=C["bg"], fg=C["border"],
                 font=(self.UI_FONT, 32)).pack()
        tk.Label(msg_frame, text="Open a folder to browse characters",
                 bg=C["bg"], fg=C["fg_muted"],
                 font=(self.UI_FONT, 10)).pack(pady=(12, 0))
        tk.Label(msg_frame, text="Click \u2b21 Open Folder in the toolbar",
                 bg=C["bg"], fg=C["fg_muted"],
                 font=(self.UI_FONT, 8)).pack(pady=(4, 0))

    def _render_detail(self):
        if not self._current_data:
            self._show_empty_detail()
            return
        for w in self._detail_frame.winfo_children():
            w.destroy()

        tab = self._active_tab.get()
        data = self._current_data

        # Try jsonTemplate rendering first
        try:
            template = TEMPLATES.get(tab)
            if template:
                self._render_template(tab, data, template)
                return
        except Exception:
            pass

        # Fallback: generic key-value renderer for the selected tab's keys
        tab_keys = TAG_CONFIG.get(tab, list(data.keys()))
        self._render_kv_fallback(data, tab_keys)

    def _render_template(self, tab: str, data: dict, template):
        """Render using jsonTemplate's RenderContext."""
        try:
            ctx = self._render_ctx
            frame = self._detail_frame
            rendered = ctx.render(tab, data, template)
            for section_title, pairs in rendered.items():
                self._add_section_header(frame, section_title)
                for key, value in pairs:
                    self._add_kv_row(frame, key, value)
        except Exception:
            tab_keys = TAG_CONFIG.get(tab, list(data.keys()))
            self._render_kv_fallback(data, tab_keys)

    def _render_kv_fallback(self, data: dict, keys):
        frame = self._detail_frame
        for key in keys:
            if key not in data:
                continue
            self._add_kv_row(frame, key, data[key])

        # Show any remaining unknown keys under "Other"
        shown = set(keys)
        remaining = [k for k in data if k not in shown]
        if remaining:
            self._add_section_header(frame, "Other")
            for k in remaining:
                self._add_kv_row(frame, k, data[k])

    def _add_section_header(self, parent, title: str):
        row = tk.Frame(parent, bg=C["bg"])
        row.pack(fill=tk.X, padx=20, pady=(16, 4))
        tk.Label(row, text=title.upper(), bg=C["bg"], fg=C["accent"],
                 font=(self.UI_FONT, 7, "bold")).pack(side=tk.LEFT)
        tk.Frame(row, bg=C["border"], height=1).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), pady=6)

    def _add_kv_row(self, parent, key: str, value):
        row = tk.Frame(parent, bg=C["bg"])
        row.pack(fill=tk.X, padx=20, pady=2)

        key_lbl = tk.Label(row, text=str(key), bg=C["bg"], fg=C["fg_dim"],
                           font=(self.UI_FONT, self.UI_SIZE), width=22, anchor="w")
        key_lbl.pack(side=tk.LEFT)

        display_val = self._format_value(value)
        val_lbl = tk.Label(row, text=display_val, bg=C["bg"], fg=C["fg"],
                           font=(self.UI_FONT, self.UI_SIZE), anchor="w",
                           wraplength=520, justify="left")
        val_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Copy on click
        def _copy(v=display_val):
            self.root.clipboard_clear()
            self.root.clipboard_append(v)
            self.status.set(f"Copied: {v[:40]}{'...' if len(v) > 40 else ''}", "ok")

        copy_btn = tk.Label(row, text=Icons.COPY, bg=C["bg"], fg=C["fg_muted"],
                            font=(self.UI_FONT, 8), cursor="hand2", padx=4)
        copy_btn.pack(side=tk.RIGHT)
        copy_btn.bind("<Button-1>", lambda e: _copy())
        copy_btn.bind("<Enter>", lambda e: copy_btn.config(fg=C["accent"]))
        copy_btn.bind("<Leave>", lambda e: copy_btn.config(fg=C["fg_muted"]))

    @staticmethod
    def _format_value(value) -> str:
        if isinstance(value, list):
            if not value:
                return "(empty list)"
            if all(isinstance(v, str) for v in value):
                return ", ".join(value)
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, indent=2)
        if value is None:
            return "(null)"
        return str(value)

    # ------------------------------------------------------------------
    # Export / Copy
    # ------------------------------------------------------------------

    def _copy_json(self):
        if not self._current_data:
            self.status.set("Nothing to copy — no character loaded", "warn")
            return
        text = json.dumps(self._current_data, ensure_ascii=False, indent=2)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set(f"Copied JSON for {self._current_file.name}", "ok")

    def _export_json(self):
        if not self._current_data:
            self.status.set("Nothing to export — no character loaded", "warn")
            return
        default_name = self._current_file.name if self._current_file else "character.json"
        out_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=default_name,
            title="Export Character JSON",
        )
        if not out_path:
            return
        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(self._current_data, fh, ensure_ascii=False, indent=2)
            self.status.set(f"Exported to {Path(out_path).name}", "ok")
        except Exception as exc:
            self.status.set(f"Export failed: {exc}", "error")
            messagebox.showerror("Export Error", str(exc))

    # ------------------------------------------------------------------
    # Hub navigation
    # ------------------------------------------------------------------

    def back_to_hub(self):
        if self._on_close:
            self._on_close()

    def minimize(self):
        self.root.iconify()
