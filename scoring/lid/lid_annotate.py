#!/usr/bin/env python3
"""Per-token language-ID tagger for the code-switched classroom corpus.

Tags every normalized token as one of:

  L1     Spanish            L2     English
  AMBIG  ambiguous / short function word common to both languages
  NE     proper noun (heuristic: capitalized mid-sentence, repeated
         often enough not to be a one-off typo)
  LOAN   established loanword / classroom jargon (ok, zoom, wifi, ...)
  OTHER  pure numeral/punctuation token
  UNK    not recognized in either language's frequency list

Uses `wordfreq` zipf frequency in Spanish vs English as the core signal,
with hand-curated override sets for cases frequency alone gets wrong.
"""
from __future__ import annotations

import collections
import re

AMBIG = {
    "no", "a", "me", "si", "sin", "son", "van", "ha", "he", "la", "e", "o", "y",
    "u", "un", "en", "come", "ten", "as", "is", "an", "hay", "van", "mi", "que",
    "final", "total", "general", "natural", "hospital", "animal", "capital",
    "personal", "central", "social", "actual", "real", "normal", "ideal",
    "local", "material", "original", "familiar", "similar", "popular", "regular",
    "color", "error", "doctor", "actor", "director", "favor", "honor", "terror",
    "chocolate", "hotel", "taxi", "radio", "video", "piano", "banana", "idea",
    "area", "opera", "drama", "cine", "auto", "solo", "gas", "plan", "club",
}
LOAN = {"ok", "okay", "email", "internet", "online", "zoom", "chat", "link",
        "quiz", "test", "click", "wifi", "app", "software", "笑"}
FILLER_ES = {"eh", "este", "pues", "bueno", "o sea", "mmm", "ajam"}
FILLER_EN = {"um", "uh", "mhm", "aha", "hmm", "like", "yeah", "okay", "so", "well"}

_RE_NUM = re.compile(r"^[\d.,:%-]+$")


def ne_set(rows: list[dict], *, text_key: str = "text", speaker_key: str = "speaker",
           min_count: int = 2, min_ratio: float = 0.8) -> set[str]:
    """Heuristic proper-noun set: speaker names (always) plus any word that
    is capitalized mid-sentence often enough (>= min_count times, >= min_ratio
    of its own occurrences) not to be a one-off capitalization slip."""
    ne: set[str] = set()
    upper = collections.Counter()
    total = collections.Counter()
    END = tuple(".?!…")
    for r in rows:
        for part in r[speaker_key].split():
            if len(part) > 2 and part.isalpha():
                ne.add(part.lower())
        raw = r[text_key].split()
        for i, w in enumerate(raw):
            core = re.sub(r"^[^\w]+|[^\w]+$", "", w)
            if len(core) < 3 or not core.isalpha():
                continue
            total[core.lower()] += 1
            start_of_sentence = i == 0 or raw[i - 1].endswith(END)
            if core[0].isupper() and not start_of_sentence:
                upper[core.lower()] += 1
    for t, n in upper.items():
        if n >= min_count and n / total[t] >= min_ratio:
            ne.add(t)
    return ne


def tag(token: str, ne: set[str], margin: float = 0.75) -> str:
    from wordfreq import zipf_frequency
    if _RE_NUM.match(token):
        return "OTHER"
    if token in LOAN:
        return "LOAN"
    if token in AMBIG:
        return "AMBIG"
    if token in FILLER_ES:
        return "L1"
    if token in FILLER_EN:
        return "L2"
    if token in ne:
        return "NE"
    zs = zipf_frequency(token, "es")
    ze = zipf_frequency(token, "en")
    if zs == 0 and ze == 0:
        return "UNK"
    if abs(zs - ze) < margin:
        return "AMBIG"
    return "L1" if zs > ze else "L2"


def tag_tokens(toks: list[str], ne: set[str]) -> list[str]:
    return [tag(t, ne) for t in toks]
