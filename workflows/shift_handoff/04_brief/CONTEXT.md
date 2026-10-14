# Stage 04: Next-shift brief

**One job:** write the one-page brief the incoming shift reads first.

## Inputs
| Source | File | Why |
|---|---|---|
| Layer 4 | `<run>/02_summary/summary.md`, `<run>/03_issues/issues.md` | the facts (as approved) |
| Layer 3 | `<run>/references/format.md` | your plant's brief layout |

## Tools allowed
none

## Process
1. One model call, streamed: safety first, at most 3 priorities, open issues with owners,
   watch items, and the handover sign-off lines. Keep `[L#]` references. Under ~300 words.

## Output
- `<run>/04_brief/brief.md` -- the deliverable. Copy it into your handover system or print it.

## Approval
- gate: final (edit `brief.md` directly if needed).

## Must not
- Introduce anything that is not in the approved summary or issues.
