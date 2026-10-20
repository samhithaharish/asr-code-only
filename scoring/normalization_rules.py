"""Text normalizer: removes bracketed meta-linguistic tags (e.g. [laugh]),
unintelligible-speech markers (e.g. (???)), stray ellipses, and punctuation,
while preserving token-final ellipses used for disfluencies (e.g. "don...").
Lowercasing is configurable (default on, matching case-insensitive WER)."""

from __future__ import annotations

import re
import unicodedata

# Note: apostrophe and hyphen are deliberately excluded (so "don't" keeps its own).
PUNCTUATION_TO_REMOVE = ",?¿¡!\";:."

# Internal sentinel to shield token-final ellipses; U+0000 can't appear in real text.
_ELLIPSIS_SENTINEL = "\x00E\x00"

_RE_BRACKET_TAG = re.compile(r"\[[^\]]*\]")
_RE_BRACE_TAG = re.compile(r"\{[^}]*\}")
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


def normalize(text: str, lowercase: bool = True) -> str:
    """The single entry point: both training targets and scoring
    hypotheses/references must pass through here."""
    if text is None:
        return ""

    out = unicodedata.normalize("NFC", str(text))
    out = _RE_BRACKET_TAG.sub(" ", out)
    out = _RE_BRACE_TAG.sub(" ", out)
    out = _strip_paren_annotations(out)
    out = out.replace("…", "...")
    out = _RE_TOKEN_FINAL_ELLIPSIS.sub(_ELLIPSIS_SENTINEL, out)
    out = " ".join(tok for tok in out.split() if set(tok) != {"."})
    out = _RE_PUNCT.sub("", out)
    out = out.replace(_ELLIPSIS_SENTINEL, "...")

    if lowercase:
        out = out.lower()

    return _RE_WHITESPACE.sub(" ", out).strip()


def tokenize(text: str, lowercase: bool = True) -> list[str]:
    """Whole-token, whitespace-split tokenization (no subword splitting)."""
    normalized = normalize(text, lowercase=lowercase)
    return normalized.split() if normalized else []
