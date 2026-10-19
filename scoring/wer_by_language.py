#!/usr/bin/env python3
"""WER on code-switched turns vs. monolingual turns.

A turn-level role split doesn't work here, because code-switching is a
property of the *turn*, not the *speaker*: filtering down to just the
code-switched turns would make the rest of the hypothesis count as
insertions and inflate the WER. Instead this aligns each whole session
word-by-word, attributes every error to the reference turn it falls in,
and aggregates by turn type afterward.

Turn classification comes from a per-token LID label (L1 Spanish, L2
English, AMBIG, NE, LOAN, OTHER, UNK):

  code-switched   has at least one L1 *and* at least one L2 token
  spanish-only    has L1, no L2
  english-only    has L2, no L1

AMBIG/NE/LOAN tokens don't count as evidence of a switch. Insertions fall
outside any reference turn, so they're attributed to the preceding one and
reported separately.

Usage:
    python3 wer_by_language.py \\
        --hyp zeroshot_output.json --name zero-shot \\
        --hyp finetuned_output.json --name fine-tuned \\
        --out results/CS_BREAKDOWN.md
"""
from __future__ import annotations

import argparse
import bisect
import collections
import csv
import json
import sys
from pathlib import Path

import jiwer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "preprocessing"))
import normalize_text as N  # noqa: E402

CLASES = ("code-switched", "spanish-only", "english-only")


def clasifica(labels: list[str]) -> str | None:
    l1 = any(x == "L1" for x in labels)
    l2 = any(x == "L2" for x in labels)
    if l1 and l2:
        return "code-switched"
    if l1:
        return "spanish-only"
    if l2:
        return "english-only"
    return None            # solo AMBIG/NE/LOAN/OTHER: no dice nada, se descarta


def referencia() -> dict[str, list[tuple[str, list[str]]]]:
    """Por sesion, la lista de (clase, palabras normalizadas) en orden."""
    por = collections.defaultdict(list)
    with (ROOT / "corpus" / "ref_lid.csv").open(encoding="utf-8") as fh:
        filas = sorted(csv.DictReader(fh),
                       key=lambda r: (r["session_id"], int(r["order"])))
    for r in filas:
        labs = r["lid_labels"].split()
        cl = clasifica(labs)
        if cl is None:
            continue
        pal = N.normalize(r["text_norm"]).split()
        if pal:
            por[r["session_id"]].append((cl, pal))
    return por


def hipotesis(p: Path) -> dict[str, list[str]]:
    por = collections.defaultdict(list)
    for s in json.loads(p.read_text()):
        por[s["session_id"]].append((float(s.get("start_time", 0)), s["words"]))
    return {k: N.normalize(" ".join(w for _, w in sorted(v))).split()
            for k, v in por.items()}


def mide(ref_por_sesion, hyp_por_sesion) -> tuple[dict, int]:
    """Errores por clase de turno, alineando cada sesion entera."""
    acc = {c: collections.Counter() for c in CLASES}
    inserciones_huerfanas = 0

    for sid, turnos in ref_por_sesion.items():
        if sid not in hyp_por_sesion:
            continue
        # indice: para cada palabra de referencia, a que clase pertenece
        clase_de = []
        for cl, pal in turnos:
            clase_de += [cl] * len(pal)
        ref = [w for _, pal in turnos for w in pal]
        hyp = hyp_por_sesion[sid]
        if not ref or not hyp:
            continue

        out = jiwer.process_words([" ".join(ref)], [" ".join(hyp)])
        for ch in out.alignments[0]:
            if ch.type == "insert":
                # no cae en ningun turno: se atribuye al anterior
                i = min(max(ch.ref_start_idx - 1, 0), len(clase_de) - 1)
                acc[clase_de[i]]["ins"] += ch.hyp_end_idx - ch.hyp_start_idx
                inserciones_huerfanas += ch.hyp_end_idx - ch.hyp_start_idx
                continue
            for i in range(ch.ref_start_idx, ch.ref_end_idx):
                c = clase_de[i]
                acc[c]["n"] += 1
                if ch.type == "substitute":
                    acc[c]["sub"] += 1
                elif ch.type == "delete":
                    acc[c]["del"] += 1
    return acc, inserciones_huerfanas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hyp", type=Path, action="append", required=True)
    ap.add_argument("--name", action="append", required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if len(args.hyp) != len(args.name):
        ap.error("--hyp y --name van en pares")

    ref = referencia()
    tok = {c: sum(len(p) for s in ref.values() for cl, p in s if cl == c)
           for c in CLASES}
    turnos = {c: sum(1 for s in ref.values() for cl, _ in s if cl == c)
              for c in CLASES}
    total = sum(tok.values())

    L = ["# Error rate by turn type: code-switched against monolingual", "",
         "Word-level alignment over each whole session; every error is charged",
         "to the reference turn it falls in. A turn counts as *code-switched*",
         "if it contains at least one Spanish and one English token. Ambiguous",
         "words, proper nouns and established loans are not evidence of a",
         "switch and do not count.", "",
         "## How much material of each kind", "",
         "| turn type | turns | tokens | % of tokens |", "|---|---|---|---|"]
    for c in CLASES:
        L.append(f"| {c} | {turnos[c]:,} | {tok[c]:,} | {100*tok[c]/total:.1f} % |")

    L += ["", "## Error rate by turn type", "",
          "| system | " + " | ".join(CLASES) + " | ratio mixed / Spanish |",
          "|---|" + "---|" * (len(CLASES) + 1)]
    for p, nom in zip(args.hyp, args.name):
        acc, huer = mide(ref, hipotesis(p))
        wers = {}
        for c in CLASES:
            a = acc[c]
            wers[c] = 100 * (a["sub"] + a["del"] + a["ins"]) / max(a["n"], 1)
        ratio = wers["code-switched"] / max(wers["spanish-only"], 1e-9)
        L.append(f"| {nom} | " +
                 " | ".join(f"{wers[c]:.2f}" for c in CLASES) +
                 f" | {ratio:.2f}x |")
        print(f"{nom}: " + "  ".join(f"{c} {wers[c]:.2f}" for c in CLASES) +
              f"  (ratio {ratio:.2f}x, {huer} inserciones atribuidas al turno previo)")

    L += ["", "Insertions fall outside any reference turn, so they are charged to",
          "the preceding one. That is the only debatable choice in the method,",
          "which is why the script reports the count separately.", ""]

    txt = "\n".join(L)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(txt, encoding="utf-8")
        print(f"-> {args.out}")
    else:
        print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
