# jsonTemplate.py
from __future__ import annotations
import re
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ─────────────────────────────────────────────
# DATACLASSES
# ─────────────────────────────────────────────

@dataclass
class Field:
    label: str
    key: str
    formatter: Optional[Callable] = None

    def resolve(self, data: dict) -> Any:
        parts = self.key.split(".")
        val = data
        for p in parts:
            if not isinstance(val, dict):
                return None
            val = val.get(p)
        return val


@dataclass
class Section:
    title: str
    fields: list[Field]


@dataclass
class Column:
    label: str
    key: str
    width: int = 20
    align: str = "left"
    formatter: Optional[Callable] = None


@dataclass
class PatternRule:
    tag: str
    keyword: Optional[str] = None
    regex: Optional[str] = None


@dataclass
class SubTabDef:
    key: str
    label: str
    font_type: str
    templates: list[str]


@dataclass
class TabDef:
    icon: str
    label: str
    key: str
    font_type: str
    templates: list[str]
    subtabs: Optional[list[SubTabDef]] = None


# ─────────────────────────────────────────────
# TEMPLATE BASE
# ─────────────────────────────────────────────

class BaseTemplate:
    def render(self, widget, data: dict) -> None:
        raise NotImplementedError


# ─────────────────────────────────────────────
# TEMPLATE TYPES
# ─────────────────────────────────────────────

def _fmt_val(v) -> str:
    if v is None: return "null"
    if isinstance(v, bool): return str(v)
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, str): return v if v != "" else "(empty)"
    if isinstance(v, list): return f"[{len(v)} items]"
    if isinstance(v, dict): return f"{{ {len(v)} fields }}"
    return str(v)


def _divider(widget, char="─", n=72):
    widget.insert("end", char * n + "\n", "divider")


# FIX #1 — unified row helper; all label widths consistent at 24
def _row(widget, label: str, val, tag: str = "value", width: int = 24):
    widget.insert("end", f"  {label:<{width}}", "label")
    widget.insert("end", f"{val}\n", tag)


class FieldListTemplate(BaseTemplate):
    def __init__(self, sections: list[Section]):
        self.sections = sections

    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        for sec in self.sections:
            widget.insert("end", f" {sec.title}\n", "section")
            _divider(widget)
            for f in sec.fields:
                val = f.resolve(data)
                display = f.formatter(val) if f.formatter and val is not None else _fmt_val(val)
                tag = "null_val" if val is None or val == "" else "value"
                _row(widget, f.label, display, tag)
            widget.insert("end", "\n")
        widget.config(state="disabled")


class PatternTemplate(BaseTemplate):
    def __init__(self, json_key: str, patterns: list[PatternRule],
                 fallback_tag: str = "value", split_on: str = "\n"):
        self.json_key = json_key
        self.patterns = patterns
        self.fallback_tag = fallback_tag
        self.split_on = split_on

    def _resolve(self, data: dict) -> Any:
        parts = self.json_key.split(".")
        val = data
        for p in parts:
            if not isinstance(val, dict):
                return None
            val = val.get(p)
        return val

    def _tag_for_line(self, line: str) -> str:
        for rule in self.patterns:
            if rule.keyword and rule.keyword in line:
                return rule.tag
            if rule.regex and re.search(rule.regex, line):
                return rule.tag
        return self.fallback_tag

    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        val = self._resolve(data)
        if not val:
            widget.insert("end", "\n  (none)\n", "null_val")
            widget.config(state="disabled")
            return
        text = val if isinstance(val, str) else json.dumps(val, indent=2)
        for line in text.split(self.split_on):
            stripped = line.strip()
            if not stripped:
                continue
            tag = self._tag_for_line(stripped)
            widget.insert("end", f"  {stripped}\n", tag)
        widget.config(state="disabled")


class NarrativeTemplate(BaseTemplate):
    def __init__(self, json_key: str, speaker_key: str = "role",
                 content_key: str = "content",
                 speaker_tags: Optional[dict] = None,
                 default_tag: str = "value",
                 show_index: bool = True,
                 reverse: bool = True):
        self.json_key = json_key
        self.speaker_key = speaker_key
        self.content_key = content_key
        self.speaker_tags = speaker_tags or {}
        self.default_tag = default_tag
        self.show_index = show_index
        self.reverse = reverse

    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        history = data.get(self.json_key, [])
        if not isinstance(history, list):
            history = []
        # FIX #2 — player detection uses player_bind_string_id
        player_id = data.get("player_bind_string_id", "main_hero")
        items = list(reversed(history)) if self.reverse else history
        for i, msg in enumerate(items, 1):
            idx = len(history) - i + 1 if self.reverse else i
            if isinstance(msg, dict):
                speaker = msg.get(self.speaker_key, "?")
                text = msg.get(self.content_key, "")
                stag = self.speaker_tags.get(speaker, self.default_tag)
                if self.show_index:
                    widget.insert("end", f" [{idx:03d}] ", "muted")
                widget.insert("end", f"{speaker}:", stag)
                widget.insert("end", f" {text}\n\n", self.default_tag)
            elif isinstance(msg, str):
                if ":" in msg:
                    speaker, text = msg.split(":", 1)
                    is_player = player_id in speaker or speaker.strip().startswith("Unidentified")
                    stag = "player" if is_player else "npc"
                    if self.show_index:
                        widget.insert("end", f" [{idx:03d}] ", "muted")
                    widget.insert("end", f"{speaker.strip()}:", stag)
                    widget.insert("end", f"{text}\n\n", self.default_tag)
                else:
                    if self.show_index:
                        widget.insert("end", f" [{idx:03d}] ", "muted")
                    widget.insert("end", f"{msg}\n\n", "muted")
        widget.config(state="disabled")


