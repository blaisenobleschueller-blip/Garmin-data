# Garmin Calendar Integration

Export workouts, sleep, body battery, stress, and HRV data from Garmin Connect as an `.ics` calendar file importable into **Google Calendar, Apple Calendar, or Outlook**.

## What gets exported

| Metric | Calendar entry |
|---|---|
| Workouts (run, ride, swim, strength, …) | Timed event with pace, HR, calories, VO2 Max |
| Sleep | Overnight event with deep/light/REM breakdown and sleep score |
| Body Battery | All-day note showing daily high/low |
| Stress | All-day note with average stress level |
| HRV | All-day note with overnight HRV reading |

Wellness metrics (body battery, stress, HRV) are combined into a single all-day event per day so your calendar stays clean.

---

## Quick start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env and set GARMIN_EMAIL and GARMIN_PASSWORD
```

> Your credentials are only used to authenticate with Garmin Connect directly from your machine. They are never stored or transmitted elsewhere. The `.env` file is in `.gitignore`.

### 3. Run

```bash
# Export the last 30 days (all metrics) → garmin.ics
python main.py

# Custom date range
python main.py --start 2024-01-01 --end 2024-03-31

# Only workouts and sleep
python main.py --metrics activities,sleep

# Custom output path
python main.py --output ~/Desktop/garmin.ics

# All options
python main.py --help
```

### 4. Import into your calendar

| App | Steps |
|---|---|
| **Google Calendar** | Settings → Import → select `garmin.ics` |
| **Apple Calendar** | File → Import → select `garmin.ics` |
| **Outlook** | File → Open & Export → Import/Export → Import an iCalendar file |

---

## CLI reference

```
Options:
  --start YYYY-MM-DD     Start date (default: 30 days ago)
  --end   YYYY-MM-DD     End date   (default: today)
  --metrics METRICS      Comma-separated: activities, sleep, body_battery,
                         stress, hrv, all  (default: all)
  --output / -o PATH     Output .ics file  (default: garmin.ics)
  --calendar-name TEXT   Name shown in the calendar app  (default: Garmin Health)
  --verbose / -v         Enable verbose logging
  --help                 Show this message and exit.
```

---

## Project layout

```
Garmin-data/
├── main.py              # CLI entry point
├── garmin_client.py     # Garmin Connect authentication & data fetching
├── calendar_builder.py  # iCalendar event construction
├── requirements.txt     # Python dependencies
├── .env.example         # Credential template
└── .gitignore
```

## Dependencies

| Package | Purpose |
|---|---|
| `garminconnect` | Unofficial Garmin Connect API client |
| `icalendar` | RFC 5545 iCalendar (.ics) generation |
| `python-dotenv` | Load credentials from `.env` |
| `click` | CLI argument parsing |
| `pytz` | Timezone handling |
