"""
Calendar builder — converts Garmin data dictionaries into VEVENT objects
and assembles a full VCALENDAR that can be saved as an .ics file.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytz
from icalendar import Calendar, Event, vText

if TYPE_CHECKING:
    from recovery_scorer import RecoveryResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ACTIVITY_EMOJI: dict[str, str] = {
    "running": "🏃",
    "cycling": "🚴",
    "swimming": "🏊",
    "strength_training": "🏋",
    "hiking": "🥾",
    "walking": "🚶",
    "yoga": "🧘",
    "cardio": "💪",
    "elliptical": "⚙",
    "rowing": "🚣",
    "skiing": "⛷",
    "snowboarding": "🏂",
    "golf": "⛳",
    "tennis": "🎾",
    "basketball": "🏀",
    "soccer": "⚽",
    "other": "⚡",
}

_SLEEP_EMOJI = "😴"
_BATTERY_EMOJI = "🔋"
_STRESS_EMOJI = "😤"
_HRV_EMOJI = "❤"


def _activity_icon(activity_type: str) -> str:
    key = (activity_type or "other").lower()
    for k, v in _ACTIVITY_EMOJI.items():
        if k in key:
            return v
    return _ACTIVITY_EMOJI["other"]


def _format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "unknown duration"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


def _m_to_km(meters: float | None) -> str:
    if meters is None:
        return "—"
    return f"{meters / 1000:.2f} km"


def _bpm(val: float | None) -> str:
    return f"{int(val)} bpm" if val else "—"


def _pace(seconds_per_meter: float | None) -> str:
    if not seconds_per_meter:
        return "—"
    spm = int(seconds_per_meter * 1000)
    m, s = divmod(spm, 60)
    return f"{m}:{s:02d} /km"


# ---------------------------------------------------------------------------
# Activity events
# ---------------------------------------------------------------------------

def activity_to_event(activity: dict[str, Any]) -> Event:
    """Convert a Garmin activity dict to a calendar VEVENT."""
    event = Event()

    # Timing
    start_str: str = activity.get("startTimeLocal") or activity.get("startTimeGMT", "")
    duration_s: float = activity.get("duration") or activity.get("elapsedDuration", 0)

    if start_str:
        try:
            dt_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except ValueError:
            dt_start = datetime.now(tz=timezone.utc)
    else:
        dt_start = datetime.now(tz=timezone.utc)

    dt_end = dt_start + timedelta(seconds=int(duration_s or 0))

    # Title
    activity_type: str = (
        activity.get("activityType", {}).get("typeKey")
        or activity.get("activityType", "activity")
    )
    if isinstance(activity_type, dict):
        activity_type = activity_type.get("typeKey", "activity")
    icon = _activity_icon(str(activity_type))
    name: str = activity.get("activityName") or activity_type.replace("_", " ").title()
    event.add("summary", f"{icon} {name}")

    # Description
    distance_m: float | None = activity.get("distance")
    avg_hr: float | None = activity.get("averageHR")
    max_hr: float | None = activity.get("maxHR")
    calories: float | None = activity.get("calories")
    avg_speed: float | None = activity.get("averageSpeed")
    elevation_gain: float | None = activity.get("elevationGain")
    steps: int | None = activity.get("steps")
    training_effect: float | None = activity.get("aerobicTrainingEffect")
    vo2max: float | None = activity.get("vO2MaxValue")

    lines = [
        f"Duration: {_format_duration(duration_s)}",
    ]
    if distance_m:
        lines.append(f"Distance: {_m_to_km(distance_m)}")
    if avg_speed and distance_m:
        lines.append(f"Avg Pace: {_pace(avg_speed)}")
    if avg_hr:
        lines.append(f"Avg HR: {_bpm(avg_hr)}")
    if max_hr:
        lines.append(f"Max HR: {_bpm(max_hr)}")
    if calories:
        lines.append(f"Calories: {int(calories)} kcal")
    if elevation_gain:
        lines.append(f"Elevation Gain: {int(elevation_gain)} m")
    if steps:
        lines.append(f"Steps: {steps:,}")
    if training_effect:
        lines.append(f"Aerobic Training Effect: {training_effect:.1f}/5")
    if vo2max:
        lines.append(f"VO2 Max: {vo2max:.1f}")

    event.add("description", "\n".join(lines))
    event.add("dtstart", dt_start)
    event.add("dtend", dt_end)
    event.add("uid", f"garmin-activity-{activity.get('activityId', uuid4())}@garmin")

    # Categorise
    event.add("categories", [activity_type.replace("_", " ").title()])

    return event


# ---------------------------------------------------------------------------
# Sleep events
# ---------------------------------------------------------------------------

def sleep_to_event(sleep_data: dict[str, Any]) -> Event | None:
    """Convert a Garmin sleep record to a calendar VEVENT."""
    dto: dict[str, Any] = sleep_data.get("dailySleepDTO", {})
    if not dto:
        return None

    event = Event()

    sleep_start_ms: int | None = dto.get("sleepStartTimestampGMT") or dto.get("sleepStartTimestampLocal")
    sleep_end_ms: int | None = dto.get("sleepEndTimestampGMT") or dto.get("sleepEndTimestampLocal")
    sleep_time_s: int | None = dto.get("sleepTimeSeconds")
    deep_s: int | None = dto.get("deepSleepSeconds")
    light_s: int | None = dto.get("lightSleepSeconds")
    rem_s: int | None = dto.get("remSleepSeconds")
    awake_s: int | None = dto.get("awakeSleepSeconds")
    score: int | None = dto.get("sleepScores", {}).get("overall", {}).get("value") if isinstance(dto.get("sleepScores"), dict) else None
    avg_spo2: float | None = dto.get("averageSpO2Value")
    avg_rhr: float | None = dto.get("averageRespirationValue") or dto.get("restingHeartRate")
    avg_hrv: float | None = sleep_data.get("hrvSummary", {}).get("lastNight") if isinstance(sleep_data.get("hrvSummary"), dict) else None

    record_date: str = sleep_data.get("_date", "")

    if sleep_start_ms:
        dt_start = datetime.fromtimestamp(sleep_start_ms / 1000, tz=timezone.utc)
    elif record_date:
        # Fall back to previous evening 22:00
        d = date.fromisoformat(record_date)
        dt_start = datetime(d.year, d.month, d.day, 22, 0, tzinfo=timezone.utc) - timedelta(days=1)
    else:
        return None

    if sleep_end_ms:
        dt_end = datetime.fromtimestamp(sleep_end_ms / 1000, tz=timezone.utc)
    elif sleep_time_s:
        dt_end = dt_start + timedelta(seconds=sleep_time_s)
    else:
        dt_end = dt_start + timedelta(hours=8)

    score_label = f" · Score {score}/100" if score else ""
    event.add("summary", f"{_SLEEP_EMOJI} Sleep{score_label}")

    lines = [f"Total Sleep: {_format_duration(sleep_time_s)}"]
    if deep_s:
        lines.append(f"Deep: {_format_duration(deep_s)}")
    if light_s:
        lines.append(f"Light: {_format_duration(light_s)}")
    if rem_s:
        lines.append(f"REM: {_format_duration(rem_s)}")
    if awake_s:
        lines.append(f"Awake: {_format_duration(awake_s)}")
    if score:
        lines.append(f"Sleep Score: {score}/100")
    if avg_spo2:
        lines.append(f"Avg SpO2: {avg_spo2:.1f}%")
    if avg_rhr:
        lines.append(f"Resting HR: {_bpm(avg_rhr)}")
    if avg_hrv:
        lines.append(f"Overnight HRV: {avg_hrv:.0f} ms")

    event.add("description", "\n".join(lines))
    event.add("dtstart", dt_start)
    event.add("dtend", dt_end)
    event.add("uid", f"garmin-sleep-{record_date or uuid4()}@garmin")
    event.add("categories", ["Sleep"])

    return event


# ---------------------------------------------------------------------------
# Daily wellness all-day events
# ---------------------------------------------------------------------------

def _daily_wellness_event(
    day: date,
    body_battery_max: int | None,
    body_battery_min: int | None,
    avg_stress: int | None,
    hrv_summary: dict[str, Any] | None,
    recovery: "RecoveryResult | None" = None,
) -> Event | None:
    """Combine recovery score, body battery, stress, and HRV into a single all-day note."""
    parts: list[str] = []
    summary_parts: list[str] = []

    # Recovery score — shown first and prominently
    if recovery is not None:
        parts.append(
            f"{recovery.emoji} Recovery {recovery.score}/100 · {recovery.label}"
        )
        parts.append(f"   {recovery.recommendation}")
        parts.append("")  # blank separator
        summary_parts.append(f"{recovery.emoji} Recovery {recovery.score}")

    if body_battery_max is not None:
        parts.append(f"{_BATTERY_EMOJI} Body Battery: {body_battery_min}–{body_battery_max}")
        if recovery is None:
            summary_parts.append(f"BB {body_battery_max}")
    if avg_stress is not None:
        stress_label = (
            "low" if avg_stress < 26
            else "medium" if avg_stress < 51
            else "high" if avg_stress < 76
            else "very high"
        )
        parts.append(f"{_STRESS_EMOJI} Avg Stress: {avg_stress} ({stress_label})")
        if recovery is None:
            summary_parts.append(f"Stress {avg_stress}")
    if hrv_summary:
        last_night = hrv_summary.get("lastNight")
        status = hrv_summary.get("hrvStatusSummary", {})
        status_str = ""
        if isinstance(status, dict):
            status_str = status.get("overallHrvStatus", "")
        if last_night:
            hrv_line = f"{_HRV_EMOJI} HRV: {last_night:.0f} ms"
            if status_str:
                hrv_line += f" ({status_str})"
            if recovery and recovery.hrv_baseline:
                hrv_line += f" · baseline {recovery.hrv_baseline:.0f} ms"
            parts.append(hrv_line)

    if not parts:
        return None

    event = Event()
    event.add("summary", " · ".join(summary_parts) if summary_parts else "Wellness")
    event.add("description", "\n".join(parts))
    event.add("dtstart", day)
    event.add("dtend", day + timedelta(days=1))
    event.add("uid", f"garmin-wellness-{day.isoformat()}@garmin")
    event.add("categories", ["Wellness"])
    event["X-MICROSOFT-CDO-ALLDAYEVENT"] = vText("TRUE")

    return event


# ---------------------------------------------------------------------------
# Calendar assembly
# ---------------------------------------------------------------------------

def build_calendar(
    activities: list[dict[str, Any]],
    sleep_records: list[dict[str, Any]],
    body_battery: list[dict[str, Any]],
    stress_records: list[dict[str, Any]],
    hrv_records: list[dict[str, Any]],
    recovery_map: "dict[str, RecoveryResult] | None" = None,
    calendar_name: str = "Garmin Health",
) -> Calendar:
    """Assemble all Garmin data into a single VCALENDAR object."""
    cal = Calendar()
    cal.add("prodid", "-//Garmin Calendar Integration//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", calendar_name)
    cal.add("x-wr-timezone", "UTC")
    cal.add("x-wr-caldesc", "Workouts, sleep and wellness metrics from Garmin Connect")

    # --- Activities ---
    for activity in activities:
        try:
            event = activity_to_event(activity)
            cal.add_component(event)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping activity (parse error): %s", exc)

    # --- Sleep ---
    for record in sleep_records:
        try:
            event = sleep_to_event(record)
            if event:
                cal.add_component(event)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping sleep record (parse error): %s", exc)

    # --- Daily wellness: body battery + stress + HRV keyed by date ---
    # Index body battery by date
    bb_by_date: dict[str, tuple[int | None, int | None]] = {}
    for entry in body_battery:
        if isinstance(entry, dict):
            d = entry.get("date") or entry.get("calendarDate", "")
            charged = entry.get("charged")
            drained = entry.get("drained")
            bb_by_date[d] = (charged, drained)

    # Index stress by date
    stress_by_date: dict[str, int] = {}
    for entry in stress_records:
        if isinstance(entry, dict):
            d = entry.get("_date") or entry.get("calendarDate", "")
            avg = entry.get("avgStressLevel")
            if avg and avg > 0:
                stress_by_date[d] = avg

    # Index HRV by date
    hrv_by_date: dict[str, dict] = {}
    for entry in hrv_records:
        if isinstance(entry, dict):
            d = entry.get("_date") or entry.get("startTimestampLocal", "")[:10]
            hrv_by_date[d] = entry.get("hrvSummary", {})

    # Collect all unique dates
    all_dates = set(bb_by_date) | set(stress_by_date) | set(hrv_by_date)
    for date_str in sorted(all_dates):
        try:
            day = date.fromisoformat(date_str)
        except ValueError:
            continue
        bb = bb_by_date.get(date_str, (None, None))
        stress = stress_by_date.get(date_str)
        hrv = hrv_by_date.get(date_str)
        recovery = (recovery_map or {}).get(date_str)
        try:
            event = _daily_wellness_event(day, bb[0], bb[1], stress, hrv, recovery)
            if event:
                cal.add_component(event)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping wellness event for %s: %s", date_str, exc)

    logger.info(
        "Built calendar with %d components",
        len(list(cal.walk("VEVENT"))),
    )
    return cal
