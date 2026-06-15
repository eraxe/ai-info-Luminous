#!/usr/bin/env python3
"""
Luminous AI — Collections Drawer
CollectionsDrawer: slide-in sidebar that lets users organise prompt
files into named collections (bookmarks / curated sets), independent
of their on-disk category hierarchy.

Architecture
------------
Collections are stored in-memory as a dict:
    {collection_name: [PromptFileEntry, …]}

The drawer receives prompt entries via ``add_entry()`` / ``remove_entry()``,
and broadcasts selection events back to the caller via the optional
``on_select`` callback.

The drawer is hidden by default; call ``open()`` / ``close()`` or
``toggle()`` to animate it in/out using a simple slide effect.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.simpledialog as sd
import tkinter.messagebox   as mb
from typing import Callable, Optional

from colors import C
from widgets import FlatButton, AccentButton
from prompt_index import PromptFileEntry


# ─────────────────────────────────────────────────────────────────────────────
# _CollectionItem  (a single row inside the file list of a collection)
# ─────────────────────────────────────────────────────────────────────────────

class _CollectionItem(tk.Frame):
    """Single entry row inside an expanded collection."""

    def __init__(
        self,
        parent: tk.Widget,
        entry: PromptFileEntry,
        on_select:  Callable[[PromptFileEntry], None],
        on_remove:  Callable[[PromptFileEntry], None],
        **kw,
    ) -> None:
        kw.setdefault("bg", C["surface2"])
        super().__init__(parent, **kw)
        self._entry     = entry
        self._on_select = on_select
        self._on_remove = on_remove
        self._build()

    def _build(self) -> None:
        # Extension badge
        ext_color = C["accent2"] if self._entry.is_json else C["accent"]
        ext_lbl = tk.Label(
            self,
            text=self._entry.extension.lstrip(".").upper() or "?",
            bg=ext_color, fg="#ffffff",
            font=("Segoe UI", 7, "bold"),
            padx=4, pady=1,
        )
        ext_lbl.pack(side=tk.LEFT, padx=(8, 4), pady=4)

        name_lbl = tk.Label(
            self,
            text=self._entry.display_name,
            bg=C["surface2"], fg=C["fg"],
            font=("Segoe UI", 9),
            anchor="w",
            cursor="hand2",
        )
        name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)

        remove_btn = FlatButton(
            self, text="✕",
            command=lambda: self._on_remove(self._entry),
            bg=C["surface2"], fg=C["fg_muted"],
            hover_fg=C["red"],
            font=("Segoe UI", 8), padx=6, pady=2,
        )
        remove_btn.pack(side=tk.RIGHT, padx=4, pady=4)

        # Click anywhere on the row → select
        for w in (self, name_lbl, ext_lbl):
            w.bind("<Button-1>", lambda _: self._on_select(self._entry))
            w.bind("<Enter>",   lambda _: self.config(bg=C["surface3"]))
            w.bind("<Leave>",   lambda _: self.config(bg=C["surface2"]))


# ─────────────────────────────────────────────────────────────────────────────
# _CollectionSection  (collapsible header + item list for one collection)
# ─────────────────────────────────────────────────────────────────────────────

class _CollectionSection(tk.Frame):
    """Collapsible section for a single named collection."""

    def __init__(
        self,
        parent: tk.Widget,
        name: str,
        on_select:  Callable[[PromptFileEntry], None],
        on_rename:  Callable[[str, str], None],
        on_delete:  Callable[[str], None],
        on_add_active: Callable[[str], None],
        **kw,
    ) -> None:
        kw.setdefault("bg", C["surface"])
        super().__init__(parent, **kw)
        self.name            = name
        self._on_select      = on_select
        self._on_rename      = on_rename
        self._on_delete      = on_delete
        self._on_add_active  = on_add_active
        self._entries:    list[PromptFileEntry] = []
        self._expanded    = True
        self._item_frames: list[_CollectionItem] = []
        self._build()

    # ── public ────────────────────────────────────────────────────────────────

    def add_entry(self, entry: PromptFileEntry) -> bool:
        """Add *entry* if not already in this collection.  Returns True if added."""
        if any(e.path == entry.path for e in self._entries):
            return False
        self._entries.append(entry)
        self._refresh_items()
        self._update_count()
        return True

    def remove_entry(self, entry: PromptFileEntry) -> None:
        self._entries = [e for e in self._entries if e.path != entry.path]
        self._refresh_items()
        self._update_count()

    def get_entries(self) -> list[PromptFileEntry]:
        return list(self._entries)

    def load_entries(self, entries: list[PromptFileEntry]) -> None:
        self._entries = list(entries)
        self._refresh_items()
        self._update_count()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header row
        self._header = tk.Frame(self, bg=C["surface2"], cursor="hand2")
        self._header.pack(fill=tk.X)

        indicator_color = self._hash_accent(self.name)
        tk.Frame(self._header, bg=indicator_color, width=3).pack(side=tk.LEFT, fill=tk.Y)

        self._chevron = tk.Label(
            self._header, text="▾", bg=C["surface2"], fg=C["fg_muted"],
            font=("Segoe UI", 9),
        )
        self._chevron.pack(side=tk.LEFT, padx=(6, 2), pady=6)

        self._name_label = tk.Label(
            self._header, text=self.name,
            bg=C["surface2"], fg=C["fg"],
            font=("Segoe UI", 9, "bold"), anchor="w",
        )
        self._name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)

        self._count_label = tk.Label(
            self._header, text="0", bg=C["surface2"], fg=C["fg_muted"],
            font=("Segoe UI", 8),
        )
        self._count_label.pack(side=tk.LEFT, padx=4)

        # Context menu trigger
        menu_btn = FlatButton(
            self._header, text="⋯",
            command=self._show_context_menu,
            bg=C["surface2"], fg=C["fg_muted"],
            hover_fg=C["fg"],
            font=("Segoe UI", 10), padx=8, pady=2,
        )
        menu_btn.pack(side=tk.RIGHT, padx=4)

        # Click header to collapse/expand
        for w in (self._header, self._chevron, self._name_label, self._count_label):
            w.bind("<Button-1>", lambda _: self._toggle_expand())

        # Items container
        self._items_frame = tk.Frame(self, bg=C["surface"])
        self._items_frame.pack(fill=tk.X)

        # Empty state label
        self._empty_label = tk.Label(
            self._items_frame, text="No prompts in this collection.",
            bg=C["surface"], fg=C["fg_muted"],
            font=("Segoe UI", 8), padx=16, pady=8,
        )

    # ── expand / collapse ─────────────────────────────────────────────────────

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self._chevron.config(text="▾" if self._expanded else "▸")
        if self._expanded:
            self._items_frame.pack(fill=tk.X)
        else:
            self._items_frame.pack_forget()

    # ── item rendering ────────────────────────────────────────────────────────

    def _refresh_items(self) -> None:
        for f in self._item_frames:
            f.destroy()
        self._item_frames.clear()
        self._empty_label.pack_forget()

        if not self._entries:
            self._empty_label.pack(anchor="w")
            return

        for entry in self._entries:
            item = _CollectionItem(
                self._items_frame,
                entry=entry,
                on_select=self._on_select,
                on_remove=self._do_remove_entry,
            )
            item.pack(fill=tk.X)
            self._item_frames.append(item)

    def _do_remove_entry(self, entry: PromptFileEntry) -> None:
        self.remove_entry(entry)

    def _update_count(self) -> None:
        self._count_label.config(text=str(len(self._entries)))

    # ── context menu ──────────────────────────────────────────────────────────

    def _show_context_menu(self) -> None:
        menu = tk.Menu(self, tearoff=0,
                       bg=C["surface2"], fg=C["fg"],
                       activebackground=C["accent"],
                       activeforeground="#ffffff",
                       relief="flat", borderwidth=1)
        menu.add_command(label="➕ Add current file",
                         command=lambda: self._on_add_active(self.name))
        menu.add_separator()
        menu.add_command(label="✏  Rename",
                         command=self._do_rename)
        menu.add_command(label="🗑  Delete collection",
                         command=self._do_delete)
        try:
            x = self._header.winfo_rootx()
            y = self._header.winfo_rooty() + self._header.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _do_rename(self) -> None:
        new_name = sd.askstring(
            "Rename Collection",
            "New name:",
            initialvalue=self.name,
            parent=self.winfo_toplevel(),
        )
        if new_name and new_name.strip() and new_name.strip() != self.name:
            old = self.name
            self.name = new_name.strip()
            self._name_label.config(text=self.name)
            self._on_rename(old, self.name)

    def _do_delete(self) -> None:
        if mb.askyesno("Delete Collection",
                       f"Delete collection \u201c{self.name}\u201d?\n"
                       "Prompt files on disk are not affected.",
                       parent=self.winfo_toplevel()):
            self._on_delete(self.name)

    # ── accent colour derived from name ──────────────────────────────────────

    @staticmethod
    def _hash_accent(name: str) -> str:
        """Return a deterministic accent colour from a small palette."""
        _PALETTE = [
            C["accent"],   # purple
            C["accent2"],  # blue
            C["accent3"],  # amber
            C["green"],
            C["red"],
        ]
        h = sum(ord(c) for c in name)
        return _PALETTE[h % len(_PALETTE)]


# ─────────────────────────────────────────────────────────────────────────────
# CollectionsDrawer
# ─────────────────────────────────────────────────────────────────────────────

class CollectionsDrawer(tk.Frame):
    """Slide-in right sidebar for organising prompts into named collections.

    Layout
    ------
    [handle bar]  ← 6 px wide strip on the left edge; click or drag to
                    open/close the drawer
    [drawer body] ← fixed-width panel that slides in/out

    The parent **must** use ``pack(side=tk.RIGHT, fill=tk.Y)`` for the
    drawer, or place it absolutely, so that the slide animation makes
    visual sense.

    Usage::

        drawer = CollectionsDrawer(parent, on_select=my_callback)
        drawer.pack(side=tk.RIGHT, fill=tk.Y)

        # To add the currently-selected prompt file:
        drawer.add_to_active_collection(entry)

        # To open programmatically:
        drawer.open()
    """

    _DRAWER_WIDTH = 260
    _SLIDE_STEPS  = 8
    _SLIDE_MS     = 16  # ms per step → ~128 ms total

    def __init__(
        self,
        parent: tk.Widget,
        on_select: Callable[[PromptFileEntry], None] | None = None,
        **kw,
    ) -> None:
        # Outer wrapper occupies only the handle width when closed
        kw.setdefault("bg", C["bg"])
        super().__init__(parent, bg=C["bg"], width=0)
        self.pack_propagate(False)

        self._on_select  = on_select or (lambda e: None)
        self._is_open    = False
        self._animating  = False
        self._current_w  = 0

        # Collections data: name → _CollectionSection
        self._sections: dict[str, _CollectionSection] = {}
        self._active_collection: str | None = None
        # Ephemeral "current file" reference for "add to collection" actions
        self._current_entry: Optional[PromptFileEntry] = None

        self._build()

    # ── public API ────────────────────────────────────────────────────────────

    def open(self) -> None:
        if not self._is_open and not self._animating:
            self._animate_to(self._DRAWER_WIDTH)

    def close(self) -> None:
        if self._is_open and not self._animating:
            self._animate_to(0)

    def toggle(self) -> None:
        if self._is_open:
            self.close()
        else:
            self.open()

    def set_current_entry(self, entry: PromptFileEntry | None) -> None:
        """Keep track of which file is selected in the main panel."""
        self._current_entry = entry

    def add_to_active_collection(self, entry: PromptFileEntry) -> None:
        """Add *entry* to the active (or first) collection."""
        if not self._sections:
            self._create_collection("Default")
        target = self._active_collection or next(iter(self._sections))
        self._sections[target].add_entry(entry)

    def add_to_collection(self, name: str, entry: PromptFileEntry) -> bool:
        """Add *entry* to the collection called *name*.  Returns True if added."""
        if name not in self._sections:
            return False
        return self._sections[name].add_entry(entry)

    def get_collection_entries(self, name: str) -> list[PromptFileEntry]:
        """Return entries for the named collection (empty list if missing)."""
        section = self._sections.get(name)
        return section.get_entries() if section else []

    def all_collections(self) -> dict[str, list[PromptFileEntry]]:
        """Return a snapshot of all collections as {name: [entry, …]}."""
        return {name: sec.get_entries() for name, sec in self._sections.items()}

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Handle strip on the left edge
        self._handle = tk.Frame(self, bg=C["border"], width=6, cursor="sb_h_double_arrow")
        self._handle.pack(side=tk.LEFT, fill=tk.Y)
        self._handle.bind("<Button-1>",  lambda _: self.toggle())
        self._handle.bind("<Enter>",     lambda _: self._handle.config(bg=C["accent"]))
        self._handle.bind("<Leave>",     lambda _: self._handle.config(bg=C["border"]))

        # Drawer panel (hidden until opened)
        self._panel = tk.Frame(self, bg=C["surface"], width=self._DRAWER_WIDTH)
        self._panel.pack_propagate(False)
        # Not packed yet; revealed by animation

        self._build_drawer_header()
        self._build_collections_list()
        self._build_drawer_footer()

    def _build_drawer_header(self) -> None:
        header = tk.Frame(self._panel, bg=C["surface2"], height=40)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(
            header, text="◧ Collections",
            bg=C["surface2"], fg=C["fg"],
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=12, pady=8)

        FlatButton(
            header, text="✕",
            command=self.close,
            bg=C["surface2"], fg=C["fg_muted"],
            hover_fg=C["red"],
            font=("Segoe UI", 10), padx=8, pady=4,
        ).pack(side=tk.RIGHT, padx=4)

        tk.Frame(self._panel, bg=C["border"], height=1).pack(fill=tk.X)

    def _build_collections_list(self) -> None:
        """Scrollable area that holds all _CollectionSection widgets."""
        container = tk.Frame(self._panel, bg=C["surface"])
        container.pack(fill=tk.BOTH, expand=True)

        canvas  = tk.Canvas(container, bg=C["surface"], bd=0, highlightthickness=0)
        scroll  = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)

        self._list_inner = tk.Frame(canvas, bg=C["surface"])
        window = canvas.create_window((0, 0), window=self._list_inner, anchor="nw")

        def _on_inner_conf(_=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_conf(e=None):
            if e:
                canvas.itemconfig(window, width=e.width)

        self._list_inner.bind("<Configure>", _on_inner_conf)
        canvas.bind("<Configure>", _on_canvas_conf)

        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mousewheel scrolling
        def _on_wheel(e):
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        canvas.bind("<MouseWheel>", _on_wheel)

        # Empty state
        self._empty_state = tk.Frame(self._list_inner, bg=C["surface"])
        self._empty_state.pack(fill=tk.X, pady=32, padx=16)
        tk.Label(
            self._empty_state,
            text="No collections yet.\nCreate one below.",
            bg=C["surface"], fg=C["fg_muted"],
            font=("Segoe UI", 9), justify="center",
        ).pack()

    def _build_drawer_footer(self) -> None:
        tk.Frame(self._panel, bg=C["border"], height=1).pack(fill=tk.X)
        footer = tk.Frame(self._panel, bg=C["surface2"], height=44)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        AccentButton(
            footer, text="＋ New Collection",
            command=self._do_new_collection,
            accent="purple",
            font=("Segoe UI", 8, "bold"), padx=12, pady=4,
        ).pack(side=tk.LEFT, padx=8, pady=8)

        FlatButton(
            footer, text="+ Add file",
            command=self._do_add_current_file,
            bg=C["surface2"], fg=C["fg_muted"],
            hover_fg=C["accent2"],
            font=("Segoe UI", 8), padx=8, pady=4,
        ).pack(side=tk.RIGHT, padx=8)

    # ── collection management ─────────────────────────────────────────────────

    def _do_new_collection(self) -> None:
        name = sd.askstring(
            "New Collection", "Collection name:",
            parent=self.winfo_toplevel(),
        )
        if name and name.strip():
            self._create_collection(name.strip())

    def _create_collection(self, name: str) -> None:
        if name in self._sections:
            mb.showinfo("Duplicate", f"A collection named \u201c{name}\u201d already exists.",
                        parent=self.winfo_toplevel())
            return
        sec = _CollectionSection(
            self._list_inner,
            name=name,
            on_select=self._on_select,
            on_rename=self._handle_rename,
            on_delete=self._handle_delete,
            on_add_active=self._handle_add_active_to,
        )
        sec.pack(fill=tk.X, pady=(0, 2))
        self._sections[name] = sec
        self._active_collection = name
        self._update_empty_state()

    def _handle_rename(self, old: str, new: str) -> None:
        if new in self._sections and new != old:
            mb.showinfo("Duplicate", f"A collection named \u201c{new}\u201d already exists.",
                        parent=self.winfo_toplevel())
            return
        sec = self._sections.pop(old)
        self._sections[new] = sec
        if self._active_collection == old:
            self._active_collection = new

    def _handle_delete(self, name: str) -> None:
        sec = self._sections.pop(name, None)
        if sec:
            sec.destroy()
        if self._active_collection == name:
            self._active_collection = next(iter(self._sections), None)
        self._update_empty_state()

    def _handle_add_active_to(self, collection_name: str) -> None:
        if self._current_entry is None:
            mb.showinfo("No file selected",
                        "Select a prompt file first, then use this button.",
                        parent=self.winfo_toplevel())
            return
        added = self._sections[collection_name].add_entry(self._current_entry)
        if not added:
            mb.showinfo("Already in collection",
                        f"\u201c{self._current_entry.display_name}\u201d is already in \u201c{collection_name}\u201d.",
                        parent=self.winfo_toplevel())

    def _do_add_current_file(self) -> None:
        if self._current_entry is None:
            mb.showinfo("No file selected",
                        "Select a prompt file in the file list first.",
                        parent=self.winfo_toplevel())
            return
        if not self._sections:
            self._create_collection("Default")
        target = self._active_collection or next(iter(self._sections))
        added  = self._sections[target].add_entry(self._current_entry)
        if not added:
            mb.showinfo("Already in collection",
                        f"\u201c{self._current_entry.display_name}\u201d is already in \u201c{target}\u201d.",
                        parent=self.winfo_toplevel())

    def _update_empty_state(self) -> None:
        if self._sections:
            self._empty_state.pack_forget()
        else:
            self._empty_state.pack(fill=tk.X, pady=32, padx=16)

    # ── slide animation ───────────────────────────────────────────────────────

    def _animate_to(self, target_w: int) -> None:
        self._animating = True
        start_w   = self._current_w
        delta     = target_w - start_w
        step_size = delta / self._SLIDE_STEPS

        if target_w > 0 and not self._panel.winfo_ismapped():
            self._panel.pack(side=tk.LEFT, fill=tk.Y)

        def _step(step: int) -> None:
            if step >= self._SLIDE_STEPS:
                self._current_w = target_w
                self.config(width=target_w + 6)  # +6 for handle
                if target_w == 0:
                    self._panel.pack_forget()
                    self._is_open = False
                else:
                    self._is_open = True
                self._animating = False
                return
            w = int(start_w + step_size * step)
            self.config(width=w + 6)
            self.after(self._SLIDE_MS, lambda: _step(step + 1))

        _step(0)
