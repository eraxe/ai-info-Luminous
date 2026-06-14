#!/usr/bin/env python3
"""
Luminous AI — Main Launcher
Entry point: shows hub with section buttons, each opens its own page.
"""
import tkinter as tk
import tkinter.messagebox as mb
import platform
import subprocess
import threading
import sys
import os

C = {
    "bg":       "#0d0f14",
    "surface":  "#13161e",
    "surface2": "#1a1e29",
    "surface3": "#212537",
    "fg":       "#e2e8f0",
    "fg_dim":   "#7b879e",
    "fg_muted": "#445069",
    "accent":   "#7c6af7",
    "accent2":  "#38bdf8",
    "accent3":  "#f59e0b",
    "green":    "#22d3a0",
    "red":      "#f87171",
    "border":   "#252a38",
}


class CustomTitleBar(tk.Frame):
    def __init__(self, parent, root, title=""):
        super().__init__(parent, bg=C["bg"], height=36)
        self.pack_propagate(False)
        self._root = root
        self._is_max = False
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<B1-Motion>", self._do_move)
        lbl = tk.Label(self, text=f" {title}", bg=C["bg"], fg=C["fg_dim"],
                       font=("Segoe UI", 9, "bold"))
        lbl.pack(side=tk.LEFT, padx=12)
        lbl.bind("<ButtonPress-1>", self._start_move)
        lbl.bind("<B1-Motion>", self._do_move)
        btns = tk.Frame(self, bg=C["bg"])
        btns.pack(side=tk.RIGHT, fill=tk.Y)
        self._mk_btn(btns, "\u2014", self._minimize, C["bg"])
        self._max_btn = self._mk_btn(btns, "\u2610", self._toggle_max, C["bg"])
        self._mk_btn(btns, "\u2715", root.destroy, C["bg"], hover_bg=C["red"])

    def _mk_btn(self, parent, text, cmd, bg, hover_bg=None):
        hbg = hover_bg or C["surface3"]
        lbl = tk.Label(parent, text=text, bg=bg, fg=C["fg"],
                       font=("Segoe UI", 9), padx=14, pady=6, cursor="hand2")
        lbl.pack(side=tk.LEFT, fill=tk.Y)
        lbl.bind("<Enter>", lambda e: lbl.config(bg=hbg))
        lbl.bind("<Leave>", lambda e: lbl.config(bg=bg))
        lbl.bind("<Button-1>", lambda e: cmd())
        return lbl

    def _start_move(self, e):
        if not self._is_max:
            self._root.x, self._root.y = e.x, e.y

    def _do_move(self, e):
        if not self._is_max:
            x = self._root.winfo_x() + e.x - self._root.x
            y = self._root.winfo_y() + e.y - self._root.y
            self._root.geometry(f"+{x}+{y}")

    def _minimize(self):
        if platform.system() == "Windows":
            self._root.overrideredirect(False)
            self._root.iconify()
            self._root.bind("<Map>", lambda e: (
                self._root.overrideredirect(True), self._root.unbind("<Map>")))
        else:
            self._root.iconify()

    def _toggle_max(self):
        if self._is_max:
            self._root.geometry(self._norm_geo)
            self._is_max = False
            self._max_btn.config(text="\u2610")
        else:
            self._norm_geo = self._root.geometry()
            sw, sh = self._root.winfo_screenwidth(), self._root.winfo_screenheight()
            self._root.geometry(f"{sw}x{sh}+0+0")
            self._is_max = True
            self._max_btn.config(text="\u2750")


