#!/usr/bin/env python3
"""
Score Muse Voice Transcribe output against the gold reference transcripts.

Muse only gives turn-level timestamps (no word-level alignment), so this
scores at the document level: concatenate gold utterances and Muse turns
in time order and compute WER/CER over the whole thing.

For a partially-transcribed recording (e.g. Muse only covered the first
N minutes), the gold reference is truncated to the same time window so
the comparison is apples-to-apples rather than penalizing Muse for audio
it was never given.

Usage: python3 score.py
"""
import json
import re
from pathlib import Path

import jiwer

SCRIPT_DIR = Path(__file__).resolve().parent
GOLD_DIR = SCRIPT_DIR.parent / "sessions" / "gold_legacy"
MUSE_DIR = SCRIPT_DIR.parent / "sessions" / "muse_output_legacy"
SCORES_DIR = SCRIPT_DIR.parent / "sessions" / "scores_legacy"

# Strip transcriber annotations like {laughs} or [unintelligible] before
# scoring -- no ASR system can output these tokens, so leaving them in the
# reference would count every one as an unfair, unrecoverable deletion.
_RE_ANNOT = re.compile(r"\{[^}]*\}|\[[^\]]*\]")


def strip_annotations(text):
    return " ".join(_RE_ANNOT.sub(" ", text).split())

TRANSFORM = jiwer.Compose([
    jiwer.ToLowerCase(),
    jiwer.RemoveMultipleSpaces(),
    jiwer.Strip(),
    jiwer.RemovePunctuation(),
])
WORDS_TRANSFORM = jiwer.Compose([*TRANSFORM.transforms, jiwer.ReduceToListOfListOfWords()])
CHARS_TRANSFORM = jiwer.Compose([*TRANSFORM.transforms, jiwer.ReduceToListOfListOfChars()])

RECORDINGS = ["s83ldou", "s06mps9", "spa416_week1_group2"]

# Role mapping where the gold transcript only has generic diarization IDs
# (Speaker 1-4, UNKNOWN) and no ground-truth role label.
ROLE_MAPS = {
    "spa416_week1_group2": {
        "Teacher": {"Speaker 1"},
        "Student": {"Speaker 2", "Speaker 3", "Speaker 4", "UNKNOWN"},
    },
}


def concat_text(entries, key="text_clean"):
    entries = sorted(entries, key=lambda e: e["start_s"] if e.get("start_s") is not None else 0)
    cleaned = (strip_annotations(e[key]) for e in entries)
    return " ".join(t for t in cleaned if t)


def merge_windows(intervals, pad=0.5):
    """Merge (possibly overlapping, after padding) time intervals into a
    minimal set of covering windows."""
    if not intervals:
        return []
    padded = sorted((max(0.0, s - pad), e + pad) for s, e in intervals)
    merged = [padded[0]]
    for s, e in padded[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))
    return merged


def overlaps_any(start, end, windows):
    return any(start < w_end and end > w_start for w_start, w_end in windows)


def build_diff(word_out):
    """Turn jiwer's alignment chunks into a readable list of error spans."""
    ref_words = word_out.references[0]
    hyp_words = word_out.hypotheses[0]
    diff = []
    for chunk in word_out.alignments[0]:
        if chunk.type == "equal":
            continue
        diff.append({
            "type": chunk.type,  # "substitute", "delete", "insert"
            "ref_words": ref_words[chunk.ref_start_idx:chunk.ref_end_idx],
            "hyp_words": hyp_words[chunk.hyp_start_idx:chunk.hyp_end_idx],
        })
    return diff


