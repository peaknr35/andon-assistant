# Frontend (Next.js) -- contract

One job: a polished, responsive UI to ask a question, watch research stream in,
switch/compare models, manage keys in the browser, and export the report.

## Inputs
- Reference: `../_shared/api-contract.md` (event shape -> `lib/types.ts`),
  `../_shared/providers.md` (model catalog -> `lib/models.ts`).
- Env: `NEXT_PUBLIC_BACKEND_URL` (backend origin), `NEXT_PUBLIC_GOOGLE_CLIENT_ID`
  (optional, enables the OAuth "Create Google Doc" export).

## Structure
```
app/
  layout.tsx        root layout -> Providers (contexts + Header persist across routes)
  page.tsx          main research view
  compare/page.tsx  compare view
  globals.css       theme tokens (light/dark) + component + markdown styles
contexts/
  ApiKeyContext     keys in localStorage (save/import/export/clear)
  ResearchContext   main + compare run state; streams via lib/api; persists to sessionStorage
lib/
  types.ts          SSE event + state types (mirror of the API contract)
  models.ts         provider/model catalog
  api.ts            streamResearch() / streamDecision(): POST + ReadableStream SSE parser
  research.ts       applyEvent() reducer (shared by main + compare)
  storage.ts        localStorage keys + sessionStorage state helpers
  googleDocs.ts     copy-for-Docs + OAuth create-doc
components/         Header, ModelSelector, ApiKeyManager, ProgressStages,
                    FindingCard, SourceList, ReportView, ExportMenu,
                    ResearchInterface, CompareView, Markdown
```

## Key behaviours
- Streaming: `fetch` POST to `/research/stream`, parse `data:` frames, fold each
  event into state with `applyEvent`. One code path handles errors (delivered as
  an `error` event).
- State persistence: contexts live in the root layout, so navigating Home <->
  Compare keeps state; state is also mirrored to sessionStorage for reloads.
- Keys: never leave the browser except as the per-request body to the backend.
- Compare: fires N independent streams (one per model); each column reduces with
  the same `applyEvent`.

## Run / build
- Dev: `npm install && npm run dev` (http://localhost:3000)
- Typecheck: `npm run typecheck`
- Build: `npm run build` (standalone output for Docker)

## Human check
Open `/`, enter a key via Keys, ask a question -> stages + sources + report stream
in. Navigate to `/compare` and back -> state preserved. `npm run build` succeeds.

## Avoid
- Putting keys in any request to anything other than the backend.
- Using EventSource (the request is a POST; use the fetch stream reader).
- Letting the event shape drift from `../_shared/api-contract.md`.
