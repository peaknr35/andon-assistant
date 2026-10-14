# Stage 01: Notes

**One job:** store the outgoing supervisor's notes exactly as written, so every later
claim can point at a line.

## Inputs
| Source | What | Why |
|---|---|---|
| Person | pasted end-of-shift notes + line / shift / supervisor | the only facts this workflow may use |

## Tools allowed
none (no model call)

## Process
1. Save the notes verbatim to `01_notes/notes.md`. Line N of that file is `[LN]`.
2. If the notes have fewer than 15 words, write `01_notes/STOP.md` and halt.

## Output
- `01_notes/notes.md` -- verbatim. Later stages cite its line numbers.

## Must not
- Rewrite, summarize or "clean up" the notes. Editing them changes what L-numbers mean.
