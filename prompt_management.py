#!/usr/bin/env python3
"""
Luminous AI — Prompt Management Section  (Part 1: Foundation)
PromptManagementApp: campaign discovery, file model, 3-panel layout scaffold.
No full editor yet — Panel 3 shows selection info only.
"""
import tkinter as tk
import json
import os
import sys
import platform
from pathlib import Path
from typing import Optional

try:
    from settings import SettingsManager, settings_manager as _global_sm
except ImportError as _e:
    import tkinter.messagebox as _mb
    _r = tk.Tk(); _r.withdraw()
    _mb.showerror("Import Error", f"prompt_management.py: {_e}")
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

# Ordered category list (matches prompts/ subfolder names)
PROMPT_CATEGORIES = [
    "actions",
    "character_creation",
    "diplomacy_internal_thoughts",
    "dynamic_events_generator",
    "dynamic_events_internal_thoughts",
    "group_conversation",
    "internal_thoughts",
    "json_output",
    "kingdom_statement",
    "npc_initiative",
    "rules",
    "world_data",
]

# Root-level files that live directly in prompts/
ROOT_PROMPT_FILES = [
    "playerdescription.txt",
    "PromptModuleResponse.txt",
]

CATEGORY_ICONS = {
    "actions":                        "\u25b6",
    "character_creation":             "\u25c6",
    "diplomacy_internal_thoughts":    "\u2666",
    "dynamic_events_generator":       "\u2734",
    "dynamic_events_internal_thoughts": "\u2733",
    "group_conversation":             "\u25a6",
    "internal_thoughts":              "\u25cb",
    "json_output":                    "\u2692",
    "kingdom_statement":              "\u2654",
    "npc_initiative":                 "\u25cf",
    "rules":                          "\u2261",
    "world_data":                     "\u25bb",
    "__root__":                       "\u2026",
}


# ===========================================================================
# Data model
# ===========================================================================

class PromptFileEntry:
    """
    Represents one logical prompt file in the file model.

    Paired files (base.txt + base_active.txt) are a single entry.
    .json files in world_data are a separate entry with kind='json'.
    """
    __slots__ = ("name", "base_path", "active_path", "kind", "category")

    def __init__(self, name: str, base_path: str,
                 active_path: Optional[str],
                 kind: str,           # 'txt', 'paired', 'json'
                 category: str):      # category key or '__root__'
        self.name = name
        self.base_path = base_path
        self.active_path = active_path
        self.kind = kind
        self.category = category

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def has_active(self) -> bool:
        return self.active_path is not None

    @property
    def type_tag(self) -> str:
        if self.kind == "json":
            return "JSON"
        if self.kind == "paired":
            return "PAIRED"
        return "TXT"


class CategoryModel:
    """Holds all PromptFileEntry objects for one category."""
    __slots__ = ("key", "path", "entries", "exists")

    def __init__(self, key: str, path: str):
        self.key = key
        self.path = path
        self.entries: list[PromptFileEntry] = []
        self.exists: bool = False

    @property
    def count(self) -> int:
        return len(self.entries)


