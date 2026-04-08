#!/usr/bin/env python3
"""
One-time local authentication setup.

Run this on your own machine to generate Garmin session tokens.
These tokens let the Render server access your data without going through
the login flow (which Cloudflare blocks on cloud server IPs).

Usage:
    python auth_setup.py
"""

import getpass
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _print_tokens(token_string: str) -> None:
    print("\n" + "=" * 60)
    print("Success! Got Garmin session tokens.")
    print("=" * 60)
    print("""
Add the following as a new Environment Variable in Render:

  NAME:  GARMIN_TOKENS
  VALUE: (the long string printed below)

Steps:
  1. Go to your Render service → Environment tab
  2. Click '+ Add Environment Variable'
  3. Set NAME to:  GARMIN_TOKENS
  4. Paste the entire string below as the value
  5. Click 'Save Changes' — Render will redeploy automatically

""")
    print("-" * 60)
    print(token_string)
    print("-" * 60)
    print("\nTokens typically last several months before needing refresh.")
    print("If the server stops working later, just re-run this script.")


# ---------------------------------------------------------------------------
# Step 1 — check for tokens already cached by garth on this machine
# ---------------------------------------------------------------------------

garth_dir = Path.home() / ".garth"
if garth_dir.exists():
    token_files = list(garth_dir.glob("*.json"))
    if token_files:
        print("Found existing Garmin session tokens cached on this machine.")
        print("Attempting to load them without a fresh login...")
        try:
            import garth
            garth.resume(str(garth_dir))
            token_string = garth.client.dumps()
            _print_tokens(token_string)
            sys.exit(0)
        except Exception as exc:
            print(f"Cached tokens could not be loaded ({exc}), will try fresh login.\n")

# ---------------------------------------------------------------------------
# Step 2 — fresh login (requires Garmin rate limit to have cleared)
# ---------------------------------------------------------------------------

print("Garmin Connect — one-time token setup")
print("=" * 50)
print("NOTE: If you see a 429 error, Garmin has rate-limited your account")
print("from too many recent login attempts. Wait 1–2 hours and try again.\n")

email = input("Garmin email: ").strip()
password = getpass.getpass("Garmin password: ")

print("\nLogging in from your local machine...")

try:
    from garminconnect import Garmin, GarminConnectAuthenticationError
    api = Garmin(email, password)
    api.login()
except Exception as exc:
    msg = str(exc)
    if "429" in msg:
        print("\nGarmin rate limit active (429). Wait 1–2 hours then try again.")
        print("Do NOT retry repeatedly — each attempt resets the timer.")
    elif "401" in msg or "auth" in msg.lower() or "password" in msg.lower():
        print(f"\nLogin failed: {exc}")
        print("Double-check your email and password.")
    else:
        print(f"\nUnexpected error: {exc}")
    sys.exit(1)

token_string = api.garth.dumps()
_print_tokens(token_string)