def score_subset(gold_subset, muse, muse_covered_end):
    """Restrict to gold's own annotated windows within muse_covered_end,
    pull the overlapping Muse text, and compute WER/CER + a diff."""
    gold_in_range = [g for g in gold_subset if g["start_s"] < muse_covered_end]
    windows = merge_windows([(g["start_s"], g["end_s"]) for g in gold_in_range])
    muse_in_window = [t for t in muse
                       if t.get("start_s") is not None
                       and overlaps_any(t["start_s"], t["end_s"], windows)]

    ref_text = concat_text(gold_in_range)
    hyp_text = concat_text(muse_in_window)

    word_out = jiwer.process_words(ref_text, hyp_text,
                                    reference_transform=WORDS_TRANSFORM,
                                    hypothesis_transform=WORDS_TRANSFORM)
    char_out = jiwer.process_characters(ref_text, hyp_text,
                                         reference_transform=CHARS_TRANSFORM,
                                         hypothesis_transform=CHARS_TRANSFORM)

    return {
        "n_gold_utterances_scored": len(gold_in_range),
        "n_muse_turns_scored": len(muse_in_window),
        "wer": round(word_out.wer, 4),
        "word_hits": word_out.hits,
        "word_substitutions": word_out.substitutions,
        "word_deletions": word_out.deletions,
        "word_insertions": word_out.insertions,
        "cer": round(char_out.cer, 4),
        "char_hits": char_out.hits,
        "char_substitutions": char_out.substitutions,
        "char_deletions": char_out.deletions,
        "char_insertions": char_out.insertions,
        "reference_text": ref_text,
        "hypothesis_text": hyp_text,
        "errors": build_diff(word_out),
    }