class TableTemplate(BaseTemplate):
    def __init__(self, json_key: str, columns: list[Column],
                 header_tag: str = "section", row_tag: str = "value",
                 alt_row_tag: Optional[str] = None):
        self.json_key = json_key
        self.columns = columns
        self.header_tag = header_tag
        self.row_tag = row_tag
        self.alt_row_tag = alt_row_tag

    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        rows = data.get(self.json_key, [])
        if not isinstance(rows, list):
            widget.insert("end", "  (no data)\n", "null_val")
            widget.config(state="disabled")
            return
        header = "  ".join(
            f"{col.label:<{col.width}}" if col.align != "right" else f"{col.label:>{col.width}}"
            for col in self.columns
        )
        widget.insert("end", f"  {header}\n", self.header_tag)
        _divider(widget, "·", 60)
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            tag = self.alt_row_tag if self.alt_row_tag and i % 2 == 1 else self.row_tag
            line = "  ".join(
                ("{:>{w}}".format(
                    col.formatter(row.get(col.key)) if col.formatter and row.get(col.key) is not None
                    else _fmt_val(row.get(col.key)), w=col.width)
                if col.align == "right" else
                "{:<{w}}".format(
                    col.formatter(row.get(col.key)) if col.formatter and row.get(col.key) is not None
                    else _fmt_val(row.get(col.key)), w=col.width))
                for col in self.columns
            )
            widget.insert("end", f"  {line}\n", tag)
        widget.config(state="disabled")


class ConditionalTemplate(BaseTemplate):
    def __init__(self, condition: Callable[[dict], bool], template: BaseTemplate):
        self.condition = condition
        self.template = template

    def render(self, widget, data: dict) -> None:
        if self.condition(data):
            self.template.render(widget, data)


class CompositeTemplate(BaseTemplate):
    def __init__(self, templates: list[BaseTemplate]):
        self.templates = templates

    def render(self, widget, data: dict) -> None:
        for tpl in self.templates:
            tpl.render(widget, data)


# ─────────────────────────────────────────────
# CUSTOM RENDER CLASSES (complex tabs)
# ─────────────────────────────────────────────

