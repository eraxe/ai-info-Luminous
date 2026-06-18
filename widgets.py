#!/usr/bin/env python3
"""
widgets.py — Reusable tkinter widgets for Luminous AI
=====================================================

Provides four drop-in components that share the dark-mode palette
defined in colors.py:

    FlatButton      — Ghost/text-style button; subtle hover, no background fill.
    AccentButton    — Solid filled button with an accent colour.
    StatusBar       — Horizontal status-bar widget pinned to a window's bottom edge.
    CustomTitleBar  — Frameless title bar shared by every Luminous window.

All widgets import C from colors so they stay in sync with the rest of
the app automatically.  Pass a custom `colors` dict to override
individual colours without touching the global palette.

Usage example
-------------
    from widgets import FlatButton, AccentButton, StatusBar, CustomTitleBar

    root = tk.Tk()

    flat = FlatButton(root, text="Cancel", command=root.destroy)
    flat.pack(side=tk.LEFT, padx=4)

    ok = AccentButton(root, text="Confirm", command=root.destroy)
    ok.pack(side=tk.LEFT, padx=4)

    bar = StatusBar(root)
    bar.pack(fill=tk.X, side=tk.BOTTOM)
    bar.set("Ready")

    root.mainloop()
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from colors import C  # Luminous palette  (#0d0f14 bg, #7c6af7 accent, etc.)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _merge(base: dict, override: Optional[dict]) -> dict:
    """Return *base* updated with any keys present in *override*."""
    if override:
        return {**base, **override}
    return base


# ---------------------------------------------------------------------------
# FlatButton
# ---------------------------------------------------------------------------

class FlatButton(tk.Label):
    """Ghost / text-style button.

    Renders as plain text with no background fill.  On hover the text
    brightens and a subtle surface tint appears; on press the surface
    deepens slightly to give tactile feedback.

    Parameters
    ----------
    parent:
        Tkinter parent widget.
    text:
        Button label.
    command:
        Callable invoked on click.  Defaults to None (no-op).
    fg:
        Normal foreground colour.  Defaults to C["fg_dim"].
    fg_hover / hover_fg:
        Foreground colour while the pointer is inside.
        Defaults to C["fg"].  Both spellings accepted.
    bg_hover / hover_bg:
        Background colour while the pointer is inside.
        Defaults to C["surface2"].  Both spellings accepted.
    bg_active:
        Background colour while the mouse button is held down.
        Defaults to C["surface3"].
    font:
        Tkinter font tuple.  Defaults to ("Segoe UI", 9).
    padx / pady:
        Internal padding.  Defaults to 14 / 6.
    colors:
        Optional dict of colour overrides applied on top of the
        Luminous palette.  Only the keys you supply are changed.
    """

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "Button",
        command: Optional[Callable] = None,
        fg: Optional[str] = None,
        fg_hover: Optional[str] = None,
        bg_hover: Optional[str] = None,
        bg_active: Optional[str] = None,
        font: tuple = ("Segoe UI", 9),
        padx: int = 14,
        pady: int = 6,
        colors: Optional[dict] = None,
        **kw,
    ):
        palette = _merge(C, colors)
        # Support both spellings: hover_bg/hover_fg (legacy) and bg_hover/fg_hover (canonical)
        if bg_hover is None and "hover_bg" in kw:
            bg_hover = kw.pop("hover_bg")
        else:
            kw.pop("hover_bg", None)
        if fg_hover is None and "hover_fg" in kw:
            fg_hover = kw.pop("hover_fg")
        else:
            kw.pop("hover_fg", None)
        self._fg_normal = fg or palette["fg_dim"]
        self._fg_hover  = fg_hover  or palette["fg"]
        self._bg_normal = kw.pop("bg", palette["bg"])
        self._bg_hover  = bg_hover  or palette["surface2"]
        self._bg_active = bg_active or palette["surface3"]
        self._command   = command

        super().__init__(
            parent,
            text=text,
            fg=self._fg_normal,
            bg=self._bg_normal,
            font=font,
            padx=padx,
            pady=pady,
            cursor="hand2",
            **kw,
        )

        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_enter(self, _=None) -> None:
        self.config(fg=self._fg_hover, bg=self._bg_hover)

    def _on_leave(self, _=None) -> None:
        self.config(fg=self._fg_normal, bg=self._bg_normal)

    def _on_press(self, _=None) -> None:
        self.config(bg=self._bg_active)

    def _on_release(self, _=None) -> None:
        self.config(bg=self._bg_hover)
        if self._command:
            self.after(60, self._command)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def configure_command(self, command: Callable) -> None:
        """Replace the click handler at runtime."""
        self._command = command

    def set_text(self, text: str) -> None:
        """Update the button label."""
        self.config(text=text)


# ---------------------------------------------------------------------------
# AccentButton
# ---------------------------------------------------------------------------

class AccentButton(tk.Label):
    """Solid filled button with an accent colour.

    Used for primary / confirmation actions.  Ships with four accent
    presets that mirror the section accents in main.py:

        "purple"   → C["accent"]   (#7c6af7) — default
        "blue"     → C["accent2"]  (#38bdf8)
        "amber"    → C["accent3"]  (#f59e0b)
        "green"    → C["green"]    (#22d3a0)
        "red"      → C["red"]      (#f87171)

    Parameters
    ----------
    parent:
        Tkinter parent widget.
    text:
        Button label.
    command:
        Callable invoked on click.  Defaults to None (no-op).
    accent:
        One of the preset name strings *or* any valid hex colour string.
        Defaults to "purple".
    fg:
        Foreground (text) colour.  Defaults to "#ffffff".
    font:
        Tkinter font tuple.  Defaults to ("Segoe UI", 9, "bold").
    padx / pady:
        Internal padding.  Defaults to 18 / 7.
    colors:
        Optional dict of colour overrides applied on top of the
        Luminous palette.
    """

    _ACCENT_MAP = {
        "purple": "accent",
        "blue":   "accent2",
        "amber":  "accent3",
        "green":  "green",
        "red":    "red",
    }

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "OK",
        command: Optional[Callable] = None,
        accent: str = "purple",
        fg: str = "#ffffff",
        font: tuple = ("Segoe UI", 9, "bold"),
        padx: int = 18,
        pady: int = 7,
        colors: Optional[dict] = None,
        **kw,
    ):
        palette = _merge(C, colors)

        # Resolve accent to a hex colour
        key = self._ACCENT_MAP.get(accent)
        bg_hex = palette[key] if key else accent

        self._bg_normal = bg_hex
        self._bg_hover  = self._lighten(bg_hex, factor=0.15)
        self._bg_active = self._darken(bg_hex,  factor=0.20)
        self._fg        = fg
        self._command   = command

        super().__init__(
            parent,
            text=text,
            fg=fg,
            bg=self._bg_normal,
            font=font,
            padx=padx,
            pady=pady,
            cursor="hand2",
            **kw,
        )

        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    # ------------------------------------------------------------------
    # Colour arithmetic (pure Python, no third-party libs)
    # ------------------------------------------------------------------

    @staticmethod
    def _lighten(hex_color: str, factor: float = 0.15) -> str:
        """Return *hex_color* lightened by *factor* (0-1)."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.20) -> str:
        """Return *hex_color* darkened by *factor* (0-1)."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_enter(self, _=None) -> None:
        self.config(bg=self._bg_hover)

    def _on_leave(self, _=None) -> None:
        self.config(bg=self._bg_normal)

    def _on_press(self, _=None) -> None:
        self.config(bg=self._bg_active)

    def _on_release(self, _=None) -> None:
        self.config(bg=self._bg_hover)
        if self._command:
            self.after(60, self._command)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def configure_command(self, command: Callable) -> None:
        """Replace the click handler at runtime."""
        self._command = command

    def set_text(self, text: str) -> None:
        """Update the button label."""
        self.config(text=text)

    def set_accent(self, accent: str) -> None:
        """Swap the accent colour at runtime (preset name or hex string)."""
        key = self._ACCENT_MAP.get(accent)
        bg_hex = C[key] if key else accent
        self._bg_normal = bg_hex
        self._bg_hover  = self._lighten(bg_hex, factor=0.15)
        self._bg_active = self._darken(bg_hex,  factor=0.20)
        self.config(bg=self._bg_normal)


# ---------------------------------------------------------------------------
# StatusBar
# ---------------------------------------------------------------------------

class StatusBar(tk.Frame):
    """Horizontal status bar pinned to the bottom of a window.

    Shows a primary message on the left and an optional auxiliary label
    on the right.  Messages auto-clear after ``auto_clear_ms``
    milliseconds (default 5 s).  Call ``set()`` with a ``level`` keyword
    to colour-code the message.

    Parameters
    ----------
    parent:
        Tkinter parent widget (usually the root window).
    height:
        Bar height in pixels.  Defaults to 24.
    font:
        Tkinter font tuple.  Defaults to ("Segoe UI", 8).
    auto_clear_ms:
        Time in milliseconds before the status text resets to
        ``idle_text``.  Pass 0 to disable auto-clear.  Defaults to 5000.
    idle_text:
        Text shown when no message is active.  Defaults to "Ready".
    colors:
        Optional dict of colour overrides.
    """

    _LEVEL_COLORS = {
        "info":    "fg_dim",
        "success": "green",
        "warning": "accent3",
        "error":   "red",
    }

    def __init__(
        self,
        parent: tk.Widget,
        height: int = 24,
        font: tuple = ("Segoe UI", 8),
        auto_clear_ms: int = 5000,
        idle_text: str = "Ready",
        colors: Optional[dict] = None,
        **kw,
    ):
        palette = _merge(C, colors)
        self._palette       = palette
        self._auto_clear_ms = auto_clear_ms
        self._idle_text     = idle_text
        self._clear_job: Optional[str] = None  # after() id

        super().__init__(
            parent,
            bg=palette["surface"],
            height=height,
            highlightbackground=palette["border"],
            highlightthickness=1,
            **kw,
        )
        self.pack_propagate(False)

        # Top separator line
        tk.Frame(self, bg=palette["border"], height=1).pack(fill=tk.X, side=tk.TOP)

        # Left status label
        self._left_var = tk.StringVar(value=idle_text)
        self._left_lbl = tk.Label(
            self,
            textvariable=self._left_var,
            bg=palette["surface"],
            fg=palette["fg_dim"],
            font=font,
            anchor="w",
        )
        self._left_lbl.pack(side=tk.LEFT, padx=(10, 0), fill=tk.Y)

        # Right auxiliary label
        self._right_var = tk.StringVar(value="")
        self._right_lbl = tk.Label(
            self,
            textvariable=self._right_var,
            bg=palette["surface"],
            fg=palette["fg_muted"],
            font=font,
            anchor="e",
        )
        self._right_lbl.pack(side=tk.RIGHT, padx=(0, 10), fill=tk.Y)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set(self, message: str, *, level: str = "info") -> None:
        """Display *message* in the status bar.

        Parameters
        ----------
        message:
            The text to display.
        level:
            Colour level — one of "info", "success", "warning", "error".
        """
        color_key = self._LEVEL_COLORS.get(level, "fg_dim")
        fg = self._palette[color_key]
        self._left_var.set(message)
        self._left_lbl.config(fg=fg)

        # Cancel any previous auto-clear job
        if self._clear_job:
            self._left_lbl.after_cancel(self._clear_job)
            self._clear_job = None

        if self._auto_clear_ms > 0:
            self._clear_job = self._left_lbl.after(
                self._auto_clear_ms, self.clear
            )

    def set_right(self, text: str) -> None:
        """Update the right-side auxiliary label."""
        self._right_var.set(text)

    def clear(self) -> None:
        """Reset the status message to the idle text immediately."""
        self._clear_job = None
        self._left_var.set(self._idle_text)
        self._left_lbl.config(fg=self._palette["fg_dim"])


# ---------------------------------------------------------------------------
# CustomTitleBar
# ---------------------------------------------------------------------------

class CustomTitleBar(tk.Frame):
    """Canonical frameless title bar shared by every Luminous window.

    Replaces the three divergent inline copies that previously lived in
    ``main.py``, ``about.py``, and ``ai_characters.py``.

    Fixes consolidated from all three variants:
    - ``_norm_geo`` guard: never crashes on first maximize (was broken in
      ``main.py`` and ``about.py`` which read ``self._norm_geo`` without
      an ``hasattr`` check).
    - Windows-aware minimize: ``overrideredirect`` trick from ``main.py``
      preserved and isolated so it does not affect other platforms.
    - Drag guard: move is silently ignored while the window is maximised
      (from ``ai_characters.py``).
    - Double-click to toggle maximize (from ``ai_characters.py``).
    - Window controls use ``FlatButton`` for consistent hover styling
      (from ``ai_characters.py``).

    Parameters
    ----------
    parent:
        The widget that receives this bar (usually the root window itself).
    root:
        The ``tk.Tk`` / ``tk.Toplevel`` whose geometry and state are
        controlled.
    title:
        Text shown in the title area.
    on_close:
        Callable invoked when the ✕ button is clicked.  Defaults to
        ``root.destroy``.
    on_back:
        If provided, a "◆ Hub" back-button is rendered on the far left
        and calls this callable when clicked.  Leave ``None`` to omit.
    grip_widget:
        Optional resize-grip widget that is hidden while the window is
        maximised and re-shown on restore.
    colors:
        Optional dict of colour overrides merged on top of ``C``.
    """

    def __init__(
        self,
        parent: tk.Widget,
        root: tk.Misc,
        title: str = "",
        on_close: Optional[Callable] = None,
        on_back: Optional[Callable] = None,
        grip_widget: Optional[tk.Widget] = None,
        colors: Optional[dict] = None,
    ):
        palette = _merge(C, colors)
        super().__init__(parent, bg=palette["bg"], height=36)
        self.pack_propagate(False)

        self._root      = root
        self._palette   = palette
        self._is_max    = False
        self._norm_geo  = ""          # set on first maximize
        self._grip      = grip_widget
        self._on_close  = on_close or root.destroy

        # ── optional back button ────────────────────────────────────────
        if on_back:
            back = tk.Label(
                self, text="\u2b21 Hub",
                bg=palette["bg"], fg=palette["fg_muted"],
                font=("Segoe UI", 8), padx=10, pady=6, cursor="hand2",
            )
            back.pack(side=tk.LEFT)
            back.bind("<Enter>", lambda e: back.config(fg=palette["accent"]))
            back.bind("<Leave>", lambda e: back.config(fg=palette["fg_muted"]))
            back.bind("<Button-1>", lambda e: on_back())
            tk.Frame(self, bg=palette["border"], width=1).pack(
                side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=6
            )

        # ── title label ─────────────────────────────────────────────────
        lbl = tk.Label(
            self, text=f" {title}",
            bg=palette["bg"], fg=palette["fg_dim"],
            font=("Segoe UI", 9, "bold"),
        )
        lbl.pack(side=tk.LEFT, padx=(4 if on_back else 12))

        # Drag and double-click bindings on both the bar frame and the label
        for w in (self, lbl):
            w.bind("<ButtonPress-1>",   self._start_move)
            w.bind("<B1-Motion>",       self._do_move)
            w.bind("<Double-Button-1>", lambda e: self._toggle_max())

        # ── window control buttons (right-to-left pack order) ───────────
        btns = tk.Frame(self, bg=palette["bg"])
        btns.pack(side=tk.RIGHT, fill=tk.Y)

        FlatButton(
            btns, text="\u2715", command=self._close,
            bg=palette["bg"], bg_hover=palette["red"],
            fg=palette["fg"], fg_hover="#ffffff",
            padx=14, pady=6,
        ).pack(side=tk.RIGHT, fill=tk.Y)

        self._max_btn = FlatButton(
            btns, text="\u2610", command=self._toggle_max,
            bg=palette["bg"], bg_hover=palette["surface3"],
            fg=palette["fg"], fg_hover=palette["fg"],
            padx=14, pady=6,
        )
        self._max_btn.pack(side=tk.RIGHT, fill=tk.Y)

        FlatButton(
            btns, text="\u2014", command=self._minimize,
            bg=palette["bg"], bg_hover=palette["surface3"],
            fg=palette["fg"], fg_hover=palette["fg"],
            padx=14, pady=6,
        ).pack(side=tk.RIGHT, fill=tk.Y)

    # ------------------------------------------------------------------
    # Drag-to-move
    # ------------------------------------------------------------------

    def _start_move(self, event: tk.Event) -> None:
        if self._is_max:
            return
        self._root._drag_x = event.x  # type: ignore[attr-defined]
        self._root._drag_y = event.y  # type: ignore[attr-defined]

    def _do_move(self, event: tk.Event) -> None:
        if self._is_max:
            return
        dx = event.x - getattr(self._root, "_drag_x", event.x)
        dy = event.y - getattr(self._root, "_drag_y", event.y)
        x  = self._root.winfo_x() + dx
        y  = self._root.winfo_y() + dy
        self._root.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Window controls
    # ------------------------------------------------------------------

    def _minimize(self) -> None:
        import platform as _platform
        if _platform.system() == "Windows":
            self._root.overrideredirect(False)
            self._root.iconify()
            self._root.bind(
                "<Map>",
                lambda e: (
                    self._root.overrideredirect(True),
                    self._root.unbind("<Map>"),
                ),
            )
        else:
            self._root.iconify()

    def _toggle_max(self) -> None:
        if self._is_max:
            # Restore — only geometry if we have a saved value
            if self._norm_geo:
                self._root.geometry(self._norm_geo)
            self._is_max = False
            self._max_btn.set_text("\u2610")
            if self._grip:
                self._grip.place(relx=1.0, rely=1.0, anchor="se")
        else:
            self._norm_geo = self._root.geometry()
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
            self._root.geometry(f"{sw}x{sh}+0+0")
            self._is_max = True
            self._max_btn.set_text("\u2750")
            if self._grip:
                self._grip.place_forget()

    def _close(self) -> None:
        self._on_close()
