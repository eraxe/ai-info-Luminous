#!/usr/bin/env python3
"""
Luminous AI — Prompt Management Section
Full PromptManagementApp. Launched from main.py hub.
"""
import sys
import os

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    import json
    import platform
    import subprocess
    import shutil
    import zipfile
    from datetime import datetime
    from pathlib import Path
except Exception as _import_err:
    import tkinter as _tk
    import tkinter.messagebox as _mb
    _r = _tk.Tk()
    _r.withdraw()
    _mb.showerror("Import Error", f"prompt_management.py failed to load:\n\n{_import_err}")
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

SETTINGS_PATH = Path(__file__).parent / "luminous_ai" / "settings.json"
COLLECTIONS_DIR = Path(__file__).parent / "luminous_data" / "collections"

CATEGORIES = [
    ("actions",                         "▦"),
    ("character_creation",               "▦"),
    ("diplomacy_internal_thoughts",      "▦"),
    ("dynamic_events_generator",         "▦"),
    ("dynamic_events_internal_thoughts", "▦"),
    ("group_conversation",               "▦"),
    ("internal_thoughts",                "▦"),
    ("json_output",                      "▦"),
    ("kingdom_statement",                "▦"),
    ("npc_initiative",                   "▦"),
    ("rules",                            "▦"),
    ("world_data",                       "▦"),
    ("root_files",                       "▦"),
]


# ---------------------------------------------------------------------------
# Reusable widgets (matching ai_characters.py style)
# ---------------------------------------------------------------------------

class FlatButton(tk.Label):
    def __init__(self, parent, text="", command=None, bg=C["surface2"], fg=C["fg"],
                 hover_bg=C["surface3"], hover_fg=C["accent"], font=("Segoe UI", 9),
                 padx=12, pady=6, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady,
                         cursor="hand2", **kw)
        self._bg, self._fg = bg, fg
        self._hbg, self._hfg = hover_bg, hover_fg
        self._cmd = command
        self.bind("<Enter>",    lambda e: self.config(bg=self._hbg, fg=self._hfg))
        self.bind("<Leave>",    lambda e: self.config(bg=self._bg,  fg=self._fg))
        self.bind("<Button-1>", lambda e: self.after(50, self._cmd) if self._cmd else None)


class AccentButton(FlatButton):
    def __init__(self, parent, text="", command=None, **kw):
        super().__init__(parent, text=text, command=command, bg=C["accent"], fg="#ffffff",
                         hover_bg="#9580ff", hover_fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), **kw)


class StatusBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["surface"], height=26, **kw)
        self.pack_propagate(False)
        self._dot = tk.Label(self, text="●", bg=C["surface"], fg=C["green"],
                             font=("Segoe UI", 8))
        self._dot.pack(side=tk.LEFT, padx=(10, 4))
        self._msg = tk.Label(self, text="Ready", bg=C["surface"], fg=C["fg_dim"],
                             font=("Segoe UI", 9), anchor="w")
        self._msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._timer = None

    def set(self, msg, level="ok"):
        color = {"ok": C["green"], "warn": C["accent3"], "error": C["red"],
                 "info": C["accent2"]}.get(level, C["green"])
        self._dot.config(fg=color)
        self._msg.config(text=msg, fg=C["fg"])
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(5000, lambda: self._msg.config(text="Ready", fg=C["fg_dim"]))


