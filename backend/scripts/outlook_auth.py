"""One-time Microsoft (Outlook) OAuth via device code: creates a token cache file.

Prereqs:
  1) Register an app in Microsoft Entra (Azure AD):
       - Supported account types: choose what you need (personal and/or work/school).
       - API permissions: Microsoft Graph -> Delegated -> Calendars.ReadWrite (grant consent).
       - Authentication: set "Allow public client flows" = Yes.
     Note the Application (client) ID.
  2) pip install msal

Run (from the backend folder):
  APP_OUTLOOK_CLIENT_ID=<client-id> PYTHONPATH=. .venv/Scripts/python.exe scripts/outlook_auth.py

Follow the device-code prompt (open the URL, enter the code, sign in). It writes
outlook_token.json. Then set:
  APP_OUTLOOK_CALENDAR=1
  APP_OUTLOOK_CLIENT_ID=<client-id>
  APP_OUTLOOK_TENANT=common            (or your tenant id)
  APP_OUTLOOK_TOKEN_CACHE=<absolute path to outlook_token.json>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SCOPES = ["Calendars.ReadWrite"]


def main() -> None:
    try:
        import msal
    except ImportError:
        print("Missing dependency. Run: pip install msal")
        sys.exit(1)

    client_id = os.getenv("APP_OUTLOOK_CLIENT_ID", "")
    tenant = os.getenv("APP_OUTLOOK_TENANT", "common")
    if not client_id:
        print("Set APP_OUTLOOK_CLIENT_ID to your Entra app's Application (client) ID first.")
        sys.exit(1)

    cache_path = Path(os.getenv("APP_OUTLOOK_TOKEN_CACHE", "") or "outlook_token.json")
    cache = msal.SerializableTokenCache()
    if cache_path.exists():
        cache.deserialize(cache_path.read_text(encoding="utf-8"))

    app = msal.PublicClientApplication(
        client_id, authority=f"https://login.microsoftonline.com/{tenant}", token_cache=cache
    )
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        print("Failed to start device flow:", flow.get("error_description"))
        sys.exit(1)
    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        print("Sign-in failed:", result.get("error_description"))
        sys.exit(1)

    cache_path.write_text(cache.serialize(), encoding="utf-8")
    print(f"Wrote {cache_path.resolve()}")
    print("Now set:  APP_OUTLOOK_CALENDAR=1")
    print(f"          APP_OUTLOOK_CLIENT_ID={client_id}")
    print(f"          APP_OUTLOOK_TENANT={tenant}")
    print(f"          APP_OUTLOOK_TOKEN_CACHE={cache_path.resolve()}")


if __name__ == "__main__":
    main()
