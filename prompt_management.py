#!/usr/bin/env python3
"""
Luminous AI — Prompt Management Section  (Part 2: Full Editor)
PromptManagementApp: 3-panel prompt editor with save/backup/reset,
JSON form editor, paired active-file toggle
"""
from __future__ import annotations

import sys
from pathlib import Path

# ── standalone import fix ──────────────────────────────────────────────────────
# Ensures sibling modules (colors, widgets, etc.) are resolvable whether this
# file is run directly (`python prompt_management.py`) or via `python -m`.
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import tkinter as tk
import tkinter.messagebox
import tkinter.ttk as ttk
from datetime import datetime
from typing import Callable, Optional

# ── local imports ─────────────────────────────────────────────────────────────
from colors import C
from widgets import FlatButton, AccentButton, StatusBar
from prompt_index import PromptIndex, PromptFileEntry
from prompt_editor import PromptEditor
from collections_drawer import CollectionsDrawer
from category_tree import CategoryTree
from file_list import VirtualFileList
from snapshot import snapshot_from_file, snapshot_from_category, snapshot_from_campaign
from campaigns import discover_campaigns
from save_manager import SaveManager


class PromptManagementApp:
    """Three-panel prompt management window."""

    def __init__(
        self,
        root: tk.Toplevel | tk.Tk,
        on_close: Callable[[], None] | None = None,
        save_manager: SaveManager | None = None,
    ) -> None:
        self.root = root
        self._on_close = on_close
        self.sm = save_manager or SaveManager()

        self._prompt_index: PromptIndex | None = None
        self._current_campaign: str = ""
        self._campaigns: list[str] = []
        self._active_category: str | None = None
        self._selected_entry: PromptFileEntry | None = None
        self._collections_open: bool = False

        self._setup_window()
        self._build_ui()
        self._refresh_campaigns()

    # ── window setup ──────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.root.title("Luminous — Prompt Management")
        self.root.configure(bg=C["bg"])
        self.root.geometry("1280x800")
        self.root.minsize(900, 600)
        if self._on_close:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── top bar ────────────────────────────────────────────────────────
        top_bar = tk.Frame(self.root, bg=C["surface"], height=40)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        top_bar.pack_propagate(False)
        self._build_top_bar(top_bar)

        # ── toolbar ────────────────────────────────────────────────────────
        toolbar = tk.Frame(self.root, bg=C["surface"], height=34)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        toolbar.pack_propagate(False)
        self._build_toolbar(toolbar)

        tk.Frame(self.root, bg=C["border"], height=1).pack(fill=tk.X)

        # ── body ───────────────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        self._build_panel1(body)
        self._build_panel2(body)
        self._build_panel3(body)
        self._build_collections_drawer(body)

        # ── status bar ─────────────────────────────────────────────────────
        self.status = StatusBar(self.root)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_top_bar(self, bar: tk.Frame) -> None:
        tk.Label(
            bar, text="Prompt Management",
            bg=C["surface"], fg=C["fg"],
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=16, pady=8)

        right = tk.Frame(bar, bg=C["surface"])
        right.pack(side=tk.RIGHT, padx=8)

        tk.Label(right, text="Campaign:", bg=C["surface"], fg=C["fg_muted"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)

        self._campaign_var = tk.StringVar(value="")
        self._campaign_menu = tk.OptionMenu(right, self._campaign_var, "(none)")
        self._campaign_menu.config(
            bg=C["surface2"], fg=C["fg"], activebackground=C["accent"],
            relief="flat", borderwidth=0, font=("Segoe UI", 9), width=20,
        )
        self._campaign_menu["menu"].config(bg=C["surface2"], fg=C["fg"], font=("Segoe UI", 9))
        self._campaign_menu.pack(side=tk.LEFT, padx=(4, 8))

        FlatButton(
            right, text="↺ Refresh",
            command=self._refresh_campaigns,
            bg=C["surface"], fg=C["fg_muted"],
            hover_bg=C["surface2"], hover_fg=C["accent"],
            font=("Segoe UI", 8), padx=8, pady=4,
        ).pack(side=tk.LEFT)

    def _build_toolbar(self, toolbar: tk.Frame) -> None:
        """Populate the secondary toolbar row with action buttons."""
        self._collections_btn = FlatButton(
            toolbar,
            text="\u25a6 Collections",
            command=self._toggle_collections_drawer,
            bg=C["surface"], fg=C["fg_muted"],
            hover_bg=C["surface2"], hover_fg=C["accent2"],
            font=("Segoe UI", 8, "bold"), padx=12, pady=6,
        )
        self._collections_btn.pack(side=tk.LEFT, fill=tk.Y)

        tk.Frame(toolbar, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, pady=6)

        FlatButton(
            toolbar,
            text="\u2316 Snap File",
            command=self._do_snapshot_file,
            bg=C["surface"], fg=C["fg_muted"],
            hover_bg=C["surface2"], hover_fg=C["accent2"],
            font=("Segoe UI", 8), padx=10, pady=6,
        ).pack(side=tk.LEFT, fill=tk.Y)

        FlatButton(
            toolbar,
            text="\u2316 Snap Category",
            command=self._do_snapshot_category,
            bg=C["surface"], fg=C["fg_muted"],
            hover_bg=C["surface2"], hover_fg=C["accent3"],
            font=("Segoe UI", 8), padx=10, pady=6,
        ).pack(side=tk.LEFT, fill=tk.Y)

        FlatButton(
            toolbar,
            text="\u2316 Snap Campaign",
            command=self._do_snapshot_campaign,
            bg=C["surface"], fg=C["fg_muted"],
            hover_bg=C["surface2"], hover_fg=C["green"],
            font=("Segoe UI", 8), padx=10, pady=6,
        ).pack(side=tk.LEFT, fill=tk.Y)

    def _build_panel1(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=C["surface"], width=220)
        panel.pack(side=tk.LEFT, fill=tk.Y)
        panel.pack_propagate(False)

        header = tk.Frame(panel, bg=C["surface2"], height=32)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Categories", bg=C["surface2"], fg=C["fg_muted"],
                 font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=10, pady=8)

        self._cat_tree = CategoryTree(panel, on_select=self._on_category_selected)
        self._cat_tree.pack(fill=tk.BOTH, expand=True)
        tk.Frame(parent, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)

    def _build_panel2(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=C["surface"], width=260)
        panel.pack(side=tk.LEFT, fill=tk.Y)
        panel.pack_propagate(False)

        header = tk.Frame(panel, bg=C["surface2"], height=32)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        self._panel2_header = tk.Label(
            header, text="Files", bg=C["surface2"], fg=C["fg_muted"],
            font=("Segoe UI", 8, "bold"),
        )
        self._panel2_header.pack(side=tk.LEFT, padx=10, pady=8)
        self._panel2_count = tk.Label(
            header, text="", bg=C["surface2"], fg=C["fg_faint"],
            font=("Segoe UI", 8),
        )
        self._panel2_count.pack(side=tk.RIGHT, padx=10)

        search_frame = tk.Frame(panel, bg=C["surface"], pady=4)
        search_frame.pack(fill=tk.X, padx=8)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        search_entry = tk.Entry(
            search_frame, textvariable=self._search_var,
            bg=C["surface3"], fg=C["fg"],
            insertbackground=C["accent"],
            relief="flat", borderwidth=0,
            highlightthickness=1,
            highlightbackground=C["border"],
            highlightcolor=C["accent"],
            font=("Segoe UI", 9),
        )
        search_entry.pack(fill=tk.X, ipady=4)

        inner = tk.Frame(panel, bg=C["surface"])
        inner.pack(fill=tk.BOTH, expand=True)
        self._file_list = VirtualFileList(inner, on_select=self._on_file_selected)
        self._file_list.pack(fill=tk.BOTH, expand=True)

    def _build_panel3(self, parent: tk.Frame) -> None:
        tk.Frame(parent, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)
        self._editor = PromptEditor(
            parent,
            get_readonly=self._is_readonly,
            get_prompts_root=self._get_prompts_root,
            on_status=lambda msg, lvl="ok": self.status.set(msg, lvl),
        )
        self._editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _build_collections_drawer(self, parent: tk.Frame) -> None:
        tk.Frame(parent, bg=C["border"], width=1).pack(side=tk.RIGHT, fill=tk.Y)
        self._coll_drawer = CollectionsDrawer(parent)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _is_readonly(self) -> bool:
        return False

    def _get_prompts_root(self) -> Path | None:
        return self._prompt_index.prompts_root if self._prompt_index else None

    def _on_campaign_selected(self, name: str) -> None:
        self._current_campaign = name
        self._campaign_var.set(name)
        save_path = self.sm.save_data_path()
        self._prompt_index = PromptIndex.from_campaign(save_path, name)
        cats = self._prompt_index.categories()
        self._cat_tree.load(cats)
        self._active_category = None
        self._selected_entry = None
        self._editor.clear()
        self._file_list.load([], "")
        self.status.set(f"Campaign '{name}' loaded", "ok")

    def _on_category_selected(self, key: str) -> None:
        if self._editor.has_unsaved:
            ans = tk.messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes.\nSwitch category and discard them?",
                parent=self.root
            )
            if not ans:
                self._cat_tree.set_active(self._active_category)
                return
        self._active_category = key
        entries = (self._prompt_index.entries_for_category(key)
                   if self._prompt_index else [])
        label = key.replace("_", " ").title() if key != "__root__" else "Root Files"
        self._panel2_header.config(text=label)
        self._panel2_count.config(text=f"{len(entries)} file{'s' if len(entries) != 1 else ''}")
        self._file_list.load(entries, self._search_var.get())
        self._selected_entry = None
        self._editor.clear()

    def _on_file_selected(self, entry: PromptFileEntry) -> None:
        if self._editor.has_unsaved:
            ans = tk.messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes.\nSwitch file and discard them?",
                parent=self.root
            )
            if not ans:
                return
        self._selected_entry = entry
        self._editor.load_entry(entry)

    def _on_search_changed(self, *_) -> None:
        self._file_list.filter(self._search_var.get())

    def _refresh_campaigns(self) -> None:
        save_path = self.sm.save_data_path()
        self._campaigns = discover_campaigns(save_path)
        names = self._campaigns if self._campaigns else ["(no campaigns found)"]
        menu = self._campaign_menu["menu"]
        menu.delete(0, "end")
        for name in names:
            menu.add_command(label=name,
                             command=lambda n=name: self._on_campaign_selected(n))
        self.status.set(f"Campaigns refreshed — {len(self._campaigns)} found", "info")

    def _toggle_collections_drawer(self) -> None:
        if self._collections_open:
            self._coll_drawer.pack_forget()
            self._collections_open = False
            self._collections_btn.config(fg=C["fg_muted"])
        else:
            self._coll_drawer.refresh()
            self._coll_drawer.pack(side=tk.RIGHT, fill=tk.Y, before=self._editor)
            self._collections_open = True
            self._collections_btn.config(fg=C["accent2"])

    # ── snapshot helpers ──────────────────────────────────────────────────────

    def _ask_snapshot_name(self, default: str) -> str | None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Snapshot Name")
        dialog.resizable(False, False)
        dialog.configure(bg=C["surface"])
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.update_idletasks()
        px = self.root.winfo_x() + self.root.winfo_width() // 2
        py = self.root.winfo_y() + self.root.winfo_height() // 2
        dialog.geometry(f"360x150+{px - 180}+{py - 75}")
        tk.Label(
            dialog, text="Snapshot name:", bg=C["surface"], fg=C["fg"],
            font=("Segoe UI", 9, "bold"),
        ).pack(padx=20, pady=(18, 6), anchor="w")
        name_var = tk.StringVar(value=default)
        entry = tk.Entry(
            dialog, textvariable=name_var,
            bg=C["surface3"], fg=C["fg"],
            insertbackground=C["accent"],
            selectbackground=C["accent"], selectforeground="#fff",
            relief="flat", borderwidth=0,
            highlightthickness=1, highlightbackground=C["border"],
            highlightcolor=C["accent"],
            font=("Segoe UI", 10),
        )
        entry.pack(fill=tk.X, padx=20)
        entry.select_range(0, tk.END)
        entry.focus_set()
        result: list[str | None] = [None]

        def _confirm(_=None):
            v = name_var.get().strip()
            if v:
                result[0] = v
                dialog.destroy()

        def _cancel(_=None):
            dialog.destroy()

        btn_row = tk.Frame(dialog, bg=C["surface"])
        btn_row.pack(pady=14)
        AccentButton(btn_row, text="Create Snapshot", command=_confirm, padx=10, pady=4).pack(side=tk.LEFT, padx=6)
        FlatButton(btn_row, text="Cancel", command=_cancel,
                   bg=C["surface2"], fg=C["fg_dim"],
                   hover_bg=C["surface3"], hover_fg=C["fg"],
                   font=("Segoe UI", 9), padx=10, pady=4).pack(side=tk.LEFT, padx=6)
        entry.bind("<Return>", _confirm)
        entry.bind("<Escape>", _cancel)
        dialog.wait_window()
        return result[0]

    def _do_snapshot_file(self) -> None:
        """Create a snapshot of the currently selected file."""
        if self._selected_entry is None:
            tk.messagebox.showwarning(
                "No File Selected",
                "Select a prompt file first, then create a snapshot.",
                parent=self.root,
            )
            return
        if self._prompt_index is None or not self._current_campaign:
            tk.messagebox.showwarning("No Campaign", "Load a campaign first.", parent=self.root)
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = f"{self._selected_entry.name}_{ts}"
        name = self._ask_snapshot_name(default)
        if name is None:
            return
        result = snapshot_from_file(
            entry=self._selected_entry,
            prompts_root=self._prompt_index.prompts_root,
            campaign_id=self._current_campaign,
            snapshot_name=name,
        )
        if result["success"]:
            self.status.set(f"Snapshot '{result['name']}' created — {result['file_count']} file(s)", "ok")
            tk.messagebox.showinfo(
                "Snapshot Created",
                f"File snapshot '{result['name']}' created successfully.\n{result['file_count']} file(s) saved.",
                parent=self.root,
            )
            self._coll_drawer.refresh()
        else:
            self.status.set(f"Snapshot failed: {result['error']}", "error")
            tk.messagebox.showerror("Snapshot Failed", f"Could not create snapshot:\n{result['error']}", parent=self.root)

    def _do_snapshot_category(self) -> None:
        """Create a snapshot of all files in the active category."""
        if self._active_category is None:
            tk.messagebox.showwarning(
                "No Category Selected",
                "Select a category first, then create a snapshot.",
                parent=self.root,
            )
            return
        if self._prompt_index is None or not self._current_campaign:
            tk.messagebox.showwarning("No Campaign", "Load a campaign first.", parent=self.root)
            return
        entries = self._prompt_index.entries_for_category(self._active_category)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = self._active_category if self._active_category != "__root__" else "root"
        default = f"{self._current_campaign}_{label}_{ts}"
        name = self._ask_snapshot_name(default)
        if name is None:
            return
        result = snapshot_from_category(
            category_key=self._active_category,
            entries=entries,
            prompts_root=self._prompt_index.prompts_root,
            campaign_id=self._current_campaign,
            snapshot_name=name,
        )
        if result["success"]:
            self.status.set(f"Category snapshot '{result['name']}' — {result['file_count']} file(s)", "ok")
            tk.messagebox.showinfo(
                "Snapshot Created",
                f"Category snapshot '{result['name']}' created successfully.\n{result['file_count']} file(s) saved.",
                parent=self.root,
            )
            self._coll_drawer.refresh()
        else:
            self.status.set(f"Snapshot failed: {result['error']}", "error")
            tk.messagebox.showerror("Snapshot Failed", f"Could not create snapshot:\n{result['error']}", parent=self.root)

    def _do_snapshot_campaign(self) -> None:
        """Create a full snapshot of all prompts in the current campaign."""
        if self._prompt_index is None or not self._current_campaign:
            tk.messagebox.showwarning("No Campaign", "Load a campaign first.", parent=self.root)
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = f"{self._current_campaign}_full_{ts}"
        name = self._ask_snapshot_name(default)
        if name is None:
            return
        result = snapshot_from_campaign(
            prompt_index=self._prompt_index,
            campaign_id=self._current_campaign,
            snapshot_name=name,
        )
        if result["success"]:
            self.status.set(f"Campaign snapshot '{result['name']}' — {result['file_count']} file(s)", "ok")
            tk.messagebox.showinfo(
                "Snapshot Created",
                f"Campaign snapshot '{result['name']}' created successfully.\n{result['file_count']} file(s) saved.",
                parent=self.root,
            )
            self._coll_drawer.refresh()
        else:
            self.status.set(f"Snapshot failed: {result['error']}", "error")
            tk.messagebox.showerror("Snapshot Failed", f"Could not create snapshot:\n{result['error']}", parent=self.root)


def launch_standalone():
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel(root)
    PromptManagementApp(win, on_close=root.destroy)
    root.mainloop()


if __name__ == "__main__":
    launch_standalone()
