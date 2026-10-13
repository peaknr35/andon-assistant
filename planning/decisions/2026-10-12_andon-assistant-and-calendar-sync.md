# 2026-10-12 -- Andon Assistant rebrand + two-way calendar sync

## Status
Accepted (implemented).

## Context
The project was demoed to a Toyota group leader as a shop-floor troubleshooting assistant.
That drove a rebrand and a round of hardening plus a real two-way calendar integration.

## Decisions
1. **Rebrand** the assistant to "Andon Assistant" (TPS "andon" = surface + resolve problems).
   A ~5-file change (header, title, config, README, CLAUDE.md); working title only, no code-shape change.
2. **deep_research as a fast tool.** Keep the full progressive pipeline (`services/research.py`,
   `/research` UI) but give the in-chat `deep_research` tool a lean path: parallel web searches +
   one ~700-token cited report (~12s). Speed matters more than depth for a conversational turn.
3. **Full Claude model lineup** in the picker so users can trade cost/quality (Haiku 5.5 cheapest).
4. **Two-way calendar sync, provider-symmetric, off by default.** Local SQLite stays the source
   of truth. Each provider is a small module with the same shape
   (`is_enabled` / `create_event` / `list_events`), best-effort and never raising. Push on create,
   pull on list + a periodic loop, de-duplicated by cloud id (`google_id` / `outlook_id`). The
   agent's tool surface (`calendar_create` / `calendar_list`) is unchanged -- sync is transparent.
   - Google: finish the scaffolded sync (token refresh + list + a one-time OAuth bootstrap script).
   - Outlook: new module via Microsoft Graph (httpx) + MSAL device-code auth.

## Consequences
- OAuth requires the user to create a Google Cloud app + an Entra app; the code ships gated OFF,
  so it is zero-risk until configured. Secrets (token/credentials files) are gitignored.
- New optional deps: `google-auth-oauthlib`, `msal`.
- Contracts added/updated: `_shared/calendar-sync.md`, `memory-schema.md` (outlook_id), `tools.md`.

## Alternatives considered
- One-way sync only (simpler) -- rejected; the user wanted existing cloud events pulled in too.
- Two-way as a background-only cron -- folded into an on-read pull + a light periodic loop instead.
