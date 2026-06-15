#!/usr/bin/env python3
"""
Luminous AI — Prompt Index
PromptFileEntry: lightweight data model for a single prompt file.
PromptIndex:     builds and queries a campaign's prompt file tree,
                 grouping entries by category (subdirectory name).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# ── data model ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PromptFileEntry:
    """Represents a single prompt file discovered on disk.

    Attributes:
        path        Absolute path to the file.
        name        Display name — stem of the filename (no extension).
        category    Category key — the immediate parent directory name,
                    or ``"__root__"`` for files directly under *prompts_root*.
        rel_path    Path relative to *prompts_root* (for display / storage).
        extension   File extension including the leading dot (e.g. ``.txt``).
        size        File size in bytes at index time; ``-1`` if unavailable.
    """

    path: Path
    name: str
    category: str
    rel_path: Path
    extension: str
    size: int = field(default=-1, compare=False)

    # ── convenience ──────────────────────────────────────────────────────────

    @property
    def display_name(self) -> str:
        """Human-readable name with extension stripped."""
        return self.name

    @property
    def is_text(self) -> bool:
        """True for plain-text prompt formats."""
        return self.extension.lower() in {".txt", ".md", ".markdown", ".prompt"}

    @property
    def is_json(self) -> bool:
        """True for JSON-format prompts."""
        return self.extension.lower() in {".json", ".jsonc"}

    def read_text(self, encoding: str = "utf-8") -> str:
        """Read and return the file contents as a string."""
        return self.path.read_text(encoding=encoding, errors="replace")

    def __str__(self) -> str:
        return f"<PromptFileEntry {self.rel_path}>"


# ── supported prompt file extensions ─────────────────────────────────────────

_PROMPT_EXTENSIONS: frozenset[str] = frozenset(
    {".txt", ".md", ".markdown", ".prompt", ".json", ".jsonc"}
)

# ── index ─────────────────────────────────────────────────────────────────────

class PromptIndex:
    """Index of all prompt files beneath a campaign's *prompts* directory.

    Directory layout assumed::

        <save_path>/
        └── campaigns/
            └── <campaign_id>/
                └── prompts/          ← prompts_root
                    ├── file_a.txt    ← category "__root__"
                    ├── intro.md
                    └── characters/   ← category "characters"
                        ├── hero.txt
                        └── villain.txt

    Categories are the *direct* subdirectories of *prompts_root*; files in
    deeper subdirectories are assigned to the top-level subdirectory that
    contains them (e.g. ``prompts/characters/npcs/guard.txt`` → ``"characters"``).

    Usage::

        index = PromptIndex.from_campaign(save_path, "my_campaign")
        for cat in index.categories():
            print(cat, [e.name for e in index.entries_for_category(cat)])
    """

    # ── construction ──────────────────────────────────────────────────────────

    def __init__(self, prompts_root: Path) -> None:
        self._prompts_root: Path = prompts_root.resolve()
        # category key → ordered list of entries
        self._index: dict[str, list[PromptFileEntry]] = {}
        self._build()

    @classmethod
    def from_campaign(cls, save_path: Path | str, campaign_id: str) -> "PromptIndex":
        """Construct an index for *campaign_id* under *save_path*.

        Tries the conventional layout::

            <save_path>/campaigns/<campaign_id>/prompts/

        Falls back to::

            <save_path>/<campaign_id>/prompts/

        and then::

            <save_path>/<campaign_id>/

        so the class works with various project structures.
        """
        save_path = Path(save_path).resolve()
        candidates: list[Path] = [
            save_path / "campaigns" / campaign_id / "prompts",
            save_path / campaign_id / "prompts",
            save_path / campaign_id,
            save_path / "prompts",
            save_path,
        ]
        for candidate in candidates:
            if candidate.is_dir():
                return cls(candidate)
        # last resort — return an empty index rooted at save_path
        return cls(save_path)

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def prompts_root(self) -> Path:
        """Absolute path to the directory that was indexed."""
        return self._prompts_root

    def categories(self) -> list[str]:
        """Return category keys in sorted order, ``"__root__"`` last."""
        keys = sorted(k for k in self._index if k != "__root__")
        if "__root__" in self._index:
            keys.append("__root__")
        return keys

    def entries_for_category(self, category: str) -> list[PromptFileEntry]:
        """Return entries for *category*, sorted alphabetically by name.

        Returns an empty list if the category is not present.
        """
        return list(self._index.get(category, []))

    def all_entries(self) -> list[PromptFileEntry]:
        """Return every indexed entry across all categories."""
        result: list[PromptFileEntry] = []
        for entries in self._index.values():
            result.extend(entries)
        return sorted(result, key=lambda e: (e.category == "__root__", e.category, e.name))

    def entry_count(self) -> int:
        """Total number of indexed prompt files."""
        return sum(len(v) for v in self._index.values())

    def find_by_name(self, name: str) -> list[PromptFileEntry]:
        """Return all entries whose ``name`` matches *name* (case-insensitive)."""
        needle = name.casefold()
        return [e for e in self.all_entries() if e.name.casefold() == needle]

    def search(self, query: str) -> list[PromptFileEntry]:
        """Return entries whose name or relative path contains *query* (case-insensitive)."""
        needle = query.casefold()
        return [
            e for e in self.all_entries()
            if needle in e.name.casefold() or needle in str(e.rel_path).casefold()
        ]

    def __iter__(self) -> Iterator[PromptFileEntry]:
        return iter(self.all_entries())

    def __len__(self) -> int:
        return self.entry_count()

    def __repr__(self) -> str:
        return (
            f"PromptIndex(root={self._prompts_root!r}, "
            f"categories={len(self._index)}, entries={self.entry_count()})"
        )

    # ── internal build ────────────────────────────────────────────────────────

    def _build(self) -> None:
        """Walk *prompts_root* and populate ``self._index``."""
        if not self._prompts_root.is_dir():
            return

        for dirpath, _dirnames, filenames in os.walk(self._prompts_root):
            dir_path = Path(dirpath)
            for filename in sorted(filenames):
                file_path = dir_path / filename
                ext = file_path.suffix.lower()
                if ext not in _PROMPT_EXTENSIONS:
                    continue

                rel = file_path.relative_to(self._prompts_root)
                # category = the first path component below prompts_root
                # (or "__root__" for top-level files)
                parts = rel.parts
                category = parts[0] if len(parts) > 1 else "__root__"
                # for direct subdirectory entries the category IS the
                # directory name; strip file component
                if len(parts) > 1:
                    category = parts[0]

                try:
                    size = file_path.stat().st_size
                except OSError:
                    size = -1

                entry = PromptFileEntry(
                    path=file_path,
                    name=file_path.stem,
                    category=category,
                    rel_path=rel,
                    extension=file_path.suffix,
                    size=size,
                )
                self._index.setdefault(category, []).append(entry)

        # sort each bucket by display name
        for key in self._index:
            self._index[key].sort(key=lambda e: e.name.casefold())