def overlap_amount(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_turns_to_roles(gold_in_range, muse_in_window, role_of_speaker):
    """Give each Muse turn to exactly one role: whichever gold utterance
    it overlaps most (falling back to closest by midpoint distance)."""
    assigned = {role: [] for role in set(role_of_speaker.values())}
    for t in muse_in_window:
        best_g, best_score = None, -1.0
        for g in gold_in_range:
            ov = overlap_amount(t["start_s"], t["end_s"], g["start_s"], g["end_s"])
            if ov > best_score:
                best_g, best_score = g, ov
        if best_g is None:
            continue
        if best_score <= 0:
            t_mid = (t["start_s"] + t["end_s"]) / 2
            best_g = min(gold_in_range, key=lambda g: abs((g["start_s"] + g["end_s"]) / 2 - t_mid))
        assigned[role_of_speaker[best_g["speaker"]]].append(t)
    return assigned


def score_by_role(gold, muse, muse_covered_end, role_map):
    role_of_speaker = {spk: role for role, spks in role_map.items() for spk in spks}
    gold_in_range = [g for g in gold if g["start_s"] < muse_covered_end and g["speaker"] in role_of_speaker]
    windows = merge_windows([(g["start_s"], g["end_s"]) for g in gold_in_range])
    muse_in_window = [t for t in muse
                       if t.get("start_s") is not None
                       and overlaps_any(t["start_s"], t["end_s"], windows)]

    assigned = assign_turns_to_roles(gold_in_range, muse_in_window, role_of_speaker)

    results = {}
    for role, speaker_ids in role_map.items():
        gold_role = [g for g in gold_in_range if g["speaker"] in speaker_ids]
        muse_role = assigned.get(role, [])

        ref_text = concat_text(gold_role)
        hyp_text = concat_text(muse_role)
        word_out = jiwer.process_words(ref_text, hyp_text,
                                        reference_transform=WORDS_TRANSFORM,
                                        hypothesis_transform=WORDS_TRANSFORM)
        char_out = jiwer.process_characters(ref_text, hyp_text,
                                             reference_transform=CHARS_TRANSFORM,
                                             hypothesis_transform=CHARS_TRANSFORM)
        results[role] = {
            "n_gold_utterances_scored": len(gold_role),
            "n_muse_turns_scored": len(muse_role),
            "wer": round(word_out.wer, 4),
            "word_hits": word_out.hits,
            "word_substitutions": word_out.substitutions,
            "word_deletions": word_out.deletions,
            "word_insertions": word_out.insertions,
            "cer": round(char_out.cer, 4),
            "char_hits": char_out.hits,
            "char_substitutions": char_out.substitutions,
            "char_deletions": char_out.deletions,
            "char_insertions": char_out.insertions,
            "reference_text": ref_text,
            "hypothesis_text": hyp_text,
            "errors": build_diff(word_out),
        }
    return results


def score_one(name):
    gold_path = GOLD_DIR / f"{name}.json"
    muse_path = MUSE_DIR / f"{name}.json"
    if not gold_path.exists() or not muse_path.exists():
        return None

    gold = json.loads(gold_path.read_text())
    muse = json.loads(muse_path.read_text())
    if not muse:
        return {"name": name, "skipped": "no Muse output"}

    muse_covered_end = max(t["end_s"] for t in muse if t.get("end_s") is not None)
    full_duration = max(g["end_s"] for g in gold) if gold else 0
    partial = muse_covered_end < full_duration - 1.0  # allow rounding slack

    result = {
        "name": name,
        "partial_coverage": partial,
        "muse_covered_end_s": round(muse_covered_end, 1),
        "gold_total_duration_s": round(full_duration, 1),
        "n_muse_turns_total": len(muse),
        "overall": score_subset(gold, muse, muse_covered_end),
    }

    role_map = ROLE_MAPS.get(name)
    if role_map:
        result["by_role"] = score_by_role(gold, muse, muse_covered_end, role_map)

    return result


def format_diff_report(name, subset_label, sub):
    lines = [f"=== {name} / {subset_label} ===",
             f"WER={sub['wer']*100:.2f}%  CER={sub['cer']*100:.2f}%  "
             f"({sub['n_gold_utterances_scored']} gold utterances, {sub['n_muse_turns_scored']} Muse turns)",
             f"word errors: {sub['word_substitutions']} substitutions, "
             f"{sub['word_deletions']} deletions, {sub['word_insertions']} insertions", ""]
    if not sub["errors"]:
        lines.append("(no word errors)")
    for e in sub["errors"]:
        ref = " ".join(e["ref_words"]) or "-"
        hyp = " ".join(e["hyp_words"]) or "-"
        if e["type"] == "substitute":
            lines.append(f"  SUBSTITUTION: gold=\"{ref}\"  ->  muse=\"{hyp}\"")
        elif e["type"] == "delete":
            lines.append(f"  MISSED (Muse dropped):  gold=\"{ref}\"")
        elif e["type"] == "insert":
            lines.append(f"  EXTRA (Muse added):     muse=\"{hyp}\"")
    lines.append("")
    return "\n".join(lines)


def main():
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    all_results = {}
    report_parts = []

    for name in RECORDINGS:
        result = score_one(name)
        if result is None:
            print(f"{name}: SKIP (missing gold or Muse output)")
            continue
        all_results[name] = result

        if "skipped" in result:
            print(f"{name}: SKIP ({result['skipped']})")
            continue

        ov = result["overall"]
        cov_note = (f" [PARTIAL: scored 0-{result['muse_covered_end_s']}s "
                    f"of {result['gold_total_duration_s']}s]") if result["partial_coverage"] else ""
        print(f"{name} (overall): WER={ov['wer']*100:.2f}%  CER={ov['cer']*100:.2f}%  "
              f"({ov['n_gold_utterances_scored']} gold utterances, "
              f"{ov['n_muse_turns_scored']}/{result['n_muse_turns_total']} Muse turns in window){cov_note}")
        report_parts.append(format_diff_report(name, "overall", ov))

        for role, sub in result.get("by_role", {}).items():
            print(f"{name} ({role}): WER={sub['wer']*100:.2f}%  CER={sub['cer']*100:.2f}%  "
                  f"({sub['n_gold_utterances_scored']} gold utterances, {sub['n_muse_turns_scored']} Muse turns)")
            report_parts.append(format_diff_report(name, role, sub))

    scores_path = SCORES_DIR / "muse_wer_cer.json"
    scores_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False))
    print(f"\nSaved full results -> {scores_path}")

    report_path = SCORES_DIR / "muse_error_highlights.txt"
    report_path.write_text("\n".join(report_parts), encoding="utf-8")
    print(f"Saved error highlights -> {report_path}")


if __name__ == "__main__":
    main()
