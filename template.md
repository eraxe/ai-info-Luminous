# NPC Viewer â€” `main.py` / `jsonTemplate.py` Split Workflow

## Overview

The codebase is split into exactly two files:

| File | Role |
|------|------|
| `main.py` | Tkinter UI, widgets, app shell, file I/O, tab switching. Calls `.render()` on templates. Contains zero display logic. |
| `jsonTemplate.py` | Template registry, template type classes, tab/subtab definitions, tag styles, known-keys registry. Contains zero tkinter code. |

The contract between them is a single method: `template.render(widget, data)`.  
`main.py` never inspects JSON structure. `jsonTemplate.py` never touches a widget directly â€” it writes to a `widget` reference passed in at render time.

---

## `jsonTemplate.py` Architecture

### 1. Template Type Classes

These are the building blocks. Each class knows how to render one category of content. All share the same interface:

```python
class SomeTemplate:
    def render(self, widget, data: dict) -> None: ...
```

#### `FieldListTemplate`
Renders labeled keyâ†’value pairs from JSON, organized into named sections.

```python
FieldListTemplate(
    sections=[
        Section("IDENTITY", [
            Field("Name",    "Name"),
            Field("Gender",  "Gender", formatter=str.capitalize),
            Field("Bind ID", "player_bind_string_id"),
        ]),
        Section("STATUS", [
            Field("Mood",     "EmotionalState.Mood"),   # dot-path supported
            Field("Location", "LocationType"),
        ]),
    ]
)
```

- `Field` supports an optional `formatter=` callable for value transformation.
- Dot-path notation (`"EmotionalState.Mood"`) traverses nested dicts automatically.
- Missing keys render as `null` with the `null_val` tag.

#### `PatternTemplate`
Parses a text field using keyword or regex patterns and applies named tags per match. Used for any freeform text that has semantic structure (e.g., internal thoughts, AI reasoning).

```python
PatternTemplate(
    json_key="LastAIResponseJson.internal_thoughts",
    patterns=[
        PatternRule(keyword="FACT CHECK:", tag="warn"),
        PatternRule(keyword="CONFIRMED:",  tag="good"),
        PatternRule(keyword="DENIED:",     tag="bad"),
        PatternRule(regex=r"STEP \d+:",    tag="step"),
        PatternRule(keyword="[Source]",    tag="fact"),
        PatternRule(keyword="[Current Data]", tag="fact"),
    ],
    fallback_tag="value"
)
```

- Rules are evaluated in order; first match wins per line.
- `regex=` and `keyword=` are mutually exclusive per rule.
- `fallback_tag` applies to lines that match no rule.

#### `NarrativeTemplate`
Renders a JSON list as a styled turn-by-turn flow. Designed for conversation history but usable for any list of turn-like objects.

```python
NarrativeTemplate(
    json_key="ConversationHistory",
    speaker_key="role",           # key inside each item that holds the speaker name
    content_key="content",        # key that holds the message text
    speaker_tags={                # map speaker values to tag names
        "user":      "player",
        "assistant": "npc",
    },
    default_tag="value",
    show_index=True,              # prefix each turn with its number
)
```

#### `TableTemplate`
Renders a list-of-dicts as a fixed-width formatted table.

```python
TableTemplate(
    json_key="NPCForces.Troops",
    columns=[
        Column("Type",   "troop_type",  width=22),
        Column("Count",  "count",       width=8,  align="right"),
        Column("Tier",   "tier",        width=6),
        Column("Morale", "morale",      width=10, formatter=lambda v: f"{v:.0%}"),
    ],
    header_tag="section",
    row_tag="value",
    alt_row_tag="muted",    # alternating row styling, optional
)
```

#### `ConditionalTemplate`
Wraps another template and only renders if a condition on the data is met.

```python
ConditionalTemplate(
    condition=lambda data: data.get("PendingDeath") not in (None, False, ""),
    template=FieldListTemplate(
        sections=[Section("PENDING DEATH", [
            Field("Reason",  "RoleplayDeathReason"),
            Field("Killer",  "KillerStringId"),
        ])]
    )
)
```

- `condition` is any callable that receives the full `data` dict and returns bool.
- If condition is False, the template produces no output (no blank space).

#### `CompositeTemplate`
Chains multiple templates in sequence, rendering them into the same widget one after another.

```python
CompositeTemplate(templates=[
    template_a,
    template_b,
    template_c,
])
```

This is how complex tabs (like AI Response) are built: a `CompositeTemplate` that runs a `PatternTemplate` for the response text, then a `FieldListTemplate` for context fields, then a `TableTemplate` for witnesses.

---

