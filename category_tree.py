"""
category_tree.py — CategoryTree widget
=======================================

Provides a tree-view widget that lists prompt categories in a collapsible
hierarchy.  Designed for Panel 1 of PromptManagementApp.

Usage
-----
    from category_tree import CategoryTree

    tree = CategoryTree(parent, on_select=my_callback)
    tree.pack(fill=tk.BOTH, expand=True)

    tree.load(["dialogue", "combat/openers", "combat/closers", "world"])
    # Callback receives the flat category key, e.g. "combat/openers".

Public API
----------
    .load(categories)          Replace the tree content with a new list of keys.
    .set_active(key)           Highlight *key* without firing the callback.
    .clear()                   Remove all rows.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from colors import C


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_tree(keys: list[str]) -> dict:
    """Convert a flat list of slash-separated category keys into a nested dict.

    Example::

        ["dialogue", "combat/openers", "combat/closers", "world"]
        →
        {
            "dialogue": {},
            "combat": {"openers": {}, "closers": {}},
            "world": {},
        }
    """
    root: dict = {}
    for key in keys:
        node = root
        for part in key.split("/"):
            node = node.setdefault(part, {})
    return root


def _flatten(tree: dict, prefix: str = "") -> list[tuple[str, str, int]]:
    """Flatten *tree* into (display_label, full_key, depth) triples.

    The triples are ordered depth-first, alphabetically within each level.
    """
    result: list[tuple[str, str, int]] = []
    depth = prefix.count("/") + (1 if prefix else 0)
    for label in sorted(tree.keys()):
        full_key = f"{prefix}/{label}" if prefix else label
        result.append((label, full_key, depth))
        result.extend(_flatten(tree[label], full_key))
    return result


# ---------------------------------------------------------------------------
# CategoryRow  (internal)
# ---------------------------------------------------------------------------

class _CategoryRow(tk.Frame):
    """Single selectable row in the category tree."""

    _INDENT = 14  # px per depth level

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        full_key: str,
        depth: int,
        has_children: bool,
        on_click: Callable[[str], None],
        on_toggle: Callable[[str], None],
    ) -> None:
        super().__init__(parent, bg=C["surface"], cursor="hand2")
        self.full_key = full_key
        self._on_click = on_click
        self._active = False
        self._has_children = has_children

        # ── indent spacer ──────────────────────────────────────────────
        indent_px = depth * self._INDENT
        if indent_px:
            tk.Frame(self, bg=C["surface"], width=indent_px).pack(side=tk.LEFT)

        # ── expand/collapse toggle icon ────────────────────────────────
        if has_children:
            self._toggle_lbl = tk.Label(
                self,
                text="▾",
                bg=C["surface"],
                fg=C["fg_muted"],
                font=("Segoe UI", 8),
                cursor="hand2",
            )
            self._toggle_lbl.pack(side=tk.LEFT, padx=(0, 2))
            self._toggle_lbl.bind("<Button-1>", lambda _: on_toggle(full_key))
        else:
            # thin spacer so labels line up
            tk.Frame(self, bg=C["surface"], width=12).pack(side=tk.LEFT)

        # ── folder / leaf icon ─────────────────────────────────────────
        icon = "◈" if has_children else "·"
        self._icon_lbl = tk.Label(
            self,
            text=icon,
            bg=C["surface"],
            fg=C["fg_muted"],
            font=("Segoe UI", 9),
        )
        self._icon_lbl.pack(side=tk.LEFT, padx=(0, 4))

        # ── label ──────────────────────────────────────────────────────
        display = label.replace("_", " ").title()
        self._lbl = tk.Label(
            self,
            text=display,
            bg=C["surface"],
            fg=C["fg"],
            font=("Segoe UI", 9),
            anchor="w",
        )
        self._lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=5)

        # ── event bindings ─────────────────────────────────────────────
        for widget in (self, self._lbl, self._icon_lbl):
            widget.bind("<Enter>", self._hover_on)
            widget.bind("<Leave>", self._hover_off)
            widget.bind("<Button-1>", self._click)

    # ------------------------------------------------------------------

    def _hover_on(self, _=None) -> None:
        if not self._active:
            bg = C["surface2"]
            self.config(bg=bg)
            for w in self.winfo_children():
                try:
                    w.config(bg=bg)
                except tk.TclError:
                    pass

    def _hover_off(self, _=None) -> None:
        if not self._active:
            bg = C["surface"]
            self.config(bg=bg)
            for w in self.winfo_children():
                try:
                    w.config(bg=bg)
                except tk.TclError:
                    pass

    def _click(self, _=None) -> None:
        self._on_click(self.full_key)

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            bg = C["surface3"]
            fg_lbl = C["accent"]
            self.config(bg=bg, highlightbackground=C["accent"], highlightthickness=0)
            self._lbl.config(bg=bg, fg=fg_lbl, font=("Segoe UI", 9, "bold"))
            self._icon_lbl.config(bg=bg, fg=C["accent"])
            if self._has_children:
                self._toggle_lbl.config(bg=bg)
        else:
            bg = C["surface"]
            self.config(bg=bg)
            self._lbl.config(bg=bg, fg=C["fg"], font=("Segoe UI", 9))
            self._icon_lbl.config(bg=bg, fg=C["fg_muted"])
            if self._has_children:
                self._toggle_lbl.config(bg=bg)

    def set_collapsed(self, collapsed: bool) -> None:
        if self._has_children:
            self._toggle_lbl.config(text="▸" if collapsed else "▾")


# ---------------------------------------------------------------------------
# CategoryTree
# ---------------------------------------------------------------------------

class CategoryTree(tk.Frame):
    """Scrollable tree-view listing prompt categories.

    Parameters
    ----------
    parent:
        Tkinter parent widget.
    on_select:
        Callback invoked with the full category key string when the
        user clicks a row.  Defaults to None.
    colors:
        Optional dict of colour overrides applied on top of C.

    Public API
    ----------
    .load(categories)
        Replace the tree with *categories* — a list of slash-separated
        key strings, e.g. ["dialogue", "combat/openers"].
    .set_active(key)
        Mark *key* as the selected row without firing the callback.
        Pass None to deselect all.
    .clear()
        Remove all rows.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_select: Optional[Callable[[str], None]] = None,
        colors: Optional[dict] = None,
        **kw,
    ) -> None:
        palette = {**C, **(colors or {})}
        super().__init__(parent, bg=palette["surface"], **kw)
        self._palette = palette
        self._on_select = on_select
        self._active_key: Optional[str] = None
        self._rows: dict[str, _CategoryRow] = {}          # key → row widget
        self._collapsed: set[str] = set()                  # keys of collapsed parents
        self._flat: list[tuple[str, str, int]] = []        # (label, key, depth)
        self._tree: dict = {}                               # nested dict

        # ── scrollable canvas ──────────────────────────────────────────
        self._canvas = tk.Canvas(
            self, bg=palette["surface"], highlightthickness=0, bd=0
        )
        self._scrollbar = tk.Scrollbar(
            self, orient="vertical", command=self._canvas.yview,
            bg=palette["surface"], troughcolor=palette["surface2"],
            activebackground=palette["surface3"],
        )
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._inner = tk.Frame(self._canvas, bg=palette["surface"])
        self._inner_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)
        self._canvas.bind("<Button-5>", self._on_mousewheel)

    # ------------------------------------------------------------------
    # Layout callbacks
    # ------------------------------------------------------------------

    def _on_inner_configure(self, _=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self._canvas.itemconfig(self._inner_id, width=event.width)

    def _on_mousewheel(self, event) -> None:
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, categories: list[str]) -> None:
        """Rebuild the tree from *categories* (list of key strings)."""
        self.clear()
        if not categories:
            self._render_empty()
            return
        self._tree = _build_tree(categories)
        self._flat = _flatten(self._tree)
        self._render()

    def set_active(self, key: Optional[str]) -> None:
        """Highlight *key* as the active row.  Pass None to clear selection."""
        if self._active_key and self._active_key in self._rows:
            self._rows[self._active_key].set_active(False)
        self._active_key = key
        if key and key in self._rows:
            self._rows[key].set_active(True)

    def clear(self) -> None:
        """Destroy all row widgets and reset internal state."""
        for w in self._inner.winfo_children():
            w.destroy()
        self._rows.clear()
        self._flat = []
        self._tree = {}
        self._active_key = None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        """Populate self._inner with _CategoryRow widgets."""
        for label, key, depth in self._flat:
            parent_key = key.rsplit("/", 1)[0] if "/" in key else None
            if parent_key and self._is_collapsed(parent_key):
                continue

            # Does this key have children?
            parts = key.split("/")
            node = self._tree
            for p in parts:
                node = node.get(p, {})
            has_children = bool(node)

            row = _CategoryRow(
                self._inner,
                label=label,
                full_key=key,
                depth=depth,
                has_children=has_children,
                on_click=self._row_clicked,
                on_toggle=self._row_toggled,
            )
            row.pack(fill=tk.X)
            row.set_collapsed(key in self._collapsed)
            self._rows[key] = row

        # Restore active selection
        if self._active_key and self._active_key in self._rows:
            self._rows[self._active_key].set_active(True)

    def _render_empty(self) -> None:
        tk.Label(
            self._inner,
            text="No categories",
            bg=self._palette["surface"],
            fg=self._palette["fg_muted"],
            font=("Segoe UI", 9),
        ).pack(pady=16)

    def _is_collapsed(self, key: str) -> bool:
        """Return True if *key* or any of its ancestors is collapsed."""
        parts = key.split("/")
        for i in range(len(parts)):
            if "/".join(parts[: i + 1]) in self._collapsed:
                return True
        return False

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _row_clicked(self, key: str) -> None:
        self.set_active(key)
        if self._on_select:
            self._on_select(key)

    def _row_toggled(self, key: str) -> None:
        if key in self._collapsed:
            self._collapsed.discard(key)
        else:
            self._collapsed.add(key)
        # Re-render to show/hide children
        for w in self._inner.winfo_children():
            w.destroy()
        self._rows.clear()
        self._render()
