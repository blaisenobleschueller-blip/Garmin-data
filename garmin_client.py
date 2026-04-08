"""
Garmin Connect client — authenticates and fetches activity, sleep,
body battery, stress, and HRV data for a given date range.
"""

from __future__ import annotations

import os
import logging
from datetime import date, timedelta
from typing import Any

from garminconnect import Garmin, GarminConnectAuthenticationError

logger = logging.getLogger(__name__)


class GarminClient:
    """Thin wrapper around garminconnect that handles login and data fetching."""

    def __init__(self, email: str, password: str) -> None:
        self._email = email
        self._password = password
        self._api: Garmin | None = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Authenticate with Garmin Connect.

        Prefers saved OAuth tokens (GARMIN_TOKENS env var) over a fresh login.
        Saved tokens bypass Cloudflare blocking that affects cloud server IPs.
        Generate tokens on your local machine by running: python auth_setup.py
        """
        self._api = Garmin(self._email, self._password)

        saved_tokens = os.environ.get("GARMIN_TOKENS", "").strip()
        if saved_tokens:
            try:
                self._api.garth.loads(saved_tokens)
                logger.info("Loaded saved Garmin session tokens (skipping fresh login)")
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Saved tokens invalid or expired — falling back to fresh login: %s", exc
                )

        try:
            self._api.login()
            logger.info("Logged in to Garmin Connect as %s", self._email)
        except GarminConnectAuthenticationError as exc:
            raise RuntimeError(
                "Garmin Connect authentication failed. "
                "Check GARMIN_EMAIL and GARMIN_PASSWORD."
            ) from exc

    @property
    def api(self) -> Garmin:
        if self._api is None:
            raise RuntimeError("Call connect() before accessing the API.")
        return self._api

    # ------------------------------------------------------------------
    # Activities
    # ------------------------------------------------------------------

    def get_activities(self, start: date, end: date) -> list[dict[str, Any]]:
        """Return all activities between *start* and *end* (inclusive)."""
        raw = self.api.get_activities_by_date(
            start.isoformat(), end.isoformat()
        )
        logger.info("Fetched %d activities (%s – %s)", len(raw), start, end)
        return raw

    # ------------------------------------------------------------------
    # Sleep
    # ------------------------------------------------------------------

    def get_sleep(self, start: date, end: date) -> list[dict[str, Any]]:
        """Return sleep summaries for every date in the range."""
        results: list[dict[str, Any]] = []
        current = start
        while current <= end:
            try:
                data = self.api.get_sleep_data(current.isoformat())
                if data and data.get("dailySleepDTO"):
                    data["_date"] = current.isoformat()
                    results.append(data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No sleep data for %s: %s", current, exc)
            current += timedelta(days=1)
        logger.info("Fetched sleep data for %d days", len(results))
        return results

    # ------------------------------------------------------------------
    # Body Battery
    # ------------------------------------------------------------------

    def get_body_battery(self, start: date, end: date) -> list[dict[str, Any]]:
        """Return body battery readings for the date range."""
        try:
            data = self.api.get_body_battery(start.isoformat(), end.isoformat())
            logger.info("Fetched body battery data")
            return data if data else []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch body battery: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Stress
    # ------------------------------------------------------------------

    def get_stress(self, start: date, end: date) -> list[dict[str, Any]]:
        """Return daily stress summaries for the date range."""
        results: list[dict[str, Any]] = []
        current = start
        while current <= end:
            try:
                data = self.api.get_stress_data(current.isoformat())
                if data:
                    data["_date"] = current.isoformat()
                    results.append(data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No stress data for %s: %s", current, exc)
            current += timedelta(days=1)
        return results

    # ------------------------------------------------------------------
    # HRV
    # ------------------------------------------------------------------

    def get_hrv(self, start: date, end: date) -> list[dict[str, Any]]:
        """Return HRV status readings for the date range."""
        results: list[dict[str, Any]] = []
        current = start
        while current <= end:
            try:
                data = self.api.get_hrv_data(current.isoformat())
                if data and data.get("hrvSummary"):
                    data["_date"] = current.isoformat()
                    results.append(data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No HRV data for %s: %s", current, exc)
            current += timedelta(days=1)
        return results


# ------------------------------------------------------------------
# Factory helper
# ------------------------------------------------------------------

def client_from_env() -> GarminClient:
    """Create a GarminClient from GARMIN_EMAIL / GARMIN_PASSWORD env vars."""
    email = os.environ.get("GARMIN_EMAIL", "")
    password = os.environ.get("GARMIN_PASSWORD", "")
    if not email or not password:
        raise RuntimeError(
            "Set GARMIN_EMAIL and GARMIN_PASSWORD environment variables "
            "(or add them to a .env file)."
        )
    return GarminClient(email, password)
