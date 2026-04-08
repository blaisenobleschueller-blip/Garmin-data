#!/usr/bin/env python3
"""
garmin-to-calendar — export Garmin Connect data as an .ics calendar file.

Usage:
    python main.py [OPTIONS]

Examples:
    # Last 30 days, all metrics, write to garmin.ics
    python main.py

    # Custom date range
    python main.py --start 2024-01-01 --end 2024-03-31

    # Only workouts
    python main.py --metrics activities

    # Workouts + sleep, custom output file
    python main.py --metrics activities,sleep --output ~/Desktop/garmin.ics
"""

from __future__ import annotations

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import click
from dotenv import load_dotenv

from garmin_client import GarminClient, client_from_env
from calendar_builder import build_calendar


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

VALID_METRICS = {"activities", "sleep", "body_battery", "stress", "hrv", "all"}


def _parse_metrics(metrics_str: str) -> set[str]:
    parts = {m.strip().lower() for m in metrics_str.split(",")}
    if "all" in parts:
        return {"activities", "sleep", "body_battery", "stress", "hrv"}
    invalid = parts - VALID_METRICS
    if invalid:
        raise click.BadParameter(
            f"Unknown metric(s): {', '.join(sorted(invalid))}. "
            f"Valid choices: {', '.join(sorted(VALID_METRICS - {'all'}))}."
        )
    return parts


@click.command()
@click.option(
    "--start",
    default=None,
    metavar="YYYY-MM-DD",
    help="Start date (default: 30 days ago).",
)
@click.option(
    "--end",
    default=None,
    metavar="YYYY-MM-DD",
    help="End date (default: today).",
)
@click.option(
    "--metrics",
    default="all",
    show_default=True,
    metavar="METRICS",
    help=(
        "Comma-separated list of metrics to include. "
        "Choices: activities, sleep, body_battery, stress, hrv, all."
    ),
)
@click.option(
    "--output",
    "-o",
    default="garmin.ics",
    show_default=True,
    metavar="PATH",
    help="Output .ics file path.",
)
@click.option(
    "--calendar-name",
    default="Garmin Health",
    show_default=True,
    help="Display name embedded in the calendar file.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging.",
)
def main(
    start: str | None,
    end: str | None,
    metrics: str,
    output: str,
    calendar_name: str,
    verbose: bool,
) -> None:
    """Export Garmin Connect data to an iCalendar (.ics) file."""

    # Logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        stream=sys.stderr,
    )

    # Load .env if present
    load_dotenv()

    # Parse dates
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=30)

    if start_date > end_date:
        raise click.UsageError("--start must be before --end.")

    # Parse metrics
    wanted = _parse_metrics(metrics)

    click.echo(
        f"Fetching Garmin data from {start_date} to {end_date}  "
        f"[{', '.join(sorted(wanted))}]"
    )

    # Connect
    try:
        client: GarminClient = client_from_env()
        client.connect()
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Fetch requested data
    activities = client.get_activities(start_date, end_date) if "activities" in wanted else []
    sleep_records = client.get_sleep(start_date, end_date) if "sleep" in wanted else []
    body_battery = client.get_body_battery(start_date, end_date) if "body_battery" in wanted else []
    stress_records = client.get_stress(start_date, end_date) if "stress" in wanted else []
    hrv_records = client.get_hrv(start_date, end_date) if "hrv" in wanted else []

    # Summarise fetch
    click.echo(
        f"  Activities: {len(activities)}  |  Sleep days: {len(sleep_records)}  |  "
        f"Body battery days: {len(body_battery)}  |  Stress days: {len(stress_records)}  |  "
        f"HRV days: {len(hrv_records)}"
    )

    # Build calendar
    cal = build_calendar(
        activities=activities,
        sleep_records=sleep_records,
        body_battery=body_battery,
        stress_records=stress_records,
        hrv_records=hrv_records,
        calendar_name=calendar_name,
    )

    # Write output
    output_path = Path(output).expanduser().resolve()
    output_path.write_bytes(cal.to_ical())
    click.echo(f"\nCalendar written to: {output_path}")
    click.echo(
        "Import this file into Google Calendar, Apple Calendar, or Outlook "
        "to see your Garmin data on your schedule."
    )


if __name__ == "__main__":
    main()
