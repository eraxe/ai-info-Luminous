"""
file_list.py — VirtualFileList widget
======================================

Provides a virtualized (canvas-drawn) scrollable list of prompt file
entries for Panel 2 of PromptManagementApp.

The list renders only visible rows to the canvas, keeping the UI snappy
even with thousands of entries.  Filtering is in-memory — the full
entry list is retained so re-filtering is instant.

Usage
-----
    from file_list import VirtualFileList
    from prompt_index import PromptFileEntry

    lst = VirtualFileList(parent, on_select=my_callback)
    lst.pack(fill=tk.BOTH, expand=True)

    lst.load(entries, search_query="")
    lst.filter("some search term")

Public API
----------
    .load(entries, query="")   Replace the full entry list and apply *query*.
    .filter(query)             Re-filter the current list in-place.
    .clear()                   Remove all entries and reset state.
    .selected                  Property — the currently selected entry or None.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Optional

from colors import C

# Try to import PromptFileEntry; fall back to a minimal duck-type stub so
# the module can be imported and tested independently of prompt_index.
try:
    from prompt_index import PromptFileEntry  # type: ignore
except ImportError:
    class PromptFileEntry:  # type: ignore
        """Minimal stub used when prompt_index is not available."""
        def __init__(self, name: str, path: str = "", modified: str = "") -> None:
            self.name = name
            self.path = path
            self.modified = modified


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ROW_HEIGHT    = 38          # px per list row
_FONT_NAME     = ("Segoe UI", 9)
_FONT_MODIFIED = ("Segoe UI", 7)
_PAD_LEFT      = 10
_PAD_RIGHT     = 8


# ---------------------------------------------------------------------------
# VirtualFileList
# ---------------------------------------------------------------------------

class VirtualFileList(tk.Frame):
    """Virtualized scrollable list of PromptFileEntry objects.

    Only the rows that are currently visible in the viewport are drawn;
    scrolling recycles canvas items via a sliding-window redraw strategy.
    This keeps the widget fast regardless of the total entry count.

    Parameters
    ----------
    parent:
        Tkinter parent widget.
    on_select:
        Callback invoked with the selected :class:`PromptFileEntry` when
        the user clicks a row.  Defaults to None.
    row_height:
        Height of each row in pixels.  Defaults to 38.
    colors:
        Optional dict of colour overrides applied on top of C.

    Public API
    ----------
    .load(entries, query="")
        Replace the entry list and apply an optional filter *query*.
    .filter(query)
        Re-filter the existing entries by *query* (case-insensitive
        substring match on ``entry.name``).
    .clear()
        Remove all entries and reset the widget to an empty state.
    .selected
        Read-only property returning the currently selected
        :class:`PromptFileEntry` or None.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_select: Optional[Callable[[PromptFileEntry], None]] = None,
        row_height: int = _ROW_HEIGHT,
        colors: Optional[dict] = None,
        **kw,
    ) -> None:
        palette = {**C, **(colors or {})}
        super().__init__(parent, bg=palette["surface"], **kw)
        self._palette      = palette
        self._on_select    = on_select
        self._row_height   = row_height
        self._all_entries: List[PromptFileEntry] = []
        self._visible:     List[PromptFileEntry] = []
        self._selected_idx: Optional[int] = None
        self._hover_idx:    Optional[int] = None
        self._drag_start_y: Optional[int] = None

        # ── canvas + scrollbar ────────────────────────────────────────
        self._canvas = tk.Canvas(
            self,
            bg=palette["surface"],
            highlightthickness=0,
            bd=0,
        )
        self._scrollbar = tk.Scrollbar(
            self,
            orient="vertical",
            command=self._canvas.yview,
            bg=palette["surface"],
            troughcolor=palette["surface2"],
            activebackground=palette["surface3"],
        )
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── event bindings ────────────────────────────────────────────
        self._canvas.bind("<Configure>",    self._on_canvas_configure)
        self._canvas.bind("<Button-1>",     self._on_click)
        self._canvas.bind("<Motion>",       self._on_motion)
        self._canvas.bind("<Leave>",        self._on_leave)
        self._canvas.bind("<MouseWheel>",   self._on_mousewheel)
        self._canvas.bind("<Button-4>",     self._on_mousewheel)
        self._canvas.bind("<Button-5>",     self._on_mousewheel)

        # Drag-to-scroll
        self._canvas.bind("<ButtonPress-2>",   self._drag_start)
        self._canvas.bind("<B2-Motion>",        self._drag_motion)
        self._canvas.bind("<ButtonPress-3>",    self._drag_start)
        self._canvas.bind("<B3-Motion>",        self._drag_motion)

        self._canvas_width: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def selected(self) -> Optional[PromptFileEntry]:
        """The currently selected entry, or None."""
        if self._selected_idx is not None and self._selected_idx < len(self._visible):
            return self._visible[self._selected_idx]
        return None

    def load(self, entries: List[PromptFileEntry], query: str = "") -> None:
        """Replace all entries and apply *query* as an initial filter."""
        self._all_entries = list(entries)
        self._selected_idx = None
        self._hover_idx    = None
        self._apply_filter(query)

    def filter(self, query: str) -> None:
        """Re-filter the current entry list by *query*."""
        prev_selected = self.selected
        self._selected_idx = None
        self._apply_filter(query)
        # Restore selection if the previously selected entry is still visible
        if prev_selected is not None:
            for i, e in enumerate(self._visible):
                if e is prev_selected or e.path == prev_selected.path:
                    self._selected_idx = i
                    break
        self._redraw()

    def clear(self) -> None:
        """Remove all entries and reset to empty state."""
        self._all_entries.clear()
        self._visible.clear()
        self._selected_idx = None
        self._hover_idx    = None
        self._canvas.delete("all")
        self._canvas.configure(scrollregion=(0, 0, 0, 0))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_filter(self, query: str) -> None:
        q = query.strip().lower()
        if q:
            self._visible = [
                e for e in self._all_entries
                if q in e.name.lower()
            ]
        else:
            self._visible = list(self._all_entries)
        self._update_scroll_region()
        self._redraw()

    def _update_scroll_region(self) -> None:
        total_h = len(self._visible) * self._row_height
        self._canvas.configure(scrollregion=(0, 0, self._canvas_width, total_h))

    def _row_at_y(self, canvas_y: int) -> Optional[int]:
        """Return the row index at canvas coordinate *canvas_y*, or None."""
        idx = int(canvas_y // self._row_height)
        if 0 <= idx < len(self._visible):
            return idx
        return None

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _redraw(self) -> None:
        """Redraw only the rows currently visible in the viewport."""
        self._canvas.delete("all")

        if not self._visible:
            self._draw_empty()
            return

        cw = max(self._canvas_width, 1)
        ch = self._canvas.winfo_height()
        rh = self._row_height

        # Determine visible range from current scroll position
        scroll_top = self._canvas.canvasy(0)
        first = max(0, int(scroll_top // rh))
        last  = min(len(self._visible), int((scroll_top + ch) // rh) + 2)

        p = self._palette
        for i in range(first, last):
            y0 = i * rh
            y1 = y0 + rh
            entry = self._visible[i]

            # ── row background ─────────────────────────────────────
            if i == self._selected_idx:
                bg = p["surface3"]
                fg = p["fg"]
                fg_sub = p["fg_dim"]
                accent_bar = True
            elif i == self._hover_idx:
                bg = p["surface2"]
                fg = p["fg"]
                fg_sub = p["fg_dim"]
                accent_bar = False
            else:
                bg = p["surface"]
                fg = p["fg_dim"]
                fg_sub = p["fg_muted"]
                accent_bar = False

            self._canvas.create_rectangle(
                0, y0, cw, y1,
                fill=bg, outline="",
                tags=(f"row_{i}",),
            )

            # ── accent side bar for selected row ───────────────────
            if accent_bar:
                self._canvas.create_rectangle(
                    0, y0, 3, y1,
                    fill=p["accent"], outline="",
                    tags=(f"row_{i}",),
                )

            # ── file name ──────────────────────────────────────────
            name = entry.name if len(entry.name) <= 28 else entry.name[:26] + "…"
            self._canvas.create_text(
                _PAD_LEFT + (4 if accent_bar else 0),
                y0 + rh // 2 - 6,
                text=name,
                anchor="w",
                fill=fg,
                font=_FONT_NAME,
                tags=(f"row_{i}",),
            )

            # ── modified date / path sub-label ─────────────────────
            sub = getattr(entry, "modified", "") or entry.path
            if sub and len(sub) > 32:
                sub = sub[:30] + "…"
            if sub:
                self._canvas.create_text(
                    _PAD_LEFT + (4 if accent_bar else 0),
                    y0 + rh // 2 + 8,
                    text=sub,
                    anchor="w",
                    fill=fg_sub,
                    font=_FONT_MODIFIED,
                    tags=(f"row_{i}",),
                )

            # ── divider ────────────────────────────────────────────
            if i < len(self._visible) - 1:
                self._canvas.create_line(
                    0, y1 - 1, cw, y1 - 1,
                    fill=p["border"], width=1,
                    tags=(f"row_{i}",),
                )

    def _draw_empty(self) -> None:
        cw = max(self._canvas_width, 1)
        ch = self._canvas.winfo_height()
        self._canvas.create_text(
            cw // 2, ch // 2,
            text="No files",
            fill=self._palette["fg_muted"],
            font=("Segoe UI", 9),
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_canvas_configure(self, event) -> None:
        self._canvas_width = event.width
        self._update_scroll_region()
        self._redraw()

    def _on_mousewheel(self, event) -> None:
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._redraw()

    def _on_click(self, event) -> None:
        y = self._canvas.canvasy(event.y)
        idx = self._row_at_y(y)
        if idx is None:
            return
        prev = self._selected_idx
        self._selected_idx = idx
        if prev != idx:
            self._redraw()
            if self._on_select:
                self.after(0, lambda: self._on_select(self._visible[idx]))

    def _on_motion(self, event) -> None:
        y = self._canvas.canvasy(event.y)
        idx = self._row_at_y(y)
        if idx != self._hover_idx:
            self._hover_idx = idx
            self._redraw()

    def _on_leave(self, _=None) -> None:
        if self._hover_idx is not None:
            self._hover_idx = None
            self._redraw()

    def _drag_start(self, event) -> None:
        self._drag_start_y = event.y

    def _drag_motion(self, event) -> None:
        if self._drag_start_y is not None:
            delta = self._drag_start_y - event.y
            self._canvas.yview_scroll(int(delta / 8), "units")
            self._drag_start_y = event.y
            self._redraw()
