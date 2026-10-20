#!/usr/bin/env python3
"""The single text normalizer used for *scoring* (WER/CER). All per-cue and
document-level scoring in this project passes through here.

Unicode NFC, bracket/brace annotation tags and unintelligible markers
removed, punctuation stripped, but apostrophes and hyphens kept (lexical in
English and compound words). Numerals are spelled out as words rather than
left as digits, since collapsing both sides to digits would neutralize
language exactly where code-switching matters most ("siete"/"seven" both
become "7"). Diacritics are preserved by default (`strip_accents=True` is
only for a sensitivity check).

NOTE: this is the *scoring* normalizer -- it strips essentially all
punctuation, which is correct for WER/CER but destroys readability. For a
cleaned, human-readable transcript, use clean_rules.py's lighter cleanup
instead, and normalize with this module only at scoring time.
"""
from __future__ import annotations

import re
import unicodedata

# Note: apostrophe and hyphen are deliberately excluded (so "don't" keeps its own).
PUNCTUATION_TO_REMOVE = ",?¿¡!\";:."

_ELLIPSIS_SENTINEL = "\x00E\x00"

_RE_BRACKET_TAG = re.compile(r"\[[^\]]*\]")
# Parenthetical annotations: correction pairs (verbatim=target), unclear
# overlap ((  )), and unintelligible markers (???) are all meta-annotation,
# never literal spoken text, so the whole span is stripped like [...]/{...}.
_RE_PAREN_ANNOTATION = re.compile(r"\([^()]*\)")
_RE_TOKEN_FINAL_ELLIPSIS = re.compile(r"(?<=\w)\.{2,}")
_RE_PUNCT = re.compile("[" + re.escape(PUNCTUATION_TO_REMOVE) + "]")
_RE_WHITESPACE = re.compile(r"\s+")


def _strip_paren_annotations(text: str) -> str:
    """Repeatedly strip innermost (...) spans so nested annotations like the
    unclear-overlap marker "((  ))" are fully removed, not just their
    innermost level."""
    while True:
        new = _RE_PAREN_ANNOTATION.sub(" ", text)
        if new == text:
            return new
        text = new


def _cs_normalize(text: str, lowercase: bool = True) -> str:
    """Bracket/brace/paren annotation tags, disfluency-ellipsis protection,
    and punctuation removal, in the order that preserves token-final
    ellipses."""
    if text is None:
        return ""
    out = unicodedata.normalize("NFC", str(text))
    out = _RE_BRACKET_TAG.sub(" ", out)
    out = _strip_paren_annotations(out)
    out = out.replace("…", "...")
    out = _RE_TOKEN_FINAL_ELLIPSIS.sub(_ELLIPSIS_SENTINEL, out)
    out = " ".join(tok for tok in out.split() if set(tok) != {"."})
    out = _RE_PUNCT.sub("", out)
    out = out.replace(_ELLIPSIS_SENTINEL, "...")
    if lowercase:
        out = out.lower()
    return _RE_WHITESPACE.sub(" ", out).strip()


_ES_UNITS = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
             "ocho", "nueve", "diez", "once", "doce", "trece", "catorce",
             "quince", "dieciseis", "diecisiete", "dieciocho", "diecinueve",
             "veinte", "veintiuno", "veintidos", "veintitres", "veinticuatro",
             "veinticinco", "veintiseis", "veintisiete", "veintiocho",
             "veintinueve", "treinta"]
_EN_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven",
             "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
             "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
             "twenty", "twentyone", "twentytwo", "twentythree", "twentyfour",
             "twentyfive", "twentysix", "twentyseven", "twentyeight",
             "twentynine", "thirty"]

_RE_INT = re.compile(r"\b\d+\b")
_RE_ORDINAL_MARK = re.compile(r"\b(\d+)(º|ª|°|st|nd|rd|th)\b", re.IGNORECASE)

# 0-30 only: above that the digit is left as-is.
NUMERAL_WORDS = set(_ES_UNITS)


def _spell(n: int, lang: str) -> str:
    table = _ES_UNITS if lang == "es" else _EN_UNITS
    return table[n] if 0 <= n < len(table) else str(n)


def _digits_to_words(text: str, lang: str) -> str:
    text = _RE_ORDINAL_MARK.sub(lambda m: m.group(1), text)
    return _RE_INT.sub(lambda m: _spell(int(m.group(0)), lang), text)


# Typographic quotes/dashes unified to ASCII so curly vs. straight
# apostrophes don't count as different tokens.
_TYPOGRAPHIC = {"’": "'", "‘": "'", "“": '"', "”": '"',
                "´": "'", "′": "'"}
_RE_DASH = re.compile(r"[‐-―−]")

# Transcriber annotations in curly braces ({coughs}, {types in chat}):
# not speech, shouldn't count as reference words at scoring time.
_RE_BRACES = re.compile(r"\{[^}]*\}")


def _unify_typography(text: str) -> str:
    for a, b in _TYPOGRAPHIC.items():
        text = text.replace(a, b)
    text = _RE_DASH.sub(" ", text)
    return " ".join(t for t in text.split() if set(t) - set("-'\""))


def normalize(text: str, *, numerals: str = "words", lang: str = "es",
              strip_accents: bool = False, lowercase: bool = True) -> str:
    """Normalize for scoring.

    numerals: "words" (default) spells digits out in `lang`; "digits" keeps
    digits as-is (sensitivity check, favors Zoom); "keep" touches nothing.
    """
    out = _unify_typography(str(text or ""))
    out = _RE_BRACES.sub(" ", out)
    out = _cs_normalize(out, lowercase=lowercase)
    if numerals == "words":
        out = _digits_to_words(out, lang)
    if strip_accents:
        out = "".join(c for c in unicodedata.normalize("NFD", out)
                       if unicodedata.category(c) != "Mn")
    return " ".join(out.split())


def tokens(text: str, **kw) -> list[str]:
    n = normalize(text, **kw)
    return n.split() if n else []


def chars(text: str, **kw) -> list[str]:
    """Character sequence for CER, spaces included."""
    return list(normalize(text, **kw))


if __name__ == "__main__":
    for t in ["Tenemos 3 grupos, ¿ok? [laughs] I don... I don't know",
              "La unidad 7 y la 21 — see you!", "Está bien… (???) sí"]:
        print(f" in : {t}\n es : {normalize(t)}\n en : {normalize(t, lang='en')}"
              f"\n dig: {normalize(t, numerals='digits')}\n")
