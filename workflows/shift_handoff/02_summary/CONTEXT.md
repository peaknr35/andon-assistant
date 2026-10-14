# Stage 02: Summary

**One job:** sort the notes into a structured shift summary, every bullet cited.

## Inputs
| Source | File | Why |
|---|---|---|
| Layer 4 | `<run>/01_notes/notes.md` (shown to the model as numbered lines) | the facts |
| Layer 3 | `<run>/references/glossary.md` | plant terms and abbreviations |

## Tools allowed
none

## Process
1. One model call, streamed. Sections, in order: Safety, Quality, Production,
   Downtime & maintenance, People & staffing, Unclear -- ask the outgoing shift.
2. Each bullet ends with its note line(s): `[L3]` or `[L3, L7]`. Empty section: `- None noted.`
3. Code checks citations; problems are shown at the gate.

## Output
- `<run>/02_summary/summary.md`

## Approval
- gate: required. The supervisor fixes wording, moves items, deletes noise, or rejects.

## Must not
- Invent numbers, names, part numbers, times or causes. Anything uncertain goes to Unclear.
