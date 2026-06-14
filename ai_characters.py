#!/usr/bin/env python3
"""
Luminous AI — AI Characters Section
Previously the main HubApp. Launched from main.py hub.
"""
import tkinter as tk
import platform
import subprocess
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
        self._mk_btn(btns, "—", self._minimize, C["bg"])
        self._max_btn = self._mk_btn(btns, "☐", self._toggle_max, C["bg"])
        self._mk_btn(btns, "✕", root.destroy, C["bg"], hover_bg=C["red"])

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
            self._max_btn.config(text="☐")
        else:
            self._norm_geo = self._root.geometry()
            sw, sh = self._root.winfo_screenwidth(), self._root.winfo_screenheight()
            self._root.geometry(f"{sw}x{sh}+0+0")
            self._is_max = True
            self._max_btn.config(text="❐")


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
        arrow = tk.Label(inner, text="→", bg=C["surface"], fg=C["fg_muted"],
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


class HubApp:
    SECTIONS = [
        {
            "icon":     "◆",
            "title":    "AI Characters",
            "subtitle": "Browse, inspect and edit NPC character JSON files",
            "module":   "ai_characters.py",
            "accent":   C["accent"],
        },
        {
            "icon":     "⊞",
            "title":    "Prompt Management",
            "subtitle": "Manage, organise and export prompt templates",
            "module":   "prompt_management.py",
            "accent":   C["accent2"],
        },
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        root.overrideredirect(True)
        root.configure(bg=C["bg"])
        root.geometry("900x640")
        root.resizable(True, True)

        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - 900) // 2
        y = (sh - 640) // 2
        root.geometry(f"900x640+{x}+{y}")

        bar = CustomTitleBar(root, root, title="Luminous AI — AI Characters")
        bar.pack(fill=tk.X)

        # Back button row
        nav = tk.Frame(root, bg=C["bg"])
        nav.pack(fill=tk.X, padx=20, pady=(8, 0))
        back_btn = tk.Label(nav, text="← Back to Hub", bg=C["bg"], fg=C["fg_dim"],
                            font=("Segoe UI", 9), cursor="hand2")
        back_btn.pack(side=tk.LEFT)
        back_btn.bind("<Enter>", lambda e: back_btn.config(fg=C["accent"]))
        back_btn.bind("<Leave>", lambda e: back_btn.config(fg=C["fg_dim"]))
        back_btn.bind("<Button-1>", lambda e: self._back_to_hub())

        header = tk.Frame(root, bg=C["bg"])
        header.pack(fill=tk.X, padx=32, pady=(12, 8))
        tk.Label(header, text="AI Characters", bg=C["bg"], fg=C["fg"],
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(header, text="Browse, inspect and edit NPC character JSON files",
                 bg=C["bg"], fg=C["fg_dim"],
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        tk.Frame(root, bg=C["border"], height=1).pack(fill=tk.X, padx=32, pady=(8, 16))

        content = tk.Frame(root, bg=C["bg"])
        content.pack(fill=tk.BOTH, expand=True, padx=32, pady=(0, 28))
        tk.Label(content, text="AI Characters viewer will be implemented here.",
                 bg=C["bg"], fg=C["fg_dim"], font=("Segoe UI", 11)).pack(expand=True)

    def _back_to_hub(self):
        self.root.destroy()
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        subprocess.Popen([sys.executable, path])


def main():
    root = tk.Tk()
    HubApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
