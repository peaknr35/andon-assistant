# frontend/contexts -- React shared state

One job: hold the app's shared, persistent state. Mounted in `app/providers.tsx`
(above the pages) so it survives navigation.

## What's here
- `ApiKeyContext.tsx` -- the user's API keys (localStorage; import/export). `useApiKeys()`.
- `ChatContext.tsx` -- the assistant conversation: messages + per-turn activity
  (phases, tools, memory); `run/stop/reset`; streams via `lib/api.streamChat`; folds
  TurnEvents into message activity; persists to sessionStorage. `useChat()`.
- `ResearchContext.tsx` -- the research run + compare runs; `decideMain()` resumes a paused
  run (the API key is passed in at click time, never kept in persisted state). `useResearch()`.

## Reads / Writes
- Reads: `../lib/api.ts` (streaming), `../lib/research.ts`, `../lib/storage.ts`.
- Writes: `localStorage` (keys) + `sessionStorage` (chat + research state), per-viewer only.

## Rules
- Keys never leave the browser except as the per-request body to our backend.
- On hydrate, coerce any persisted `running` flag to false (the stream is gone).

## Where to add state
Add a field + action to the matching context; persist via `../lib/storage.ts`; a new
kind of state can get a new context mounted in `../app/providers.tsx`.

## Links
- Lib: `../lib/CONTEXT.md` . Parent: `../CONTEXT.md`