class PromptIndex:
    """
    Full index of all prompts for a single campaign.
    Build once via scan(); then query via categories / all_entries.
    """

    def __init__(self):
        self.campaign_id: str = ""
        self.prompts_root: str = ""
        self.categories: dict[str, CategoryModel] = {}
        self.root_entries: list[PromptFileEntry] = []

    def scan(self, save_data_path: str, campaign_id: str) -> bool:
        """
        Scan save_data_path/<campaign_id>/prompts/ and populate the model.
        Returns True if the prompts folder exists.
        """
        self.campaign_id = campaign_id
        self.prompts_root = os.path.join(save_data_path, campaign_id, "prompts")
        self.categories = {}
        self.root_entries = []

        if not os.path.isdir(self.prompts_root):
            return False

        # scan each category subfolder
        for cat_key in PROMPT_CATEGORIES:
            cat_path = os.path.join(self.prompts_root, cat_key)
            model = CategoryModel(cat_key, cat_path)
            model.exists = os.path.isdir(cat_path)
            if model.exists:
                model.entries = _scan_category_folder(cat_path, cat_key)
            self.categories[cat_key] = model

        # scan root-level files
        for fname in ROOT_PROMPT_FILES:
            fp = os.path.join(self.prompts_root, fname)
            if os.path.isfile(fp):
                self.root_entries.append(
                    PromptFileEntry(
                        name=fname,
                        base_path=fp,
                        active_path=None,
                        kind="txt",
                        category="__root__"
                    )
                )
        # also pick up any other loose .txt in prompts root
        try:
            for fname in sorted(os.listdir(self.prompts_root)):
                fp = os.path.join(self.prompts_root, fname)
                if not os.path.isfile(fp):
                    continue
                if fname in ROOT_PROMPT_FILES:
                    continue
                if fname.endswith(".txt") and not fname.endswith("_active.txt"):
                    self.root_entries.append(
                        PromptFileEntry(
                            name=fname,
                            base_path=fp,
                            active_path=None,
                            kind="txt",
                            category="__root__"
                        )
                    )
        except OSError:
            pass

        return True

    def total_files(self) -> int:
        n = len(self.root_entries)
        for cm in self.categories.values():
            n += cm.count
        return n

    def entries_for_category(self, key: str) -> list[PromptFileEntry]:
        if key == "__root__":
            return list(self.root_entries)
        cm = self.categories.get(key)
        return list(cm.entries) if cm else []


def _scan_category_folder(folder: str, cat_key: str) -> list[PromptFileEntry]:
    """
    Scan a single category folder.
    Pair base.txt + base_active.txt into one PromptFileEntry(kind='paired').
    .json files get kind='json'.
    Standalone .txt (no _active counterpart) get kind='txt'.
    """
    entries: list[PromptFileEntry] = []
    try:
        all_files = sorted(os.listdir(folder))
    except OSError:
        return entries

    seen: set[str] = set()
    # build set of active stems for fast lookup
    active_stems: set[str] = set()
    for fn in all_files:
        if fn.endswith("_active.txt"):
            active_stems.add(fn[: -len("_active.txt")])

    for fn in all_files:
        if fn in seen:
            continue
        fp = os.path.join(folder, fn)
        if not os.path.isfile(fp):
            continue

        if fn.endswith("_active.txt"):
            # will be consumed by its base entry
            seen.add(fn)
            continue

        if fn.endswith(".json"):
            entries.append(PromptFileEntry(
                name=fn,
                base_path=fp,
                active_path=None,
                kind="json",
                category=cat_key,
            ))
            seen.add(fn)
            continue

        if fn.endswith(".txt"):
            stem = fn[: -len(".txt")]
            active_fn = stem + "_active.txt"
            active_fp = os.path.join(folder, active_fn) if active_fn in set(all_files) else None
            kind = "paired" if active_fp and os.path.isfile(active_fp) else "txt"
            entries.append(PromptFileEntry(
                name=fn,
                base_path=fp,
                active_path=active_fp,
                kind=kind,
                category=cat_key,
            ))
            seen.add(fn)
            if active_fn in set(all_files):
                seen.add(active_fn)
            continue

    return entries


# ===========================================================================
# Campaign discovery
# ===========================================================================

def discover_campaigns(save_data_path: str) -> list[str]:
    """
    Return sorted list of campaign IDs (subfolder names) found under
    save_data_path. A valid campaign folder must contain a prompts/ subfolder
    OR at least look like a campaign directory (non-hidden folder).
    """
    if not save_data_path or not os.path.isdir(save_data_path):
        return []
    campaigns = []
    try:
        for entry in sorted(os.listdir(save_data_path)):
            if entry.startswith("."):
                continue
            full = os.path.join(save_data_path, entry)
            if os.path.isdir(full):
                campaigns.append(entry)
    except OSError:
        pass
    return campaigns


# ===========================================================================
# Shared widget helpers (no ttk)
# ===========================================================================

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


# ===========================================================================
# CustomTitleBar  (section variant)
# ===========================================================================

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

        tk.Frame(self, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y,
                                                     padx=(0, 8), pady=6)
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
        FlatButton(btns, text="\u2715",
                   command=lambda: self.root.event_generate("WM_DELETE_WINDOW"),
                   bg=C["bg"], hover_bg=C["red"], hover_fg="#fff",
                   padx=14).pack(side=tk.LEFT, fill=tk.Y)

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


