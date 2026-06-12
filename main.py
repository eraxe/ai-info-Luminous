# main.py
#!/usr/bin/env python3
"""
NPC Character Viewer — Dark UI
BannerForge / Eraxshe — Full JSON viewer with organized tabs
"""
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox, font as tkfont
import json
import os
import platform
from datetime import datetime
from pathlib import Path

from jsonTemplate import TEMPLATES, TABS, TAG_CONFIG, KNOWN_KEYS

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
    FOLDER   = "⬡"
    REFRESH  = "↺"
    BOOKMARK = "◈"
    SETTINGS = "◉"
    SEARCH   = "⌕"
    COLLAPSE = "‹"
    COPY     = "⎘"
    EXPORT   = "↗"
    PIN      = "⊕"
    TRASH    = "⊘"


# ─────────────────────────────────────────────
# CUSTOM WIDGETS
# ─────────────────────────────────────────────

class FlatButton(tk.Label):
    def __init__(self, parent, text="", command=None, bg=C["surface2"], fg=C["fg"],
                 hover_bg=C["surface3"], hover_fg=C["accent"], font=("Segoe UI", 9),
                 padx=12, pady=6, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady,
                         cursor="hand2", **kw)
        self._bg = bg; self._fg = fg; self._hbg = hover_bg; self._hfg = hover_fg
        self._cmd = command
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _=None): self.config(bg=self._hbg, fg=self._hfg)
    def _on_leave(self, _=None): self.config(bg=self._bg, fg=self._fg)
    def _on_click(self, _=None):
        self._on_enter()
        if self._cmd: self.after(50, self._cmd)


class AccentButton(FlatButton):
    def __init__(self, parent, text="", command=None, **kw):
        super().__init__(parent, text=text, command=command, bg=C["accent"], fg="#ffffff",
                         hover_bg="#9580ff", hover_fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), **kw)


class SidebarItem(tk.Frame):
    def __init__(self, parent, icon="", label="", command=None,
                 ui_font="Segoe UI", ui_size=9, **kw):
        super().__init__(parent, bg=C["surface"], cursor="hand2", **kw)
        self._cmd = command; self._active = False
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
            for w in (self, self._icon_lbl, self._text_lbl): w.config(bg=C["surface2"])
            self.winfo_children()[1].config(bg=C["surface2"])

    def _hover_off(self, _=None):
        if not self._active:
            for w in (self, self._icon_lbl, self._text_lbl): w.config(bg=C["surface"])
            self.winfo_children()[1].config(bg=C["surface"])

    def _click(self, _=None):
        if self._cmd: self._cmd()

    def set_active(self, active: bool):
        self._active = active
        bg = C["surface3"] if active else C["surface"]
        fg_icon = C["accent"] if active else C["fg_dim"]
        fg_text = C["fg"] if active else C["fg_dim"]
        ind = C["accent"] if active else C["surface"]
        for w in (self, self._icon_lbl, self._text_lbl): w.config(bg=bg)
        self.winfo_children()[1].config(bg=bg)
        self._icon_lbl.config(fg=fg_icon)
        self._text_lbl.config(fg=fg_text)
        self._indicator.config(bg=ind)


class StatusBar(tk.Frame):
    def __init__(self, parent, ui_font, ui_size, **kw):
        super().__init__(parent, bg=C["surface"], height=26, **kw)
        self.pack_propagate(False)
        self._dot = tk.Label(self, text="●", bg=C["surface"], fg=C["green"],
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
        if self._timer: self.after_cancel(self._timer)
        self._timer = self.after(5000, lambda: self._msg.config(text="Ready", fg=C["fg_dim"]))


class CustomTitleBar(tk.Frame):
    def __init__(self, parent, app, title=""):
        super().__init__(parent, bg=C["bg"], height=36)
        self.pack_propagate(False)
        self.app = app; self.root = app.root
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)
        self.bind("<Double-Button-1>", lambda e: self.toggle_max())
        self.lbl = tk.Label(self, text=f" {title}", bg=C["bg"], fg=C["fg_dim"],
                            font=("Segoe UI", 9, "bold"))
        self.lbl.pack(side=tk.LEFT, padx=12)
        self.lbl.bind("<ButtonPress-1>", self.start_move)
        self.lbl.bind("<B1-Motion>", self.do_move)
        self.lbl.bind("<Double-Button-1>", lambda e: self.toggle_max())
        btns = tk.Frame(self, bg=C["bg"]); btns.pack(side=tk.RIGHT, fill=tk.Y)
        FlatButton(btns, text="—", command=self.min_app, bg=C["bg"],
                   hover_bg=C["surface3"], padx=14).pack(side=tk.LEFT, fill=tk.Y)
        self.max_btn = FlatButton(btns, text="☐", command=self.toggle_max,
                                  bg=C["bg"], hover_bg=C["surface3"], padx=14)
        self.max_btn.pack(side=tk.LEFT, fill=tk.Y)
        FlatButton(btns, text="✕", command=self.close_app, bg=C["bg"],
                   hover_bg=C["red"], hover_fg="#fff", padx=14).pack(side=tk.LEFT, fill=tk.Y)
        self._is_max = False

    def start_move(self, event):
        if self._is_max: return
        self.root.x = event.x; self.root.y = event.y

    def do_move(self, event):
        if self._is_max: return
        x = self.root.winfo_x() + event.x - self.root.x
        y = self.root.winfo_y() + event.y - self.root.y
        self.root.geometry(f"+{x}+{y}")

    def min_app(self): self.app.minimize()

    def toggle_max(self):
        if self._is_max:
            if hasattr(self, "_normal_geo"): self.root.geometry(self._normal_geo)
            self._is_max = False; self.max_btn.config(text="☐")
            self.app.grip.place(relx=1.0, rely=1.0, anchor="se")
        else:
            self._normal_geo = self.root.geometry()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self._is_max = True; self.max_btn.config(text="❐")
            self.app.grip.place_forget()

    def close_app(self): self.root.event_generate("WM_DELETE_WINDOW")


