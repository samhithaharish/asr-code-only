#!/usr/bin/env python3

from __future__ import annotations

import argparse
import collections
import csv
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "lid_runs"

REF_TURNS_COLUMNS = ["session_id", "site", "order", "speaker", "role", "text"]

# --- text normalization ---

PUNCTUATION_TO_REMOVE = ",?¿¡!\";:."
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


def _cs_normalize(text: str, lowercase: bool = True) -> str:
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

_NUMERAL_WORDS = set(_ES_UNITS)


def _spell(n: int, lang: str) -> str:
    table = _ES_UNITS if lang == "es" else _EN_UNITS
    return table[n] if 0 <= n < len(table) else str(n)


def _digits_to_words(text: str, lang: str) -> str:
    text = _RE_ORDINAL_MARK.sub(lambda m: m.group(1), text)
    return _RE_INT.sub(lambda m: _spell(int(m.group(0)), lang), text)


_TYPOGRAPHIC = {"’": "'", "‘": "'", "“": '"', "”": '"',
                "´": "'", "′": "'"}
_RE_DASH = re.compile(r"[‐-―−]")


def _unify_typography(text: str) -> str:
    for a, b in _TYPOGRAPHIC.items():
        text = text.replace(a, b)
    text = _RE_DASH.sub(" ", text)
    return " ".join(t for t in text.split() if set(t) - set("-'\""))


def normalize(text: str, *, numerals: str = "words", lang: str = "es",
              strip_accents: bool = False, lowercase: bool = True) -> str:
    out = _unify_typography(str(text or ""))
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


# --- per-token language tagging ---

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


def _ne_set(rows: list[dict], min_count: int = 2, min_ratio: float = 0.8) -> set[str]:
    ne: set[str] = set()
    upper = collections.Counter()
    total = collections.Counter()
    END = tuple(".?!…")
    for r in rows:
        for part in r["speaker"].split():
            if len(part) > 2 and part.isalpha():
                ne.add(part.lower())
        raw = r["text"].split()
        for i, w in enumerate(raw):
            core = re.sub(r"^[^\w]+|[^\w]+$", "", w)
            if len(core) < 3 or not core.isalpha():
                continue
            total[core.lower()] += 1
            inicio_de_frase = i == 0 or raw[i - 1].endswith(END)
            if core[0].isupper() and not inicio_de_frase:
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


# --- Zoom caption-file parsing ---

_HEADER = re.compile(r"^\[(.+?)\]\s+\d{2}:\d{2}:\d{2}$")


def parse_zoom_captions(text: str, *, session_id: str, site: str,
                         instructors: set[str] | None = None) -> list[dict]:
    instructors = instructors or set()
    rows: list[dict] = []
    speaker = None
    buf: list[str] = []
    order = 0

    def flush():
        nonlocal order
        if speaker and buf:
            turn_text = " ".join(buf).strip()
            if turn_text:
                order += 1
                role = "instructor" if speaker in instructors else "student"
                rows.append({"session_id": session_id, "site": site, "order": order,
                             "speaker": speaker, "role": role, "text": turn_text})

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _HEADER.match(line)
        if m:
            flush()
            speaker = m.group(1)
            buf = []
        else:
            buf.append(line)
    flush()
    return rows


def _load_passthrough(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        missing = set(REF_TURNS_COLUMNS) - set(r.fieldnames or [])
        if missing:
            raise SystemExit(f"{path}: missing columns {sorted(missing)}")
        return list(r)


# --- pipeline ---

def run(rows: list[dict]) -> tuple[list[dict], collections.Counter,
                                    dict, collections.Counter]:
    """Tags every row's text; returns (lid_rows, overall_counts, role_counts, unk)."""
    ne = _ne_set(rows)
    lid_rows, counts, unk = [], collections.Counter(), collections.Counter()
    role_cat = collections.defaultdict(collections.Counter)
    for r in rows:
        toks = tokens(r["text"])
        labs = [tag(t, ne) for t in toks]
        assert len(toks) == len(labs)
        for t, l in zip(toks, labs):
            counts[l] += 1
            role_cat[r["role"]][l] += 1
            if l == "UNK":
                unk[t] += 1
        lid_rows.append({**r, "text_norm": " ".join(toks), "lid_labels": " ".join(labs)})
    return lid_rows, counts, role_cat, unk


def report(lid_rows: list[dict], counts: collections.Counter,
           role_cat: dict, unk: collections.Counter) -> str:
    L = []
    tot = sum(counts.values())
    L.append(f"{len(lid_rows)} turnos, {tot} tokens")
    for k, n in counts.most_common():
        L.append(f"  {k:<6} {n:>6}  {100*n/tot:5.1f} %")
    L.append("\npor rol (% de tokens del rol):")
    for role, c in role_cat.items():
        t = sum(c.values())
        L.append(f"  {role:<11} " + "  ".join(
            f"{k} {100*c[k]/t:4.1f}%" for k in ("L1", "L2", "AMBIG", "NE", "LOAN", "UNK")))
    L.append("")

    for label in ("L1", "UNK", "OTHER"):
        hits = []
        for r in lid_rows:
            for t, l in zip(r["text_norm"].split(), r["lid_labels"].split()):
                if l == label:
                    flag = " [numeral artifact]" if t in _NUMERAL_WORDS else ""
                    hits.append((t, r["speaker"], r["text_norm"], flag))
        if not hits:
            continue
        L.append(f"=== {label} tokens ({len(hits)}) — review these ===")
        for t, spk, text, flag in hits:
            L.append(f"  {t!r:15}{flag:20} {spk:20} {text}")
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--transcript", type=Path,
                      help="Zoom saved_closed_caption.txt-style file")
    src.add_argument("--ref-turns", type=Path,
                      help="existing ref_turns.csv to pass straight through")
    ap.add_argument("--name", required=True,
                     help="run name; output goes to runs/<name>/")
    ap.add_argument("--session-id", default=None, help="default: --name")
    ap.add_argument("--site", default="unspecified")
    ap.add_argument("--instructor", action="append", default=[],
                     help="speaker name to tag role=instructor (repeatable); "
                          "everyone else defaults to role=student")
    ap.add_argument("--review", action="store_true",
                     help="also print the most-common UNK tokens across the whole run")
    args = ap.parse_args()

    if args.transcript:
        rows = parse_zoom_captions(
            args.transcript.read_text(encoding="utf-8"),
            session_id=args.session_id or args.name,
            site=args.site,
            instructors=set(args.instructor),
        )
    else:
        rows = _load_passthrough(args.ref_turns)

    if not rows:
        raise SystemExit("no turns parsed — check the input format")

    lid_rows, counts, role_cat, unk = run(rows)

    out_dir = RUNS / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "ref_turns.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(REF_TURNS_COLUMNS)
        for r in rows:
            w.writerow([r[c] for c in REF_TURNS_COLUMNS])

    with (out_dir / "ref_lid.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(REF_TURNS_COLUMNS[:-1] + ["text_norm", "lid_labels"])
        for r in lid_rows:
            w.writerow([r[c] for c in REF_TURNS_COLUMNS[:-1]] + [r["text_norm"], r["lid_labels"]])

    txt = report(lid_rows, counts, role_cat, unk)
    (out_dir / "report.txt").write_text(txt, encoding="utf-8")
    print(txt)
    print(f"-> {out_dir}/")

    if args.review:
        print(f"\n{sum(unk.values())} tokens UNK, {len(unk)} tipos distintos")
        for t, n in unk.most_common(60):
            print(f"  {n:>5}  {t}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
