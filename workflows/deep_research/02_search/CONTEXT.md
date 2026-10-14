# Stage 02: Search

**One job:** collect cited evidence for each sub-question in the plan.

## Inputs
| Source | File | Why |
|---|---|---|
| Layer 4 | `<run>/01_plan/plan.md` | the numbered sub-questions (possibly edited) |
| Layer 4 | `state.json` `search` | whether web search is on for this run |

## Tools allowed
`web_search` (DuckDuckGo, top `APP_SEARCH_MAX_RESULTS`)

## Process
1. For each numbered sub-question, search the web.
2. Sources found -> one model call that answers **only from those sources**, citing URLs.
3. No sources -> record the block as `GAP (no usable sources)`. No model call; no guessing.
4. Search turned off by the user -> answer from general knowledge, labelled
   `unsourced (search off; NOT source-backed)`.

## Output
- `<run>/02_search/evidence.md`: one `## N. <sub-question>` block each, with `**Status:**`,
  the finding, and its source links.
- `<run>/02_search/sources.json`: raw search results (feeds the UI's source list).

## STOP (andon)
If search is on and **no** sub-question found any source, write `02_search/STOP.md`
(what happened + what to do), set the stage to `stopped`, and halt with an `error`
event (`code: "stop"`). Stage 03 does not run.

## Approval
- gate: auto (a person may still edit `evidence.md` and resume from `03_report`).

## Must not
- Fill a gap from general knowledge when search is on, or invent URLs.