class OverviewTemplate(BaseTemplate):
    """Full overview tab renderer."""

    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        name   = data.get("Name", "?")
        gender = data.get("Gender", "?").capitalize() if isinstance(data.get("Gender"), str) else "?"
        sid    = data.get("StringId", "?")
        widget.insert("end", f" {name} ({gender})\n", "title")
        widget.insert("end", f" ID: {sid}", "muted")
        tts_voice = data.get("AssignedTTSVoice", "")
        if tts_voice:
            widget.insert("end", f"   TTS Voice: {tts_voice}", "muted")
        widget.insert("end", "\n\n")

        # IDENTITY
        widget.insert("end", " IDENTITY\n", "section"); _divider(widget)
        for lbl, key in [("Bind ID",          "player_bind_string_id"),
                         ("TTS Last Text",     "LastTTSPlayedText"),
                         ("TTS Instructions",  "LastTTSInstructions")]:
            val = data.get(key)
            if val is not None and val != "":
                _row(widget, lbl, val)

        # CURRENT STATUS
        widget.insert("end", "\n CURRENT STATUS\n", "section"); _divider(widget)
        _row(widget, "Task",        data.get("CurrentTask", "N/A"))
        _row(widget, "In Party",
             "Yes ✓" if data.get("IsInPlayerParty") else "No",
             "good"  if data.get("IsInPlayerParty") else "muted")
        _row(widget, "With Player",
             "Yes ✓" if data.get("IsWithPlayer") else "No",
             "good"  if data.get("IsWithPlayer") else "muted")
        _row(widget, "Info Access", data.get("InformationAccessLevel", "N/A"))

        # EMOTIONAL STATE
        widget.insert("end", "\n EMOTIONAL STATE\n", "section"); _divider(widget)
        emo = data.get("EmotionalState", {})
        if isinstance(emo, dict):
            mood = emo.get("Mood", "N/A")
            _row(widget, "Mood", mood.capitalize())
            reason = emo.get("Reason", "")
            if reason:
                _row(widget, "Reason", reason)

        # TIME & WORLD
        widget.insert("end", "\n TIME & WORLD\n", "section"); _divider(widget)
        tc = data.get("TimeContext", {})
        if isinstance(tc, dict):
            season = tc.get("Season", "?").capitalize() if isinstance(tc.get("Season"), str) else "?"
            tod    = tc.get("TimeOfDay", "?").capitalize() if isinstance(tc.get("TimeOfDay"), str) else "?"
            _row(widget, "Date",
                 f"Year {tc.get('Year','?')}, Month {tc.get('Month','?')} — {season}")
            _row(widget, "Time of Day",
                 f"{tod} (Hour {tc.get('Hour','?')})")
        war = data.get("WarStatus")
        if war:
            _row(widget, "War Status", war, "warn")

        # LAST DIALOGUE
        widget.insert("end", "\n LAST DIALOGUE\n", "section"); _divider(widget)
        for lbl, key in [("Scene ID",     "LastDialogueSceneId"),
                         ("Utterance ID", "LastDynamicResponseUtteranceId")]:
            val = data.get(key, "")
            if val:
                _row(widget, lbl, val, "code")

        # FIX #6 — location parsed by semicolons, not a wall of text
        loc = data.get("LocationType", "")
        if loc:
            widget.insert("end", "\n LOCATION DETAILS\n", "section"); _divider(widget)
            segments = re.split(r";\s*", loc)
            for seg in segments:
                seg = seg.strip()
                if seg:
                    widget.insert("end", f"  • {seg}\n", "muted")

        # FIX #1 — SettlementCombatResponse now included
        # FIX #4b — bool False shown as null_val not warn
        widget.insert("end", "\n PENDING STATES\n", "section"); _divider(widget)
        pending_fields = [
            ("Surrendering",        "IsSurrendering"),
            ("Player Surrendering", "IsPlayerSurrendering"),
            ("Intimacy Notify",     "PendingIntimacyNotification"),
            ("Conception Mother",   "PendingConceptionMotherName"),
            ("Clan Tier Checked",   "ClanTierRecognitionChecked"),
            ("Knowledge Generated", "KnowledgeGenerated"),
            ("Roleplay Death",      "RoleplayDeathReason"),
            ("Killer ID",           "KillerStringId"),
            ("Pending Death",       "PendingDeath"),
            ("Combat Response",     "CombatResponse"),
            ("Marriage Response",   "MarriageResponse"),
            ("Settlement Combat",   "PendingSettlementCombat"),
            ("Settlement Response", "SettlementCombatResponse"),   # was missing
            ("Attack Target",       "PendingAttackTargetHeroId"),
            ("Relation Changes",    "PendingRelationChanges"),
            ("Lie Penalty",         "PendingLiePenalty"),
            ("Workshop Sale",       "PendingWorkshopSale"),
            ("Money Transfer",      "PendingMoneyTransfer"),
            ("Item Transfers",      "PendingItemTransfers"),
            ("Action Commands",     "PendingActionCommandsAfterMission"),
        ]
        for lbl, key in pending_fields:
            val = data.get(key)
            display = _fmt_val(val)
            if val is None or val == "" or val is False or val == [] or val == 0:
                tag = "null_val"
            else:
                tag = "warn"
            _row(widget, lbl, display, tag)

        # KNOWN DATA
        secrets    = data.get("KnownSecrets", [])
        known_info = data.get("KnownInfo", [])
        if secrets or known_info:
            widget.insert("end", "\n KNOWN DATA\n", "section"); _divider(widget)
            if secrets:
                widget.insert("end", f"  Known Secrets ({len(secrets)})\n", "label")
                for s in secrets:
                    widget.insert("end", f"   • {s}\n", "value")
            if known_info:
                widget.insert("end", f"  Known Info ({len(known_info)})\n", "label")
                for item in known_info:
                    widget.insert("end", f"   • {item}\n", "value")

        # QUIRKS
        quirks = data.get("Quirks", [])
        if quirks:
            widget.insert("end", "\n QUIRKS\n", "section"); _divider(widget)
            for q in quirks:
                widget.insert("end", f"   • {q}\n", "value")

        # EXTRA / UNKNOWN
        extra = {k: v for k, v in data.items() if k not in KNOWN_KEYS}
        if extra:
            widget.insert("end", "\n EXTRA / UNKNOWN FIELDS\n", "section"); _divider(widget)
            widget.insert("end", "  (Fields not recognised by current viewer version — shown as-is)\n", "muted")
            for k, v in extra.items():
                widget.insert("end", f"  {k:<26}", "label")
                if isinstance(v, (dict, list)):
                    widget.insert("end", f"\n{json.dumps(v, indent=4, ensure_ascii=False)}\n", "code")
                else:
                    widget.insert("end", f"{_fmt_val(v)}\n", "value")

        widget.config(state="disabled")


