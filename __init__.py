"""
Luminous AI — Package Init
Re-exports all public symbols so callers can simply do:
    from luminous import C, ANSI, ColorScheme
"""

from colors import C, ANSI, ColorScheme

__all__ = [
    "C",
    "ANSI",
    "ColorScheme",
]

__version__ = "1.0.0"
__author__  = "Luminous AI"
