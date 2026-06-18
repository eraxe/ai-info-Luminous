"""
colors.py — Color constants for Luminous AI

Two color systems:
  C           — Hex palette used by every Tkinter widget (matched to main.py).
  ANSI        — ANSI escape codes for terminal / CLI output.
  ColorScheme — Convenience dataclass that groups both.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Tk / GUI hex palette  (mirrors the `C` dict in main.py exactly)
# ---------------------------------------------------------------------------
C: dict[str, str] = {
    # ── Backgrounds ───────────────────────────────────────────────────────────
    "bg":          "#0d0f14",   # deepest background
    "surface":     "#13161e",   # card / panel surface
    "surface2":    "#1a1e29",   # hover / elevated surface
    "surface3":    "#212537",   # pressed / deepest surface layer
    # ── Foreground ───────────────────────────────────────────────────────────
    "fg":          "#e2e8f0",   # primary text
    "fg_dim":      "#7b879e",   # secondary / label text
    "fg_muted":    "#445069",   # tertiary / placeholder text
    "fg_faint":    "#2d3a4f",   # quaternary / decorative text (barely visible)
    # ── Accents ─────────────────────────────────────────────────────────────
    "accent":      "#7c6af7",   # purple — AI Characters
    "accent2":     "#38bdf8",   # sky blue — Prompt Management
    "accent3":     "#f59e0b",   # amber — Settings
    # ── Semantic ─────────────────────────────────────────────────────────────
    "green":       "#22d3a0",   # success / About & Updates
    "red":         "#f87171",   # error / close button hover
    # ── Chrome ──────────────────────────────────────────────────────────────
    "border":      "#252a38",   # widget borders / dividers
}

# ---------------------------------------------------------------------------
# ANSI escape codes for terminal / CLI printing
# ---------------------------------------------------------------------------
class ANSI:
    """ANSI SGR escape sequences."""
    RESET    = "\033[0m"

    # ── Styles ──────────────────────────────────────────────────────────────
    BOLD      = "\033[1m"
    DIM       = "\033[2m"
    ITALIC    = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK     = "\033[5m"
    REVERSE   = "\033[7m"
    STRIKE    = "\033[9m"

    # ── Standard foreground colors ───────────────────────────────────────────
    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

    # ── Bright foreground colors ─────────────────────────────────────────────
    BRIGHT_BLACK   = "\033[90m"
    BRIGHT_RED     = "\033[91m"
    BRIGHT_GREEN   = "\033[92m"
    BRIGHT_YELLOW  = "\033[93m"
    BRIGHT_BLUE    = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN    = "\033[96m"
    BRIGHT_WHITE   = "\033[97m"

    # ── Standard background colors ─────────────────────────────────────────────
    BG_BLACK   = "\033[40m"
    BG_RED     = "\033[41m"
    BG_GREEN   = "\033[42m"
    BG_YELLOW  = "\033[43m"
    BG_BLUE    = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN    = "\033[46m"
    BG_WHITE   = "\033[47m"

    # ── Luminous-themed semantic shortcuts ─────────────────────────────────────
    # Map to the closest ANSI equivalent of the GUI palette
    ACCENT  = "\033[38;2;124;106;247m"  # #7c6af7 — purple accent
    ACCENT2 = "\033[38;2;56;189;248m"   # #38bdf8 — sky blue
    ACCENT3 = "\033[38;2;245;158;11m"   # #f59e0b — amber
    SUCCESS = "\033[38;2;34;211;160m"   # #22d3a0 — green
    ERROR   = "\033[38;2;248;113;113m"  # #f87171 — red
    MUTED   = "\033[38;2;123;135;158m"  # #7b879e — dim text

    @staticmethod
    def rgb(r: int, g: int, b: int, *, bg: bool = False) -> str:
        """Return a 24-bit (true-color) ANSI escape for any RGB triple."""
        layer = 48 if bg else 38
        return f"\033[{layer};2;{r};{g};{b}m"

    @staticmethod
    def hex_to_ansi(hex_color: str, *, bg: bool = False) -> str:
        """Convert a '#rrggbb' hex string to a 24-bit ANSI escape."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return ANSI.rgb(r, g, b, bg=bg)

    @classmethod
    def paint(cls, text: str, hex_color: str, *, bold: bool = False) -> str:
        """Wrap *text* with the given hex colour and optional bold, then reset."""
        code = cls.hex_to_ansi(hex_color)
        style = cls.BOLD if bold else ""
        return f"{style}{code}{text}{cls.RESET}"


# ---------------------------------------------------------------------------
# ColorScheme — convenience bundle
# ---------------------------------------------------------------------------
@dataclass
class ColorScheme:
    """Bundles the Tk hex dict and ANSI class together.

    Usage::

        from colors import ColorScheme
        cs = ColorScheme.default()
        print(cs.ansi.paint("Luminous AI", cs.tk["accent"], bold=True))
    """
    tk:   dict[str, str] = field(default_factory=lambda: dict(C))
    ansi: type[ANSI]     = ANSI

    @classmethod
    def default(cls) -> "ColorScheme":
        """Return the default Luminous dark-mode scheme."""
        return cls(tk=dict(C), ansi=ANSI)