class ConversationTemplate(BaseTemplate):
    """Full conversation tab renderer."""

    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        history      = data.get("ConversationHistory", [])
        observations = data.get("DialogueObservations", [])

        # FIX #2 — player detection via player_bind_string_id
        player_id = data.get("player_bind_string_id", "main_hero")

        widget.insert("end", f" CONVERSATION HISTORY  ·  {len(history)} messages\n\n", "section")
        for i, msg in enumerate(reversed(history), 1):
            idx = len(history) - i + 1
            if isinstance(msg, str):
                is_player = player_id in msg or msg.startswith("Unidentified person")
                if ":" in msg:
                    speaker, text = msg.split(":", 1)
                    speaker_tag = "player" if is_player else "npc"
                    widget.insert("end", f" [{idx:03d}] ", "muted")
                    widget.insert("end", f"{speaker.strip()}:", speaker_tag)
                    widget.insert("end", f"{text}\n\n", "value")
                else:
                    widget.insert("end", f" [{idx:03d}] {msg}\n\n", "muted")

        if observations:
            widget.insert("end", "\n DIALOGUE OBSERVATIONS\n", "section"); _divider(widget)
            widget.insert("end", f"  {len(observations)} utterances recorded\n\n", "muted")
            for obs in reversed(observations):
                if not isinstance(obs, dict):
                    continue
                speaker = obs.get("speaker_name", "?")
                is_p    = obs.get("is_player", False)
                line    = obs.get("canonical_line", "")
                days    = obs.get("campaign_days")
                scene   = obs.get("scene_id", "")
                utt_id  = obs.get("utterance_id", "")
                source  = obs.get("source_tag", "")
                hearing = obs.get("hearing_role", "")
                dist    = obs.get("distance")
                widget.insert("end", f"  {'[PLAYER]' if is_p else '[NPC]   '} {speaker}  ",
                              "player" if is_p else "npc")
                if days is not None:
                    widget.insert("end", f"  Day {days:.2f}  ", "muted")
                widget.insert("end", "\n", "muted")
                widget.insert("end", f"  Source: {source}  |  Hearing: {hearing}", "muted")
                if dist is not None:
                    widget.insert("end", f"  |  Distance: {dist}", "muted")
                widget.insert("end", "\n")
                widget.insert("end", f"  {line}\n", "quote")
                widget.insert("end", f"  Scene:     {scene}\n", "code")
                widget.insert("end", f"  Utterance: {utt_id}\n\n", "code")

        widget.config(state="disabled")


class PersonalityTemplate(BaseTemplate):
    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        widget.insert("end", " CHARACTER DESCRIPTION\n", "section"); _divider(widget)
        desc = data.get("CharacterDescription", "")
        widget.insert("end", f"{desc if desc else '(none)'}\n\n",
                      "value" if desc else "null_val")

        for title, key in [("AI GENERATED PERSONALITY", "AIGeneratedPersonality"),
                            ("BACKSTORY",               "AIGeneratedBackstory"),
                            ("SPEECH QUIRKS",            "AIGeneratedSpeechQuirks")]:
            widget.insert("end", f" {title}\n", "section"); _divider(widget)
            val = data.get(key)
            if not val:
                widget.insert("end", "(not generated)\n\n", "null_val")
                continue

            if key == "AIGeneratedSpeechQuirks":
                # FIX #7 — highlight single-quoted interjections/phrases
                last = 0
                for m in re.finditer(r"'([^']+)'", val):
                    before = val[last:m.start()]
                    if before:
                        widget.insert("end", before, "value")
                    widget.insert("end", m.group(0), "fact")
                    last = m.end()
                remainder = val[last:]
                if remainder:
                    widget.insert("end", remainder, "value")
                widget.insert("end", "\n\n")
            else:
                widget.insert("end", f"{val}\n\n", "value")

        widget.config(state="disabled")


class ThoughtsTemplate(BaseTemplate):
    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        widget.insert("end", " LAST DYNAMIC RESPONSE\n", "section"); _divider(widget)
        last = data.get("LastDynamicResponse", "")
        widget.insert("end",
                      f"\n ❝{last}❞\n\n" if last else "\n (none)\n\n",
                      "quote" if last else "null_val")
        widget.config(state="disabled")


