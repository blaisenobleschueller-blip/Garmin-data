# Garmin Calendar Integration

A live iCalendar feed of your Garmin Connect data — workouts, sleep, and a daily **recovery score** — subscribed directly into Google Calendar so it stays current automatically.

## What you get in your calendar

| Event | What it shows |
|---|---|
| **Workouts** | Timed block: activity type, pace, avg/max HR, calories, VO2 max, training effect |
| **Sleep** | Overnight block: total time, deep/light/REM split, sleep score, SpO2 |
| **Daily Recovery** (all-day) | Composite score + plain-English recommendation + body battery, stress, HRV |

### Recovery score example

```
🟢 Recovery 84 · Go hard
   Prime training window — high intensity or long session

🔋 Body Battery: 44–89
😤 Avg Stress: 22 (low)
❤ HRV: 68 ms · baseline 61 ms
```

The score weights: HRV vs personal baseline (40%), sleep score (35%), body battery (25%).  
Missing signals are excluded and the remaining weights are renormalised, so the score still works if your device doesn't capture everything.

---

## Quickstart — hosted on Render (recommended)

This runs a small server on [Render's free tier](https://render.com) so your calendar URL is accessible from any device, anywhere.

### 1. Deploy to Render

1. Push this repo to GitHub (or fork it).
2. Go to [render.com](https://render.com) → New → Web Service → connect your repo.
3. Render will detect `render.yaml` and pre-fill the settings.
4. In the **Environment** tab, add:
   - `GARMIN_EMAIL` — your Garmin Connect email
   - `GARMIN_PASSWORD` — your Garmin Connect password
5. Click **Deploy**. Wait ~2 minutes for the first build.
6. Copy your app URL: `https://garmin-calendar.onrender.com`
7. Find your `CALENDAR_TOKEN` in the Render dashboard → Environment (auto-generated).

### 2. Subscribe in Google Calendar

1. Open [Google Calendar](https://calendar.google.com) → **Other calendars** → **+** → **From URL**
2. Paste your feed URL:
   ```
   https://garmin-calendar.onrender.com/garmin.ics?token=YOUR_CALENDAR_TOKEN
   ```
3. Click **Add calendar**.

Google Calendar will refresh the feed every **6–24 hours** automatically. To get data sooner after a workout, visit `https://garmin-calendar.onrender.com/refresh?token=YOUR_TOKEN` to force a cache refresh on the server — your calendar app will pick it up on its next poll.

> **Free tier note:** Render's free tier spins the server down after 15 minutes of inactivity. The first request after a sleep takes ~30 seconds (re-authenticates with Garmin). This is fine for a calendar feed. Upgrade to Render Starter ($7/mo) for always-on.

---

## Local setup (alternative)

If you prefer to run this on your own machine:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in GARMIN_EMAIL and GARMIN_PASSWORD
```

### Option A — one-shot export (no server needed)

```bash
python main.py                          # last 30 days → garmin.ics
python main.py --start 2024-01-01       # custom start date
python main.py --metrics activities,sleep --output ~/Desktop/garmin.ics
```

Import `garmin.ics` into your calendar app manually. You'll need to re-run and re-import whenever you want fresh data.

### Option B — local live server

```bash
python server.py                        # starts on http://localhost:5000
```

Subscribe Google Calendar to `http://localhost:5000/garmin.ics` — but this only works while your machine is on and the server is running. Not accessible from other devices.

---

## CLI reference (`main.py`)

```
Options:
  --start YYYY-MM-DD     Start date (default: 30 days ago)
  --end   YYYY-MM-DD     End date   (default: today)
  --metrics METRICS      activities, sleep, body_battery, stress, hrv, all
  --output / -o PATH     Output .ics file  (default: garmin.ics)
  --calendar-name TEXT   Name shown in the calendar app
  --verbose / -v         Verbose logging
  --help
```

## Server environment variables

| Variable | Default | Description |
|---|---|---|
| `GARMIN_EMAIL` | — | Garmin Connect email (required) |
| `GARMIN_PASSWORD` | — | Garmin Connect password (required) |
| `CALENDAR_TOKEN` | _(none)_ | Secret token appended to the URL — strongly recommended |
| `LOOKBACK_DAYS` | `14` | How many days of history to include |
| `CACHE_TTL_SECONDS` | `3600` | How long the server caches the .ics before re-fetching |
| `CALENDAR_NAME` | `Garmin Health` | Name shown in your calendar app |

---

## Project layout

```
Garmin-data/
├── main.py              CLI — one-shot export
├── server.py            Flask server — live iCal feed
├── garmin_client.py     Garmin Connect auth + data fetching
├── calendar_builder.py  iCalendar event construction
├── recovery_scorer.py   Recovery score (HRV + sleep + body battery)
├── render.yaml          Render deployment config
├── requirements.txt
├── .env.example
└── .gitignore
```
