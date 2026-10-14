# Stage 03: Issues & risks

**One job:** pull the open issues and next-shift risks out of the (approved) summary.

## Inputs
| Source | File | Why |
|---|---|---|
| Layer 4 | `<run>/02_summary/summary.md` (possibly edited) | the only facts |

## Tools allowed
none

## Process
1. One model call, streamed. `## Open issues` as a table: # | Issue | Category
   (Safety / Quality / Delivery / Cost / People) | Severity (High / Med / Low) | Evidence
   (`[L#]`) | Owner | Next action. Safety rows first.
2. Owner only if a name appears in the summary; otherwise `unassigned`.
3. `## Risks for next shift` as cited bullets. Nothing open -> say `No open issues.`

## Output
- `<run>/03_issues/issues.md`

## Approval
- gate: required. The supervisor sets owners, severity and next actions.

## Must not
- Add issues that are not in the summary, or guess an owner.
