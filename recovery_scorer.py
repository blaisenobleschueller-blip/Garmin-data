"""
Recovery scorer — combines HRV, sleep, and body battery into a single
readiness score (0–100) with a plain-language training recommendation.

Weights:
  HRV vs personal baseline  40 %
  Sleep score               35 %
  Morning body battery      25 %

Missing components are excluded and the remaining weights are renormalized,
so the score is still meaningful when a device doesn't capture all signals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class RecoveryResult:
    score: int           # 0–100 composite
    emoji: str           # colour indicator
    label: str           # short label e.g. "Go hard"
    recommendation: str  # one-line guidance
    hrv_score: float | None        # normalised HRV component (0–100)
    sleep_score: float | None      # sleep score as reported by Garmin (0–100)
    battery_score: float | None    # body battery charged value (0–100)
    hrv_raw: float | None          # overnight HRV in ms
    hrv_baseline: float | None     # personal balanced-range midpoint


def _label(score: int) -> tuple[str, str, str]:
    """Return (emoji, label, recommendation) for a score."""
    if score >= 80:
        return "🟢", "Go hard", "Prime training window — high intensity or long session"
    if score >= 60:
        return "🟡", "Train well", "Good to train — steady effort or moderate intensity"
    if score >= 40:
        return "🟠", "Easy session", "Keep it aerobic — technique, base miles, or yoga"
    if score >= 20:
        return "🔴", "Light only", "Low recovery — short walk or full rest"
    return "⛔", "Rest day", "Body needs recovery — skip training today"


# ---------------------------------------------------------------------------
# Per-signal normalisers
# ---------------------------------------------------------------------------

def _hrv_component(hrv_data: dict[str, Any]) -> tuple[float, float | None, float | None]:
    """
    Return (normalised_score_0_100, hrv_raw_ms, baseline_midpoint).
    Compares last-night HRV against the personal balanced range midpoint.
    """
    summary: dict = hrv_data.get("hrvSummary", {}) if isinstance(hrv_data, dict) else {}
    last_night: float | None = summary.get("lastNight")
    if last_night is None:
        return 50.0, None, None   # neutral fallback

    baseline: dict = summary.get("baseline", {}) if isinstance(summary.get("baseline"), dict) else {}
    low: float | None = baseline.get("balancedLow")
    high: float | None = baseline.get("balancedUpper")

    if low and high and low > 0:
        midpoint = (low + high) / 2.0
        # ratio: 1.0 → score 50, 1.3+ → 100, 0.7- → 0
        ratio = last_night / midpoint
        score = (ratio - 0.7) / (1.3 - 0.7) * 100.0
        return max(0.0, min(100.0, score)), last_night, midpoint

    # No baseline available — use loose absolute scale (40–80 ms typical adult range)
    score = (last_night - 20.0) / (100.0 - 20.0) * 100.0
    return max(0.0, min(100.0, score)), last_night, None


def _sleep_component(sleep_data: dict[str, Any]) -> float | None:
    """Return Garmin's sleep score (0–100) or None."""
    dto: dict = sleep_data.get("dailySleepDTO", {}) if isinstance(sleep_data, dict) else {}
    scores = dto.get("sleepScores")
    if isinstance(scores, dict):
        overall = scores.get("overall")
        if isinstance(overall, dict):
            val = overall.get("value")
            if val is not None:
                return float(val)
    # Fallback: derive rough score from total sleep time
    sleep_secs: int | None = dto.get("sleepTimeSeconds")
    if sleep_secs:
        # 8 h = 100, 6 h = 60, 4 h = 20
        hours = sleep_secs / 3600.0
        return max(0.0, min(100.0, (hours - 4.0) / (9.0 - 4.0) * 100.0))
    return None


def _battery_component(bb_entry: dict[str, Any] | None) -> float | None:
    """Return the morning (charged) body battery value (0–100) or None."""
    if not bb_entry or not isinstance(bb_entry, dict):
        return None
    charged = bb_entry.get("charged")
    if charged is not None:
        return float(max(0, min(100, charged)))
    return None


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_recovery(
    hrv_data: dict[str, Any] | None,
    sleep_data: dict[str, Any] | None,
    body_battery_entry: dict[str, Any] | None,
) -> RecoveryResult | None:
    """
    Compute a composite recovery score from available Garmin signals.
    Returns None only if *all* signals are absent.
    """
    components: list[tuple[float, float]] = []  # (score, weight)
    hrv_norm, hrv_raw, hrv_baseline = (None, None, None)
    sleep_norm: float | None = None
    battery_norm: float | None = None

    # HRV — 40 %
    if hrv_data:
        hrv_norm, hrv_raw, hrv_baseline = _hrv_component(hrv_data)
        components.append((hrv_norm, 0.40))

    # Sleep — 35 %
    if sleep_data:
        sleep_norm = _sleep_component(sleep_data)
        if sleep_norm is not None:
            components.append((sleep_norm, 0.35))

    # Body battery — 25 %
    battery_norm = _battery_component(body_battery_entry)
    if battery_norm is not None:
        components.append((battery_norm, 0.25))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    weighted_sum = sum(s * w for s, w in components)
    raw_score = weighted_sum / total_weight   # renormalise for missing signals

    score = max(0, min(100, round(raw_score)))
    emoji, label, recommendation = _label(score)

    return RecoveryResult(
        score=score,
        emoji=emoji,
        label=label,
        recommendation=recommendation,
        hrv_score=round(hrv_norm, 1) if hrv_norm is not None else None,
        sleep_score=round(sleep_norm, 1) if sleep_norm is not None else None,
        battery_score=round(battery_norm, 1) if battery_norm is not None else None,
        hrv_raw=round(hrv_raw, 1) if hrv_raw is not None else None,
        hrv_baseline=round(hrv_baseline, 1) if hrv_baseline is not None else None,
    )


# ---------------------------------------------------------------------------
# Build a date-keyed map of recovery results
# ---------------------------------------------------------------------------

def build_recovery_map(
    hrv_records: list[dict[str, Any]],
    sleep_records: list[dict[str, Any]],
    body_battery: list[dict[str, Any]],
) -> dict[str, RecoveryResult]:
    """
    Return a dict mapping ISO date strings → RecoveryResult.
    Handles mismatched or missing data gracefully.
    """
    # Index each source by date
    hrv_by_date: dict[str, dict] = {}
    for entry in hrv_records:
        if isinstance(entry, dict):
            d = entry.get("_date") or (entry.get("startTimestampLocal") or "")[:10]
            if d:
                hrv_by_date[d] = entry

    sleep_by_date: dict[str, dict] = {}
    for entry in sleep_records:
        if isinstance(entry, dict):
            d = entry.get("_date") or ""
            if d:
                sleep_by_date[d] = entry

    bb_by_date: dict[str, dict] = {}
    for entry in body_battery:
        if isinstance(entry, dict):
            d = entry.get("date") or entry.get("calendarDate") or ""
            if d:
                bb_by_date[d] = entry

    all_dates = set(hrv_by_date) | set(sleep_by_date) | set(bb_by_date)
    result: dict[str, RecoveryResult] = {}

    for d in sorted(all_dates):
        recovery = compute_recovery(
            hrv_data=hrv_by_date.get(d),
            sleep_data=sleep_by_date.get(d),
            body_battery_entry=bb_by_date.get(d),
        )
        if recovery:
            result[d] = recovery

    return result