### 2. The `TEMPLATES` Registry

All template instances live in a single dict:

```python
TEMPLATES: dict[str, BaseTemplate] = {
    "overview":          FieldListTemplate(...),
    "conversation":      NarrativeTemplate(...),
    "personality":       FieldListTemplate(...),
    "internal_thoughts": PatternTemplate(...),
    "forces":            CompositeTemplate([...]),
    "events":            TableTemplate(...),
    "relationship":      FieldListTemplate(...),
    "ai_response":       PatternTemplate(...),
    "ai_thoughts":       PatternTemplate(...),
    "ai_actions":        FieldListTemplate(...),
    "ai_context":        FieldListTemplate(...),
    "ai_witnesses":      TableTemplate(...),
    "ai_raw":            None,   # raw JSON tab; handled natively in main.py
    # Add new templates here without touching main.py
}
```

**Adding a custom template** requires only adding an entry to this dict.

---

### 3. Tab & Subtab Definitions

```python
@dataclass
class SubTabDef:
    key:       str
    label:     str          # display label including icon
    font_type: str          # "content" | "code"
    templates: list[str]    # keys into TEMPLATES

@dataclass
class TabDef:
    icon:      str
    label:     str
    key:       str
    font_type: str          # "content" | "code"
    templates: list[str]    # keys into TEMPLATES (for simple tabs)
    subtabs:   list[SubTabDef] | None = None  # for tabs with a subtab bar

TABS: list[TabDef] = [
    TabDef(icon="âŠ›", label="AI Response", key="ai",
           font_type="content", templates=[],
           subtabs=[
               SubTabDef("ai_response",  "ðŸ’¬ Response",         "content", ["ai_response"]),
               SubTabDef("ai_thoughts",  "ðŸ§  Internal Thoughts","content", ["ai_thoughts"]),
               SubTabDef("ai_actions",   "âš¡ Actions",          "content", ["ai_actions"]),
               SubTabDef("ai_context",   "ðŸ“‹ Context Fields",   "content", ["ai_context"]),
               SubTabDef("ai_witnesses", "ðŸ‘ Witnesses",        "content", ["ai_witnesses"]),
               SubTabDef("ai_raw",       "âŸ¨âŸ© Raw JSON",         "code",    ["ai_raw"]),
           ]),
    TabDef(icon="ðŸ’­", label="Thoughts",    key="thoughts",    font_type="content", templates=["ai_thoughts"]),
    TabDef(icon="â—†",  label="Overview",   key="overview",    font_type="content", templates=["overview"]),
    TabDef(icon="âŒ˜",  label="Conversation",key="conv",       font_type="content", templates=["conversation"]),
    TabDef(icon="â™›",  label="Personality",key="personality", font_type="content", templates=["personality"]),
    TabDef(icon="â‹",  label="Internal",   key="internal",    font_type="content", templates=["internal_thoughts"]),
    TabDef(icon="âš”",  label="Military",   key="forces",      font_type="code",    templates=["forces"]),
    TabDef(icon="â—ˆ",  label="Events",     key="events",      font_type="content", templates=["events"]),
    TabDef(icon="â™¥",  label="Relationship",key="rel",        font_type="content", templates=["relationship"]),
    TabDef(icon="âŸ¨âŸ©", label="Raw JSON",   key="raw",         font_type="code",    templates=[]),
]
```

---

### 4. Tag Configuration

All text styling lives in `jsonTemplate.py`. `main.py` reads this dict to call `widget.tag_configure(...)`.

```python
TAG_CONFIG: dict[str, dict] = {
    "title":    dict(font_delta=+5, weight="bold",   fg="accent",    spacing1=4,  spacing3=6),
    "section":  dict(font_delta=+1, weight="bold",   fg="accent2",   spacing1=12, spacing3=4),
    "label":    dict(font_delta=-1, weight="bold",   fg="fg_dim"),
    "value":    dict(font_delta=0,  weight="normal", fg="fg"),
    "good":     dict(font_delta=0,  weight="normal", fg="green"),
    "bad":      dict(font_delta=0,  weight="normal", fg="red"),
    "warn":     dict(font_delta=0,  weight="normal", fg="accent3"),
    "muted":    dict(font_delta=0,  weight="normal", fg="fg_muted"),
    "code":     dict(font_delta=0,  weight="normal", fg="accent2",   use_code_font=True),
    "quote":    dict(font_delta=0,  weight="italic", fg="fg_dim",    lmargin1=20, lmargin2=20, bg="surface2"),
    "divider":  dict(font_delta=0,  weight="normal", fg="border"),
    "player":   dict(font_delta=0,  weight="bold",   fg="accent3"),
    "npc":      dict(font_delta=0,  weight="bold",   fg="accent"),
    "step":     dict(font_delta=-1, weight="normal", fg="green"),
    "fact":     dict(font_delta=-1, weight="normal", fg="accent2"),
    "null_val": dict(font_delta=-1, weight="italic", fg="fg_muted"),
}
```