class InternalThoughtsTemplate(BaseTemplate):
    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        it = (data.get("PendingAIResponse") or {}).get("internal_thoughts") or data.get("InternalThoughts", "")
        widget.insert("end", " INTERNAL THOUGHTS\n", "section"); _divider(widget)
        if it:
            # FIX #3 — split on sentence boundaries, not bare "."
            sentences = re.split(r'(?<=[.!?])\s+', it.strip())
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                upper = sentence.upper()
                if upper.startswith("FACT CHECK"):
                    widget.insert("end", " FACT CHECK\n", "label")
                    widget.insert("end", f"  {sentence[len('FACT CHECK:'):].strip()}\n\n", "fact")
                elif re.match(r"STEP\s+\d+", upper):
                    widget.insert("end", f"\n  {sentence}\n", "step")
                elif sentence.startswith("[Source]"):
                    widget.insert("end", " SOURCE\n", "label")
                    widget.insert("end", f"  {sentence[len('[Source]'):].strip()}\n\n", "fact")
                else:
                    widget.insert("end", f"  {sentence}\n", "value")
        else:
            widget.insert("end", "\n (none)\n", "null_val")
        widget.config(state="disabled")


class ForcesTemplate(BaseTemplate):
    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        widget.insert("end", " MILITARY & FORCES\n", "section"); _divider(widget)

        def render_force(label, fdata):
            if not isinstance(fdata, dict):
                return
            widget.insert("end", f"\n {label}\n", "label"); _divider(widget, "·", 60)
            _row(widget, "Party Size", fdata.get("PartySize", 0))
            _row(widget, "Has Army",
                 "Yes" if fdata.get("HasArmy") else "No",
                 "good" if fdata.get("HasArmy") else "muted")
            wounded_pct = fdata.get("WoundedPercentage", 0.0)
            _row(widget, "Wounded", f"{wounded_pct:.1%}",
                 "bad" if wounded_pct > 0.3 else "warn" if wounded_pct > 0 else "good")

            army = fdata.get("ArmyDetails")
            if army and isinstance(army, dict):
                widget.insert("end", "\n  Army Details\n", "label")
                for k2, v2 in army.items():
                    _row(widget, f"    {k2}", v2)

            troops = fdata.get("TroopDetails", [])
            if troops:
                # FIX #4 — StringId column removed; Name widened to 36
                widget.insert("end", f"\n  Troops ({len(troops)} types):\n", "label")
                widget.insert("end",
                    f"  {'Name':<36}  {'Count':>6}  {'Wounded':>8}\n", "muted")
                _divider(widget, "·", 56)
                total = 0
                for tr in troops:
                    if not isinstance(tr, dict):
                        continue
                    name = tr.get("Name", "?")
                    cnt  = tr.get("Count", 0)
                    wnd  = tr.get("WoundedCount", 0)
                    total += cnt
                    tag  = "bad" if wnd > 0 else "value"
                    widget.insert("end", f"  {name:<36}  {cnt:>6}  {wnd:>8}\n", tag)
                _divider(widget, "·", 56)
                widget.insert("end", f"  {'TOTAL':<36}  {total:>6}\n", "good")

        render_force("PLAYER FORCES", data.get("PlayerForces"))
        render_force("NPC FORCES",    data.get("NPCForces"))

        legacy = data.get("LeadingForces") or data.get("MilitaryForces")
        if legacy:
            widget.insert("end", "\n LEGACY FORCES\n", "label"); _divider(widget)
            if isinstance(legacy, dict):
                legacy = [legacy]
            for force in legacy:
                if isinstance(force, dict):
                    for k, v in force.items():
                        _row(widget, f"  {k}", v)
                    widget.insert("end", "\n")

        widget.config(state="disabled")


class EventsTemplate(BaseTemplate):
    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        events = data.get("RecentEvents", data.get("Events", []))
        widget.insert("end", f" RECENT EVENTS  ·  {len(events)} total\n\n", "section")
        if not events:
            widget.insert("end", "  (no recent events)\n", "null_val")
        else:
            for ev in reversed(events):
                if isinstance(ev, dict):
                    widget.insert("end", f"  Day {ev.get('Day', '?'):<8}", "muted")
                    widget.insert("end", f"{ev.get('Description', str(ev))}\n", "value")
                else:
                    widget.insert("end", f"  {ev}\n", "value")
        widget.config(state="disabled")


