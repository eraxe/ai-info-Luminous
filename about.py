#!/usr/bin/env python3
"""
Luminous AI — About & Updates Section
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

APP_VERSION = "1.0.0"


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


class AboutApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.overrideredirect(True)
        root.configure(bg=C["bg"])
        root.geometry("680x420")
        root.resizable(False, False)

        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - 680) // 2
        y = (sh - 420) // 2
        root.geometry(f"680x420+{x}+{y}")

        bar = CustomTitleBar(root, root, title="Luminous AI — About & Updates")
        bar.pack(fill=tk.X)

        nav = tk.Frame(root, bg=C["bg"])
        nav.pack(fill=tk.X, padx=20, pady=(8, 0))
        back_btn = tk.Label(nav, text="← Back to Hub", bg=C["bg"], fg=C["fg_dim"],
                            font=("Segoe UI", 9), cursor="hand2")
        back_btn.pack(side=tk.LEFT)
        back_btn.bind("<Enter>", lambda e: back_btn.config(fg=C["accent"]))
        back_btn.bind("<Leave>", lambda e: back_btn.config(fg=C["fg_dim"]))
        back_btn.bind("<Button-1>", lambda e: self._back_to_hub())

        # Content
        body = tk.Frame(root, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=48, pady=24)

        tk.Label(body, text="◎  Luminous AI", bg=C["bg"], fg=C["green"],
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(body, text=f"Version {APP_VERSION}", bg=C["bg"], fg=C["fg_dim"],
                 font=("Segoe UI", 11)).pack(anchor="w", pady=(4, 0))

        tk.Frame(body, bg=C["border"], height=1).pack(fill=tk.X, pady=16)

        tk.Label(body, text="A desktop hub for managing AI character data,\nprompt templates and NPC configurations.",
                 bg=C["bg"], fg=C["fg"], font=("Segoe UI", 10),
                 justify="left").pack(anchor="w")

        tk.Frame(body, bg=C["border"], height=1).pack(fill=tk.X, pady=16)

        update_btn = tk.Label(body, text="  Check for Updates  ",
                              bg=C["surface2"], fg=C["accent2"],
                              font=("Segoe UI", 10, "bold"),
                              cursor="hand2", padx=8, pady=6,
                              highlightbackground=C["border"], highlightthickness=1)
        update_btn.pack(anchor="w")
        update_btn.bind("<Enter>", lambda e: update_btn.config(bg=C["surface3"]))
        update_btn.bind("<Leave>", lambda e: update_btn.config(bg=C["surface2"]))
        update_btn.bind("<Button-1>", lambda e: self._check_updates())

        self._status_lbl = tk.Label(body, text="", bg=C["bg"], fg=C["fg_dim"],
                                    font=("Segoe UI", 9))
        self._status_lbl.pack(anchor="w", pady=(6, 0))

    def _check_updates(self):
        self._status_lbl.config(text="Update check not yet connected to a release endpoint.",
                                fg=C["fg_muted"])

    def _back_to_hub(self):
        self.root.destroy()
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        subprocess.Popen([sys.executable, path])


def main():
    root = tk.Tk()
    AboutApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