# ===========================================================================
# VirtualList — Canvas-based virtualised file list for Panel 2
# ===========================================================================

ROW_H = 38          # pixel height per row
ROW_PAD_X = 10     # left padding

TYPE_COLORS = {
    "TXT":    C["fg_dim"],
    "PAIRED": C["accent2"],
    "JSON":   C["accent3"],
}


class VirtualFileList(tk.Frame):
    """
    Canvas-based virtual list for PromptFileEntry rows.
    Only renders rows within the visible viewport.
    Supports select callback, search filtering, and external data reload.
    """

    def __init__(self, parent, on_select=None, **kw):
        super().__init__(parent, bg=C["surface"], **kw)
        self._on_select = on_select
        self._entries: list[PromptFileEntry] = []
        self._filtered: list[PromptFileEntry] = []
        self._selected_idx: Optional[int] = None
        self._hover_idx: Optional[int] = None

        self._canvas = tk.Canvas(self, bg=C["surface"], highlightthickness=0, bd=0)
        self._sb = tk.Scrollbar(self, orient="vertical",
                                command=self._canvas.yview,
                                bg=C["scrollbar"], troughcolor=C["bg"],
                                width=6, bd=0, relief="flat")
        self._canvas.configure(yscrollcommand=self._sb.set)
        self._sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._canvas.bind("<Configure>", self._on_resize)
        self._canvas.bind("<MouseWheel>", self._on_wheel)
        self._canvas.bind("<Button-4>", lambda e: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind("<Button-5>", lambda e: self._canvas.yview_scroll(1, "units"))
        self._canvas.bind("<Motion>", self._on_mouse_motion)
        self._canvas.bind("<Leave>", self._on_mouse_leave)
        self._canvas.bind("<Button-1>", self._on_click)

        self._canvas_width = 240

    # ---- public API ----

    def load(self, entries: list[PromptFileEntry], search_term: str = "") -> None:
        self._entries = entries
        self._apply_filter(search_term)

    def filter(self, search_term: str) -> None:
        self._apply_filter(search_term)

    def clear_selection(self) -> None:
        self._selected_idx = None
        self._redraw()

    def selected_entry(self) -> Optional[PromptFileEntry]:
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._filtered):
            return self._filtered[self._selected_idx]
        return None

    # ---- internal ----

    def _apply_filter(self, term: str) -> None:
        t = term.strip().lower()
        if t:
            self._filtered = [e for e in self._entries if t in e.name.lower()]
        else:
            self._filtered = list(self._entries)
        self._selected_idx = None
        self._hover_idx = None
        self._update_scroll_region()
        self._redraw()

    def _update_scroll_region(self) -> None:
        total_h = len(self._filtered) * ROW_H
        self._canvas.configure(scrollregion=(0, 0, self._canvas_width, total_h))

    def _on_resize(self, event) -> None:
        self._canvas_width = event.width
        self._update_scroll_region()
        self._redraw()

    def _on_wheel(self, event) -> None:
        delta = -1 if event.delta > 0 else 1
        self._canvas.yview_scroll(delta, "units")

    def _visible_range(self) -> tuple[int, int]:
        """Return (first_idx, last_idx) of rows in viewport."""
        top = self._canvas.canvasy(0)
        bottom = top + self._canvas.winfo_height()
        first = max(0, int(top // ROW_H))
        last = min(len(self._filtered), int(bottom // ROW_H) + 2)
        return first, last

    def _redraw(self) -> None:
        self._canvas.delete("all")
        if not self._filtered:
            self._canvas.create_text(
                self._canvas_width // 2, 40,
                text="No files", fill=C["fg_muted"],
                font=("Segoe UI", 9), anchor="center"
            )
            return

        first, last = self._visible_range()
        for i in range(first, last):
            self._draw_row(i)

    def _draw_row(self, idx: int) -> None:
        if idx >= len(self._filtered):
            return
        entry = self._filtered[idx]
        y0 = idx * ROW_H
        y1 = y0 + ROW_H
        w = self._canvas_width

        # background
        if idx == self._selected_idx:
            bg = C["surface3"]
            border_color = C["accent2"]
        elif idx == self._hover_idx:
            bg = C["surface2"]
            border_color = C["border"]
        else:
            bg = C["surface"]
            border_color = None

        self._canvas.create_rectangle(0, y0, w, y1, fill=bg, outline="")
        if idx == self._selected_idx:
            self._canvas.create_rectangle(0, y0, 3, y1, fill=C["accent2"], outline="")
        if border_color:
            self._canvas.create_line(0, y1 - 1, w, y1 - 1, fill=C["border"])

        # type badge
        tag_text = entry.type_tag
        tag_color = TYPE_COLORS.get(tag_text, C["fg_muted"])
        self._canvas.create_text(
            ROW_PAD_X, y0 + ROW_H // 2,
            text=tag_text, fill=tag_color,
            font=("Segoe UI", 7, "bold"), anchor="w"
        )

        # file name
        name_x = ROW_PAD_X + 46
        fg = C["fg"] if idx == self._selected_idx else C["fg_dim"]
        self._canvas.create_text(
            name_x, y0 + ROW_H // 2 - 5,
            text=entry.display_name, fill=fg,
            font=("Segoe UI", 9), anchor="w"
        )

        # active indicator
        if entry.has_active:
            self._canvas.create_text(
                name_x, y0 + ROW_H // 2 + 8,
                text="\u25cf active variant", fill=C["green"],
                font=("Segoe UI", 7), anchor="w"
            )

    def _row_at_y(self, canvas_y: float) -> Optional[int]:
        idx = int(canvas_y // ROW_H)
        if 0 <= idx < len(self._filtered):
            return idx
        return None

    def _on_mouse_motion(self, event) -> None:
        cy = self._canvas.canvasy(event.y)
        new_hover = self._row_at_y(cy)
        if new_hover != self._hover_idx:
            old, self._hover_idx = self._hover_idx, new_hover
            if old is not None:
                self._draw_row(old)
            if new_hover is not None:
                self._draw_row(new_hover)

    def _on_mouse_leave(self, event=None) -> None:
        old, self._hover_idx = self._hover_idx, None
        if old is not None:
            self._draw_row(old)

    def _on_click(self, event) -> None:
        cy = self._canvas.canvasy(event.y)
        idx = self._row_at_y(cy)
        if idx is None:
            return
        old, self._selected_idx = self._selected_idx, idx
        if old is not None:
            self._draw_row(old)
        self._draw_row(idx)
        if self._on_select:
            self._on_select(self._filtered[idx])


# ===========================================================================
# CategoryTree — Panel 1 lower section
# ===========================================================================

class CategoryTree(tk.Frame):
    """
    Static list of prompt categories with file-count badges.
    Calls on_select(category_key) when a node is clicked.
    """

    def __init__(self, parent, on_select=None, **kw):
        super().__init__(parent, bg=C["surface"], **kw)
        self._on_select = on_select
        self._active_key: Optional[str] = None
        self._rows: dict[str, dict] = {}  # key -> {frame, name_lbl, badge_lbl}
        self._build()

    def _build(self) -> None:
        # scrollable inner
        canvas = tk.Canvas(self, bg=C["surface"], highlightthickness=0, bd=0)
        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview,
                          bg=C["scrollbar"], troughcolor=C["bg"], width=5, bd=0)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=C["surface"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        # root-level pseudo-category
        self._add_row(inner, "__root__", "Root Files")

        # category rows
        for cat_key in PROMPT_CATEGORIES:
            label = cat_key.replace("_", " ").title()
            self._add_row(inner, cat_key, label)

    def _add_row(self, parent, key: str, label: str) -> None:
        icon = CATEGORY_ICONS.get(key, "\u25b8")
        row = tk.Frame(parent, bg=C["surface"], cursor="hand2", height=30)
        row.pack(fill=tk.X)
        row.pack_propagate(False)

        indicator = tk.Frame(row, bg=C["surface"], width=3)
        indicator.pack(side=tk.LEFT, fill=tk.Y)

        icon_lbl = tk.Label(row, text=icon, bg=C["surface"], fg=C["fg_muted"],
                            font=("Segoe UI", 9))
        icon_lbl.pack(side=tk.LEFT, padx=(6, 2), pady=4)

        name_lbl = tk.Label(row, text=label, bg=C["surface"], fg=C["fg_dim"],
                            font=("Segoe UI", 9), anchor="w")
        name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        badge = tk.Label(row, text="", bg=C["surface"], fg=C["fg_muted"],
                         font=("Segoe UI", 8), padx=6)
        badge.pack(side=tk.RIGHT, padx=(0, 6))

        self._rows[key] = {
            "frame": row,
            "indicator": indicator,
            "icon_lbl": icon_lbl,
            "name_lbl": name_lbl,
            "badge": badge,
        }

        for w in (row, indicator, icon_lbl, name_lbl, badge):
            w.bind("<Enter>", lambda e, k=key: self._hover_on(k))
            w.bind("<Leave>", lambda e, k=key: self._hover_off(k))
            w.bind("<Button-1>", lambda e, k=key: self._click(k))

    def set_counts(self, counts: dict[str, int]) -> None:
        """Update badge text for each category key."""
        for key, widgets in self._rows.items():
            n = counts.get(key, 0)
            widgets["badge"].config(text=str(n) if n else "")

    def set_active(self, key: Optional[str]) -> None:
        if self._active_key and self._active_key in self._rows:
            self._deactivate(self._active_key)
        self._active_key = key
        if key and key in self._rows:
            self._activate(key)

    def _activate(self, key: str) -> None:
        w = self._rows[key]
        w["frame"].config(bg=C["surface3"])
        w["indicator"].config(bg=C["accent2"])
        w["icon_lbl"].config(bg=C["surface3"], fg=C["accent2"])
        w["name_lbl"].config(bg=C["surface3"], fg=C["fg"])
        w["badge"].config(bg=C["surface3"])

    def _deactivate(self, key: str) -> None:
        w = self._rows[key]
        w["frame"].config(bg=C["surface"])
        w["indicator"].config(bg=C["surface"])
        w["icon_lbl"].config(bg=C["surface"], fg=C["fg_muted"])
        w["name_lbl"].config(bg=C["surface"], fg=C["fg_dim"])
        w["badge"].config(bg=C["surface"])

    def _hover_on(self, key: str) -> None:
        if key == self._active_key:
            return
        w = self._rows[key]
        for widget in (w["frame"], w["icon_lbl"], w["name_lbl"], w["badge"]):
            widget.config(bg=C["surface2"])

    def _hover_off(self, key: str) -> None:
        if key == self._active_key:
            return
        w = self._rows[key]
        for widget in (w["frame"], w["icon_lbl"], w["name_lbl"], w["badge"]):
            widget.config(bg=C["surface"])

    def _click(self, key: str) -> None:
        self.set_active(key)
        if self._on_select:
            self._on_select(key)


# ===========================================================================
# Panel 3 — Info placeholder (Part 2 will replace)
# ===========================================================================

class InfoPlaceholder(tk.Frame):
    """
    Right panel placeholder shown until an editor is implemented in Part 2.
    Displays selected file name, path, type, and active-variant status.
    """

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self._build()

    def _build(self) -> None:
        center = tk.Frame(self, bg=C["bg"])
        center.place(relx=0.5, rely=0.5, anchor="center")

        self._icon = tk.Label(center, text="\u229e", bg=C["bg"], fg=C["surface3"],
                              font=("Segoe UI", 48))
        self._icon.pack(pady=(0, 12))

        self._title = tk.Label(center, text="No file selected",
                               bg=C["bg"], fg=C["fg_dim"],
                               font=("Segoe UI", 13, "bold"))
        self._title.pack()

        self._sub = tk.Label(center, text="Select a category and file to preview it here",
                             bg=C["bg"], fg=C["fg_muted"],
                             font=("Segoe UI", 9))
        self._sub.pack(pady=(4, 0))

        # detail fields
        details = tk.Frame(center, bg=C["bg"])
        details.pack(pady=(20, 0))

        self._fields: dict[str, tk.Label] = {}
        for key in ("Type", "Category", "Path", "Active variant"):
            row = tk.Frame(details, bg=C["bg"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"{key}:", bg=C["bg"], fg=C["fg_muted"],
                     font=("Segoe UI", 8), width=12, anchor="e").pack(side=tk.LEFT, padx=(0, 8))
            val = tk.Label(row, text="—", bg=C["bg"], fg=C["fg_dim"],
                           font=("Segoe UI", 8), anchor="w")
            val.pack(side=tk.LEFT)
            self._fields[key] = val

    def show_entry(self, entry: Optional[PromptFileEntry]) -> None:
        if entry is None:
            self._title.config(text="No file selected")
            self._sub.config(text="Select a category and file to preview it here")
            for v in self._fields.values():
                v.config(text="—")
            return

        self._title.config(text=entry.display_name)
        self._sub.config(text="")
        self._fields["Type"].config(text=entry.type_tag)
        self._fields["Category"].config(text=entry.category)
        self._fields["Path"].config(text=_truncate_path(entry.base_path, 50))
        self._fields["Active variant"].config(
            text=os.path.basename(entry.active_path) if entry.active_path else "None"
        )


def _truncate_path(path: str, max_len: int) -> str:
    if len(path) <= max_len:
        return path
    return "\u2026" + path[-(max_len - 1):]


# ===========================================================================
# PromptManagementApp
# ===========================================================================

class PromptManagementApp:
    """Main class for the Prompt Management section. Launched from main.py hub."""

    # --- window config ---
    WIN_W = 1280
    WIN_H = 820
    MIN_W = 900
    MIN_H = 600
    PANEL1_W = 220
    PANEL2_W = 260

    def __init__(self, root: tk.Toplevel, on_close=None):
        self.root = root
        self.on_close = on_close

        # settings
        self.sm = SettingsManager()

        # state
        self._campaigns: list[str] = []
        self._current_campaign: Optional[str] = None
        self._prompt_index: Optional[PromptIndex] = None
        self._active_category: Optional[str] = None
        self._selected_entry: Optional[PromptFileEntry] = None

        # window setup
        root.title("Prompt Management")
        root.overrideredirect(True)
        root.geometry(f"{self.WIN_W}x{self.WIN_H}")
        root.minsize(self.MIN_W, self.MIN_H)
        root.configure(bg=C["border"])
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(
            f"{self.WIN_W}x{self.WIN_H}"
            f"+{(sw - self.WIN_W) // 2}+{(sh - self.WIN_H) // 2}"
        )
        root.protocol("WM_DELETE_WINDOW", self._on_destroy)

        self._frame = tk.Frame(root, bg=C["bg"],
                               highlightbackground=C["border"], highlightthickness=1)
        self._frame.pack(fill=tk.BOTH, expand=True)

        self._build_ui()
        self._init_data()

    # ===========================================================================
    # Hub integration
    # ===========================================================================

    def back_to_hub(self) -> None:
        self._on_destroy()

    def _on_destroy(self) -> None:
        self.root.destroy()
        if self.on_close:
            self.on_close()

    # ===========================================================================
    # Data init
    # ===========================================================================

    def _init_data(self) -> None:
        """Load settings, discover campaigns, restore last selection."""
        save_path = self.sm.save_data_path()
        self._campaigns = discover_campaigns(save_path)

        # populate campaign dropdown
        names = self._campaigns if self._campaigns else ["(no campaigns found)"]
        self._campaign_var.set("")
        menu = self._campaign_menu["menu"]
        menu.delete(0, "end")
        for name in names:
            menu.add_command(label=name,
                             command=lambda n=name: self._on_campaign_selected(n))

        # restore last
        last = self.sm.last_campaign()
        if last and last in self._campaigns:
            self._campaign_var.set(last)
            self._load_campaign(last)
        elif self._campaigns:
            first = self._campaigns[0]
            self._campaign_var.set(first)
            self._load_campaign(first)
        else:
            self._campaign_var.set(names[0])
            self.status.set("No campaigns found — set save_data path in Settings", "warn")

    def _on_campaign_selected(self, campaign_id: str) -> None:
        if campaign_id not in self._campaigns:
            return
        self._campaign_var.set(campaign_id)
        self._load_campaign(campaign_id)
        self.sm.set_last_campaign(campaign_id)
        self.sm.save()

    def _load_campaign(self, campaign_id: str) -> None:
        self._current_campaign = campaign_id
        self._prompt_index = PromptIndex()
        save_path = self.sm.save_data_path()
        ok = self._prompt_index.scan(save_path, campaign_id)
        if not ok:
            self.status.set(f"prompts/ folder not found for campaign: {campaign_id}", "warn")
        else:
            total = self._prompt_index.total_files()
            self.status.set(
                f"Campaign loaded: {campaign_id}  \u2014  {total} prompt files", "ok"
            )
        self._refresh_category_badges()
        # reset panel 2 + 3
        self._active_category = None
        self._selected_entry = None
        self._cat_tree.set_active(None)
        self._file_list.load([])
        self._info_panel.show_entry(None)
        self._panel2_header.config(text="Select a category")

    def _refresh_category_badges(self) -> None:
        if self._prompt_index is None:
            return
        counts: dict[str, int] = {}
        for cat_key, cm in self._prompt_index.categories.items():
            counts[cat_key] = cm.count
        counts["__root__"] = len(self._prompt_index.root_entries)
        self._cat_tree.set_counts(counts)

    # ===========================================================================
    # UI construction
    # ===========================================================================

    def _build_ui(self) -> None:
        bar = CustomTitleBar(self._frame, self, "Prompt Management")
        bar.pack(fill=tk.X)

        body = tk.Frame(self._frame, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        self._build_panel1(body)
        self._build_panel2(body)
        self._build_panel3(body)

        self.status = StatusBar(self._frame)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

    # ---------------------------------------------------------------------------
    # Panel 1 — sidebar: campaign picker + category tree
    # ---------------------------------------------------------------------------

    def _build_panel1(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=C["surface"], width=self.PANEL1_W)
        panel.pack(side=tk.LEFT, fill=tk.Y)
        panel.pack_propagate(False)

        # header
        hdr = tk.Frame(panel, bg=C["surface"], height=48)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="\u229e Prompts", bg=C["surface"], fg=C["accent2"],
                 font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=14, pady=12)

        tk.Frame(panel, bg=C["border"], height=1).pack(fill=tk.X)

        # campaign dropdown
        camp_frame = tk.Frame(panel, bg=C["surface"], pady=8)
        camp_frame.pack(fill=tk.X, padx=10)
        tk.Label(camp_frame, text="CAMPAIGN", bg=C["surface"], fg=C["fg_muted"],
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(0, 4))

        self._campaign_var = tk.StringVar()
        # plain tk OptionMenu styled to match
        self._campaign_menu = tk.OptionMenu(camp_frame, self._campaign_var, "")
        self._campaign_menu.config(
            bg=C["surface2"], fg=C["fg"], activebackground=C["surface3"],
            activeforeground=C["fg"], relief="flat", borderwidth=0,
            highlightthickness=1, highlightbackground=C["border"],
            font=("Segoe UI", 9), indicatoron=True, cursor="hand2"
        )
        self._campaign_menu["menu"].config(
            bg=C["surface2"], fg=C["fg"],
            activebackground=C["accent"], activeforeground="#fff",
            borderwidth=0, font=("Segoe UI", 9)
        )
        self._campaign_menu.pack(fill=tk.X)

        FlatButton(camp_frame, text="\u21ba Refresh",
                   command=self._refresh_campaigns,
                   bg=C["surface"], fg=C["fg_muted"],
                   hover_bg=C["surface2"], hover_fg=C["accent2"],
                   font=("Segoe UI", 8), padx=4, pady=3).pack(anchor="e", pady=(4, 0))

        tk.Frame(panel, bg=C["border"], height=1).pack(fill=tk.X, padx=6, pady=4)

        # category tree header
        tk.Label(panel, text="CATEGORIES", bg=C["surface"], fg=C["fg_muted"],
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=14, pady=(4, 2))

        # category tree (fills rest of panel)
        self._cat_tree = CategoryTree(panel, on_select=self._on_category_selected)
        self._cat_tree.pack(fill=tk.BOTH, expand=True)

    # ---------------------------------------------------------------------------
    # Panel 2 — file list with search
    # ---------------------------------------------------------------------------

    def _build_panel2(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=C["surface2"], width=self.PANEL2_W)
        panel.pack(side=tk.LEFT, fill=tk.Y)
        panel.pack_propagate(False)

        # thin left border
        tk.Frame(panel, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        inner = tk.Frame(panel, bg=C["surface2"])
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # header
        hdr = tk.Frame(inner, bg=C["surface2"], height=40)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        self._panel2_header = tk.Label(
            hdr, text="Select a category",
            bg=C["surface2"], fg=C["fg_dim"],
            font=("Segoe UI", 9, "bold"), anchor="w"
        )
        self._panel2_header.pack(side=tk.LEFT, padx=12, pady=10)
        self._panel2_count = tk.Label(
            hdr, text="",
            bg=C["surface2"], fg=C["accent2"],
            font=("Segoe UI", 8)
        )
        self._panel2_count.pack(side=tk.RIGHT, padx=10)

        tk.Frame(inner, bg=C["border"], height=1).pack(fill=tk.X)

        # search bar
        search_row = tk.Frame(inner, bg=C["surface2"], pady=6)
        search_row.pack(fill=tk.X, padx=8)
        tk.Label(search_row, text="\u2315", bg=C["surface2"], fg=C["fg_muted"],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        search_entry = tk.Entry(
            search_row, textvariable=self._search_var,
            bg=C["surface3"], fg=C["fg"],
            insertbackground=C["accent"],
            selectbackground=C["accent"], selectforeground="#fff",
            relief="flat", borderwidth=0,
            highlightthickness=1, highlightbackground=C["border"],
            highlightcolor=C["accent2"],
            font=("Segoe UI", 9)
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Frame(inner, bg=C["border"], height=1).pack(fill=tk.X)

        # virtual file list
        self._file_list = VirtualFileList(inner, on_select=self._on_file_selected)
        self._file_list.pack(fill=tk.BOTH, expand=True)

    # ---------------------------------------------------------------------------
    # Panel 3 — placeholder info
    # ---------------------------------------------------------------------------

    def _build_panel3(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=C["bg"])
        panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # thin left border
        tk.Frame(panel, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        inner = tk.Frame(panel, bg=C["bg"])
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._info_panel = InfoPlaceholder(inner)
        self._info_panel.pack(fill=tk.BOTH, expand=True)

    # ===========================================================================
    # Event handlers
    # ===========================================================================

    def _on_category_selected(self, cat_key: str) -> None:
        self._active_category = cat_key
        if self._prompt_index is None:
            return
        entries = self._prompt_index.entries_for_category(cat_key)
        self._file_list.load(entries, self._search_var.get())

        # update panel 2 header
        if cat_key == "__root__":
            label = "Root Files"
        else:
            label = cat_key.replace("_", " ").title()
        self._panel2_header.config(text=label)
        self._panel2_count.config(text=str(len(entries)))

        # reset panel 3
        self._selected_entry = None
        self._info_panel.show_entry(None)
        self.status.set(f"Category: {label}  \u2014  {len(entries)} files", "info")

    def _on_file_selected(self, entry: PromptFileEntry) -> None:
        self._selected_entry = entry
        self._info_panel.show_entry(entry)
        self.status.set(
            f"{entry.display_name}  \u2014  {entry.type_tag}  \u2014  {entry.base_path}",
            "info"
        )

    def _on_search_changed(self, *_) -> None:
        self._file_list.filter(self._search_var.get())

    def _refresh_campaigns(self) -> None:
        self._init_data()
        self.status.set("Campaigns refreshed", "ok")


# ===========================================================================
# Standalone entry point
# ===========================================================================

def main():
    root = tk.Tk()
    root.withdraw()
    app = PromptManagementApp(root)
    root.update_idletasks()
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
