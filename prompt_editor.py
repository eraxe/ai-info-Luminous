#!/usr/bin/env python3
"""
Luminous AI — Prompt Editor
PromptEditor: full-featured editor widget for the right panel of
PromptManagementApp.  Handles text/JSON prompt files with save,
backup, reset, active-file toggle, and live dirty-state tracking.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
import tkinter.messagebox as mb
import tkinter.ttk as ttk

from colors import C
from widgets import FlatButton, AccentButton
from prompt_index import PromptFileEntry


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _iso_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _backup_path(file_path: Path) -> Path:
    """Return a timestamped backup path adjacent to *file_path*."""
    backups_dir = file_path.parent / ".backups"
    backups_dir.mkdir(exist_ok=True)
    return backups_dir / f"{file_path.stem}_{_iso_stamp()}{file_path.suffix}.bak"


# ─────────────────────────────────────────────────────────────────────────────
# LineNumbers  (canvas that tracks the Text widget's line count)
# ─────────────────────────────────────────────────────────────────────────────

class _LineNumbers(tk.Canvas):
    """Minimal gutter widget that draws line numbers beside a Text widget."""

    _PAD_H = 4
    _PAD_W = 8
    _WIDTH  = 40

    def __init__(self, parent: tk.Widget, text_widget: tk.Text, **kw) -> None:
        kw.setdefault("bg",    C["surface2"])
        kw.setdefault("bd",    0)
        kw.setdefault("width", self._WIDTH)
        super().__init__(parent, **kw)
        self._text = text_widget
        self._redraw()

    # ------------------------------------------------------------------

    def attach(self) -> None:
        """Wire the gutter to redraw whenever the Text widget scrolls / changes."""
        self._text.bind("<<Change>>",    self._on_change)
        self._text.bind("<Configure>",   self._on_change)
        self._text.bind("<KeyRelease>",  self._on_change)
        self._text.bind("<ButtonRelease>", self._on_change)

    def _on_change(self, _=None) -> None:
        self._redraw()

    def _redraw(self, _=None) -> None:
        self.delete("all")
        i = self._text.index("@0,0")
        while True:
            dline = self._text.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(
                self._WIDTH - self._PAD_W, y + self._PAD_H,
                anchor="ne",
                text=linenum,
                fill=C["fg_muted"],
                font=("Consolas", 9),
            )
            i = self._text.index(f"{i}+1line")
            if self._text.compare(i, ">=", "end"):
                break


# ─────────────────────────────────────────────────────────────────────────────
# JSON Form View
# ─────────────────────────────────────────────────────────────────────────────

class _JsonFormView(tk.Frame):
    """Editable key/value grid for flat JSON objects.

    For simple ``{"key": "value", …}`` structures only; nested objects
    fall back to raw text display and a warning.
    """

    _CELL_BG  = C["surface3"]
    _CELL_FG  = C["fg"]
    _LABEL_FG = C["fg_muted"]

    def __init__(self, parent: tk.Widget, on_change: Callable[[], None], **kw) -> None:
        kw.setdefault("bg", C["surface"])
        super().__init__(parent, **kw)
        self._on_change  = on_change
        self._entries: list[tuple[str, tk.Entry, tk.Entry]] = []  # (key, key_w, val_w)
        self._readonly   = False
        self._warn_label: Optional[tk.Label] = None

        self._canvas  = tk.Canvas(self, bg=C["surface"], bd=0, highlightthickness=0)
        self._scroll  = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scroll.set)
        self._inner   = tk.Frame(self._canvas, bg=C["surface"])
        self._window  = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # ── public ────────────────────────────────────────────────────────────────

    def load(self, data: dict, readonly: bool = False) -> None:
        """Populate the form from *data*."""
        self._readonly = readonly
        self._clear()
        if any(not isinstance(v, (str, int, float, bool, type(None))) for v in data.values()):
            self._show_warning("Nested JSON detected — use Raw editor for full control.")
            return
        for row_idx, (k, v) in enumerate(data.items()):
            self._add_row(row_idx, k, "" if v is None else str(v))

    def collect(self) -> dict:
        """Return the current form values as a dict."""
        result: dict = {}
        for key, _k_entry, v_entry in self._entries:
            result[key] = v_entry.get()
        return result

    def set_readonly(self, readonly: bool) -> None:
        self._readonly = readonly
        state = "disabled" if readonly else "normal"
        for _, _k_entry, v_entry in self._entries:
            v_entry.config(state=state)

    # ── internals ─────────────────────────────────────────────────────────────

    def _clear(self) -> None:
        for w in self._inner.winfo_children():
            w.destroy()
        self._entries.clear()
        if self._warn_label:
            self._warn_label = None

    def _add_row(self, row: int, key: str, value: str) -> None:
        key_lbl = tk.Label(
            self._inner, text=key, bg=C["surface"], fg=self._LABEL_FG,
            font=("Segoe UI", 9), anchor="e", width=22,
        )
        key_lbl.grid(row=row, column=0, sticky="e", padx=(8, 4), pady=3)

        val_var = tk.StringVar(value=value)
        val_entry = tk.Entry(
            self._inner,
            textvariable=val_var,
            bg=self._CELL_BG,
            fg=self._CELL_FG,
            insertbackground=C["accent"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=C["border"],
            highlightcolor=C["accent"],
            font=("Segoe UI", 9),
            state="disabled" if self._readonly else "normal",
        )
        val_entry.grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=3)
        val_var.trace_add("write", lambda *_: self._on_change())
        self._entries.append((key, key_lbl, val_entry))
        self._inner.columnconfigure(1, weight=1)

    def _show_warning(self, msg: str) -> None:
        self._warn_label = tk.Label(
            self._inner, text=f"⚠  {msg}",
            bg=C["surface"], fg=C["accent3"],
            font=("Segoe UI", 9), wraplength=320, justify="left",
        )
        self._warn_label.grid(row=0, column=0, columnspan=2, padx=12, pady=16, sticky="w")

    def _on_inner_configure(self, _=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e=None) -> None:
        if e:
            self._canvas.itemconfig(self._window, width=e.width)


# ─────────────────────────────────────────────────────────────────────────────
# PromptEditor
# ─────────────────────────────────────────────────────────────────────────────

class PromptEditor(tk.Frame):
    """Three-tab editor panel for a single prompt file.

    Tabs
    ----
    Raw   — syntax-highlighted (minimal) plain-text / JSON editor with
            line numbers, word-wrap toggle, and find bar.
    Form  — key/value grid for flat JSON files.
    Info  — read-only metadata (path, size, last-modified, extension).

    External interface
    ------------------
    ``load(entry)``     — load a PromptFileEntry.
    ``clear()``         — reset to empty/placeholder state.
    ``has_unsaved``     — True when the buffer differs from disk.
    ``save()``          — write changes to disk (creates backup first).
    ``reset()``         — discard edits; reload from disk.
    """

    _FONT_MONO = ("Consolas", 10)
    _FONT_UI   = ("Segoe UI", 9)

    def __init__(
        self,
        parent: tk.Widget,
        get_readonly:    Callable[[], bool]           = lambda: False,
        get_prompts_root: Callable[[], Optional[Path]] = lambda: None,
        on_status:       Callable[[str, str], None]   = lambda m, l="ok": None,
        **kw,
    ) -> None:
        kw.setdefault("bg", C["bg"])
        super().__init__(parent, **kw)

        self._get_readonly    = get_readonly
        self._get_prompts_root = get_prompts_root
        self._on_status       = on_status

        self._entry:       Optional[PromptFileEntry] = None
        self._disk_text:   str = ""          # snapshot from disk
        self._is_active:   bool = False       # "active file" toggle state

        self._build()

    # ── public ────────────────────────────────────────────────────────────────

    @property
    def has_unsaved(self) -> bool:
        """True when the editor buffer differs from the last-saved snapshot."""
        return self._get_raw_text() != self._disk_text

    def load(self, entry: PromptFileEntry) -> None:
        """Load *entry* into the editor."""
        self._entry     = entry
        self._disk_text = entry.read_text()
        self._is_active = self._detect_active_state(entry)

        self._set_raw_text(self._disk_text)
        self._refresh_info_tab(entry)
        if entry.is_json:
            self._load_form_tab(self._disk_text)
        else:
            self._clear_form_tab()

        self._active_toggle.config(
            text=self._active_label(),
            fg=C["accent2"] if self._is_active else C["fg_muted"],
        )
        self._update_dirty_indicator()
        self._update_header(entry)
        self._on_status(f"Loaded: {entry.rel_path}", "ok")

    def clear(self) -> None:
        """Reset to an empty placeholder state."""
        self._entry     = None
        self._disk_text = ""
        self._set_raw_text("")
        self._clear_form_tab()
        self._clear_info_tab()
        self._header_label.config(text="No file selected", fg=C["fg_muted"])
        self._path_label.config(text="")
        self._dirty_label.config(text="", fg=C["fg_muted"])
        self._active_toggle.config(text="○ inactive", fg=C["fg_muted"])

    def save(self) -> bool:
        """Write the current buffer to disk.  Returns True on success."""
        if self._entry is None:
            return False
        if self._get_readonly():
            self._on_status("Read-only — cannot save", "warn")
            return False

        text = self._get_raw_text()
        # If JSON form tab is active and clean, collect from form instead
        if self._entry.is_json and self._tabs.tab(self._tabs.select(), "text").startswith("Form"):
            try:
                data = self._form_view.collect()
                text = json.dumps(data, indent=2, ensure_ascii=False)
            except Exception as exc:
                self._on_status(f"Form collect error: {exc}", "error")
                return False

        # Validate JSON before writing
        if self._entry.is_json:
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                if not mb.askyesno(
                    "Invalid JSON",
                    f"The content is not valid JSON:\n\n{exc}\n\nSave anyway?",
                ):
                    return False

        # Backup
        try:
            if self._entry.path.exists():
                shutil.copy2(self._entry.path, _backup_path(self._entry.path))
        except Exception as exc:
            self._on_status(f"Backup failed: {exc}", "warn")

        # Write
        try:
            self._entry.path.write_text(text, encoding="utf-8")
            self._disk_text = text
            self._update_dirty_indicator()
            self._on_status(f"Saved: {self._entry.rel_path}", "ok")
            return True
        except Exception as exc:
            self._on_status(f"Save error: {exc}", "error")
            return False

    def reset(self) -> None:
        """Discard edits and reload from disk."""
        if self._entry is None:
            return
        if self.has_unsaved:
            if not mb.askyesno("Discard changes?",
                               "Unsaved changes will be lost.  Continue?"):
                return
        self.load(self._entry)
        self._on_status("Reset to saved version", "ok")

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── header bar ────────────────────────────────────────────────────
        header = tk.Frame(self, bg=C["surface"], height=40)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        self._build_header_bar(header)

        # ── action bar ────────────────────────────────────────────────────
        action_bar = tk.Frame(self, bg=C["surface2"], height=32)
        action_bar.pack(fill=tk.X, side=tk.TOP)
        action_bar.pack_propagate(False)
        self._build_action_bar(action_bar)

        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        # ── tab notebook ──────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Editor.TNotebook",
            background=C["bg"],
            borderwidth=0,
        )
        style.configure(
            "Editor.TNotebook.Tab",
            background=C["surface"],
            foreground=C["fg_muted"],
            padding=[10, 4],
            font=("Segoe UI", 8),
        )
        style.map(
            "Editor.TNotebook.Tab",
            background=[("selected", C["surface2"])],
            foreground=[("selected", C["fg"])],
        )
        self._tabs = ttk.Notebook(self, style="Editor.TNotebook")
        self._tabs.pack(fill=tk.BOTH, expand=True)

        self._build_raw_tab()
        self._build_form_tab()
        self._build_info_tab()

    def _build_header_bar(self, bar: tk.Frame) -> None:
        left = tk.Frame(bar, bg=C["surface"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=6)

        self._header_label = tk.Label(
            left, text="No file selected", bg=C["surface"], fg=C["fg_muted"],
            font=("Segoe UI", 10, "bold"), anchor="w",
        )
        self._header_label.pack(anchor="w")

        self._path_label = tk.Label(
            left, text="", bg=C["surface"], fg=C["fg_muted"],
            font=("Segoe UI", 8), anchor="w",
        )
        self._path_label.pack(anchor="w")

        right = tk.Frame(bar, bg=C["surface"])
        right.pack(side=tk.RIGHT, padx=12, pady=6)

        self._dirty_label = tk.Label(
            right, text="", bg=C["surface"], fg=C["fg_muted"],
            font=("Segoe UI", 8),
        )
        self._dirty_label.pack(side=tk.LEFT, padx=(0, 12))

        self._active_toggle = FlatButton(
            right,
            text="○ inactive",
            command=self._toggle_active,
            bg=C["surface"],
            fg=C["fg_muted"],
            hover_fg=C["accent2"],
            font=("Segoe UI", 8),
            padx=8, pady=2,
        )
        self._active_toggle.pack(side=tk.LEFT)

    def _build_action_bar(self, bar: tk.Frame) -> None:
        AccentButton(
            bar, text="💾 Save", command=self.save,
            accent="blue",
            font=("Segoe UI", 8, "bold"), padx=12, pady=4,
        ).pack(side=tk.LEFT, padx=(8, 0), pady=4)

        FlatButton(
            bar, text="↺ Reset", command=self.reset,
            bg=C["surface2"], hover_bg=C["surface3"],
            fg=C["fg_muted"], hover_fg=C["accent3"],
            font=("Segoe UI", 8), padx=10, pady=4,
        ).pack(side=tk.LEFT, padx=4, pady=4)

        tk.Frame(bar, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, pady=6)

        # Word-wrap toggle
        self._wrap_var = tk.BooleanVar(value=True)
        FlatButton(
            bar, text="⇔ Wrap",
            command=self._toggle_wrap,
            bg=C["surface2"], hover_bg=C["surface3"],
            fg=C["fg_muted"], hover_fg=C["fg"],
            font=("Segoe UI", 8), padx=10, pady=4,
        ).pack(side=tk.LEFT, padx=4, pady=4)

        # Find toggle
        FlatButton(
            bar, text="⌕ Find",
            command=self._toggle_find_bar,
            bg=C["surface2"], hover_bg=C["surface3"],
            fg=C["fg_muted"], hover_fg=C["accent"],
            font=("Segoe UI", 8), padx=10, pady=4,
        ).pack(side=tk.LEFT, padx=4, pady=4)

        # Format JSON button (right-aligned)
        FlatButton(
            bar, text="{ } Format",
            command=self._format_json,
            bg=C["surface2"], hover_bg=C["surface3"],
            fg=C["fg_muted"], hover_fg=C["green"],
            font=("Segoe UI", 8), padx=10, pady=4,
        ).pack(side=tk.RIGHT, padx=8, pady=4)

    # ── Raw tab ───────────────────────────────────────────────────────────────

    def _build_raw_tab(self) -> None:
        frame = tk.Frame(self._tabs, bg=C["bg"])
        self._tabs.add(frame, text="Raw")

        # Find bar (hidden by default)
        self._find_bar = tk.Frame(frame, bg=C["surface2"])
        self._find_var  = tk.StringVar()
        self._find_var.trace_add("write", lambda *_: self._do_find())

        find_entry = tk.Entry(
            self._find_bar, textvariable=self._find_var,
            bg=C["surface3"], fg=C["fg"],
            insertbackground=C["accent"],
            relief="flat", borderwidth=0,
            highlightthickness=1,
            highlightbackground=C["border"],
            highlightcolor=C["accent"],
            font=self._FONT_MONO, width=24,
        )
        find_entry.pack(side=tk.LEFT, padx=8, pady=4, ipady=3)
        self._find_count = tk.Label(
            self._find_bar, text="", bg=C["surface2"], fg=C["fg_muted"],
            font=("Segoe UI", 8),
        )
        self._find_count.pack(side=tk.LEFT)
        FlatButton(
            self._find_bar, text="↑", command=lambda: self._find_navigate(-1),
            bg=C["surface2"], font=("Segoe UI", 9), padx=8, pady=2,
        ).pack(side=tk.LEFT)
        FlatButton(
            self._find_bar, text="↓", command=lambda: self._find_navigate(1),
            bg=C["surface2"], font=("Segoe UI", 9), padx=8, pady=2,
        ).pack(side=tk.LEFT)
        FlatButton(
            self._find_bar, text="✕", command=self._hide_find_bar,
            bg=C["surface2"], fg=C["fg_muted"], hover_fg=C["red"],
            font=("Segoe UI", 9), padx=8, pady=2,
        ).pack(side=tk.RIGHT, padx=4)
        # Not packed yet — shown on demand

        # Editor row: gutter + text + scrollbar
        editor_row = tk.Frame(frame, bg=C["bg"])
        editor_row.pack(fill=tk.BOTH, expand=True)

        self._raw_text = tk.Text(
            editor_row,
            bg=C["surface"],
            fg=C["fg"],
            insertbackground=C["accent"],
            selectbackground=C["accent"],
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            font=self._FONT_MONO,
            wrap="word",
            undo=True,
            autoseparators=True,
            maxundo=50,
            highlightthickness=0,
            padx=8, pady=6,
            spacing1=2,
        )

        self._gutter = _LineNumbers(editor_row, self._raw_text)
        self._gutter.pack(side=tk.LEFT, fill=tk.Y)
        self._gutter.attach()

        vscroll = tk.Scrollbar(editor_row, orient="vertical",
                               command=self._raw_text.yview)
        hscroll = tk.Scrollbar(frame, orient="horizontal",
                               command=self._raw_text.xview)
        self._raw_text.configure(
            yscrollcommand=vscroll.set,
            xscrollcommand=hscroll.set,
        )
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._raw_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hscroll.pack(fill=tk.X)

        # Dirty tracking
        self._raw_text.bind("<<Modified>>", self._on_text_modified)

        # Tab → 4 spaces
        self._raw_text.bind("<Tab>", self._on_tab_key)

    # ── Form tab ──────────────────────────────────────────────────────────────

    def _build_form_tab(self) -> None:
        frame = tk.Frame(self._tabs, bg=C["surface"])
        self._tabs.add(frame, text="Form")
        self._form_view = _JsonFormView(frame, on_change=self._update_dirty_indicator)
        self._form_view.pack(fill=tk.BOTH, expand=True)

    # ── Info tab ──────────────────────────────────────────────────────────────

    def _build_info_tab(self) -> None:
        frame = tk.Frame(self._tabs, bg=C["surface"])
        self._tabs.add(frame, text="Info")
        self._info_frame = frame
        self._info_labels: dict[str, tk.Label] = {}

        rows = [
            ("File",      "—"),
            ("Path",      "—"),
            ("Category",  "—"),
            ("Extension", "—"),
            ("Size",      "—"),
            ("Modified",  "—"),
        ]
        for r, (key, _) in enumerate(rows):
            tk.Label(
                frame, text=f"{key}:", bg=C["surface"], fg=C["fg_muted"],
                font=("Segoe UI", 9), anchor="e", width=12,
            ).grid(row=r, column=0, sticky="e", padx=(16, 6), pady=5)

            lbl = tk.Label(
                frame, text="—", bg=C["surface"], fg=C["fg"],
                font=("Segoe UI", 9), anchor="w",
            )
            lbl.grid(row=r, column=1, sticky="w", pady=5)
            self._info_labels[key] = lbl

        frame.columnconfigure(1, weight=1)

    # ── internal helpers ──────────────────────────────────────────────────────

    def _get_raw_text(self) -> str:
        return self._raw_text.get("1.0", "end-1c")

    def _set_raw_text(self, text: str) -> None:
        self._raw_text.config(state="normal")
        self._raw_text.delete("1.0", "end")
        self._raw_text.insert("1.0", text)
        self._raw_text.edit_reset()
        self._raw_text.edit_modified(False)
        self._gutter._redraw()

    def _load_form_tab(self, text: str) -> None:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                self._form_view.load(data, readonly=self._get_readonly())
            else:
                self._form_view.load({}, readonly=True)
        except json.JSONDecodeError:
            self._form_view.load({}, readonly=True)

    def _clear_form_tab(self) -> None:
        self._form_view.load({}, readonly=True)

    def _refresh_info_tab(self, entry: PromptFileEntry) -> None:
        try:
            stat     = entry.path.stat()
            mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_str = f"{stat.st_size:,} bytes"
        except OSError:
            mod_time = "—"
            size_str = "—"

        self._info_labels["File"].config(text=entry.name)
        self._info_labels["Path"].config(text=str(entry.path))
        self._info_labels["Category"].config(text=entry.category)
        self._info_labels["Extension"].config(text=entry.extension)
        self._info_labels["Size"].config(text=size_str)
        self._info_labels["Modified"].config(text=mod_time)

    def _clear_info_tab(self) -> None:
        for lbl in self._info_labels.values():
            lbl.config(text="—")

    def _update_header(self, entry: PromptFileEntry) -> None:
        self._header_label.config(text=entry.display_name, fg=C["fg"])
        self._path_label.config(text=str(entry.rel_path), fg=C["fg_muted"])

    def _update_dirty_indicator(self, *_) -> None:
        if self.has_unsaved:
            self._dirty_label.config(text="● unsaved", fg=C["accent3"])
        else:
            self._dirty_label.config(text="✓ saved", fg=C["green"])

    def _on_text_modified(self, _=None) -> None:
        if self._raw_text.edit_modified():
            self._update_dirty_indicator()
            self._gutter._redraw()
            self._raw_text.edit_modified(False)

    def _on_tab_key(self, event) -> str:
        self._raw_text.insert(tk.INSERT, "    ")
        return "break"

    # ── active-file toggle ───────────────────────────────────────────────────

    def _detect_active_state(self, entry: PromptFileEntry) -> bool:
        """Check whether a sibling `.active` marker file exists."""
        marker = entry.path.with_suffix(entry.extension + ".active")
        return marker.exists()

    def _active_label(self) -> str:
        return "● active" if self._is_active else "○ inactive"

    def _toggle_active(self) -> None:
        if self._entry is None:
            return
        marker = self._entry.path.with_suffix(self._entry.extension + ".active")
        if self._is_active:
            try:
                marker.unlink(missing_ok=True)
                self._is_active = False
                self._on_status(f"Deactivated: {self._entry.name}", "ok")
            except OSError as exc:
                self._on_status(f"Could not deactivate: {exc}", "error")
        else:
            try:
                marker.touch()
                self._is_active = True
                self._on_status(f"Activated: {self._entry.name}", "ok")
            except OSError as exc:
                self._on_status(f"Could not activate: {exc}", "error")
        self._active_toggle.config(
            text=self._active_label(),
            fg=C["accent2"] if self._is_active else C["fg_muted"],
        )

    # ── find bar ──────────────────────────────────────────────────────────────

    def _toggle_find_bar(self) -> None:
        if self._find_bar.winfo_ismapped():
            self._hide_find_bar()
        else:
            self._find_bar.pack(fill=tk.X, before=self._raw_text.master)

    def _hide_find_bar(self) -> None:
        self._find_bar.pack_forget()
        self._raw_text.tag_remove("find", "1.0", "end")
        self._find_count.config(text="")

    def _do_find(self) -> None:
        self._raw_text.tag_remove("find", "1.0", "end")
        query = self._find_var.get()
        if not query:
            self._find_count.config(text="")
            return
        count  = 0
        start  = "1.0"
        while True:
            pos = self._raw_text.search(query, start, stopindex="end", nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self._raw_text.tag_add("find", pos, end)
            start  = end
            count += 1
        self._raw_text.tag_config(
            "find",
            background=C["accent"],
            foreground="#ffffff",
        )
        self._find_count.config(text=f"{count} match{'es' if count != 1 else ''}")

    def _find_navigate(self, direction: int) -> None:
        query = self._find_var.get()
        if not query:
            return
        current = self._raw_text.index(tk.INSERT)
        if direction > 0:
            pos = self._raw_text.search(query, current + "+1c", stopindex="end", nocase=True)
            if not pos:
                pos = self._raw_text.search(query, "1.0", stopindex="end", nocase=True)
        else:
            pos = self._raw_text.search(query, current, stopindex="1.0",
                                         nocase=True, backwards=True)
            if not pos:
                pos = self._raw_text.search(query, "end", stopindex="1.0",
                                             nocase=True, backwards=True)
        if pos:
            end = f"{pos}+{len(query)}c"
            self._raw_text.mark_set(tk.INSERT, pos)
            self._raw_text.see(pos)
            self._raw_text.tag_remove("find_current", "1.0", "end")
            self._raw_text.tag_add("find_current", pos, end)
            self._raw_text.tag_config("find_current", background=C["accent3"],
                                       foreground="#000000")

    # ── word wrap ─────────────────────────────────────────────────────────────

    def _toggle_wrap(self) -> None:
        current = self._raw_text.cget("wrap")
        self._raw_text.config(wrap="none" if current == "word" else "word")

    # ── JSON formatting ───────────────────────────────────────────────────────

    def _format_json(self) -> None:
        text = self._get_raw_text()
        try:
            data = json.loads(text)
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            self._set_raw_text(formatted)
            self._on_status("JSON formatted", "ok")
        except json.JSONDecodeError as exc:
            self._on_status(f"Invalid JSON: {exc}", "error")
