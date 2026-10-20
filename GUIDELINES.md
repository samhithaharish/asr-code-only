# Manual Transcription Handout

*L2 Spanish-English Classroom ASR Gold Standard*

**Main principle: write what you hear. Do not correct, translate or smooth.**

## Before you start

- Transcribe from the audio only. Do not edit Zoom, or another transcript tool during first-pass gold creation.
- Use the provided timestamps as a guide. You do not need to make perfect time alignments. Only split, merge, or flag a segment when the boundary is clearly wrong and affects transcription.
- Write down both the verbatim form and the target word (`sabo = sé`, `estabanos = estabamos`). Use brackets after the incorrect form, e.g.:

  > Student1: yo piensa (piensa=pienso) que…..

## Core transcription rules

| Rule | What to do |
|---|---|
| Verbatim speech | Keep grammar, word order, learner errors, pronunciation-based forms, and non-standard varieties exactly as spoken, e.g. `Student 1: Soy fierte (fierte=fuerte)`. If you don't know the correct form, don't guess — say you don't know, e.g. `Student 2: Soy fam (fam=UNK)`. Insert question punctuation where necessary (clear rising intonation). |
| Segmentation corrections | If one segment contains two speakers, split it. If one speaker's turn is wrongly split, merge it or flag the problem in notes. |
| Code-switching | Keep English and Spanish exactly where they occur. Do not translate. Do not add language tags. |
| Fillers | Keep fillers using the controlled spellings: `um, uh, eh, mhm, aha`. Keep the transcription of fillers consistent — don't vary the spelling of the same filler. |
| Repetitions and repairs | Keep repeated words and self-repairs, e.g. `um I think que que sí`. |
| Cut-off | Use `_` at the cut point, e.g. `empeza_`, `I was go_`, `because I_`. |
| False starts | Use `-`, e.g. `Teacher: Puedes usar adje- adjetivos de aquí`. False starts differ from cut-offs: for cut-offs the speaker begins an utterance or construction, abandons it, and starts again, typically with a different formulation. |
| Unclear speech | Use `[*inaudible]` when unintelligible. Do not silently guess. |
| Non-speech sounds | Use only these tags: `{laugh}`, `{cough}`, `{breath}`, `{pause}`. |
| Overlap | If two people talk at once, transcribe both when possible and mark `[ov]` where overlap starts and `[/ov]` where it ends. |
| Numbers | Spell out what was spoken: `one zero three`, `ciento tres`, `eight thirty`, `ocho y media`. |
| Contractions | Preserve spoken forms such as `gonna`, `wanna`, `I'm`, `it's`. Do not expand them in verbatim text. |

### Short overlap guideline

If two speakers talk at the same time, use one row per speaker and mark the overlapped words with `[ov] ... [/ov]`. Mark the closest full words — exact timing is not required.

| speaker_id | verbatim_text |
|---|---|
| Student1 | yo pienso que el personaje es muy `[ov]` triste `[/ov]` |
| Teacher | `[ov]` muy triste `[/ov]` |

If the overlap is unclear, write `[ov] (( )) [/ov]`.

## Examples

| Case | Write | Reminder |
|---|---|---|
| Learner grammar | `yo no sabo` | Do not change to `yo no sé`. |
| Code-switching | `yo quiero to say algo` | Do not translate to `yo quiero decir algo`. |
| Filler + repetition | `um I I think que sí` | Keep both the filler and repetition. |
| Cut-off | `Yo fui_ yo quería ir al supermercado` | Use `_` for the incomplete word. |
| False starts | `Puedes am-amable, gentil, right?` / `Puedes usar adje- adjetivos de aquí` / `Ex- ex- excelente okay. Perfecto` | Use `-`. |
| Unclear | `Speaker: [*inaudible] otros countries, pero en México, I say lentes` | Use a guess only if you genuinely hear one. |

## Timestamp corrections

**Important:** use timestamps as a guide, not a precision task. Correct boundaries only when they clearly affect who is speaking or what should be transcribed.

| Problem | Provided segment | What transcriber should do |
|---|---|---|
| One time segment contains two speakers | `00:01:10-00:01:18, Teacher`, but the teacher speaks first and then Student1 answers | Split into two rows with approximate times: `00:01:10-00:01:14, Teacher` and `00:01:14-00:01:18, Student1` |
| One speaker's turn is split unnaturally | `00:02:05-00:02:08, Student1` and `00:02:08-00:02:12, Student1`, but it is one continuous turn | Merge into one row: `00:02:05-00:02:12, Student1` |
| Wrong speaker label | `00:03:20-00:03:26, Teacher`, but the speaker is a learner | Change `speaker_id`/`speaker_role`, and note: speaker corrected from Teacher to Student2 |
| Boundary is uncertain | The speaker change may happen around `00:04:11`, but it is hard to hear | Keep the closest boundary and write: uncertain boundary around `00:04:11` |

## Required spreadsheet columns

| Column | Meaning |
|---|---|
| `segment_id` | Unique row ID. |
| `start_time` | Segment start time. |
| `end_time` | Segment end time. |
| `speaker_id` | Teacher, Student1, Student2, Student3, or Student_UNK. |
| `speaker_role` | teacher or learner. |
| `verbatim_text` | Exact transcript from audio. |
| `notes` | Brief uncertainty or context note, if needed. |

**When uncertain: mark it. Do not guess, clean up, or silently correct.**
