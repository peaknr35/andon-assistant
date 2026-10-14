# frontend/app -- Next.js App Router

One job: routing, the root layout, and the pages. The client state providers mount
here so state survives navigation.

## What's here
- `layout.tsx` -- root layout + metadata; wraps everything in `Providers`.
- `providers.tsx` -- mounts `ApiKeyProvider` + `ChatProvider` + `ResearchProvider` +
  `Header` above the pages, so chat/research/key state persists across route changes.
- `page.tsx` -- the assistant chat home (renders `ChatWindow`).
- `research/` -- the `/research` route (the original Deep Research Studio UI).
- `handoff/` -- the `/handoff` route: shift handoff (notes -> reviewed summary -> issues -> brief).
- `compare/` -- the `/compare` route.
- `globals.css` -- theme tokens (light/dark) + component classes + markdown styles.

## Rules
- Pages are thin: they render a component from `../components/`. Logic lives there.
- State that must survive navigation lives in a context in `providers.tsx`, not a page.

## Where to add a page
Create `app/<route>/page.tsx` that renders a component from `../components/`.

## Links
- Parent: `../CONTEXT.md` . Components: `../components/CONTEXT.md`