`fg` values reference color keys from the `C` dict in `main.py` â€” no hex codes in `jsonTemplate.py`.

---

### 5. Known Keys Registry

```python
KNOWN_KEYS: set[str] = {
    "Name", "StringId", "Gender", "AssignedTTSVoice", ...
}
```

Used by `main.py` to detect and surface unknown/extra fields in the Overview tab.

---

## `main.py` Responsibilities

`main.py` handles **only**:

1. **Tkinter custom widgets** â€” `FlatButton`, `AccentButton`, `SidebarItem`, `StatusBar`, `CustomTitleBar`, `ScrollableFrame`
2. **App shell** â€” window setup, layout grid, sidebar, header, status bar
3. **UI construction from `TABS`** â€” iterates `TABS` to build frames and subtab bars; never hardcodes tab keys
4. **Tab switching** â€” `_switch_tab(key)`, `_switch_ai_subtab(key)`
5. **File I/O** â€” browse, load JSON, config persistence, bookmarks
6. **Tag setup** â€” reads `TAG_CONFIG` from `jsonTemplate.py`, applies to each widget via `_cfg_tags()`
7. **Populate dispatch** â€” `_display_data()` iterates the active tab's `templates` list and calls `.render(widget, data)` on each
8. **Raw JSON tab** â€” the one native exception: dumps JSON directly, no template needed
9. **Settings dialog** â€” font/size preferences, compact mode toggle

### The Populate Loop (core of the contract)

```python
def _display_data(self):
    data = self.current_json_data
    for tab in TABS:
        widget = self._get_widget_for_tab(tab.key)
        self._clear(widget)
        self._cfg_tags(widget, ...)
        for tpl_key in tab.templates:
            tpl = TEMPLATES.get(tpl_key)
            if tpl:
                tpl.render(widget, data)
```

This is the entire display pipeline. `main.py` has no knowledge of fields, patterns, or formatting.

---

## Adding a New Custom Sub-Template: Step-by-Step

1. **Open `jsonTemplate.py` only.**
2. Choose the appropriate template type (`PatternTemplate`, `FieldListTemplate`, etc.) or compose via `CompositeTemplate`.
3. Instantiate it and add it to `TEMPLATES` with a new key.
4. Reference that key in the relevant `TabDef.templates` or `SubTabDef.templates` list.
5. Done. `main.py` is not touched.

### Example â€” Adding a `KnownSecrets` parser

```python
# In jsonTemplate.py

TEMPLATES["known_secrets"] = PatternTemplate(
    json_key="KnownSecrets",
    patterns=[
        PatternRule(keyword="CONFIRMED:", tag="good"),
        PatternRule(keyword="RUMORED:",   tag="warn"),
        PatternRule(keyword="DENIED:",    tag="bad"),
        PatternRule(regex=r"\[Source\w*\]", tag="fact"),
    ],
    fallback_tag="value"
)

# Then add to the relevant tab:
# TabDef(key="internal", templates=["internal_thoughts", "known_secrets"])
```

---

## Dependency Graph

```
jsonTemplate.py
    â”œâ”€â”€ defines: BaseTemplate, FieldListTemplate, PatternTemplate,
    â”‚            NarrativeTemplate, TableTemplate, ConditionalTemplate,
    â”‚            CompositeTemplate
    â”œâ”€â”€ defines: TEMPLATES (registry)
    â”œâ”€â”€ defines: TABS, TabDef, SubTabDef
    â”œâ”€â”€ defines: TAG_CONFIG
    â””â”€â”€ defines: KNOWN_KEYS

main.py
    â”œâ”€â”€ imports: TEMPLATES, TABS, TAG_CONFIG, KNOWN_KEYS from jsonTemplate
    â”œâ”€â”€ owns: all tkinter widgets and app logic
    â””â”€â”€ calls: template.render(widget, data) â€” the only display call
```

`jsonTemplate.py` has **zero imports from `main.py`** and **zero tkinter imports**.

---

## File Size & Scope Estimates

| File | Est. Lines | Contents |
|------|-----------|----------|
| `jsonTemplate.py` | ~250â€“300 | Template classes + all instances + TABS + TAG_CONFIG + KNOWN_KEYS |
| `main.py` | ~650â€“700 | Widgets, app shell, file I/O, populate loop, settings |
