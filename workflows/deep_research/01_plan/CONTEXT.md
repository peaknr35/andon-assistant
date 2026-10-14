# Stage 01: Plan

**One job:** turn the question into a short list of searchable sub-questions.

## Inputs
| Source | File | Why |
|---|---|---|
| Layer 4 | `<run>/question.md` (via `state.json` `query`) | the question |
| Layer 4 | `state.json` `max_subquestions` | upper bound on the list |

## Tools allowed
none

## Process
1. Ask the model for a JSON array of focused, non-overlapping sub-questions.
2. Parse it robustly; fall back to the question itself if parsing fails.

## Output
- `<run>/01_plan/plan.md`: `Question: ...` then numbered lines `1. ...`.
- Stage 02 searches **exactly the numbered lines**. Anything else in the file is ignored.

## Approval
- gate: auto today; becomes `required` with the approval step. A person may reword,
  add or delete numbered lines, then resume from `02_search`.

## Must not
- Search the web, answer the question, or write conclusions.
