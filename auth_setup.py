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

from dotenv import load_dotenv
from garminconnect import Garmin, GarminConnectAuthenticationError

load_dotenv()

print("Garmin Connect — one-time token setup")
print("=" * 50)
email = input("Garmin email: ").strip()
password = getpass.getpass("Garmin password: ")

print("\nLogging in from your local machine...")

try:
    api = Garmin(email, password)
    api.login()
except GarminConnectAuthenticationError as exc:
    print(f"\nLogin failed: {exc}")
    print("Double-check your email and password and try again.")
    sys.exit(1)
except Exception as exc:
    print(f"\nUnexpected error: {exc}")
    sys.exit(1)

token_string = api.garth.dumps()

print("\n" + "=" * 60)
print("Login successful!")
print("=" * 60)
print("""
Add the following as a new Environment Variable in Render:

  NAME:  GARMIN_TOKENS
  VALUE: (the long string printed below)

Steps:
  1. Go to your Render service → Environment tab
  2. Click '+ Add Environment Variable'
  3. Set NAME to:  GARMIN_TOKENS
  4. Set VALUE to the entire string below (copy all of it)
  5. Click 'Save Changes' — Render will redeploy automatically

""")
print("-" * 60)
print(token_string)
print("-" * 60)
print("\nTokens typically last several months before needing refresh.")
print("If the server stops working later, just re-run this script.")
