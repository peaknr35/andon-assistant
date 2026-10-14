# frontend/components -- React components

One job: all the UI pieces. Pages compose these; components read/write shared state
through contexts.

## What's here
- `chat/` -- the assistant chat UI (ChatWindow, TurnTimeline, PhaseBadge, ToolCallCard,
  MemoryPanel). Its own CONTEXT.
- `Header.tsx` -- top nav (Assistant / Research / Compare) + opens the Keys modal.
- `ResearchInterface.tsx` -- the research view (used by `/research`); "Review plan first" toggle.
- `ApprovalPanel.tsx` -- the review gate: the stage's file (plan.md) in an editor + approve /
  approve-with-edits / reject; for an andon stop it shows STOP.md and offers retry / close.
- `CompareView.tsx` -- multi-model compare grid (used by `/compare`).
- `ApiKeyManager.tsx` -- the keys modal (save/import/export/clear).
- `ModelSelector.tsx` -- provider + model dropdowns with a key-status chip.
- `ProgressStages.tsx`, `FindingCard.tsx`, `SourceList.tsx`, `ReportView.tsx`,
  `ExportMenu.tsx` -- research rendering + Google Docs export.
- `Markdown.tsx` -- react-markdown wrapper (findings, report, chat answers).

## Rules
- PascalCase filenames; add `"use client"` if it uses state/effects/handlers.
- Read/write shared state via `../contexts/`; style with tokens in `../app/globals.css`.

## Where to add a component
See `../../_templates/new-component.md`.

## Links
- Chat: `chat/CONTEXT.md` . Contexts: `../contexts/CONTEXT.md` . Lib: `../lib/CONTEXT.md`
  . Parent: `../CONTEXT.md`
