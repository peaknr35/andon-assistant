"""One-time Google OAuth: turn a downloaded credentials.json into a token.json.

Prereqs:
  1) A Google Cloud project with the Google Calendar API enabled.
  2) An OAuth client of type "Desktop app"; download its credentials.json.
  3) pip install google-auth-oauthlib google-api-python-client google-auth

Run (from the backend folder):
  PYTHONPATH=. .venv/Scripts/python.exe scripts/google_auth.py <path-to-credentials.json>

It opens a browser for consent and writes token.json next to credentials.json. Then set:
  APP_GOOGLE_CALENDAR=1
  APP_GOOGLE_TOKEN_FILE=<absolute path to token.json>
"""
from __future__ import annotations

import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def main() -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Missing dependency. Run: pip install google-auth-oauthlib "
              "google-api-python-client google-auth")
        sys.exit(1)

    creds_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("credentials.json")
    if not creds_path.exists():
        print(f"credentials.json not found at {creds_path}.")
        print("Download it from Google Cloud Console -> APIs & Services -> Credentials -> "
              "OAuth client ID (type 'Desktop app').")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)
    out = creds_path.with_name("token.json")
    out.write_text(creds.to_json(), encoding="utf-8")
    print(f"Wrote {out.resolve()}")
    print("Now set:  APP_GOOGLE_CALENDAR=1")
    print(f"          APP_GOOGLE_TOKEN_FILE={out.resolve()}")


if __name__ == "__main__":
    main()
