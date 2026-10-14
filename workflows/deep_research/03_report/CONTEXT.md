# Stage 03: Report

**One job:** write the final cited markdown report from the evidence file.

## Inputs
| Source | File | Why |
|---|---|---|
| Layer 4 | `<run>/02_search/evidence.md` | the only facts the report may use (possibly edited) |
| Layer 4 | `state.json` `query` | the original question |

## Tools allowed
none

## Process
1. Stream a report: executive summary, themed `##` sections, conclusion.
2. Keep inline citations. Say plainly which points were GAPs; do not fill them in.
3. If the evidence is labelled unsourced, say at the top the report is NOT source-backed.

## Output
- `<run>/03_report/report.md`, and the `report` event with the de-duplicated
  sources from `sources.json`.

## Approval
- gate: auto (the report is the last stage; edit `report.md` directly if needed).

## Must not
- Search the web, or claim anything not in `evidence.md`.
