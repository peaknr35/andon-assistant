# Calendar Sync (Google + Outlook) — Setup

Two-way sync is **off by default**. The local SQLite calendar always works on its own; turning a
provider on makes events you create also appear in that cloud calendar, and pulls your existing
cloud events into "what's coming up?" (de-duplicated, refreshed on a timer).

You only need to do this once per machine, and only for the provider(s) you want.

---

## Google Calendar

1. **Google Cloud Console** → create/choose a project → **APIs & Services → Library** → enable
   **Google Calendar API**.
2. **APIs & Services → Credentials → Create credentials → OAuth client ID**, application type
   **Desktop app**. Download the JSON (it's your `credentials.json`).
3. Install the extra and run the one-time consent:
   ```bash
   cd backend
   .venv/Scripts/python.exe -m pip install google-api-python-client google-auth google-auth-oauthlib
   PYTHONPATH=. .venv/Scripts/python.exe scripts/google_auth.py C:\path\to\credentials.json
   ```
   A browser opens — approve access. It writes `token.json` next to your credentials.
4. Add to `backend/.env` (then restart the backend):
   ```
   APP_GOOGLE_CALENDAR=1
   APP_GOOGLE_TOKEN_FILE=C:\path\to\token.json
   ```

---

## Outlook / Microsoft 365

1. **Microsoft Entra admin center** (Azure AD) → **App registrations → New registration**.
   - Supported account types: pick what you need (personal and/or work/school).
   - After creating it, note the **Application (client) ID**.
2. **API permissions → Add a permission → Microsoft Graph → Delegated → `Calendars.ReadWrite`**,
   then **Grant admin consent** (if it's a work tenant).
3. **Authentication → Advanced settings → Allow public client flows → Yes.**
4. Install the extra and run the one-time device-code sign-in:
   ```bash
   cd backend
   .venv/Scripts/python.exe -m pip install msal
   # PowerShell: $env:APP_OUTLOOK_CLIENT_ID="<client-id>"; then run the next line
   APP_OUTLOOK_CLIENT_ID=<client-id> PYTHONPATH=. .venv/Scripts/python.exe scripts/outlook_auth.py
   ```
   Open the URL it prints, enter the code, sign in. It writes `outlook_token.json`.
5. Add to `backend/.env` (then restart the backend):
   ```
   APP_OUTLOOK_CALENDAR=1
   APP_OUTLOOK_CLIENT_ID=<client-id>
   APP_OUTLOOK_TENANT=common
   APP_OUTLOOK_TOKEN_CACHE=C:\path\to\outlook_token.json
   ```

---

## Options & notes
- `APP_CALENDAR_TIMEZONE` (default `UTC`) — the timezone used when creating cloud events. Set an
  IANA name like `America/Chicago` so times land correctly.
- `APP_CALENDAR_SYNC_MINUTES` (default `15`) — how often the background pull runs. A pull also
  happens right before any "what's coming up?" list.
- **Secrets stay local:** `credentials.json`, `token.json`, and `outlook_token.json` are gitignored
  and never leave your machine.
- Sync is best-effort: if a provider is unreachable, the local calendar keeps working and the
  assistant simply doesn't mirror that turn.