class ScrollableFrame(tk.Frame):
    def __init__(self, parent, **kw):
        outer = tk.Frame(parent, bg=kw.get("bg", C["surface"]))
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, bg=kw.get("bg", C["surface"]),
                           highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                                 bg=C["scrollbar"], troughcolor=C["bg"], width=6)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        super().__init__(canvas, bg=kw.get("bg", C["surface"]))
        self._win_id = canvas.create_window((0, 0), window=self, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self._win_id, width=e.width))
        self.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))


def dark_text(parent, font, **kw):
    st = scrolledtext.ScrolledText(
        parent, wrap=tk.WORD, font=font, bg=C["surface"], fg=C["fg"],
        insertbackground=C["accent"], selectbackground=C["accent"],
        selectforeground="#ffffff", borderwidth=0, highlightthickness=0,
        padx=16, pady=12, **kw
    )
    st.vbar.config(bg=C["scrollbar"], troughcolor=C["bg"], width=8, relief="flat", bd=0)
    _attach_copy_menu(st)
    return st


def _attach_copy_menu(widget):
    menu = tk.Menu(widget, tearoff=0, bg=C["surface2"], fg=C["fg"],
                   activebackground=C["accent"], activeforeground="#fff",
                   borderwidth=0, font=("Segoe UI", 9))
    menu.add_command(label="  Copy", accelerator="Ctrl+C",
                     command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="  Select All", accelerator="Ctrl+A",
                     command=lambda: (widget.tag_add("sel", "1.0", tk.END), None))
    menu.add_separator()
    menu.add_command(label="  Copy All Text", command=lambda: _copy_all_text(widget))

    def show_menu(event):
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()

    widget.bind("<Button-3>", show_menu)


def _copy_all_text(widget):
    try:
        widget.clipboard_clear()
        widget.clipboard_append(widget.get("1.0", tk.END))
    except Exception:
        pass


def _atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ─────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────

