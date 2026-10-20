#!/usr/bin/env python3
"""Transcript-hygiene fixes for the *readable* transcript (text_clean) --
punctuation and casing preserved -- as opposed to normalize_text.normalize(),
the heavy stripping normalizer used only at scoring time. Every function
here is non-destructive: none drop a turn or delete words, only tag in
place or log to a `notes` list so ambiguous cases are reviewable.
"""
from __future__ import annotations

import re

from normalize_text import _digits_to_words, _unify_typography  # reuse, don't reimplement

MAX_CUE_SECONDS = 30.0

# Closed list of permitted annotation markers. Anything not in it is kept
# (never deleted) but reported so a human can extend the list.
ANNOTATION_WHITELIST = {
    "laugh": "[laughs]", "laughs": "[laughs]", "laughing": "[laughs]",
    "cough": "[cough]", "coughs": "[cough]", "coughing": "[cough]",
    "breath": "[breath]", "breathing": "[breath]",
    "pause": "[pause]",
    "unintelligible": "[unintelligible]", "inaudible": "[unintelligible]",
    "*inaudible": "[unintelligible]",
    "?": "[unintelligible]", "??": "[unintelligible]", "???": "[unintelligible]",
    "ov": "[ov]", "/ov": "[/ov]",
}

_RE_PAREN_UNINTELLIGIBLE = re.compile(r"\(\?+\)")
_RE_ANNOTATION_SPAN = re.compile(r"[{\[]([^{}\[\]]*)[}\]]")


def clean_annotations(text: str, notes: list[str] | None = None) -> str:
    """Map every {..}/[..] annotation and (???) marker to the whitelist's
    canonical [marker] spelling. A marker not on the whitelist is converted
    to bracket form (so at least the typography is consistent) and appended
    to `notes` for manual review -- its content is kept, never dropped."""
    text = _RE_PAREN_UNINTELLIGIBLE.sub(" [unintelligible] ", text)

    def repl(m: re.Match) -> str:
        raw = m.group(1).strip()
        key = raw.lower()
        if key in ANNOTATION_WHITELIST:
            return ANNOTATION_WHITELIST[key]
        if notes is not None:
            notes.append(f"unknown annotation marker: {{{raw}}} (kept as [{raw}], review needed)")
        return f"[{raw}]" if raw else ""

    text = _RE_ANNOTATION_SPAN.sub(repl, text)
    return " ".join(text.split())


# --------------------------------------------------------- typography --

def ascii_typography(text: str) -> str:
    """Unify curly quotes/dashes/ellipsis to the project's ASCII convention."""
    return _unify_typography(text.replace("…", "..."))


_SPANISH_Q_WORDS = {
    "que", "qué", "como", "cómo", "donde", "dónde", "cuando", "cuándo",
    "cual", "cuál", "cuales", "cuáles", "quien", "quién", "quienes", "quiénes",
    "cuanto", "cuánto", "cuanta", "cuánta", "cuantos", "cuántos", "cuantas", "cuántas",
}
# A clause containing any of these is confidently English regardless of
# `lang_hint`.
_ENGLISH_MARKERS = {
    "the", "you", "your", "is", "are", "can", "do", "does", "don't", "doesn't",
    "what", "that", "this", "and", "to", "of", "in", "i", "we", "my", "our",
    "their", "his", "her", "not", "have", "has", "will", "would", "should",
    "could", "screen", "see", "share", "going", "gonna", "with", "for",
}
_ACCENTED_ES = re.compile(r"[áéíóúñü]", re.IGNORECASE)
_RE_SENTENCE = re.compile(r"[^.!?]*[.!?]|[^.!?]+$")


def _looks_spanish(clause: str, lang_hint: str = "es") -> bool:
    words = re.findall(r"[\w']+", clause.lower())
    if any(w in _ENGLISH_MARKERS for w in words):
        return False
    if _ACCENTED_ES.search(clause) or any(w in _SPANISH_Q_WORDS for w in words):
        return True
    # No strong signal either way: fall back to the cue's own dominant
    # language (see dominant_language()).
    return lang_hint == "es"


def add_opening_marks(text: str, lang_hint: str = "es") -> str:
    """Insert a missing opening ¿/¡ on Spanish-looking clauses that already
    have the closing mark, e.g. "Si pueden ver mi pantalla?" ->
    "¿Si pueden ver mi pantalla?". Never removes an existing mark, and
    never invents one on a clause it isn't confident about."""
    out_parts = []
    for m in _RE_SENTENCE.finditer(text):
        clause = m.group(0)
        if not clause:
            continue
        leading_ws = clause[: len(clause) - len(clause.lstrip())]
        body = clause.strip()
        if body and _looks_spanish(body, lang_hint):
            if body.endswith("?") and not body.startswith("¿"):
                body = "¿" + body
            elif body.endswith("!") and not body.startswith("¡"):
                body = "¡" + body
        out_parts.append(leading_ws + body)
    result = " ".join(p for p in out_parts if p)
    return result if result else text


# ------------------------------------------------------------ numerals --

def spell_numerals_in_text(text: str, lang: str) -> str:
    """Spell out digit runs as words in `lang`, on the *readable* transcript
    (punctuation intact)."""
    return _digits_to_words(text, lang)


def dominant_language(lid_labels: list[str]) -> str:
    """Per-cue dominant language from its own LID tags, for use as the
    `lang` argument to spell_numerals_in_text()/normalize_text.normalize().
    Falls back to Spanish (the base language of instruction) when a cue has
    no L1/L2 evidence at all (e.g. "okay", "mhm")."""
    l1 = lid_labels.count("L1")
    l2 = lid_labels.count("L2")
    if l1 == 0 and l2 == 0:
        return "es"
    return "es" if l1 >= l2 else "en"


# ------------------------------------------------------------- speaker --

_RE_INLINE_CLARIFICATION = re.compile(r"\s*[{(][^{}()]*[)}]\s*$")


def sanitize_speaker(raw_speaker: str, speaker_map: dict[str, str] | None = None) -> tuple[str, str]:
    """Return (stable_id, display_name) for a raw speaker field.

    Zoom display names sometimes carry an inline clarification, e.g.
    "Name {AKA Nickname}". If `speaker_map` (raw name -> canonical display
    name) is supplied, it's consulted first; otherwise the inline
    clarification is simply stripped and the remaining name is slugified.
    """
    raw = raw_speaker.strip()
    if speaker_map and raw in speaker_map:
        display = speaker_map[raw]
    else:
        display = _RE_INLINE_CLARIFICATION.sub("", raw).strip() or raw
    slug = re.sub(r"[^a-z0-9]+", "_", display.lower()).strip("_") or "unknown"
    return slug, display


def flag_long_cues(cues: list[dict], max_seconds: float = MAX_CUE_SECONDS) -> list[int]:
    """Indices of cues longer than `max_seconds`, so they're surfaced for
    review instead of silently dropped downstream."""
    return [i for i, c in enumerate(cues)
            if c.get("end_s") is not None and (c["end_s"] - c["start_s"]) > max_seconds]


# ---------------------------------------------------------- caption txt --

def assign_missing_end_times(cues: list[dict], default_dur: float = 3.0) -> None:
    """In place: fill end_s for cues parsed from the caption .txt format
    (which only has a start time per turn) from the next cue's start,
    within the same recording. The very last cue gets `default_dur` since
    there is no next start to borrow from."""
    for i, c in enumerate(cues):
        if c.get("end_s") is not None:
            continue
        if i + 1 < len(cues):
            c["end_s"] = cues[i + 1]["start_s"]
        else:
            c["end_s"] = c["start_s"] + default_dur