class RelationshipTemplate(BaseTemplate):
    def render(self, widget, data: dict) -> None:
        widget.config(state="normal")
        widget.insert("end", " PLAYER RELATION\n", "section"); _divider(widget)
        rel = data.get("PlayerRelation", {})
        if isinstance(rel, dict):
            rel_val  = rel.get("Value", 0)
            rel_desc = rel.get("Description", "neutral")
            color_tag = "good" if rel_val >= 50 else ("bad" if rel_val < 0 else "warn")
            _row(widget, "Value",  f"{rel_val:+d}", color_tag)
            _row(widget, "Status", rel_desc.capitalize())

        cs = data.get("CounterpartySocial", {})
        if isinstance(cs, dict) and cs:
            with_int = {k: v for k, v in cs.items()
                        if isinstance(v, dict) and v.get("interaction_count", 0) > 0}
            zero_int = {k: v for k, v in cs.items() if k not in with_int}

            widget.insert("end", f"\n COUNTERPARTY SOCIAL  ·  {len(cs)} contacts\n", "section")
            _divider(widget)

            if with_int:
                widget.insert("end", f"\n  ── Active Contacts ({len(with_int)}) ──\n", "label")
                for hero_id, social in with_int.items():
                    widget.insert("end", f"\n  {hero_id}\n", "npc")
                    _divider(widget, "·", 60)
                    fields = [
                        ("Trust Level",          "trust_level",                lambda v: f"{v:.2%}"),
                        ("Escalation State",     "escalation_state",           None),
                        ("Threat Level",         "threat_level",               None),
                        ("Interaction Count",    "interaction_count",          None),
                        ("Neg. Tone Count",      "negative_tone_count",        None),
                        ("Lie Penalty Sum",      "lie_penalty_sum",            lambda v: f"{v:.2f}"),
                        ("Last Dialogue Day",    "last_dialogue_campaign_days",
                         lambda v: f"{v:.2f}" if v >= 0 else "never"),
                        ("Suspected Lie",        "suspected_lie",              None),
                        ("Identity Recognized",  "identity_recognized",        None),
                        ("Claimed Name",         "claimed_name",               None),
                        ("Claimed Clan",         "claimed_clan",               None),
                        ("Claimed Age",          "claimed_age",                None),
                        ("Claimed Gold",         "claimed_gold",               None),
                        ("Real Name",            "real_name",                  None),
                        ("Real Clan",            "real_clan",                  None),
                        ("Real Clan ID",         "real_clan_id",               None),
                        ("Real Age",             "real_age",                   None),
                        ("Real Gender",          "real_gender",                None),
                        ("Real Culture",         "real_culture",               None),
                    ]
                    for lbl, key, fmt_fn in fields:
                        v = social.get(key)
                        if v is None or v == "" or (v == 0 and key not in (
                                "interaction_count", "negative_tone_count", "claimed_gold")):
                            display, tag = "null", "null_val"
                        else:
                            display = fmt_fn(v) if fmt_fn else str(v)
                            tag = "value"
                        _row(widget, f"    {lbl}", display, tag, width=28)

            # FIX #5 — zero-interaction contacts collapsed to summary strip (3 per row)
            if zero_int:
                widget.insert("end",
                    f"\n  ── Other Known Contacts ({len(zero_int)}) — no interactions ──\n", "muted")
                ids = list(zero_int.keys())
                for i in range(0, len(ids), 3):
                    chunk = ids[i:i+3]
                    widget.insert("end", "   " + "   ".join(chunk) + "\n", "muted")
                widget.insert("end", "\n")

        widget.config(state="disabled")


# ─────────────────────────────────────────────
# AI RESPONSE SUB-RENDERERS  (FIX #10)
# ─────────────────────────────────────────────

class _AIResponseSub(BaseTemplate):
    def render(self, widget, data: dict) -> None:
        ai = data.get("PendingAIResponse") or data.get("LastAIResponseJson")
        if isinstance(ai, str):
            try:
                ai = json.loads(ai)
            except Exception:
                ai = {"raw": ai}
        widget.config(state="normal")
        if not ai:
            widget.insert("end", "\n  No AI Response Data\n", "null_val")
            widget.config(state="disabled")
            return
        self._draw(widget, ai)
        widget.config(state="disabled")

    def _draw(self, widget, ai: dict) -> None:
        raise NotImplementedError


class AISpokenResponseTemplate(_AIResponseSub):
    def _draw(self, widget, ai):
        widget.insert("end", " NPC SPOKEN RESPONSE\n", "section"); _divider(widget)
        response = ai.get("response", "")
        widget.insert("end",
                      f"\n ❝{response}❞\n\n" if response else "\n  (no response)\n\n",
                      "quote" if response else "null_val")


class AIActionsTemplate(_AIResponseSub):
    def _draw(self, widget, ai):
        widget.insert("end", " ACTIONS\n", "section"); _divider(widget)
        actions = ai.get("actions", [])
        if actions:
            for i, act in enumerate(actions, 1):
                widget.insert("end", f"  [{i}] ", "label")
                if isinstance(act, dict):
                    for ak, av in act.items():
                        widget.insert("end", f"{ak}: ", "label")
                        widget.insert("end", f"{_fmt_val(av)}  ", "value")
                else:
                    widget.insert("end", f"{act}", "value")
                widget.insert("end", "\n")
        else:
            widget.insert("end", "  (no actions)\n", "null_val")


