# Beyond Aggregate WER: In-domain Adaptation, Learner Speech, Code-Switching, and Speaker Attribution in Online Spanish Learning Classrooms

Scoring and language-identification code for *Beyond Aggregate WER:
In-domain Adaptation, Learner Speech, Code-Switching, and Speaker
Attribution in Online L2 Spanish Classrooms*.

This repository contains only the analysis code. It does not include the
Zoom transcripts, LoRA adapter weights, or evaluation spreadsheets used in
the paper, which are not distributed here.

## Scoring

`scoring/score.py` implements the underlying edit-distance scoring. Filler
removal and other normalization rules are in `scoring/normalize_text.py`
and `scoring/normalization_rules.py`. Language classification is in
`scoring/lid/`.

## Guidelines

`GUIDELINES.md` is the manual transcription handout the normalization
rules are built to match (annotation tags, filler spellings, cut-off/
false-start markers, overlap markers).

## License

See `LICENSE`.
