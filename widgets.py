"""
widgets.py — Reusable tkinter widgets for Luminous AI
=====================================================

Provides three drop-in components that share the dark-mode palette
defined in colors.py:

    FlatButton   — Ghost/text-style button; subtle hover, no background fill.
    AccentButton — Solid filled button with an accent colour.
    StatusBar    — Horizontal status-bar widget pinned to a window's bottom edge.

All widgets import C from colors so they stay in sync with the rest of
the app automatically.  Pass a custom `colors` dict to override
individual colours without touching the global palette.

Usage example
-------------
    from widgets import FlatButton, AccentButton, StatusBar

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
    fg_hover:
        Foreground colour while the pointer is inside.
        Defaults to C["fg"].
    bg_hover:
        Background colour while the pointer is inside.
        Defaults to C["surface2"].
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
        """Return *hex_color* lightened by *factor* (0–1)."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.20) -> str:
        """Return *hex_color* darkened by *factor* (0–1)."""
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

    Displays a short status message on the left and an optional
    right-side segment (e.g. version string or mode indicator).
    A 1-pixel top border separates the bar from the content area.

    The bar auto-clears temporary messages after a configurable
    timeout (``auto_clear_ms``, default 5000 ms; set to 0 to disable).

    Parameters
    ----------
    parent:
        Tkinter parent widget (usually the root window or a Frame).
    height:
        Bar height in pixels.  Defaults to 24.
    font:
        Tkinter font tuple for both labels.  Defaults to ("Segoe UI", 8).
    auto_clear_ms:
        Milliseconds before a message set via ``set()`` is
        automatically cleared back to the idle text.  Pass ``0`` to
        keep the message indefinitely.  Defaults to 5000.
    idle_text:
        Text shown when no status message is active.
        Defaults to "Ready".
    colors:
        Optional dict of colour overrides.

    Public API
    ----------
    .set(message, *, level="info")
        Set the status message.  *level* controls the text colour:
        "info"    → C["fg_dim"]   (default, dimmed white)
        "success" → C["green"]
        "warning" → C["accent3"]  (amber)
        "error"   → C["red"]
    .set_right(text)
        Update the right-side label.
    .clear()
        Reset to the idle text immediately.
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