class AIWitnessesTemplate(_AIResponseSub):
    def _draw(self, widget, ai):
        widget.insert("end", " WITNESSES\n", "section"); _divider(widget)
        witnesses = ai.get("witnesses", [])
        if witnesses:
            for w in witnesses:
                widget.insert("end", f"  • {w}\n", "value")
        else:
            widget.insert("end", "  (no witnesses)\n", "null_val")


class AIThoughtsTemplate(_AIResponseSub):
    def _draw(self, widget, ai):
        widget.insert("end", " AI INTERNAL THOUGHTS\n", "section"); _divider(widget)
        it = ai.get("internal_thoughts", "")
        if not it:
            widget.insert("end", "  (no internal thoughts)\n", "null_val")
            return
        full = it
        if "FACT CHECK:" in full:
            fc_start = full.index("FACT CHECK:")
            prefix = full[:fc_start].strip()
            if prefix:
                widget.insert("end", f"  {prefix}\n\n", "muted")
            rest = full[fc_start:]
            if "[Source]" in rest:
                fc_body, src_rest = rest.split("[Source]", 1)
            else:
                fc_body, src_rest = rest, ""
            widget.insert("end", " FACT CHECK\n", "fact")
            if "[Current Data]" in fc_body:
                _, cd = fc_body.split("[Current Data]", 1)
                widget.insert("end", "  [Current Data]\n", "label")
                for seg in cd.split("→"):
                    seg = seg.strip(" →\n")
                    if seg:
                        widget.insert("end", f"   → {seg}\n", "value")
            else:
                widget.insert("end",
                    f"  {fc_body.replace('FACT CHECK:', '').strip()}\n", "value")
            if src_rest:
                widget.insert("end", "\n  [Source]\n", "label")
                widget.insert("end", f"   {src_rest.strip()}\n", "fact")
            steps_text = src_rest if src_rest else fc_body
        else:
            widget.insert("end", f"  {full}\n", "value")
            steps_text = ""
        if steps_text:
            step_matches = re.split(r"(STEP \d+:)", steps_text)
            for part in step_matches:
                if re.match(r"STEP \d+:", part):
                    widget.insert("end", f"\n {part} ", "step")
                else:
                    stripped = part.strip()
                    if stripped:
                        widget.insert("end", f"{stripped}\n", "value")


class AIContextTemplate(_AIResponseSub):
    def _draw(self, widget, ai):
        widget.insert("end", " ALL AI RESPONSE FIELDS\n", "section"); _divider(widget)
        CORE = {"internal_thoughts", "response", "actions", "witnesses"}
        non_null    = {k: v for k, v in ai.items()
                       if k not in CORE and v is not None and v != "" and v != [] and v != 0}
        null_fields = {k: v for k, v in ai.items()
                       if k not in CORE and k not in non_null}
        if non_null:
            widget.insert("end", "\n  ── Active Fields ──\n", "label")
            for k, v in non_null.items():
                widget.insert("end", f"  {k:<36}", "label")
                if isinstance(v, (dict, list)):
                    widget.insert("end", f"\n{json.dumps(v, indent=4, ensure_ascii=False)}\n", "code")
                else:
                    widget.insert("end", f"{_fmt_val(v)}\n", "value")
        if null_fields:
            widget.insert("end", "\n  ── Null / Empty Fields ──\n", "muted")
            for k, v in null_fields.items():
                _row(widget, f"  {k}", _fmt_val(v), "null_val", width=36)


class AIRawTemplate(_AIResponseSub):
    def _draw(self, widget, ai):
        widget.insert("end", json.dumps(ai, indent=2, ensure_ascii=False))


# Legacy dispatch wrapper — keeps TEMPLATES registry clean
class AIResponseTemplate(BaseTemplate):
    _dispatch = {
        "ai_response":  AISpokenResponseTemplate,
        "ai_actions":   AIActionsTemplate,
        "ai_witnesses": AIWitnessesTemplate,
        "ai_thoughts":  AIThoughtsTemplate,
        "ai_context":   AIContextTemplate,
        "ai_raw":       AIRawTemplate,
    }

    def __init__(self, subtab_key: str):
        self.subtab_key = subtab_key
        cls = self._dispatch.get(subtab_key)
        self._impl = cls() if cls else None

    def render(self, widget, data: dict) -> None:
        if self._impl:
            self._impl.render(widget, data)


# ─────────────────────────────────────────────
# TEMPLATES REGISTRY
# ─────────────────────────────────────────────

TEMPLATES: dict[str, Optional[BaseTemplate]] = {
    "overview":          OverviewTemplate(),
    "conversation":      ConversationTemplate(),
    "personality":       PersonalityTemplate(),
    "thoughts":          ThoughtsTemplate(),
    "internal_thoughts": InternalThoughtsTemplate(),
    "forces":            ForcesTemplate(),
    "events":            EventsTemplate(),
    "relationship":      RelationshipTemplate(),
    "ai_response":       AISpokenResponseTemplate(),
    "ai_thoughts":       AIThoughtsTemplate(),
    "ai_actions":        AIActionsTemplate(),
    "ai_context":        AIContextTemplate(),
    "ai_witnesses":      AIWitnessesTemplate(),
    "ai_raw":            AIRawTemplate(),
}


# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────

TABS: list[TabDef] = [
    TabDef(icon="⊛", label="AI Response", key="ai",
           font_type="content", templates=[],
           subtabs=[
               SubTabDef("ai_response",  "💬 Response",          "content", ["ai_response"]),
               SubTabDef("ai_thoughts",  "🧠 Internal Thoughts", "content", ["ai_thoughts"]),
               SubTabDef("ai_actions",   "⚡ Actions",           "content", ["ai_actions"]),
               SubTabDef("ai_context",   "📋 Context Fields",    "content", ["ai_context"]),
               SubTabDef("ai_witnesses", "👁 Witnesses",         "content", ["ai_witnesses"]),
               SubTabDef("ai_raw",       "⟨⟩ Raw JSON",          "code",    ["ai_raw"]),
           ]),
    TabDef(icon="💭", label="Thoughts",     key="thoughts",     font_type="content", templates=["thoughts"]),
    TabDef(icon="◆",  label="Overview",    key="overview",     font_type="content", templates=["overview"]),
    TabDef(icon="⌘",  label="Conversation",key="conv",         font_type="content", templates=["conversation"]),
    TabDef(icon="♛",  label="Personality", key="personality",  font_type="content", templates=["personality"]),
    TabDef(icon="❋",  label="Internal",    key="internal",     font_type="content", templates=["internal_thoughts"]),
    TabDef(icon="⚔",  label="Military",    key="forces",       font_type="code",    templates=["forces"]),
    TabDef(icon="◈",  label="Events",      key="events",       font_type="content", templates=["events"]),
    TabDef(icon="♥",  label="Relationship",key="rel",          font_type="content", templates=["relationship"]),
    TabDef(icon="⟨⟩", label="Raw JSON",    key="raw",          font_type="code",    templates=[]),
]


# ─────────────────────────────────────────────
# TAG CONFIG  (FIX #8 — spacing added to value/good/bad/warn)
# ─────────────────────────────────────────────

TAG_CONFIG: dict[str, dict] = {
    "title":    dict(font_delta=+5, weight="bold",   fg="accent",    spacing1=4,  spacing3=6),
    "section":  dict(font_delta=+1, weight="bold",   fg="accent2",   spacing1=12, spacing3=4),
    "label":    dict(font_delta=-1, weight="bold",   fg="fg_dim"),
    "value":    dict(font_delta=0,  weight="normal", fg="fg",        spacing1=1,  spacing3=1),
    "good":     dict(font_delta=0,  weight="normal", fg="green",     spacing1=1,  spacing3=1),
    "bad":      dict(font_delta=0,  weight="normal", fg="red",       spacing1=1,  spacing3=1),
    "warn":     dict(font_delta=0,  weight="normal", fg="accent3",   spacing1=1,  spacing3=1),
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


# ─────────────────────────────────────────────
# KNOWN KEYS
# ─────────────────────────────────────────────

KNOWN_KEYS: set[str] = {
    "Name", "StringId", "Gender", "AssignedTTSVoice", "LastTTSPlayedText", "LastTTSInstructions",
    "LastDialogueSceneId", "LastDynamicResponseUtteranceId", "IsInPlayerParty", "IsWithPlayer",
    "player_bind_string_id", "ConversationHistory", "DialogueObservations", "WarStatus",
    "PlayerRelation", "CurrentTask", "RecentEvents", "EmotionalState", "LocationType",
    "TimeContext", "PlayerForces", "NPCForces", "Quirks", "InformationAccessLevel",
    "CombatResponse", "IsSurrendering", "IsPlayerSurrendering", "MarriageResponse",
    "PendingDeath", "PendingSettlementCombat", "SettlementCombatResponse",
    "PendingAttackTargetHeroId", "RoleplayDeathReason", "KillerStringId",
    "LastDynamicResponse", "PendingAIResponse", "PendingActionCommandsAfterMission",
    "PendingRelationChanges", "PendingLiePenalty", "PendingWorkshopSale",
    "PendingMoneyTransfer", "PendingItemTransfers", "PendingIntimacyNotification",
    "PendingConceptionMotherName", "CharacterDescription", "AIGeneratedPersonality",
    "AIGeneratedBackstory", "AIGeneratedSpeechQuirks", "KnownSecrets", "KnownInfo",
    "ClanTierRecognitionChecked", "KnowledgeGenerated", "CounterpartySocial",
    "TrustLevel", "DaysSinceLastConversation", "InteractionCount", "Skills",
    "LeadingForces", "MilitaryForces", "Events", "LastAIResponseJson",
}