class NavCard(tk.Frame):
    def __init__(self, parent, icon, title, subtitle, command, accent=C["accent"], **kw):
        super().__init__(parent, bg=C["surface"], cursor="hand2",
                         highlightbackground=C["border"], highlightthickness=1, **kw)
        self._cmd = command
        self._accent = accent
        self._indicator = tk.Frame(self, bg=accent, height=3)
        self._indicator.pack(fill=tk.X)
        inner = tk.Frame(self, bg=C["surface"])
        inner.pack(fill=tk.BOTH, expand=True, padx=28, pady=24)
        tk.Label(inner, text=icon, bg=C["surface"], fg=accent,
                 font=("Segoe UI", 32)).pack(anchor="w")
        tk.Label(inner, text=title, bg=C["surface"], fg=C["fg"],
                 font=("Segoe UI", 14, "bold"), anchor="w").pack(anchor="w", pady=(10, 2))
        tk.Label(inner, text=subtitle, bg=C["surface"], fg=C["fg_dim"],
                 font=("Segoe UI", 9), wraplength=200, justify="left",
                 anchor="w").pack(anchor="w")
        arrow = tk.Label(inner, text="\u2192", bg=C["surface"], fg=C["fg_muted"],
                         font=("Segoe UI", 14))
        arrow.pack(anchor="e", pady=(16, 0))
        for w in self.winfo_children() + inner.winfo_children() + [inner, arrow]:
            try:
                w.bind("<Enter>", self._hover_on)
                w.bind("<Leave>", self._hover_off)
                w.bind("<Button-1>", self._click)
            except Exception:
                pass
        self.bind("<Enter>", self._hover_on)
        self.bind("<Leave>", self._hover_off)
        self.bind("<Button-1>", self._click)

    def _hover_on(self, _=None):
        self.config(bg=C["surface2"], highlightbackground=self._accent)
        for w in self.winfo_children():
            if isinstance(w, tk.Frame) and w != self._indicator:
                w.config(bg=C["surface2"])
                for c in w.winfo_children():
                    try:
                        c.config(bg=C["surface2"])
                    except Exception:
                        pass

    def _hover_off(self, _=None):
        self.config(bg=C["surface"], highlightbackground=C["border"])
        for w in self.winfo_children():
            if isinstance(w, tk.Frame) and w != self._indicator:
                w.config(bg=C["surface"])
                for c in w.winfo_children():
                    try:
                        c.config(bg=C["surface"])
                    except Exception:
                        pass

    def _click(self, _=None):
        if self._cmd:
            self.after(80, self._cmd)


def _open_section(script_name: str):
    """Launch a section script as a separate process; show error popup if it crashes."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    if not os.path.exists(path):
        mb.showinfo("Coming Soon", f"Section '{script_name}' is not yet implemented.")
        return

    proc = subprocess.Popen(
        [sys.executable, path],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )

    def _watch():
        _, stderr = proc.communicate()
        if proc.returncode != 0 and stderr:
            msg = stderr.decode(errors="replace").strip()
            # schedule messagebox on main thread
            try:
                import tkinter as _tk
                r = _tk.Tk()
                r.withdraw()
                mb.showerror("Launch Error", f"{script_name} crashed:\n\n{msg}", parent=r)
                r.destroy()
            except Exception:
                pass

    threading.Thread(target=_watch, daemon=True).start()


class LuminousHub:
    SECTIONS = [
        {
            "icon":     "\u25c6",
            "title":    "AI Characters",
            "subtitle": "Browse, inspect and edit NPC character JSON files",
            "script":   "ai_characters.py",
            "accent":   C["accent"],
        },
        {
            "icon":     "\u229e",
            "title":    "Prompt Management",
            "subtitle": "Manage, organise and export prompt templates",
            "script":   "prompt_management.py",
            "accent":   C["accent2"],
        },
        {
            "icon":     "\u2699",
            "title":    "Settings",
            "subtitle": "Configure application preferences and paths",
            "script":   "settings.py",
            "accent":   C["accent3"],
        },
        {
            "icon":     "\u25ce",
            "title":    "About & Updates",
            "subtitle": "App info, version details and update checker",
            "script":   "about.py",
            "accent":   C["green"],
        },
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        root.overrideredirect(True)
        root.configure(bg=C["bg"])
        root.geometry("780x520")
        root.resizable(False, False)

        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - 780) // 2
        y = (sh - 520) // 2
        root.geometry(f"780x520+{x}+{y}")

        bar = CustomTitleBar(root, root, title="Luminous AI \u2014 Hub")
        bar.pack(fill=tk.X)

        header = tk.Frame(root, bg=C["bg"])
        header.pack(fill=tk.X, padx=32, pady=(24, 8))
        tk.Label(header, text="Luminous AI", bg=C["bg"], fg=C["fg"],
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(header, text="Select a section to get started", bg=C["bg"], fg=C["fg_dim"],
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        tk.Frame(root, bg=C["border"], height=1).pack(fill=tk.X, padx=32, pady=(8, 20))

        grid = tk.Frame(root, bg=C["bg"])
        grid.pack(fill=tk.BOTH, expand=True, padx=32, pady=(0, 28))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        for i, sec in enumerate(self.SECTIONS):
            row, col = divmod(i, 2)
            script = sec["script"]
            card = NavCard(
                grid,
                icon=sec["icon"],
                title=sec["title"],
                subtitle=sec["subtitle"],
                command=lambda s=script: _open_section(s),
                accent=sec["accent"],
            )
            card.grid(row=row, column=col, sticky="nsew",
                      padx=(0, 8) if col == 0 else (8, 0),
                      pady=(0, 8) if row == 0 else (8, 0))


def main():
    root = tk.Tk()
    LuminousHub(root)
    root.mainloop()


if __name__ == "__main__":
    main()