class NPCViewerApp:

    def __init__(self, root):
        self.root = root
        self.root.title("NPC Viewer")
        self.root.overrideredirect(True)
        self.root.geometry("1700x1000")
        self.root.minsize(1100, 700)
        self.root.configure(bg=C["border"])
        self._app_frame = tk.Frame(self.root, bg=C["bg"],
                                   highlightbackground=C["border"], highlightthickness=1)
        self._app_frame.pack(fill=tk.BOTH, expand=True)
        try:
            self.config_dir = Path.home() / ".npc_viewer"
            self.config_dir.mkdir(exist_ok=True)
            self.config_path = self.config_dir / "npc_viewer_config.json"
            self.bookmarks_path = self.config_dir / "npc_viewer_bookmarks.json"
        except Exception:
            self.config_path = Path("npc_viewer_config.json")
            self.bookmarks_path = Path("npc_viewer_bookmarks.json")

        self.current_directory = ""
        self.current_json_data = None
        self.current_file_path = None
        self.file_paths = []
        self.bookmarks = []
        self.sidebar_visible = True
        self._active_tab = "ai"
        self._tab_frames = {}
        self._tab_widgets = {}
        self._sidebar_items = {}
        self.settings = {
            "auto_load_last": True,
            "show_timestamps": True,
            "compact_mode": False,
            "ui_font_family": "Segoe UI",
            "ui_font_size": 10,
            "content_font_family": "Segoe UI",
            "content_font_size": 11,
            "code_font_family": "Consolas",
            "code_font_size": 10,
            "autosave_delay_ms": 1000,
        }
        self.load_config()
        self.load_bookmarks()
        self._setup_styles()
        self._build_ui()
        if self.settings.get("auto_load_last", True):
            self._auto_load_last_session()

    def minimize(self):
        if platform.system() == "Windows":
            self.root.overrideredirect(False)
            self.root.iconify()
            self.root.bind("<Map>", self._on_map)
        else:
            self.root.iconify()

    def _on_map(self, event):
        if event.widget == self.root:
            self.root.overrideredirect(True)
            self.root.unbind("<Map>")

    # ══════════════════════════════════════════
    # STYLES & UI
    # ══════════════════════════════════════════

    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        uf = (self.settings["ui_font_family"], self.settings["ui_font_size"])
        s.configure("TEntry", fieldbackground=C["surface2"], foreground=C["fg"],
                    insertcolor=C["accent"], borderwidth=0, padding=(8, 6), font=uf)
        s.configure("Search.TEntry", fieldbackground=C["surface2"], foreground=C["fg"],
                    insertcolor=C["accent"], borderwidth=0, padding=(8, 5), font=uf)
        s.configure("TScrollbar", background=C["scrollbar"], troughcolor=C["bg"],
                    borderwidth=0, arrowsize=0)
        s.configure("TCheckbutton", background=C["surface"], foreground=C["fg"], font=uf)
        s.map("TCheckbutton", background=[("active", C["surface2"])])
        s.configure("TScale", background=C["surface"], troughcolor=C["surface3"], borderwidth=0)
        s.configure("TCombobox", fieldbackground=C["surface2"], background=C["surface2"],
                    foreground=C["fg"], borderwidth=0, font=uf)
        s.map("TCombobox", fieldbackground=[("readonly", C["surface2"])],
              selectbackground=[("readonly", C["accent"])])
        s.configure("Treeview", background=C["surface2"], foreground=C["fg"],
                    fieldbackground=C["surface2"], borderwidth=0, font=uf, rowheight=26)
        s.map("Treeview", background=[("selected", C["accent"])],
              foreground=[("selected", "#ffffff")])
        s.configure("Treeview.Heading", background=C["surface"], foreground=C["fg_dim"],
                    font=(uf[0], uf[1], "bold"), relief="flat")
        s.map("Treeview.Heading", background=[("active", C["surface3"])])

    def _build_ui(self):
        self.title_bar = CustomTitleBar(self._app_frame, self, "NPC Viewer Engine")
        self.title_bar.pack(fill=tk.X)
        self._body = tk.Frame(self._app_frame, bg=C["bg"])
        self._body.pack(fill=tk.BOTH, expand=True)
        self._body.columnconfigure(1, weight=1)
        self._body.rowconfigure(0, weight=1)
        self._build_sidebar(self._body)
        self._build_main_area(self._body)
        self.grip = ttk.Sizegrip(self._app_frame)
        self.grip.place(relx=1.0, rely=1.0, anchor="se")

    def _build_sidebar(self, parent):
        uf = self.settings["ui_font_family"]; us = self.settings["ui_font_size"]
        self._sidebar = tk.Frame(parent, bg=C["surface"], width=240)
        self._sidebar.grid(row=0, column=0, sticky="ns")
        self._sidebar.grid_propagate(False)
        self._sidebar.columnconfigure(0, weight=1)

        logo_frame = tk.Frame(self._sidebar, bg=C["surface"], height=64)
        logo_frame.pack(fill=tk.X)
        tk.Label(logo_frame, text="◆ NPC", bg=C["surface"], fg=C["accent"],
                 font=(uf, us + 4, "bold")).pack(side=tk.LEFT, padx=(16, 0), pady=16)
        tk.Label(logo_frame, text="Viewer", bg=C["surface"], fg=C["fg_dim"],
                 font=(uf, us + 1)).pack(side=tk.LEFT, padx=(4, 0), pady=16)
        self._toggle_btn = tk.Label(logo_frame, text=Icons.COLLAPSE, bg=C["surface"],
                                    fg=C["fg_muted"], font=(uf, us + 2), cursor="hand2")
        self._toggle_btn.pack(side=tk.RIGHT, padx=16)
        self._toggle_btn.bind("<Button-1>", lambda _: self._toggle_sidebar())

        tk.Frame(self._sidebar, bg=C["border"], height=1).pack(fill=tk.X)
        section = tk.Frame(self._sidebar, bg=C["surface"])
        section.pack(fill=tk.X, padx=10, pady=(12, 6))
        tk.Label(section, text="DIRECTORY", bg=C["surface"], fg=C["fg_muted"],
                 font=(uf, us - 2, "bold")).pack(anchor="w")
        dir_row = tk.Frame(section, bg=C["surface2"], pady=4)
        dir_row.pack(fill=tk.X, pady=(4, 0))
        self.dir_entry = ttk.Entry(dir_row, style="Search.TEntry")
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        FlatButton(dir_row, text=Icons.FOLDER, command=self.browse_directory,
                   bg=C["surface2"], fg=C["accent2"], font=(uf, us)).pack(side=tk.LEFT, padx=2)
        FlatButton(dir_row, text=Icons.REFRESH, command=self.refresh_file_list,
                   bg=C["surface2"], fg=C["fg_dim"], font=(uf, us)).pack(side=tk.LEFT, padx=(0, 4))

        search_row = tk.Frame(section, bg=C["surface"])
        search_row.pack(fill=tk.X, pady=(8, 0))
        tk.Label(search_row, text=Icons.SEARCH, bg=C["surface"], fg=C["fg_muted"],
                 font=(uf, us)).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search_change)
        ttk.Entry(search_row, textvariable=self.search_var, style="Search.TEntry").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        list_header = tk.Frame(self._sidebar, bg=C["surface"])
        list_header.pack(fill=tk.X, padx=10, pady=(8, 2))
        tk.Label(list_header, text="FILES", bg=C["surface"], fg=C["fg_muted"],
                 font=(uf, us - 2, "bold")).pack(side=tk.LEFT)
        self._file_count_lbl = tk.Label(list_header, text="", bg=C["surface"],
                                        fg=C["accent"], font=(uf, us - 2))
        self._file_count_lbl.pack(side=tk.RIGHT)

        list_outer = tk.Frame(self._sidebar, bg=C["border"], pady=1)
        list_outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))
        self.file_listbox = tk.Listbox(list_outer, bg=C["surface2"], fg=C["fg"],
                                       selectbackground=C["accent"], selectforeground="#ffffff",
                                       activestyle="none", font=(uf, us - 1),
                                       borderwidth=0, highlightthickness=0)
        file_sb = tk.Scrollbar(list_outer, orient="vertical", command=self.file_listbox.yview,
                               bg=C["scrollbar"], troughcolor=C["bg"], width=6, bd=0)
        self.file_listbox.config(yscrollcommand=file_sb.set)
        file_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.file_listbox.bind("<<ListboxSelect>>", self._on_file_select)

        bm_header = tk.Frame(self._sidebar, bg=C["surface"])
        bm_header.pack(fill=tk.X, padx=10, pady=(4, 2))
        tk.Label(bm_header, text="BOOKMARKS", bg=C["surface"], fg=C["fg_muted"],
                 font=(uf, us - 2, "bold")).pack(side=tk.LEFT)
        FlatButton(bm_header, text=f"{Icons.PIN} Add", command=self.add_bookmark,
                   bg=C["surface"], fg=C["fg_muted"], font=(uf, us - 2),
                   padx=4, pady=1).pack(side=tk.RIGHT)

        bm_outer = tk.Frame(self._sidebar, bg=C["border"], pady=1)
        bm_outer.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.bookmark_listbox = tk.Listbox(bm_outer, bg=C["surface2"], fg=C["fg"],
                                           selectbackground=C["accent3"],
                                           selectforeground="#ffffff", activestyle="none",
                                           font=(uf, us - 1), height=5,
                                           borderwidth=0, highlightthickness=0)
        bm_sb = tk.Scrollbar(bm_outer, orient="vertical", command=self.bookmark_listbox.yview,
                             bg=C["scrollbar"], troughcolor=C["bg"], width=6, bd=0)
        self.bookmark_listbox.config(yscrollcommand=bm_sb.set)
        bm_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.bookmark_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.bookmark_listbox.bind("<<ListboxSelect>>", self._on_bookmark_select)

        self._bm_ctx = tk.Menu(self.bookmark_listbox, tearoff=0, bg=C["surface2"], fg=C["fg"],
                               activebackground=C["accent"], activeforeground="#fff",
                               borderwidth=0, font=(uf, us))
        self._bm_ctx.add_command(label=f"{Icons.TRASH} Remove bookmark",
                                 command=self.remove_bookmark)
        self.bookmark_listbox.bind("<Button-3>", self._show_bm_ctx)
        self._refresh_bookmark_list()

        tk.Frame(self._sidebar, bg=C["border"], height=1).pack(fill=tk.X)
        FlatButton(self._sidebar, text=f"{Icons.SETTINGS} Settings",
                   command=self.open_settings, bg=C["surface"], fg=C["fg_dim"],
                   font=(uf, us), padx=16, pady=10).pack(fill=tk.X, anchor="w")

    def _build_main_area(self, parent):
        uf = self.settings["ui_font_family"]; us = self.settings["ui_font_size"]
        self._main = tk.Frame(parent, bg=C["bg"])
        self._main.grid(row=0, column=1, sticky="nsew")
        self._main.columnconfigure(0, weight=1); self._main.rowconfigure(1, weight=1)

        self._header = tk.Frame(self._main, bg=C["surface"], height=72)
        self._header.grid(row=0, column=0, sticky="ew"); self._header.grid_propagate(False)
        self._header.columnconfigure(1, weight=1)
        tgl = tk.Label(self._header, text="≡", bg=C["surface"], fg=C["fg_muted"],
                       font=(uf, 16), cursor="hand2")
        tgl.grid(row=0, column=0, padx=(16, 0), rowspan=2, sticky="ns")
        tgl.bind("<Button-1>", lambda _: self._toggle_sidebar())
        self._name_lbl = tk.Label(self._header, text="Select a file to begin",
                                  bg=C["surface"], fg=C["fg"], font=(uf, 18, "bold"), anchor="w")
        self._name_lbl.grid(row=0, column=1, sticky="ew", padx=(14, 0), pady=(12, 0))
        self._stats_lbl = tk.Label(self._header, text="", bg=C["surface"], fg=C["fg_dim"],
                                   font=(uf, us), anchor="w")
        self._stats_lbl.grid(row=1, column=1, sticky="ew", padx=(14, 0), pady=(0, 10))

        content = tk.Frame(self._main, bg=C["bg"])
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(1, weight=1); content.rowconfigure(0, weight=1)

        self._nav = tk.Frame(content, bg=C["surface"], width=180)
        self._nav.grid(row=0, column=0, sticky="ns"); self._nav.grid_propagate(False)
        tk.Label(self._nav, text="NAVIGATE", bg=C["surface"], fg=C["fg_muted"],
                 font=(uf, us - 2, "bold")).pack(anchor="w", padx=14, pady=(12, 6))
        for tab in TABS:
            item = SidebarItem(self._nav, icon=tab.icon, label=tab.label,
                               command=lambda k=tab.key: self._switch_tab(k),
                               ui_font=uf, ui_size=us)
            item.pack(fill=tk.X)
            self._sidebar_items[tab.key] = item

        self._canvas = tk.Frame(content, bg=C["bg"])
        self._canvas.grid(row=0, column=1, sticky="nsew")
        self._canvas.columnconfigure(0, weight=1); self._canvas.rowconfigure(0, weight=1)

        self._build_tab_frames()
        self._switch_tab("ai")

        self.status = StatusBar(self._main, uf, us)
        self.status.grid(row=2, column=0, sticky="ew")
        self.status.set("Ready — open a directory to begin", "info")

    def _build_tab_frames(self):
        c_ff = self.settings["content_font_family"]
        c_fs = self.settings["content_font_size"]
        k_ff = self.settings["code_font_family"]
        k_fs = self.settings["code_font_size"]
        u_ff = self.settings["ui_font_family"]
        u_fs = self.settings["ui_font_size"]

        def _make_frame(key):
            f = tk.Frame(self._canvas, bg=C["bg"])
            f.columnconfigure(0, weight=1); f.rowconfigure(0, weight=1)
            self._tab_frames[key] = f
            return f

        for tab in TABS:
            if tab.subtabs:
                f = _make_frame(tab.key)
                f.rowconfigure(0, weight=1)
                outer = tk.Frame(f, bg=C["bg"])
                outer.grid(sticky="nsew")
                outer.columnconfigure(1, weight=1); outer.rowconfigure(1, weight=1)

                subtab_frames = {}
                subtab_btns = {}
                nav_bar = tk.Frame(outer, bg=C["surface2"])
                nav_bar.grid(row=0, column=0, columnspan=2, sticky="ew")

                for st in tab.subtabs:
                    ff = c_ff if st.font_type == "content" else k_ff
                    fs = c_fs if st.font_type == "content" else k_fs
                    sf = tk.Frame(outer, bg=C["bg"])
                    sf.grid(row=1, column=0, columnspan=2, sticky="nsew")
                    sf.columnconfigure(0, weight=1); sf.rowconfigure(0, weight=1)
                    w = dark_text(sf, font=(ff, fs))
                    w.grid(sticky="nsew")
                    subtab_frames[st.key] = (sf, w)
                    btn = FlatButton(nav_bar, text=st.label,
                                     command=lambda k=st.key, d=subtab_frames, b=subtab_btns:
                                         self._switch_subtab(k, d, b),
                                     bg=C["surface2"], fg=C["fg_dim"],
                                     font=(u_ff, u_fs - 1), padx=14, pady=6)
                    btn.pack(side=tk.LEFT)
                    subtab_btns[st.key] = btn

                self._tab_widgets[tab.key] = {
                    "subtab_frames": subtab_frames,
                    "subtab_btns": subtab_btns,
                }
                if tab.subtabs:
                    self._switch_subtab(tab.subtabs[0].key, subtab_frames, subtab_btns)

            elif tab.key == "raw":
                f = _make_frame(tab.key)
                f.rowconfigure(1, weight=1)
                raw_tb = tk.Frame(f, bg=C["surface"], pady=4)
                raw_tb.grid(row=0, column=0, sticky="ew")
                FlatButton(raw_tb, text=f"{Icons.COPY} Copy JSON",
                           command=self.copy_raw_json, bg=C["surface"], fg=C["fg_dim"],
                           font=(u_ff, u_fs - 1)).pack(side=tk.LEFT, padx=8, pady=2)
                self.raw_text = dark_text(f, font=(k_ff, k_fs))
                self.raw_text.grid(row=1, column=0, sticky="nsew")
                self._tab_widgets[tab.key] = {"widget": self.raw_text}

            elif tab.key == "conv":
                f = _make_frame(tab.key)
                f.rowconfigure(1, weight=1)
                sb = tk.Frame(f, bg=C["surface"], pady=6)
                sb.grid(row=0, column=0, sticky="ew")
                tk.Label(sb, text=Icons.SEARCH, bg=C["surface"], fg=C["fg_dim"],
                         font=(u_ff, u_fs)).pack(side=tk.LEFT, padx=(12, 4))
                self.conv_search_var = tk.StringVar()
                ttk.Entry(sb, textvariable=self.conv_search_var,
                          style="Search.TEntry", width=32).pack(side=tk.LEFT)
                FlatButton(sb, text="Find", command=self._search_conversation,
                           bg=C["surface2"], font=(u_ff, u_fs - 1),
                           padx=10, pady=4).pack(side=tk.LEFT, padx=6)
                ff = c_ff if tab.font_type == "content" else k_ff
                fs = c_fs if tab.font_type == "content" else k_fs
                w = dark_text(f, font=(ff, fs))
                w.grid(row=1, column=0, sticky="nsew")
                self._tab_widgets[tab.key] = {"widget": w}

            else:
                f = _make_frame(tab.key)
                ff = c_ff if tab.font_type == "content" else k_ff
                fs = c_fs if tab.font_type == "content" else k_fs
                w = dark_text(f, font=(ff, fs))
                w.grid(sticky="nsew")
                self._tab_widgets[tab.key] = {"widget": w}

    # ══════════════════════════════════════════
    # TAB & NAV LOGIC
    # ══════════════════════════════════════════

    def _switch_tab(self, key):
        for k, f in self._tab_frames.items(): f.grid_remove()
        if key in self._tab_frames: self._tab_frames[key].grid(sticky="nsew")
        for k, item in self._sidebar_items.items(): item.set_active(k == key)
        self._active_tab = key

    def _switch_subtab(self, key, subtab_frames: dict, subtab_btns: dict):
        for sf, _ in subtab_frames.values(): sf.grid_remove()
        if key in subtab_frames: subtab_frames[key][0].grid(sticky="nsew")
        for k, btn in subtab_btns.items():
            btn.config(bg=C["accent"] if k == key else C["surface2"],
                       fg="#ffffff" if k == key else C["fg_dim"])

    def _toggle_sidebar(self):
        if self.sidebar_visible:
            self._sidebar.grid_remove(); self.sidebar_visible = False
        else:
            self._sidebar.grid(); self.sidebar_visible = True

    # ══════════════════════════════════════════
    # TAG CONFIGURATION
    # ══════════════════════════════════════════

    def _cfg_tags(self, widget, ff):
        c_fs = self.settings["content_font_size"]
        k_ff = self.settings["code_font_family"]
        k_fs = self.settings["code_font_size"]
        for tag_name, cfg in TAG_CONFIG.items():
            delta = cfg.get("font_delta", 0)
            weight = cfg.get("weight", "normal")
            use_code = cfg.get("use_code_font", False)
            font_family = k_ff if use_code else ff
            font_size = (k_fs if use_code else c_fs) + delta

            style = "italic" if weight == "italic" else weight
            if style == "italic":
                font_spec = (font_family, font_size, "italic")
            elif style == "bold":
                font_spec = (font_family, font_size, "bold")
            else:
                font_spec = (font_family, font_size)

            kwargs = {"font": font_spec}
            fg_key = cfg.get("fg")
            if fg_key and fg_key in C:
                kwargs["foreground"] = C[fg_key]
            bg_key = cfg.get("bg")
            if bg_key and bg_key in C:
                kwargs["background"] = C[bg_key]
            for attr in ("spacing1", "spacing3", "lmargin1", "lmargin2"):
                if attr in cfg:
                    kwargs[attr] = cfg[attr]
            widget.tag_configure(tag_name, **kwargs)

    # ══════════════════════════════════════════
    # FILE / DATA OPERATIONS
    # ══════════════════════════════════════════

    def load_config(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.current_directory = cfg.get("last_directory", "")
                self.current_file_path = cfg.get("last_file", None)
                self.settings.update(cfg.get("settings", {}))
            except Exception:
                pass

    def save_config(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({"last_directory": self.current_directory,
                           "last_file": self.current_file_path,
                           "settings": self.settings}, f, indent=2)
        except Exception:
            pass

    def load_bookmarks(self):
        if self.bookmarks_path.exists():
            try:
                with open(self.bookmarks_path, "r", encoding="utf-8") as f:
                    self.bookmarks = json.load(f)
            except Exception:
                self.bookmarks = []

    def save_bookmarks(self):
        try:
            with open(self.bookmarks_path, "w", encoding="utf-8") as f:
                json.dump(self.bookmarks, f, indent=2)
        except Exception:
            pass

    def browse_directory(self):
        d = filedialog.askdirectory(initialdir=self.current_directory)
        if d:
            self.current_directory = d
            self.dir_entry.delete(0, tk.END); self.dir_entry.insert(0, d)
            self.save_config(); self.refresh_file_list()

    def refresh_file_list(self):
        self.file_listbox.delete(0, tk.END); self.file_paths = []
        directory = self.dir_entry.get().strip()
        if not directory or not os.path.exists(directory):
            return
        self.current_directory = directory; self.save_config()
        try:
            files = [(fn, os.path.getmtime(os.path.join(directory, fn)),
                      os.path.join(directory, fn))
                     for fn in os.listdir(directory)
                     if fn.endswith(".json") and fn not in {
                         "npc_viewer_config.json", "npc_viewer_bookmarks.json"}]
            files.sort(key=lambda x: x[1], reverse=True)
            for fn, mtime, fp in files:
                dt = datetime.fromtimestamp(mtime).strftime("%m/%d %H:%M")
                self.file_listbox.insert(tk.END, f" {dt} · {fn}")
                self.file_paths.append(fp)
            self._file_count_lbl.config(text=str(len(files)))
        except Exception:
            pass

    def _on_search_change(self, *_):
        term = self.search_var.get().lower()
        if not term: return self.refresh_file_list()
        self.file_listbox.delete(0, tk.END); self.file_paths = []
        directory = self.dir_entry.get().strip()
        if not directory or not os.path.exists(directory): return
        for fn in sorted(os.listdir(directory)):
            if fn.endswith(".json") and term in fn.lower():
                fp = os.path.join(directory, fn)
                dt = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%m/%d")
                self.file_listbox.insert(tk.END, f" {dt} · {fn}")
                self.file_paths.append(fp)

    def _on_file_select(self, event=None):
        sel = self.file_listbox.curselection()
        if sel and 0 <= sel[0] < len(self.file_paths):
            self.load_json_file(self.file_paths[sel[0]])

    def _auto_load_last_session(self):
        if self.current_directory and os.path.exists(self.current_directory):
            self.dir_entry.insert(0, self.current_directory)
            self.refresh_file_list()
        if self.current_file_path and os.path.exists(self.current_file_path):
            self.load_json_file(self.current_file_path)

    def load_json_file(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self.current_json_data = json.load(f)
            self.current_file_path = filepath
            self.save_config()
            self._display_data()
            self.status.set(f"Loaded: {os.path.basename(filepath)}", "ok")
        except Exception as e:
            self.status.set(f"Load error: {e}", "error")

    def copy_raw_json(self):
        if self.current_json_data:
            self.root.clipboard_clear()
            self.root.clipboard_append(json.dumps(self.current_json_data,
                                                   indent=2, ensure_ascii=False))
            self.status.set("JSON copied", "ok")

    # ══════════════════════════════════════════
    # DISPLAY / POPULATE LOOP
    # ══════════════════════════════════════════

    def _display_data(self):
        if not self.current_json_data: return
        data = self.current_json_data
        c_ff = self.settings["content_font_family"]

        self._name_lbl.config(text=f"◆ {data.get('Name', 'Unknown')}")

        parts = []
        rel_obj = data.get("PlayerRelation", {})
        if isinstance(rel_obj, dict):
            rel_val = rel_obj.get("Value", 0)
            rel_desc = rel_obj.get("Description", "")
            parts.append(f"Relation {rel_val:+d} ({rel_desc})" if rel_desc else f"Relation {rel_val:+d}")
        mood = data.get("EmotionalState", {}).get("Mood", "")
        mi = {"joyful": "😊", "happy": "😊", "sad": "😔", "angry": "😠",
              "neutral": "😐", "calm": "😌"}.get(mood.lower() if mood else "", "•")
        if mood: parts.append(f"{mi} {mood.capitalize()}")
        if data.get("IsInPlayerParty"): parts.append("In Party ⬟")
        if data.get("IsWithPlayer"): parts.append("With Player")
        cs = data.get("CounterpartySocial", {})
        hero_social = cs.get("main_hero", {}) if isinstance(cs, dict) else {}
        trust = hero_social.get("trust_level")
        if trust is not None: parts.append(f"Trust {trust:.0%}")
        self._stats_lbl.config(text=" · ".join(parts))

        for tab in TABS:
            if tab.key == "raw":
                t = self._tab_widgets["raw"]["widget"]
                t.config(state="normal")
                t.delete("1.0", tk.END)
                t.insert(tk.END, json.dumps(data, indent=2, ensure_ascii=False))
                t.config(state="disabled")
                continue

            if tab.subtabs:
                td = self._tab_widgets.get(tab.key, {})
                subtab_frames = td.get("subtab_frames", {})
                for st in tab.subtabs:
                    if st.key not in subtab_frames:
                        continue
                    _, widget = subtab_frames[st.key]
                    widget.config(state="normal")
                    widget.delete("1.0", tk.END)
                    self._cfg_tags(widget, c_ff)
                    for tpl_key in st.templates:
                        tpl = TEMPLATES.get(tpl_key)
                        if tpl:
                            tpl.render(widget, data)
                continue

            td = self._tab_widgets.get(tab.key, {})
            widget = td.get("widget")
            if widget is None:
                continue
            widget.config(state="normal")
            widget.delete("1.0", tk.END)
            self._cfg_tags(widget, c_ff)
            for tpl_key in tab.templates:
                tpl = TEMPLATES.get(tpl_key)
                if tpl:
                    tpl.render(widget, data)

    def _search_conversation(self):
        term = self.conv_search_var.get()
        if not term: return
        td = self._tab_widgets.get("conv", {})
        conv_widget = td.get("widget")
        if not conv_widget: return
        conv_widget.tag_remove("search", "1.0", tk.END)
        conv_widget.tag_configure("search", background=C["accent3"], foreground="#000")
        pos = "1.0"
        while True:
            pos = conv_widget.search(term, pos, nocase=True, stopindex=tk.END)
            if not pos: break
            end = f"{pos}+{len(term)}c"
            conv_widget.tag_add("search", pos, end)
            pos = end

    # ══════════════════════════════════════════
    # BOOKMARKS & SETTINGS
    # ══════════════════════════════════════════

    def add_bookmark(self):
        if not self.current_file_path: return
        for bm in self.bookmarks:
            if bm["path"] == self.current_file_path: return
        self.bookmarks.append({
            "path": self.current_file_path,
            "name": self.current_json_data.get("Name", "Unknown") if self.current_json_data else "Unknown",
            "added": datetime.now().isoformat()
        })
        self.save_bookmarks(); self._refresh_bookmark_list()

    def _refresh_bookmark_list(self):
        self.bookmark_listbox.delete(0, tk.END)
        for bm in self.bookmarks:
            dt = datetime.fromisoformat(bm.get("added", "")).strftime("%m/%d") if "added" in bm else "?"
            self.bookmark_listbox.insert(tk.END, f" {dt} · {bm.get('name', '?')}")

    def _on_bookmark_select(self, event=None):
        sel = self.bookmark_listbox.curselection()
        if sel and 0 <= sel[0] < len(self.bookmarks):
            fp = self.bookmarks[sel[0]]["path"]
            if os.path.exists(fp): self.load_json_file(fp)

    def _show_bm_ctx(self, event):
        idx = self.bookmark_listbox.nearest(event.y)
        self.bookmark_listbox.selection_clear(0, tk.END)
        self.bookmark_listbox.selection_set(idx)
        self._bm_ctx.tk_popup(event.x_root, event.y_root)

    def remove_bookmark(self):
        sel = self.bookmark_listbox.curselection()
        if sel and 0 <= sel[0] < len(self.bookmarks):
            self.bookmarks.pop(sel[0]); self.save_bookmarks(); self._refresh_bookmark_list()

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings"); win.geometry("560x640"); win.configure(bg=C["surface"])
        win.transient(self.root); win.grab_set()
        tk.Label(win, text=" ◉ Settings", bg=C["surface"], fg=C["accent"],
                 font=("Segoe UI", 14, "bold"), anchor="w").pack(fill=tk.X, pady=(20, 0), padx=20)
        tk.Frame(win, bg=C["border"], height=1).pack(fill=tk.X, pady=12)
        body = ScrollableFrame(win, bg=C["surface"])
        body.pack(fill=tk.BOTH, expand=True, padx=12)

        def sec(txt):
            tk.Label(body, text=txt, bg=C["surface"], fg=C["fg_dim"],
                     font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(14, 4), padx=12)

        sec("GENERAL")
        auto_var = tk.BooleanVar(value=self.settings.get("auto_load_last", True))
        ttk.Checkbutton(body, text="Auto-load last session", variable=auto_var,
                        style="TCheckbutton").pack(anchor="w", padx=24, pady=2)
        delay_var = tk.IntVar(value=self.settings.get("autosave_delay_ms", 1000))
        d_f = tk.Frame(body, bg=C["surface"]); d_f.pack(fill=tk.X, padx=24, pady=6)
        tk.Label(d_f, text="Autosave Delay (ms)", bg=C["surface"], fg=C["fg"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        ttk.Entry(d_f, textvariable=delay_var, width=8, style="TEntry").pack(side=tk.RIGHT)
        fonts = [f for f in sorted(set(tkfont.families())) if not f.startswith("@")]

        def font_picker(title, f_key, s_key, max_s=32):
            sec(title)
            f = tk.Frame(body, bg=C["surface2"], pady=8)
            f.pack(fill=tk.X, padx=12, pady=2)
            ff_var = tk.StringVar(value=self.settings.get(f_key, "Segoe UI"))
            fs_var = tk.IntVar(value=self.settings.get(s_key, 11))
            ttk.Combobox(f, textvariable=ff_var, values=fonts, width=20,
                         state="readonly").pack(side=tk.LEFT, padx=12)
            lbl = tk.Label(f, text=f"{fs_var.get()}pt", bg=C["surface2"], fg=C["accent"],
                           font=("Segoe UI", 9, "bold"), width=4)
            lbl.pack(side=tk.RIGHT, padx=12)
            ttk.Scale(f, from_=8, to=max_s, variable=fs_var, orient=tk.HORIZONTAL, length=140,
                      command=lambda v: lbl.config(text=f"{int(float(v))}pt")).pack(
                          side=tk.RIGHT, padx=4)
            return ff_var, fs_var

        ui_ff, ui_fs = font_picker("UI FONT (Requires Restart)", "ui_font_family", "ui_font_size", 24)
        c_ff, c_fs = font_picker("CONTENT FONT (Prose & Logs)", "content_font_family", "content_font_size", 32)
        k_ff, k_fs = font_picker("CODE FONT (JSON & Stats)", "code_font_family", "code_font_size", 32)
        tk.Frame(win, bg=C["border"], height=1).pack(fill=tk.X, pady=(12, 0))
        btn_row = tk.Frame(win, bg=C["surface"]); btn_row.pack(fill=tk.X, padx=24, pady=12)

        def save():
            self.settings.update({
                "auto_load_last": auto_var.get(), "autosave_delay_ms": delay_var.get(),
                "ui_font_family": ui_ff.get(), "ui_font_size": int(ui_fs.get()),
                "content_font_family": c_ff.get(), "content_font_size": int(c_fs.get()),
                "code_font_family": k_ff.get(), "code_font_size": int(k_fs.get()),
            })
            self.save_config(); self._display_data()
            self.status.set("Settings saved (Restart for UI changes)", "ok")
            win.destroy()

        AccentButton(btn_row, text="Save Settings", command=save).pack(side=tk.LEFT)
        FlatButton(btn_row, text="Cancel", command=win.destroy, bg=C["surface2"],
                   fg=C["fg_dim"], hover_bg=C["surface3"],
                   hover_fg=C["red"]).pack(side=tk.LEFT, padx=8)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.withdraw()
    app = NPCViewerApp(root)
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = 1700, 1000
    root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
    root.deiconify(); root.update_idletasks()
    if platform.system() == "Windows":
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x00040000)
        except Exception:
            pass
    root.protocol("WM_DELETE_WINDOW", lambda: (app.save_config(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()