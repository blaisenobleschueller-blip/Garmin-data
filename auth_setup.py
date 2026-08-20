#!/usr/bin/env python3
"""
One-time local authentication setup.

Run this on your own machine to generate Garmin session tokens.
These tokens let the Render server access your data without going through
the login flow (which Cloudflare blocks on cloud server IPs).

Usage:
    python auth_setup.py

Works with garminconnect 0.2.x AND 0.3.x.
"""

import getpass
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Token extraction — handles garminconnect 0.2.x and 0.3.x
# ---------------------------------------------------------------------------

def _extract_tokens_v2(api) -> str:
    """garminconnect 0.2.x: uses garth, tokens on api.garth."""
    return api.garth.dumps()


def _extract_tokens_v3(api) -> str:
    """garminconnect 0.3.x: uses curl_cffi with OAuth tokens."""
    token_data = {"_format": "gc-0.3"}

    # Primary: OAuth token objects (most likely in 0.3.x)
    for attr in ["oauth1_token", "oauth2_token"]:
        val = getattr(api, attr, None)
        if val is not None:
            # Convert to dict if it's an object
            if hasattr(val, "__dict__"):
                token_data[attr] = val.__dict__
            elif isinstance(val, dict):
                token_data[attr] = val
            else:
                token_data[attr] = str(val)

    # Secondary: session cookies (curl_cffi stores auth state here)
    for session_attr in ["session", "client", "_session"]:
        sess = getattr(api, session_attr, None)
        if sess is not None:
            try:
                # curl_cffi cookies can be iterated as dict
                cookies = {}
                jar = getattr(sess, "cookies", None)
                if jar is not None:
                    for c in jar:
                        # cookie objects have .name and .value
                        if hasattr(c, "name"):
                            cookies[c.name] = c.value
                        elif hasattr(c, "key"):
                            cookies[c.key] = c.value
                    if not cookies:
                        # try dict() directly
                        cookies = dict(jar)
                if cookies:
                    token_data["cookies"] = cookies
            except Exception:
                pass
            break

    # Tertiary: known string token attributes
    for attr in ["access_token", "refresh_token", "token", "session_token"]:
        val = getattr(api, attr, None)
        if val and isinstance(val, str):
            token_data[attr] = val

    if len(token_data) <= 1:
        # Nothing found — print diagnostic to help debug
        non_callable = [
            a for a in dir(api)
            if not a.startswith("__") and not callable(getattr(api, a, None))
        ]
        raise RuntimeError(
            f"No session tokens found in garminconnect 0.3.x Garmin object.\n"
            f"Available non-callable attributes: {non_callable}\n"
            f"Please paste this error message so we can fix token extraction."
        )

    return json.dumps(token_data)


def _extract_token_string(api) -> str:
    """Extract serialised session tokens — works with 0.2.x and 0.3.x."""
    # 0.2.x has api.garth (a garth client instance)
    if hasattr(api, "garth"):
        return _extract_tokens_v2(api)
    # 0.3.x uses curl_cffi directly (no garth)
    return _extract_tokens_v3(api)


def _load_tokens_v3(api, token_data: dict) -> None:
    """Inject 0.3.x tokens back into a fresh Garmin object."""
    for attr in ["oauth1_token", "oauth2_token"]:
        if attr in token_data:
            val = token_data[attr]
            existing = getattr(api, attr, None)
            if existing is not None and hasattr(existing, "__dict__"):
                existing.__dict__.update(val)
            else:
                setattr(api, attr, val)

    if "cookies" in token_data:
        for session_attr in ["session", "client", "_session"]:
            sess = getattr(api, session_attr, None)
            if sess is not None and hasattr(sess, "cookies"):
                try:
                    sess.cookies.update(token_data["cookies"])
                except Exception:
                    pass
                break

    for attr in ["access_token", "refresh_token", "token", "session_token"]:
        if attr in token_data:
            setattr(api, attr, token_data[attr])


def load_token_string(api, token_string: str) -> None:
    """Load serialised session tokens — works with 0.2.x and 0.3.x."""
    if hasattr(api, "garth"):
        api.garth.loads(token_string)
        return

    # 0.3.x — try JSON first, fall back to garth format
    try:
        data = json.loads(token_string)
        if isinstance(data, dict) and data.get("_format") == "gc-0.3":
            _load_tokens_v3(api, data)
            return
    except (json.JSONDecodeError, KeyError):
        pass

    raise ValueError(
        "Token string format not recognised for this garminconnect version. "
        "Re-run auth_setup.py to generate fresh tokens."
    )


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

⚠️  Do this for BOTH Render services:
  • garmin-data         (the calendar server)
  • health-dashboard    (health-dashboard-a328.onrender.com)

""")
    print("-" * 60)
    print(token_string)
    print("-" * 60)
    print("\nTokens typically last several months before needing refresh.")
    print("If the server stops working later, just re-run this script.")


# ---------------------------------------------------------------------------
# Step 1 — check for tokens already cached on this machine
# ---------------------------------------------------------------------------

# garminconnect 0.2.x caches via garth
garth_dir = Path.home() / ".garth"
if garth_dir.exists():
    token_files = list(garth_dir.glob("*.json"))
    if token_files:
        print("Found existing Garmin session cached on this machine (~/.garth).")
        print("Attempting to load without a fresh login...")
        try:
            import garth
            garth.resume(str(garth_dir))
            token_string = garth.client.dumps()
            _print_tokens(token_string)
            sys.exit(0)
        except ImportError:
            print("garth not installed, skipping cached token check.\n")
        except Exception as exc:
            print(f"Cached tokens could not be loaded ({exc}), will do fresh login.\n")

# ---------------------------------------------------------------------------
# Step 2 — fresh login
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
except GarminConnectAuthenticationError as exc:
    print(f"\nLogin failed (wrong email/password?): {exc}")
    sys.exit(1)
except Exception as exc:
    msg = str(exc)
    if "429" in msg:
        print("\nGarmin rate limit active (429). Wait 1–2 hours then try again.")
        print("Do NOT retry repeatedly — each attempt resets the timer.")
    else:
        print(f"\nUnexpected login error: {exc}")
    sys.exit(1)

# Verify the session is actually authenticated
print("Verifying login...")
try:
    name = api.get_full_name()
    print(f"Authenticated as: {name}")
except Exception as exc:
    print(f"\nLogin appeared to succeed but session is not valid: {exc}")
    print("This usually means Garmin's rate limit is still active (429).")
    print("Wait 1–2 hours and try again.")
    sys.exit(1)

# Extract tokens
try:
    token_string = _extract_token_string(api)
except RuntimeError as exc:
    print(f"\nError: {exc}")
    sys.exit(1)

_print_tokens(token_string)
