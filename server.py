"""
Flask server — serves Garmin data as a live subscribable iCalendar feed.

Endpoints:
  GET /                  Health check
  GET /garmin.ics        iCal feed (add ?token=SECRET if CALENDAR_TOKEN is set)
  GET /refresh           Force cache invalidation (requires token)

Deploy to Render (free tier) and subscribe in Google Calendar via:
  Add other calendars → From URL → https://<your-app>.onrender.com/garmin.ics?token=<TOKEN>
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import date, timedelta

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request

from calendar_builder import build_calendar
from garmin_client import GarminClient, client_from_env
from recovery_scorer import build_recovery_map

load_dotenv()

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration (from environment variables)
# ---------------------------------------------------------------------------

CALENDAR_TOKEN: str = os.environ.get("CALENDAR_TOKEN", "")
CACHE_TTL_SECONDS: int = int(os.environ.get("CACHE_TTL_SECONDS", "3600"))   # 1 hour
LOOKBACK_DAYS: int = int(os.environ.get("LOOKBACK_DAYS", "14"))
CALENDAR_NAME: str = os.environ.get("CALENDAR_NAME", "Garmin Health")

# ---------------------------------------------------------------------------
# Garmin client — module-level singleton with thread lock & auto-reconnect
# ---------------------------------------------------------------------------

_client_lock = threading.Lock()
_garmin_client: GarminClient | None = None


def _get_client() -> GarminClient:
    global _garmin_client
    with _client_lock:
        if _garmin_client is None:
            logger.info("Connecting to Garmin Connect…")
            c = client_from_env()
            c.connect()
            _garmin_client = c
            logger.info("Connected.")
        return _garmin_client


def _reset_client() -> None:
    global _garmin_client
    with _client_lock:
        _garmin_client = None


def _fetch_calendar_bytes() -> bytes:
    """Fetch all Garmin data and return a serialised .ics payload."""
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)

    try:
        client = _get_client()
    except RuntimeError as exc:
        logger.error("Auth error: %s", exc)
        raise

    def _with_reconnect(fn, *args, **kwargs):
        """Call fn; on auth failure reset client and retry once."""
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if "401" in str(exc) or "auth" in str(exc).lower():
                logger.warning("Session expired — reconnecting…")
                _reset_client()
                client2 = _get_client()
                # Rebind fn to new client
                method_name = fn.__name__
                return getattr(client2, method_name)(*args, **kwargs)
            raise

    logger.info("Fetching data %s → %s", start_date, end_date)
    activities    = _with_reconnect(client.get_activities, start_date, end_date)
    sleep_records = _with_reconnect(client.get_sleep,      start_date, end_date)
    body_battery  = _with_reconnect(client.get_body_battery, start_date, end_date)
    stress_records = _with_reconnect(client.get_stress,    start_date, end_date)
    hrv_records   = _with_reconnect(client.get_hrv,        start_date, end_date)

    logger.info(
        "Fetched: %d activities, %d sleep, %d body battery, %d stress, %d HRV",
        len(activities), len(sleep_records), len(body_battery),
        len(stress_records), len(hrv_records),
    )

    recovery_map = build_recovery_map(hrv_records, sleep_records, body_battery)

    cal = build_calendar(
        activities=activities,
        sleep_records=sleep_records,
        body_battery=body_battery,
        stress_records=stress_records,
        hrv_records=hrv_records,
        recovery_map=recovery_map,
        calendar_name=CALENDAR_NAME,
    )
    return cal.to_ical()


# ---------------------------------------------------------------------------
# Cache — avoids hammering Garmin on every calendar refresh
# ---------------------------------------------------------------------------

_cache_lock = threading.Lock()
_cached_ics: bytes | None = None
_cache_expires: float = 0.0


def _get_cached_ics(force_refresh: bool = False) -> bytes:
    global _cached_ics, _cache_expires

    with _cache_lock:
        now = time.monotonic()
        if not force_refresh and _cached_ics and now < _cache_expires:
            logger.debug("Serving from cache (%.0f s remaining)", _cache_expires - now)
            return _cached_ics

    # Fetch outside the lock so other requests don't pile up waiting
    logger.info("Cache miss — regenerating calendar…")
    ics_bytes = _fetch_calendar_bytes()

    with _cache_lock:
        _cached_ics = ics_bytes
        _cache_expires = time.monotonic() + CACHE_TTL_SECONDS

    logger.info("Calendar cached for %d seconds", CACHE_TTL_SECONDS)
    return ics_bytes


# ---------------------------------------------------------------------------
# Token auth helper
# ---------------------------------------------------------------------------

def _check_token() -> None:
    if CALENDAR_TOKEN and request.args.get("token") != CALENDAR_TOKEN:
        abort(403, description="Missing or invalid token. Append ?token=YOUR_TOKEN to the URL.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def health() -> Response:
    return jsonify(
        status="ok",
        lookback_days=LOOKBACK_DAYS,
        cache_ttl_seconds=CACHE_TTL_SECONDS,
        calendar_name=CALENDAR_NAME,
        token_protected=bool(CALENDAR_TOKEN),
    )


@app.route("/garmin.ics")
def serve_ics() -> Response:
    _check_token()
    try:
        ics_bytes = _get_cached_ics()
    except RuntimeError as exc:
        logger.error("Failed to generate calendar: %s", exc)
        abort(503, description=str(exc))

    return Response(
        ics_bytes,
        mimetype="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="garmin.ics"',
            "Cache-Control": f"public, max-age={CACHE_TTL_SECONDS}",
        },
    )


@app.route("/refresh")
def force_refresh() -> Response:
    """Force a cache refresh — useful after a workout syncs."""
    _check_token()
    try:
        ics_bytes = _get_cached_ics(force_refresh=True)
    except RuntimeError as exc:
        abort(503, description=str(exc))
    return jsonify(status="refreshed", bytes=len(ics_bytes))


# ---------------------------------------------------------------------------
# Entry point (development only — use gunicorn in production)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
