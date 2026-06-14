#!/usr/bin/env python3
"""
Luminous AI — Settings Section
"""
import tkinter as tk
import platform
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


class SettingsApp:
    def __init__(self, root: tk.Tk, on_close=None):
        self.root = root
        self._on_close = on_close
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

        bar = CustomTitleBar(root, root, title="Luminous AI \u2014 Settings")
        bar.pack(fill=tk.X)

        nav = tk.Frame(root, bg=C["bg"])
        nav.pack(fill=tk.X, padx=20, pady=(8, 0))
        back_btn = tk.Label(nav, text="\u2190 Back to Hub", bg=C["bg"], fg=C["fg_dim"],
                            font=("Segoe UI", 9), cursor="hand2")
        back_btn.pack(side=tk.LEFT)
        back_btn.bind("<Enter>", lambda e: back_btn.config(fg=C["accent"]))
        back_btn.bind("<Leave>", lambda e: back_btn.config(fg=C["fg_dim"]))
        back_btn.bind("<Button-1>", lambda e: self._back_to_hub())

        header = tk.Frame(root, bg=C["bg"])
        header.pack(fill=tk.X, padx=32, pady=(12, 8))
        tk.Label(header, text="Settings", bg=C["bg"], fg=C["fg"],
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(header, text="Configure application preferences and paths",
                 bg=C["bg"], fg=C["fg_dim"],
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        tk.Frame(root, bg=C["border"], height=1).pack(fill=tk.X, padx=32, pady=(8, 16))

        content = tk.Frame(root, bg=C["bg"])
        content.pack(fill=tk.BOTH, expand=True, padx=32, pady=(0, 28))
        tk.Label(content, text="Settings will be implemented here.",
                 bg=C["bg"], fg=C["fg_dim"], font=("Segoe UI", 11)).pack(expand=True)

    def _back_to_hub(self):
        if self._on_close:
            self._on_close()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    SettingsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