class VirtualList(tk.Frame):
    """
    Canvas-based virtual list that handles thousands of rows without creating
    per-row widgets. Row height is fixed. Supports selection + click callback.
    """
    ROW_H = 26

    def __init__(self, parent, on_select=None, bg=C["surface2"], **kw):
        super().__init__(parent, bg=bg, **kw)
        self._on_select = on_select
        self._bg = bg
        self._items = []          # list of (label, fg_color, tag)
        self._sel_idx = -1
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._sb = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview,
                                bg=C["scrollbar"], troughcolor=C["bg"], width=6)
        self._canvas.configure(yscrollcommand=self._sb.set)
        self._sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._canvas.bind("<Configure>",    self._on_resize)
        self._canvas.bind("<Button-1>",     self._on_click)
        self._canvas.bind("<MouseWheel>",   self._on_wheel)
        self._canvas.bind("<Button-4>",     lambda e: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind("<Button-5>",     lambda e: self._canvas.yview_scroll(1, "units"))
        self._width = 260

    def set_items(self, items):
        """items: list of (label_text, fg_color, tag_data)"""
        self._items = items
        self._sel_idx = -1
        self._redraw()

    def get_selected_tag(self):
        if 0 <= self._sel_idx < len(self._items):
            return self._items[self._sel_idx][2]
        return None

    def select_index(self, idx):
        self._sel_idx = idx
        self._redraw()
        if 0 <= idx < len(self._items):
            y = idx * self.ROW_H
            total = len(self._items) * self.ROW_H
            self._canvas.yview_moveto(y / max(total, 1))

    def _on_resize(self, e):
        self._width = e.width
        self._redraw()

    def _on_wheel(self, e):
        self._canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def _on_click(self, e):
        idx = int(self._canvas.canvasy(e.y) // self.ROW_H)
        if 0 <= idx < len(self._items):
            self._sel_idx = idx
            self._redraw()
            if self._on_select:
                self._on_select(self._items[idx][2])

    def _redraw(self):
        self._canvas.delete("all")
        h = self.ROW_H
        w = self._width
        total_h = max(len(self._items) * h, 1)
        self._canvas.configure(scrollregion=(0, 0, w, total_h))
        # Only draw visible rows
        try:
            top_frac = self._canvas.yview()[0]
        except Exception:
            top_frac = 0
        top_px = int(top_frac * total_h)
        vis_start = max(0, top_px // h - 1)
        vis_end   = min(len(self._items), vis_start + (400 // h) + 4)
        for i in range(vis_start, vis_end):
            label, fg, _ = self._items[i]
            y0 = i * h
            bg = C["accent"] if i == self._sel_idx else self._bg
            tfg = "#ffffff" if i == self._sel_idx else fg
            self._canvas.create_rectangle(0, y0, w, y0 + h, fill=bg, outline="")
            self._canvas.create_text(10, y0 + h // 2, text=label, anchor="w",
                                     fill=tfg, font=("Segoe UI", 9))
        # Bind scroll to trigger redraw
        self._canvas.bind("<MouseWheel>", self._scroll_and_redraw)
        self._sb.config(command=self._scroll_cmd)

    def _scroll_cmd(self, *args):
        self._canvas.yview(*args)
        self._redraw()

    def _scroll_and_redraw(self, e):
        self._canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        self._redraw()


class CustomTitleBar(tk.Frame):
    def __init__(self, parent, app, title=""):
        super().__init__(parent, bg=C["bg"], height=36)
        self.pack_propagate(False)
        self.app = app
        self.root = app.root
        self._is_max = False
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<B1-Motion>",     self._do_move)
        self.bind("<Double-Button-1>", lambda e: self._toggle_max())

        back = tk.Label(self, text="⬡ Hub", bg=C["bg"], fg=C["fg_muted"],
                        font=("Segoe UI", 8), padx=10, pady=6, cursor="hand2")
        back.pack(side=tk.LEFT)
        back.bind("<Enter>",    lambda e: back.config(fg=C["accent"]))
        back.bind("<Leave>",    lambda e: back.config(fg=C["fg_muted"]))
        back.bind("<Button-1>", lambda e: app.back_to_hub())

        tk.Frame(self, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=6)

        lbl = tk.Label(self, text=f" {title}", bg=C["bg"], fg=C["fg_dim"],
                       font=("Segoe UI", 9, "bold"))
        lbl.pack(side=tk.LEFT, padx=4)
        lbl.bind("<ButtonPress-1>", self._start_move)
        lbl.bind("<B1-Motion>",     self._do_move)

        btns = tk.Frame(self, bg=C["bg"])
        btns.pack(side=tk.RIGHT, fill=tk.Y)
        FlatButton(btns, text="—", command=self._minimize,
                   bg=C["bg"], hover_bg=C["surface3"], padx=14).pack(side=tk.LEFT, fill=tk.Y)
        self._max_btn = FlatButton(btns, text="☐", command=self._toggle_max,
                                   bg=C["bg"], hover_bg=C["surface3"], padx=14)
        self._max_btn.pack(side=tk.LEFT, fill=tk.Y)
        FlatButton(btns, text="✕", command=lambda: self.root.event_generate("WM_DELETE_WINDOW"),
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
            self.root.bind("<Map>", self._on_map)
        else:
            self.root.iconify()

    def _on_map(self, e):
        if e.widget == self.root:
            self.root.overrideredirect(True)
            self.root.unbind("<Map>")

    def _toggle_max(self):
        if self._is_max:
            self.root.geometry(self._norm_geo)
            self._is_max = False
            self._max_btn.config(text="☐")
        else:
            self._norm_geo = self.root.geometry()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self._is_max = True
            self._max_btn.config(text="❐")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_settings():
    defaults = {
        "save_data_path": "",
        "last_campaign":  "",
        "readonly_mode":  False,
        "ui_font_family": "Segoe UI",
        "ui_font_size":   10,
        "code_font_family": "Consolas",
        "code_font_size": 10,
    }
    try:
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            defaults.update(data)
    except Exception:
        pass
    return defaults


def _save_settings(cfg: dict):
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(SETTINGS_PATH) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(SETTINGS_PATH))
    except Exception:
        pass


def _prompts_dir(save_data_root: str, campaign_id: str) -> Path:
    return Path(save_data_root) / campaign_id / "prompts"


def _list_campaigns(save_data_root: str):
    p = Path(save_data_root)
    if not p.exists():
        return []
    return sorted([d.name for d in p.iterdir() if d.is_dir()])


def _category_path(prompts: Path, cat: str) -> Path:
    if cat == "root_files":
        return prompts
    return prompts / cat


def _list_category_files(prompts: Path, cat: str):
    """
    Returns list of dicts:
      { 'label', 'path', 'pair_path', 'is_active_pair', 'ftype' }
    For actions/ _active pairs, only one entry is emitted (the base).
    """
    p = _category_path(prompts, cat)
    if not p.exists():
        return []
    try:
        all_files = sorted(p.iterdir(), key=lambda x: x.name.lower())
    except Exception:
        return []

    if cat == "root_files":
        all_files = [f for f in all_files if f.is_file()]
    else:
        all_files = [f for f in all_files if f.is_file()]

    seen = set()
    result = []
    for f in all_files:
        if f.name in seen:
            continue
        if f.suffix == ".json":
            result.append({
                "label":        f.name,
                "path":         f,
                "pair_path":    None,
                "is_active_pair": False,
                "ftype":        "json",
            })
            seen.add(f.name)
        elif f.name.endswith("_active.txt"):
            # skip — will be picked up with base
            seen.add(f.name)
        elif f.name.endswith(".txt"):
            base_name = f.name
            active_name = base_name[:-4] + "_active.txt"
            active_path = p / active_name
            is_pair = active_path.exists()
            result.append({
                "label":        base_name,
                "path":         f,
                "pair_path":    active_path if is_pair else None,
                "is_active_pair": is_pair,
                "ftype":        "txt_pair" if is_pair else "txt",
            })
            seen.add(base_name)
            if is_pair:
                seen.add(active_name)
    return result


def _file_count(prompts: Path, cat: str) -> int:
    return len(_list_category_files(prompts, cat))


def _make_backup(file_path: Path):
    bak_dir = file_path.parent.parent / ".bak"
    bak_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_name = f"{file_path.stem}_{ts}{file_path.suffix}"
    shutil.copy2(str(file_path), str(bak_dir / bak_name))


def _open_explorer(path: Path):
    folder = path if path.is_dir() else path.parent
    if platform.system() == "Windows":
        os.startfile(str(folder))
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])


# ---------------------------------------------------------------------------
# Collections helpers
# ---------------------------------------------------------------------------

def _save_snapshot(name: str, campaign_id: str, scope_path: Path,
                   prompts_root: Path, status_cb=None):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip().replace(" ", "_")
    dest = COLLECTIONS_DIR / f"{safe_name}_{ts}"
    dest.mkdir(parents=True, exist_ok=True)
    # Write metadata
    meta = {
        "name":       name,
        "timestamp":  ts,
        "campaign":   campaign_id,
        "scope":      str(scope_path.relative_to(prompts_root.parent.parent))
                       if prompts_root.parent.parent in scope_path.parents or scope_path == prompts_root
                       else str(scope_path),
        "file_count": 0,
    }
    count = 0
    if scope_path.is_file():
        target = dest / scope_path.name
        shutil.copy2(str(scope_path), str(target))
        count = 1
    else:
        for root_dir, dirs, files in os.walk(str(scope_path)):
            rel = Path(root_dir).relative_to(scope_path)
            for fn in files:
                src = Path(root_dir) / fn
                tgt_dir = dest / rel
                tgt_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(tgt_dir / fn))
                count += 1
    meta["file_count"] = count
    with open(str(dest / "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    if status_cb:
        status_cb(f"Snapshot '{name}' saved ({count} files)", "ok")
    return dest


def _list_collections():
    if not COLLECTIONS_DIR.exists():
        return []
    result = []
    for d in sorted(COLLECTIONS_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "metadata.json"
        if meta_path.exists():
            try:
                with open(str(meta_path), "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["_dir"] = d
                result.append(meta)
            except Exception:
                pass
    return result


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class PromptManagementApp:

    def __init__(self, root, on_close=None):
        self.root = root
        self._on_close = on_close
        self.root.overrideredirect(True)
        self.root.configure(bg=C["border"])
        self.root.geometry("1280x820")
        self.root.minsize(900, 600)

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"1280x820+{(sw-1280)//2}+{(sh-820)//2}")

        self._settings = _load_settings()
        self._campaign_id = self._settings.get("last_campaign", "")
        self._readonly = self._settings.get("readonly_mode", False)
        self._current_cat = ""
        self._current_file_info = None   # dict from _list_category_files
        self._active_variant = "base"    # "base" or "active"
        self._unsaved = False
        self._search_mode = False        # True = panel2 showing search results
        self._search_results = []        # list of (display, file_path, line_no, line_text)
        self._collections_open = False
        self._json_kv_rows = []          # for json key-value editor

        self._app_frame = tk.Frame(self.root, bg=C["bg"],
                                   highlightbackground=C["border"], highlightthickness=1)
        self._app_frame.pack(fill=tk.BOTH, expand=True)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_wm_close)
        self.root.after(50, self._auto_load)

    # ------------------------------------------------------------------
    # Hub integration
    # ------------------------------------------------------------------

    def back_to_hub(self):
        self._save_settings_state()
        self.root.destroy()
        if self._on_close:
            self._on_close()

    def _on_wm_close(self):
        self._save_settings_state()
        self.root.destroy()

    def _save_settings_state(self):
        self._settings["last_campaign"] = self._campaign_id
        self._settings["readonly_mode"] = self._readonly
        _save_settings(self._settings)

    def minimize(self):
        if platform.system() == "Windows":
            self.root.overrideredirect(False)
            self.root.iconify()
            self.root.bind("<Map>", self._on_map)
        else:
            self.root.iconify()

    def _on_map(self, e):
        if e.widget == self.root:
            self.root.overrideredirect(True)
            self.root.unbind("<Map>")

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self._title_bar = CustomTitleBar(self._app_frame, self, "Prompt Management")
        self._title_bar.pack(fill=tk.X)

        self._toolbar = self._build_toolbar(self._app_frame)
        self._toolbar.pack(fill=tk.X)

        tk.Frame(self._app_frame, bg=C["border"], height=1).pack(fill=tk.X)

        body = tk.Frame(self._app_frame, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)

        # Panel 1 — Sidebar
        self._sidebar = tk.Frame(body, bg=C["surface"], width=220)
        self._sidebar.grid(row=0, column=0, sticky="ns")
        self._sidebar.grid_propagate(False)
        self._build_sidebar(self._sidebar)

        tk.Frame(body, bg=C["border"], width=1).grid(row=0, column=1, sticky="ns")

        # Panel 2 — File List
        self._panel2 = tk.Frame(body, bg=C["surface2"], width=260)
        self._panel2.grid(row=0, column=2, sticky="ns")
        self._panel2.grid_propagate(False)
        self._build_panel2(self._panel2)

        tk.Frame(body, bg=C["border"], width=1).grid(row=0, column=3, sticky="ns")

        # Panel 3 — Editor
        self._panel3_outer = tk.Frame(body, bg=C["bg"])
        self._panel3_outer.grid(row=0, column=4, sticky="nsew")
        body.columnconfigure(4, weight=1)
        self._build_panel3(self._panel3_outer)

        # Collections drawer (hidden by default)
        self._collections_frame = tk.Frame(self._app_frame, bg=C["surface"],
                                           highlightbackground=C["border"], highlightthickness=1)
        self._build_collections_panel(self._collections_frame)

        self.status = StatusBar(self._app_frame)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self, parent):
        bar = tk.Frame(parent, bg=C["surface"], height=36)
        bar.pack_propagate(False)

        FlatButton(bar, text="▦ Collections", command=self._toggle_collections,
                   bg=C["surface"], fg=C["fg_dim"], hover_bg=C["surface2"],
                   hover_fg=C["accent"], font=("Segoe UI", 9), padx=14, pady=6).pack(side=tk.LEFT)

        FlatButton(bar, text="⌕ Search All", command=self._open_full_search,
                   bg=C["surface"], fg=C["fg_dim"], hover_bg=C["surface2"],
                   hover_fg=C["accent2"], font=("Segoe UI", 9), padx=14, pady=6).pack(side=tk.LEFT)

        FlatButton(bar, text="⬎ Copy Structure", command=self._open_copy_structure,
                   bg=C["surface"], fg=C["fg_dim"], hover_bg=C["surface2"],
                   hover_fg=C["accent3"], font=("Segoe UI", 9), padx=14, pady=6).pack(side=tk.LEFT)

        FlatButton(bar, text="↗ Export ZIP", command=self._export_zip,
                   bg=C["surface"], fg=C["fg_dim"], hover_bg=C["surface2"],
                   hover_fg=C["green"], font=("Segoe UI", 9), padx=14, pady=6).pack(side=tk.LEFT)

        tk.Frame(bar, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, pady=6)

        self._readonly_lbl = FlatButton(bar, text="◯ Read-only: OFF",
                                        command=self._toggle_readonly,
                                        bg=C["surface"], fg=C["fg_muted"],
                                        hover_bg=C["surface2"], hover_fg=C["fg"],
                                        font=("Segoe UI", 8), padx=12, pady=6)
        self._readonly_lbl.pack(side=tk.RIGHT)
        self._update_readonly_indicator()
        return bar

    def _update_readonly_indicator(self):
        if self._readonly:
            self._readonly_lbl.config(text="🔒 Read-only: ON", fg=C["accent3"])
        else:
            self._readonly_lbl.config(text="◯ Read-only: OFF", fg=C["fg_muted"])

    def _toggle_readonly(self):
        self._readonly = not self._readonly
        self._update_readonly_indicator()
        self._update_editor_state()
        self.status.set(f"Read-only {'enabled' if self._readonly else 'disabled'}", "info")

    # ------------------------------------------------------------------
    # Sidebar (Panel 1)
    # ------------------------------------------------------------------

    def _build_sidebar(self, parent):
        tk.Label(parent, text="CAMPAIGN", bg=C["surface"], fg=C["fg_muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(12, 4))

        self._campaign_var = tk.StringVar()
        self._campaign_cb = ttk.Combobox(parent, textvariable=self._campaign_var,
                                         state="readonly", width=22,
                                         font=("Segoe UI", 9))
        self._campaign_cb.pack(fill=tk.X, padx=10, pady=(0, 8))
        self._campaign_cb.bind("<<ComboboxSelected>>", self._on_campaign_change)

        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X)

        tk.Label(parent, text="CATEGORIES", bg=C["surface"], fg=C["fg_muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(10, 4))

        cat_outer = tk.Frame(parent, bg=C["surface"])
        cat_outer.pack(fill=tk.BOTH, expand=True)

        cat_canvas = tk.Canvas(cat_outer, bg=C["surface"], highlightthickness=0, bd=0)
        cat_sb = tk.Scrollbar(cat_outer, orient="vertical", command=cat_canvas.yview,
                              bg=C["scrollbar"], troughcolor=C["bg"], width=5)
        cat_canvas.configure(yscrollcommand=cat_sb.set)
        cat_sb.pack(side=tk.RIGHT, fill=tk.Y)
        cat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._cat_inner = tk.Frame(cat_canvas, bg=C["surface"])
        win_id = cat_canvas.create_window((0, 0), window=self._cat_inner, anchor="nw")
        cat_canvas.bind("<Configure>", lambda e: cat_canvas.itemconfig(win_id, width=e.width))
        self._cat_inner.bind("<Configure>",
                             lambda e: cat_canvas.configure(scrollregion=cat_canvas.bbox("all")))
        cat_canvas.bind_all("<MouseWheel>",
                            lambda e: cat_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        self._cat_btns = {}

    def _populate_category_tree(self):
        for w in self._cat_inner.winfo_children():
            w.destroy()
        self._cat_btns = {}
        if not self._campaign_id:
            return
        save_root = self._settings.get("save_data_path", "")
        if not save_root:
            return
        prompts = _prompts_dir(save_root, self._campaign_id)

        for cat, icon in CATEGORIES:
            count = _file_count(prompts, cat) if prompts.exists() else 0
            row = tk.Frame(self._cat_inner, bg=C["surface"], cursor="hand2")
            row.pack(fill=tk.X)
            ind = tk.Frame(row, bg=C["surface"], width=3)
            ind.pack(side=tk.LEFT, fill=tk.Y)
            lbl = tk.Label(row, text=f" {icon}  {cat}", bg=C["surface"], fg=C["fg_dim"],
                           font=("Segoe UI", 9), anchor="w")
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6, padx=4)
            badge = tk.Label(row, text=str(count), bg=C["surface"], fg=C["fg_muted"],
                             font=("Segoe UI", 8), padx=6)
            badge.pack(side=tk.RIGHT)
            self._cat_btns[cat] = (row, ind, lbl, badge)

            def _click(c=cat):
                self._select_category(c)

            for w in (row, lbl, badge, ind):
                w.bind("<Button-1>", lambda e, c=cat: self._select_category(c))
                w.bind("<Enter>",    lambda e, r=row, l=lbl: (
                    r.config(bg=C["surface2"]), l.config(bg=C["surface2"])))
                w.bind("<Leave>",    lambda e, r=row, l=lbl, c=cat: (
                    r.config(bg=C["surface"] if self._current_cat != c else C["surface3"]),
                    l.config(bg=C["surface"] if self._current_cat != c else C["surface3"])))

    def _select_category(self, cat):
        self._current_cat = cat
        self._search_mode = False
        for c, (row, ind, lbl, badge) in self._cat_btns.items():
            active = c == cat
            bg = C["surface3"] if active else C["surface"]
            for w in (row, lbl, badge):
                w.config(bg=bg)
            ind.config(bg=C["accent"] if active else C["surface"])
            lbl.config(fg=C["fg"] if active else C["fg_dim"])
        self._load_file_list()

    # ------------------------------------------------------------------
    # Panel 2 — file list
    # ------------------------------------------------------------------

    def _build_panel2(self, parent):
        search_row = tk.Frame(parent, bg=C["surface"])
        search_row.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(search_row, text="⌕", bg=C["surface"], fg=C["fg_muted"],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(4, 2))
        self._file_search_var = tk.StringVar()
        self._file_search_var.trace("w", lambda *a: self._on_file_search())
        ttk.Entry(search_row, textvariable=self._file_search_var,
                  font=("Segoe UI", 9), width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._panel2_header = tk.Label(parent, text="", bg=C["surface2"], fg=C["fg_muted"],
                                       font=("Segoe UI", 8, "bold"), anchor="w")
        self._panel2_header.pack(fill=tk.X, padx=8, pady=(0, 2))

        list_frame = tk.Frame(parent, bg=C["surface2"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self._file_list = VirtualList(list_frame, on_select=self._on_file_select,
                                      bg=C["surface2"])
        self._file_list.pack(fill=tk.BOTH, expand=True)

        self._panel2_file_infos = []   # parallel list to VirtualList items

    def _load_file_list(self, filter_text=""):
        if not self._campaign_id:
            self._file_list.set_items([])
            return
        save_root = self._settings.get("save_data_path", "")
        if not save_root:
            self._file_list.set_items([])
            return
        prompts = _prompts_dir(save_root, self._campaign_id)
        infos = _list_category_files(prompts, self._current_cat)
        if filter_text:
            infos = [i for i in infos if filter_text.lower() in i["label"].lower()]

        items = []
        self._panel2_file_infos = []
        for info in infos:
            if info["ftype"] == "json":
                fg = C["accent2"]
                label = info["label"]
            elif info["ftype"] == "txt_pair":
                fg = C["green"]
                label = f"● {info['label']}"
            else:
                fg = C["fg"]
                label = info["label"]
            items.append((label, fg, info["label"]))
            self._panel2_file_infos.append(info)

        self._file_list.set_items(items)
        self._panel2_header.config(text=f"  {self._current_cat}  ({len(items)} files)")
        self.status.set(f"{len(items)} files in '{self._current_cat}'", "info")

    def _on_file_search(self):
        if self._search_mode:
            return
        self._load_file_list(self._file_search_var.get())

    def _on_file_select(self, label_key):
        # find matching info
        for info in self._panel2_file_infos:
            if info["label"] == label_key or f"● {info['label']}" == label_key:
                self._open_file(info)
                return

    # search result click
    def _on_search_result_select(self, idx):
        if 0 <= idx < len(self._search_results):
            _, fpath, line_no, _ = self._search_results[idx]
            info = {
                "label":          fpath.name,
                "path":           fpath,
                "pair_path":      None,
                "is_active_pair": False,
                "ftype":          "txt",
            }
            self._open_file(info, scroll_to_line=line_no)

    # ------------------------------------------------------------------
    # Panel 3 — editor
    # ------------------------------------------------------------------

    def _build_panel3(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Header
        hdr = tk.Frame(parent, bg=C["surface"], height=56)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.columnconfigure(1, weight=1)

        self._editor_title = tk.Label(hdr, text="Select a file", bg=C["surface"],
                                      fg=C["fg"], font=("Segoe UI", 13, "bold"), anchor="w")
        self._editor_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(10, 0))
        self._editor_meta = tk.Label(hdr, text="", bg=C["surface"], fg=C["fg_muted"],
                                     font=("Segoe UI", 8), anchor="w")
        self._editor_meta.grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 6))

        # Toggle bar (base/active + json/raw toggles)
        self._toggle_bar = tk.Frame(parent, bg=C["bg"], height=30)
        self._toggle_bar.grid(row=1, column=0, sticky="ew")
        self._toggle_bar.grid_propagate(False)
        parent.rowconfigure(1, weight=0)
        parent.rowconfigure(2, weight=1)

        self._variant_frame = tk.Frame(self._toggle_bar, bg=C["bg"])
        self._variant_frame.pack(side=tk.LEFT, padx=8)
        self._base_btn  = FlatButton(self._variant_frame, text="Base",
                                     command=lambda: self._set_variant("base"),
                                     bg=C["accent"], fg="#fff", hover_bg=C["accent"],
                                     hover_fg="#fff", font=("Segoe UI", 8, "bold"),
                                     padx=10, pady=3)
        self._active_btn = FlatButton(self._variant_frame, text="Active",
                                      command=lambda: self._set_variant("active"),
                                      bg=C["surface3"], fg=C["fg_dim"],
                                      hover_bg=C["surface3"], hover_fg=C["fg"],
                                      font=("Segoe UI", 8), padx=10, pady=3)
        self._base_btn.pack(side=tk.LEFT)
        self._active_btn.pack(side=tk.LEFT, padx=(2, 0))
        self._variant_frame.pack_forget()

        self._json_toggle_frame = tk.Frame(self._toggle_bar, bg=C["bg"])
        self._json_toggle_frame.pack(side=tk.LEFT, padx=8)
        self._json_kv_btn  = FlatButton(self._json_toggle_frame, text="Form",
                                        command=lambda: self._set_json_mode("kv"),
                                        bg=C["accent"], fg="#fff",
                                        hover_bg=C["accent"], hover_fg="#fff",
                                        font=("Segoe UI", 8, "bold"), padx=10, pady=3)
        self._json_raw_btn = FlatButton(self._json_toggle_frame, text="Raw JSON",
                                        command=lambda: self._set_json_mode("raw"),
                                        bg=C["surface3"], fg=C["fg_dim"],
                                        hover_bg=C["surface3"], hover_fg=C["fg"],
                                        font=("Segoe UI", 8), padx=10, pady=3)
        self._json_kv_btn.pack(side=tk.LEFT)
        self._json_raw_btn.pack(side=tk.LEFT, padx=(2, 0))
        self._json_toggle_frame.pack_forget()

        # Unsaved dot
        self._unsaved_dot = tk.Label(self._toggle_bar, text="● unsaved",
                                     bg=C["bg"], fg=C["accent3"],
                                     font=("Segoe UI", 8))

        # Editor area (stacked frames)
        editor_area = tk.Frame(parent, bg=C["bg"])
        editor_area.grid(row=2, column=0, sticky="nsew")
        editor_area.columnconfigure(0, weight=1)
        editor_area.rowconfigure(0, weight=1)

        # Plain text editor
        self._txt_editor = scrolledtext.ScrolledText(
            editor_area, wrap=tk.WORD,
            font=(self._settings.get("code_font_family", "Consolas"),
                  self._settings.get("code_font_size", 10)),
            bg=C["surface"], fg=C["fg"], insertbackground=C["accent"],
            selectbackground=C["accent"], selectforeground="#fff",
            borderwidth=0, highlightthickness=0, padx=16, pady=12
        )
        self._txt_editor.vbar.config(bg=C["scrollbar"], troughcolor=C["bg"], width=8,
                                     relief="flat", bd=0)
        self._txt_editor.bind("<<Modified>>", self._on_txt_modified)
        self._txt_editor.grid(row=0, column=0, sticky="nsew")

        # JSON KV editor
        self._kv_outer = tk.Frame(editor_area, bg=C["surface"])
        self._kv_canvas = tk.Canvas(self._kv_outer, bg=C["surface"],
                                    highlightthickness=0, bd=0)
        kv_sb = tk.Scrollbar(self._kv_outer, orient="vertical", command=self._kv_canvas.yview,
                             bg=C["scrollbar"], troughcolor=C["bg"], width=6)
        self._kv_canvas.configure(yscrollcommand=kv_sb.set)
        kv_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._kv_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._kv_inner = tk.Frame(self._kv_canvas, bg=C["surface"])
        kv_win = self._kv_canvas.create_window((0, 0), window=self._kv_inner, anchor="nw")
        self._kv_canvas.bind("<Configure>",
                             lambda e: self._kv_canvas.itemconfig(kv_win, width=e.width))
        self._kv_inner.bind("<Configure>",
                            lambda e: self._kv_canvas.configure(
                                scrollregion=self._kv_canvas.bbox("all")))
        self._kv_outer.grid(row=0, column=0, sticky="nsew")
        self._kv_outer.grid_remove()

        # Action buttons
        act = tk.Frame(parent, bg=C["surface"], height=42)
        act.grid(row=3, column=0, sticky="ew")
        act.grid_propagate(False)
        parent.rowconfigure(3, weight=0)

        self._save_btn = AccentButton(act, text="✔ Save", command=self._save_file,
                                      padx=14, pady=4)
        self._save_btn.pack(side=tk.LEFT, padx=(12, 4), pady=6)

        FlatButton(act, text="↺ Reset", command=self._reset_file,
                   bg=C["surface2"], fg=C["fg_dim"], hover_fg=C["accent3"],
                   padx=12, pady=4).pack(side=tk.LEFT, padx=4, pady=6)

        FlatButton(act, text="⎘ Copy", command=self._copy_to_clipboard,
                   bg=C["surface2"], fg=C["fg_dim"], padx=12, pady=4).pack(
                   side=tk.LEFT, padx=4, pady=6)

        FlatButton(act, text="⬡ Explorer", command=self._open_explorer_btn,
                   bg=C["surface2"], fg=C["fg_dim"], hover_fg=C["accent2"],
                   padx=12, pady=4).pack(side=tk.LEFT, padx=4, pady=6)

        FlatButton(act, text="⬆ Snapshot", command=self._snapshot_current_file,
                   bg=C["surface2"], fg=C["fg_dim"], hover_fg=C["green"],
                   padx=12, pady=4).pack(side=tk.LEFT, padx=4, pady=6)

        self._json_mode = "kv"  # or "raw"

    def _update_editor_state(self):
        """Enable/disable the text editor based on readonly mode."""
        state = "disabled" if self._readonly else "normal"
        self._txt_editor.config(state=state)
        self._save_btn.config(cursor="arrow" if self._readonly else "hand2")

    # ------------------------------------------------------------------
    # Open / load file
    # ------------------------------------------------------------------

    def _open_file(self, info: dict, scroll_to_line: int = 0):
        self._current_file_info = info
        self._active_variant = "base"
        self._unsaved = False
        self._unsaved_dot.pack_forget()

        # Show/hide toggle bars
        if info["ftype"] == "txt_pair":
            self._variant_frame.pack(side=tk.LEFT, padx=8)
        else:
            self._variant_frame.pack_forget()

        if info["ftype"] == "json":
            self._json_toggle_frame.pack(side=tk.LEFT, padx=8)
        else:
            self._json_toggle_frame.pack_forget()

        # Update header
        self._editor_title.config(text=info["label"])
        try:
            mtime = datetime.fromtimestamp(info["path"].stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            mtime = ""
        rel = ""
        save_root = self._settings.get("save_data_path", "")
        if save_root:
            try:
                rel = str(info["path"].relative_to(Path(save_root)))
            except Exception:
                rel = str(info["path"])
        self._editor_meta.config(text=f"{rel}   ·   Modified: {mtime}")

        if info["ftype"] == "json":
            self._load_json_editor(info["path"])
        else:
            self._load_txt_editor(info["path"], scroll_to_line)

        self._update_editor_state()
        self.status.set(f"Opened: {info['label']}", "ok")

    def _load_txt_editor(self, path: Path, scroll_to_line: int = 0):
        self._kv_outer.grid_remove()
        self._txt_editor.grid()
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            text = f"[Error reading file: {e}]"
        self._txt_editor.config(state="normal")
        self._txt_editor.delete("1.0", tk.END)
        self._txt_editor.insert("1.0", text)
        self._txt_editor.edit_modified(False)
        self._unsaved = False
        if scroll_to_line > 0:
            self._txt_editor.see(f"{scroll_to_line}.0")
        self._update_editor_state()

    def _load_json_editor(self, path: Path):
        try:
            with open(str(path), "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            data = {}
            self.status.set(f"JSON parse error: {e}", "error")

        self._json_data = data
        if self._json_mode == "kv":
            self._render_kv_editor(data)
        else:
            self._kv_outer.grid_remove()
            self._txt_editor.grid()
            self._txt_editor.config(state="normal")
            self._txt_editor.delete("1.0", tk.END)
            self._txt_editor.insert("1.0", json.dumps(data, indent=2, ensure_ascii=False))
            self._txt_editor.edit_modified(False)

    def _render_kv_editor(self, data):
        self._txt_editor.grid_remove()
        self._kv_outer.grid()
        for w in self._kv_inner.winfo_children():
            w.destroy()
        self._json_kv_rows = []

        if isinstance(data, dict):
            for key, val in data.items():
                self._add_kv_row(key, val)
        elif isinstance(data, list):
            for i, val in enumerate(data):
                self._add_kv_row(str(i), val)

        # Add row button
        add_btn = FlatButton(self._kv_inner, text="+ Add field",
                             command=self._add_kv_empty_row,
                             bg=C["surface"], fg=C["accent"],
                             font=("Segoe UI", 9), padx=12, pady=4)
        add_btn.pack(anchor="w", padx=12, pady=8)

    def _add_kv_row(self, key, value):
        row_frame = tk.Frame(self._kv_inner, bg=C["surface2"], pady=1)
        row_frame.pack(fill=tk.X, padx=8, pady=2)
        row_frame.columnconfigure(1, weight=1)

        key_var = tk.StringVar(value=str(key))
        val_var = tk.StringVar(value=str(value) if not isinstance(value, (dict, list))
                               else json.dumps(value))

        key_entry = tk.Entry(row_frame, textvariable=key_var, bg=C["surface3"],
                             fg=C["accent2"], font=("Segoe UI", 9), bd=0,
                             insertbackground=C["accent"], width=20)
        key_entry.grid(row=0, column=0, padx=(8, 4), pady=4, sticky="w")

        val_entry = tk.Entry(row_frame, textvariable=val_var, bg=C["surface3"],
                             fg=C["fg"], font=("Consolas", 9), bd=0,
                             insertbackground=C["accent"])
        val_entry.grid(row=0, column=1, padx=(0, 4), pady=4, sticky="ew")

        del_btn = FlatButton(row_frame, text="✕",
                             command=lambda rf=row_frame: self._remove_kv_row(rf),
                             bg=C["surface2"], fg=C["fg_muted"],
                             hover_bg=C["surface3"], hover_fg=C["red"],
                             font=("Segoe UI", 9), padx=8, pady=2)
        del_btn.grid(row=0, column=2, padx=(0, 4))

        self._json_kv_rows.append((row_frame, key_var, val_var))
        return row_frame

    def _add_kv_empty_row(self):
        self._add_kv_row("", "")
        self._mark_unsaved()

    def _remove_kv_row(self, row_frame):
        row_frame.destroy()
        self._json_kv_rows = [(rf, k, v) for rf, k, v in self._json_kv_rows
                              if rf.winfo_exists()]
        self._mark_unsaved()

    def _collect_kv_data(self):
        result = {}
        for rf, k_var, v_var in self._json_kv_rows:
            if not rf.winfo_exists():
                continue
            k = k_var.get().strip()
            if not k:
                continue
            raw = v_var.get()
            try:
                v = json.loads(raw)
            except Exception:
                v = raw
            result[k] = v
        return result

    def _set_variant(self, variant):
        if not self._current_file_info:
            return
        self._active_variant = variant
        if variant == "base":
            self._base_btn.config(bg=C["accent"], fg="#fff")
            self._active_btn.config(bg=C["surface3"], fg=C["fg_dim"])
            path = self._current_file_info["path"]
        else:
            self._base_btn.config(bg=C["surface3"], fg=C["fg_dim"])
            self._active_btn.config(bg=C["accent"], fg="#fff")
            path = self._current_file_info["pair_path"]
        if path:
            self._load_txt_editor(path)

    def _set_json_mode(self, mode):
        self._json_mode = mode
        if mode == "kv":
            self._json_kv_btn.config(bg=C["accent"], fg="#fff")
            self._json_raw_btn.config(bg=C["surface3"], fg=C["fg_dim"])
            if self._current_file_info:
                self._render_kv_editor(self._json_data)
        else:
            self._json_kv_btn.config(bg=C["surface3"], fg=C["fg_dim"])
            self._json_raw_btn.config(bg=C["accent"], fg="#fff")
            self._kv_outer.grid_remove()
            self._txt_editor.grid()
            self._txt_editor.config(state="normal")
            self._txt_editor.delete("1.0", tk.END)
            self._txt_editor.insert("1.0", json.dumps(self._json_data, indent=2, ensure_ascii=False))
            self._txt_editor.edit_modified(False)

    def _on_txt_modified(self, event=None):
        if self._txt_editor.edit_modified():
            self._mark_unsaved()
            self._txt_editor.edit_modified(False)

    def _mark_unsaved(self):
        if not self._unsaved:
            self._unsaved = True
            self._unsaved_dot.pack(side=tk.LEFT, padx=8)

    # ------------------------------------------------------------------
    # Save / Reset
    # ------------------------------------------------------------------

    def _current_edit_path(self) -> Path | None:
        if not self._current_file_info:
            return None
        info = self._current_file_info
        if info["ftype"] == "txt_pair" and self._active_variant == "active":
            return info["pair_path"]
        return info["path"]

    def _save_file(self):
        if self._readonly:
            self.status.set("Read-only mode — save disabled", "warn")
            return
        path = self._current_edit_path()
        if not path:
            return
        try:
            _make_backup(path)
            if self._current_file_info["ftype"] == "json" and self._json_mode == "kv":
                data = self._collect_kv_data()
                tmp = str(path) + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp, str(path))
                self._json_data = data
            else:
                content = self._txt_editor.get("1.0", tk.END)
                path.write_text(content, encoding="utf-8")
            self._unsaved = False
            self._unsaved_dot.pack_forget()
            self.status.set(f"Saved: {path.name}", "ok")
        except Exception as e:
            self.status.set(f"Save error: {e}", "error")

    def _reset_file(self):
        if not self._current_file_info:
            return
        path = self._current_edit_path()
        if path:
            if self._current_file_info["ftype"] == "json":
                self._load_json_editor(path)
            else:
                self._load_txt_editor(path)
        self._unsaved = False
        self._unsaved_dot.pack_forget()
        self.status.set("Reverted to saved", "info")

    def _copy_to_clipboard(self):
        if self._current_file_info and self._current_file_info["ftype"] == "json" \
                and self._json_mode == "kv":
            text = json.dumps(self._collect_kv_data(), indent=2, ensure_ascii=False)
        else:
            text = self._txt_editor.get("1.0", tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set("Copied to clipboard", "ok")

    def _open_explorer_btn(self):
        path = self._current_edit_path()
        if path:
            _open_explorer(path)

    def _snapshot_current_file(self):
        info = self._current_file_info
        if not info:
            self.status.set("No file selected", "warn")
            return
        self._open_snapshot_dialog(scope_path=info["path"])

    # ------------------------------------------------------------------
    # Campaign loading
    # ------------------------------------------------------------------

    def _auto_load(self):
        save_root = self._settings.get("save_data_path", "")
        campaigns = _list_campaigns(save_root) if save_root else []
        self._campaign_cb["values"] = campaigns
        last = self._settings.get("last_campaign", "")
        if last and last in campaigns:
            self._campaign_var.set(last)
            self._campaign_id = last
        elif campaigns:
            self._campaign_var.set(campaigns[0])
            self._campaign_id = campaigns[0]
        else:
            self.status.set("No campaigns found — set save_data_path in Settings", "warn")
            return
        self._populate_category_tree()
        self.status.set(f"Campaign: {self._campaign_id}", "ok")

    def _on_campaign_change(self, event=None):
        self._campaign_id = self._campaign_var.get()
        self._settings["last_campaign"] = self._campaign_id
        _save_settings(self._settings)
        self._populate_category_tree()
        self._file_list.set_items([])
        self._panel2_file_infos = []
        self._current_cat = ""
        self.status.set(f"Campaign: {self._campaign_id}", "ok")

    # ------------------------------------------------------------------
    # Full-text search
    # ------------------------------------------------------------------

    def _open_full_search(self):
        win = tk.Toplevel(self.root)
        win.title("Full-text Search")
        win.geometry("680x520")
        win.configure(bg=C["surface"])
        win.transient(self.root)
        win.grab_set()
        win.attributes("-topmost", True)

        outer = tk.Frame(win, bg=C["surface"],
                         highlightbackground=C["border"], highlightthickness=1)
        outer.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Label(outer, text="⌕ Search All Prompt Files", bg=C["surface"], fg=C["accent"],
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=20, pady=(14, 4))
        tk.Frame(outer, bg=C["border"], height=1).pack(fill=tk.X, padx=20)

        row = tk.Frame(outer, bg=C["surface"])
        row.pack(fill=tk.X, padx=20, pady=10)
        query_var = tk.StringVar()
        query_entry = tk.Entry(row, textvariable=query_var, bg=C["surface2"], fg=C["fg"],
                               font=("Segoe UI", 11), insertbackground=C["accent"],
                               bd=0, highlightthickness=1, highlightbackground=C["border"])
        query_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        query_entry.focus_set()

        results_frame = tk.Frame(outer, bg=C["surface2"])
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 12))
        results_lb = tk.Listbox(results_frame, bg=C["surface2"], fg=C["fg"],
                                selectbackground=C["accent"], selectforeground="#fff",
                                font=("Consolas", 9), borderwidth=0, highlightthickness=0,
                                activestyle="none")
        results_sb = tk.Scrollbar(results_frame, orient="vertical", command=results_lb.yview,
                                  bg=C["scrollbar"], troughcolor=C["bg"], width=6)
        results_lb.config(yscrollcommand=results_sb.set)
        results_sb.pack(side=tk.RIGHT, fill=tk.Y)
        results_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        result_data = []

        def do_search(*_):
            q = query_var.get().strip()
            if not q:
                return
            results_lb.delete(0, tk.END)
            result_data.clear()
            save_root = self._settings.get("save_data_path", "")
            if not save_root or not self._campaign_id:
                return
            prompts = _prompts_dir(save_root, self._campaign_id)
            q_lower = q.lower()
            for root_dir, dirs, files in os.walk(str(prompts)):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fn in sorted(files):
                    if not (fn.endswith(".txt") or fn.endswith(".json")):
                        continue
                    fp = Path(root_dir) / fn
                    try:
                        lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
                    except Exception:
                        continue
                    for ln, line in enumerate(lines, 1):
                        if q_lower in line.lower():
                            snippet = line.strip()[:80]
                            display = f"{fn}:{ln}  {snippet}"
                            results_lb.insert(tk.END, display)
                            result_data.append((fn, fp, ln, line))

        def open_result(event=None):
            sel = results_lb.curselection()
            if not sel:
                return
            _, fp, ln, _ = result_data[sel[0]]
            info = {
                "label": fp.name,
                "path": fp,
                "pair_path": None,
                "is_active_pair": False,
                "ftype": "txt",
            }
            win.destroy()
            self._open_file(info, scroll_to_line=ln)

        query_entry.bind("<Return>", do_search)
        results_lb.bind("<Double-Button-1>", open_result)
        AccentButton(row, text="Search", command=do_search, padx=12, pady=4).pack(
            side=tk.LEFT, padx=(8, 0))

    # ------------------------------------------------------------------
    # Export ZIP
    # ------------------------------------------------------------------

    def _export_zip(self):
        if not self._campaign_id:
            self.status.set("No campaign selected", "warn")
            return
        save_root = self._settings.get("save_data_path", "")
        if not save_root:
            return
        prompts = _prompts_dir(save_root, self._campaign_id)
        dest = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
            initialfile=f"{self._campaign_id}_prompts.zip",
        )
        if not dest:
            return
        scope = _category_path(prompts, self._current_cat) if self._current_cat else prompts
        try:
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                if scope.is_file():
                    zf.write(str(scope), scope.name)
                else:
                    for root_dir, _, files in os.walk(str(scope)):
                        for fn in files:
                            fp = Path(root_dir) / fn
                            zf.write(str(fp), str(fp.relative_to(prompts)))
            self.status.set(f"Exported to {Path(dest).name}", "ok")
        except Exception as e:
            self.status.set(f"Export error: {e}", "error")

    # ------------------------------------------------------------------
    # Snapshot / Collections
    # ------------------------------------------------------------------

    def _open_snapshot_dialog(self, scope_path: Path = None):
        if not self._campaign_id:
            self.status.set("No campaign selected", "warn")
            return
        save_root = self._settings.get("save_data_path", "")
        if not save_root:
            return
        prompts = _prompts_dir(save_root, self._campaign_id)

        win = tk.Toplevel(self.root)
        win.title("Take Snapshot")
        win.geometry("520x360")
        win.configure(bg=C["surface"])
        win.transient(self.root)
        win.grab_set()

        outer = tk.Frame(win, bg=C["surface"],
                         highlightbackground=C["border"], highlightthickness=1)
        outer.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        tk.Label(outer, text="⬆ Save Snapshot / Collection", bg=C["surface"], fg=C["accent"],
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=20, pady=(14, 4))
        tk.Frame(outer, bg=C["border"], height=1).pack(fill=tk.X, padx=20)

        tk.Label(outer, text="Name:", bg=C["surface"], fg=C["fg_dim"],
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(12, 2))
        name_var = tk.StringVar(value=f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        tk.Entry(outer, textvariable=name_var, bg=C["surface2"], fg=C["fg"],
                 font=("Segoe UI", 10), bd=0, insertbackground=C["accent"]).pack(
                 fill=tk.X, padx=20, ipady=4)

        tk.Label(outer, text="Scope:", bg=C["surface"], fg=C["fg_dim"],
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(10, 2))
        scope_var = tk.StringVar()
        scopes = [("Current file", scope_path),
                  (f"Category: {self._current_cat}",
                   _category_path(prompts, self._current_cat) if self._current_cat else None),
                  ("Entire campaign prompts", prompts)]
        scopes = [(label, p) for label, p in scopes if p is not None]
        scope_labels = [s[0] for s in scopes]
        scope_var.set(scope_labels[0] if scope_labels else "")
        cb = ttk.Combobox(outer, textvariable=scope_var, values=scope_labels,
                          state="readonly", font=("Segoe UI", 9))
        cb.pack(fill=tk.X, padx=20, pady=(0, 12))

        def confirm():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Name required", "Please enter a snapshot name.", parent=win)
                return
            sel = scope_var.get()
            chosen_path = next((p for l, p in scopes if l == sel), None)
            if not chosen_path:
                return
            win.destroy()
            _save_snapshot(name, self._campaign_id, chosen_path, prompts,
                           status_cb=self.status.set)

        btn_row = tk.Frame(outer, bg=C["surface"])
        btn_row.pack(fill=tk.X, padx=20, pady=(0, 16))
        AccentButton(btn_row, text="Save Snapshot", command=confirm, padx=12, pady=4).pack(
            side=tk.LEFT)
        FlatButton(btn_row, text="Cancel", command=win.destroy,
                   bg=C["surface2"], fg=C["fg_dim"], padx=10, pady=4).pack(
                   side=tk.LEFT, padx=8)

    def _toggle_collections(self):
        if self._collections_open:
            self._collections_frame.pack_forget()
            self._collections_open = False
        else:
            self._refresh_collections_list()
            self._collections_frame.pack(fill=tk.X, before=self.status)
            self._collections_open = True

    def _build_collections_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        tk.Label(parent, text="▦ Collections", bg=C["surface"], fg=C["accent"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(10, 4))
        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X)

        btn_row = tk.Frame(parent, bg=C["surface"])
        btn_row.pack(fill=tk.X, padx=12, pady=4)
        FlatButton(btn_row, text="+ New Snapshot", command=self._open_snapshot_dialog,
                   bg=C["surface2"], fg=C["accent"], font=("Segoe UI", 9),
                   padx=10, pady=3).pack(side=tk.LEFT)
        FlatButton(btn_row, text="✕ Close", command=self._toggle_collections,
                   bg=C["surface"], fg=C["fg_muted"], font=("Segoe UI", 9),
                   padx=10, pady=3).pack(side=tk.RIGHT)

        list_outer = tk.Frame(parent, bg=C["surface"], height=180)
        list_outer.pack(fill=tk.X, padx=12, pady=(0, 8))
        list_outer.pack_propagate(False)

        self._coll_listbox = tk.Listbox(list_outer, bg=C["surface2"], fg=C["fg"],
                                         selectbackground=C["accent"], selectforeground="#fff",
                                         font=("Segoe UI", 9), borderwidth=0,
                                         highlightthickness=0, activestyle="none")
        coll_sb = tk.Scrollbar(list_outer, orient="vertical",
                               command=self._coll_listbox.yview,
                               bg=C["scrollbar"], troughcolor=C["bg"], width=6)
        self._coll_listbox.config(yscrollcommand=coll_sb.set)
        coll_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._coll_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._coll_data = []

        act_row = tk.Frame(parent, bg=C["surface"])
        act_row.pack(fill=tk.X, padx=12, pady=(0, 10))
        FlatButton(act_row, text="↩ Restore", command=self._restore_collection,
                   bg=C["surface2"], fg=C["fg_dim"], hover_fg=C["green"],
                   font=("Segoe UI", 9), padx=10, pady=3).pack(side=tk.LEFT, padx=(0, 4))
        FlatButton(act_row, text="⬎ Copy to...", command=self._copy_collection_to,
                   bg=C["surface2"], fg=C["fg_dim"], hover_fg=C["accent2"],
                   font=("Segoe UI", 9), padx=10, pady=3).pack(side=tk.LEFT, padx=(0, 4))
        FlatButton(act_row, text="⊘ Delete", command=self._delete_collection,
                   bg=C["surface2"], fg=C["fg_dim"], hover_fg=C["red"],
                   font=("Segoe UI", 9), padx=10, pady=3).pack(side=tk.LEFT)

    def _refresh_collections_list(self):
        self._coll_listbox.delete(0, tk.END)
        self._coll_data = _list_collections()
        for meta in self._coll_data:
            ts = meta.get("timestamp", "?")
            try:
                ts_fmt = datetime.strptime(ts, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts_fmt = ts
            label = (f"  {meta.get('name', '?')}   ·   {ts_fmt}   ·   "
                     f"{meta.get('campaign', '?')}   ·   {meta.get('file_count', '?')} files")
            self._coll_listbox.insert(tk.END, label)

    def _selected_collection(self):
        sel = self._coll_listbox.curselection()
        if sel and 0 <= sel[0] < len(self._coll_data):
            return self._coll_data[sel[0]]
        return None

    def _restore_collection(self):
        meta = self._selected_collection()
        if not meta:
            self.status.set("Select a collection first", "warn")
            return
        if not messagebox.askyesno(
                "Restore Collection",
                f"Restore '{meta['name']}' to campaign '{self._campaign_id}'?\n"
                f"Current files will be auto-backed up first.",
                parent=self.root):
            return
        save_root = self._settings.get("save_data_path", "")
        if not save_root or not self._campaign_id:
            return
        prompts = _prompts_dir(save_root, self._campaign_id)
        # auto-backup current state
        _save_snapshot(f"pre-restore-backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                       self._campaign_id, prompts, prompts)
        src_dir: Path = meta["_dir"]
        count = 0
        for root_dir, _, files in os.walk(str(src_dir)):
            for fn in files:
                if fn == "metadata.json":
                    continue
                src = Path(root_dir) / fn
                rel = src.relative_to(src_dir)
                dest = prompts / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dest))
                count += 1
        self.status.set(f"Restored {count} files from '{meta['name']}'", "ok")
        self._load_file_list()

    def _copy_collection_to(self):
        meta = self._selected_collection()
        if not meta:
            self.status.set("Select a collection first", "warn")
            return
        save_root = self._settings.get("save_data_path", "")
        if not save_root:
            return
        campaigns = _list_campaigns(save_root)
        other = [c for c in campaigns if c != meta.get("campaign", "")]
        if not other:
            messagebox.showinfo("No Other Campaigns", "No other campaigns to copy to.",
                                parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("Copy Collection to Campaign")
        win.geometry("400x200")
        win.configure(bg=C["surface"])
        win.transient(self.root)
        win.grab_set()

        outer = tk.Frame(win, bg=C["surface"],
                         highlightbackground=C["border"], highlightthickness=1)
        outer.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        tk.Label(outer, text="Target Campaign:", bg=C["surface"], fg=C["fg_dim"],
                 font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(16, 4))
        target_var = tk.StringVar(value=other[0])
        cb = ttk.Combobox(outer, textvariable=target_var, values=other,
                          state="readonly", font=("Segoe UI", 10))
        cb.pack(fill=tk.X, padx=20, pady=(0, 12))

        def confirm():
            target = target_var.get()
            win.destroy()
            target_prompts = _prompts_dir(save_root, target)
            _save_snapshot(f"pre-copy-backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                           target, target_prompts, target_prompts)
            src_dir: Path = meta["_dir"]
            count = 0
            for root_dir, _, files in os.walk(str(src_dir)):
                for fn in files:
                    if fn == "metadata.json":
                        continue
                    src = Path(root_dir) / fn
                    rel = src.relative_to(src_dir)
                    dest = target_prompts / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(dest))
                    count += 1
            self.status.set(f"Copied {count} files to campaign '{target}'", "ok")

        btn_row = tk.Frame(outer, bg=C["surface"])
        btn_row.pack(fill=tk.X, padx=20, pady=(0, 16))
        AccentButton(btn_row, text="Copy", command=confirm, padx=12, pady=4).pack(side=tk.LEFT)
        FlatButton(btn_row, text="Cancel", command=win.destroy,
                   bg=C["surface2"], fg=C["fg_dim"], padx=10, pady=4).pack(
                   side=tk.LEFT, padx=8)

    def _delete_collection(self):
        meta = self._selected_collection()
        if not meta:
            self.status.set("Select a collection first", "warn")
            return
        if not messagebox.askyesno(
                "Delete Collection",
                f"Permanently delete '{meta['name']}'?",
                parent=self.root):
            return
        try:
            shutil.rmtree(str(meta["_dir"]))
            self.status.set(f"Deleted '{meta['name']}'", "ok")
        except Exception as e:
            self.status.set(f"Delete error: {e}", "error")
        self._refresh_collections_list()

    # ------------------------------------------------------------------
    # Copy Structure (Campaign → Campaign)
    # ------------------------------------------------------------------

    def _open_copy_structure(self):
        save_root = self._settings.get("save_data_path", "")
        if not save_root:
            self.status.set("save_data_path not configured", "warn")
            return
        campaigns = _list_campaigns(save_root)
        if len(campaigns) < 2:
            messagebox.showinfo("Copy Structure",
                                "Need at least 2 campaigns to copy between.",
                                parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("Copy Prompt Structure")
        win.geometry("640x560")
        win.configure(bg=C["surface"])
        win.transient(self.root)
        win.grab_set()

        outer = tk.Frame(win, bg=C["surface"],
                         highlightbackground=C["border"], highlightthickness=1)
        outer.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Label(outer, text="⬎ Copy Prompt Structure", bg=C["surface"], fg=C["accent"],
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=20, pady=(14, 4))
        tk.Frame(outer, bg=C["border"], height=1).pack(fill=tk.X, padx=20)

        row1 = tk.Frame(outer, bg=C["surface"])
        row1.pack(fill=tk.X, padx=20, pady=(10, 4))
        tk.Label(row1, text="Source:", bg=C["surface"], fg=C["fg_dim"],
                 font=("Segoe UI", 9), width=10, anchor="w").pack(side=tk.LEFT)
        src_var = tk.StringVar(value=campaigns[0])
        ttk.Combobox(row1, textvariable=src_var, values=campaigns, state="readonly",
                     width=30, font=("Segoe UI", 9)).pack(side=tk.LEFT)

        row2 = tk.Frame(outer, bg=C["surface"])
        row2.pack(fill=tk.X, padx=20, pady=(4, 4))
        tk.Label(row2, text="Target:", bg=C["surface"], fg=C["fg_dim"],
                 font=("Segoe UI", 9), width=10, anchor="w").pack(side=tk.LEFT)
        tgt_var = tk.StringVar(value=campaigns[-1])
        ttk.Combobox(row2, textvariable=tgt_var, values=campaigns, state="readonly",
                     width=30, font=("Segoe UI", 9)).pack(side=tk.LEFT)

        tk.Label(outer, text="Scope (select categories):", bg=C["surface"], fg=C["fg_dim"],
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(8, 2))

        scope_frame = tk.Frame(outer, bg=C["surface2"])
        scope_frame.pack(fill=tk.X, padx=20, pady=(0, 8))
        cat_vars = {}
        all_var = tk.BooleanVar(value=True)

        all_cb = ttk.Checkbutton(scope_frame, text="All categories", variable=all_var,
                                 style="TCheckbutton")
        all_cb.pack(anchor="w", padx=12, pady=4)
        for cat, _ in CATEGORIES:
            v = tk.BooleanVar(value=False)
            cat_vars[cat] = v
            ttk.Checkbutton(scope_frame, text=cat, variable=v,
                            style="TCheckbutton").pack(anchor="w", padx=24, pady=1)

        preview_txt = tk.Text(outer, bg=C["surface2"], fg=C["fg_dim"],
                              font=("Consolas", 8), height=6, bd=0,
                              state="disabled", wrap="none")
        preview_txt.pack(fill=tk.X, padx=20, pady=(0, 8))

        def preview():
            src = src_var.get()
            tgt = tgt_var.get()
            if src == tgt:
                preview_txt.config(state="normal")
                preview_txt.delete("1.0", tk.END)
                preview_txt.insert(tk.END, "Source and target must differ.")
                preview_txt.config(state="disabled")
                return
            src_p = _prompts_dir(save_root, src)
            tgt_p = _prompts_dir(save_root, tgt)
            cats_to_copy = list(CATEGORIES) if all_var.get() else [
                (c, i) for c, i in CATEGORIES if cat_vars[c].get()]
            lines = []
            for cat, _ in cats_to_copy:
                src_c = _category_path(src_p, cat)
                tgt_c = _category_path(tgt_p, cat)
                if not src_c.exists():
                    continue
                for root_dir, _, files in os.walk(str(src_c)):
                    for fn in files:
                        rel = Path(root_dir).relative_to(src_p) / fn
                        dest = tgt_p / rel
                        marker = "[overwrite]" if dest.exists() else "[new]"
                        lines.append(f"{marker} {rel}")
            preview_txt.config(state="normal")
            preview_txt.delete("1.0", tk.END)
            preview_txt.insert(tk.END, "\n".join(lines[:100]))
            if len(lines) > 100:
                preview_txt.insert(tk.END, f"\n... and {len(lines)-100} more")
            preview_txt.config(state="disabled")

        def confirm():
            src = src_var.get()
            tgt = tgt_var.get()
            if src == tgt:
                messagebox.showwarning("Same Campaign",
                                       "Source and target must differ.", parent=win)
                return
            if not messagebox.askyesno("Confirm Copy",
                                       f"Copy from '{src}' to '{tgt}'?\n"
                                       f"Target files will be auto-backed up.",
                                       parent=win):
                return
            tgt_p = _prompts_dir(save_root, tgt)
            src_p = _prompts_dir(save_root, src)
            _save_snapshot(f"pre-copy-backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                           tgt, tgt_p, tgt_p)
            cats_to_copy = list(CATEGORIES) if all_var.get() else [
                (c, i) for c, i in CATEGORIES if cat_vars[c].get()]
            count = 0
            for cat, _ in cats_to_copy:
                src_c = _category_path(src_p, cat)
                if not src_c.exists():
                    continue
                for root_dir, _, files in os.walk(str(src_c)):
                    for fn in files:
                        rel = Path(root_dir).relative_to(src_p) / fn
                        dest = tgt_p / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(Path(root_dir) / fn), str(dest))
                        count += 1
            win.destroy()
            self.status.set(f"Copied {count} files from '{src}' to '{tgt}'", "ok")

        btn_row = tk.Frame(outer, bg=C["surface"])
        btn_row.pack(fill=tk.X, padx=20, pady=(0, 14))
        AccentButton(btn_row, text="Preview", command=preview,
                     padx=12, pady=4).pack(side=tk.LEFT)
        AccentButton(btn_row, text="Copy", command=confirm,
                     padx=12, pady=4).pack(side=tk.LEFT, padx=8)
        FlatButton(btn_row, text="Cancel", command=win.destroy,
                   bg=C["surface2"], fg=C["fg_dim"], padx=10, pady=4).pack(side=tk.LEFT)


# ---------------------------------------------------------------------------
# Stand-alone entry point
# ---------------------------------------------------------------------------

def main():
    try:
        root = tk.Tk()
        root.withdraw()
        app = PromptManagementApp(root)
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"1280x820+{(sw-1280)//2}+{(sh-820)//2}")
        root.deiconify()
        root.protocol("WM_DELETE_WINDOW", lambda: (app._save_settings_state(), root.destroy()))
        root.mainloop()
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        try:
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror("Startup Error",
                                 f"PromptManagement crashed:\n\n{err}", parent=r)
            r.destroy()
        except Exception:
            print(err, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
