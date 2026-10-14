# frontend/lib -- framework-free helpers

One job: types, the API client, reducers, storage, the model catalog, and export
logic. No React here.

## What's here
- `types.ts` -- research SSE event + state types. Mirrors `../../_shared/api-contract.md`.
- `chatTypes.ts` -- agent TurnEvent + chat message/activity types. Mirrors
  `../../_shared/agent-turn-contract.md`.
- `models.ts` -- provider/model catalog. Mirrors `../../_shared/providers.md`.
- `api.ts` -- one SSE reader; `streamResearch()`, `streamChat()`, `fetchMemory()`,
  `fetchTrace()`; `BACKEND_URL`.
- `handoff.ts` -- shift handoff types, SSE calls (`streamHandoff`, `streamHandoffDecision`),
  `applyHandoffEvent()` reducer, run list / load. Mirrors `_shared/shift-handoff.md`.
- `research.ts` -- `applyEvent()` reducer for the research view (incl. `await_approval` ->
  `state.approval`, and `done` with `status: paused | rejected`).
- `storage.ts` -- localStorage keys + sessionStorage state helpers (all try/catch).
- `googleDocs.ts` -- copy-for-Docs + OAuth create-doc.

## Mirrors (one home per fact)
`types.ts`, `chatTypes.ts`, `models.ts` are client copies of the `_shared/` contracts.
Change a contract first, then these.

## Rules
- No DOM assumptions beyond guarded `window` access (SSR-safe); storage wrapped in try/catch.

## Where to add things
- New turn event -> `chatTypes.ts` + handle it in `contexts/ChatContext`.
- New provider/model -> `models.ts` (+ the backend; see `../../_templates/new-provider.md`).

## Links
- Contracts: `../../_shared/agent-turn-contract.md`, `../../_shared/api-contract.md`,
  `../../_shared/providers.md` . Parent: `../CONTEXT.md`
