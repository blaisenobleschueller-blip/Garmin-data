# iOS Shortcuts — Garmin Health to Google Calendar

This guide creates 3 automated iPhone Shortcuts that read your Garmin data
from Apple Health and log it to Google Calendar every morning. No server,
no rate limits, no maintenance.

**Prerequisites:**
- Garmin Connect app installed and syncing to Apple Health (Settings → Connected Apps → Apple Health → enable all categories)
- Google account added to iPhone (Settings → Mail → Accounts)
- iOS Shortcuts app (built-in)

---

## Shortcut 1 — Workouts → Calendar

Logs yesterday's workouts as timed calendar events.

### Steps

Open **Shortcuts** → tap **+** (top right) → name it `Log Workouts to Calendar`

Add these actions in order:

---

**Action 1: Set date range for yesterday**

Search for action: `Date`
- Add action: **Date**
- Set to: **Current Date**

Search for action: `Adjust Date`
- Add action: **Adjust Date**
- Input: `Date` (the result above)
- Adjust by: **-1 Days**
- This gives you "yesterday"

---

**Action 2: Get start and end of yesterday**

Search: `Get Start of Day` — this rounds the date back to midnight
- Add action: **Get Start of Day**
- Input: the adjusted date
- Set variable: name it `Yesterday Start`

Search: `Get Start of Day` again
- Add action: **Adjust Date**
- Input: `Yesterday Start`
- Adjust by: **+1 Days**
- Set variable: name it `Yesterday End`

---

**Action 3: Fetch workouts**

Search: `Find Health Samples`
- Add action: **Find Health Samples**
- Type: **Workout**
- Filter: Start Date → is after → `Yesterday Start`
- Filter: Start Date → is before → `Yesterday End`
- Sort by: Start Date, oldest first

---

**Action 4: Loop through each workout**

Search: `Repeat with Each`
- Add action: **Repeat with Each**
- Input: Health Samples (result of step above)

  Inside the loop, add:

  **4a. Build the event title**

  Search: `Get Details of Health Sample`
  - Add action: **Get Details of Health Sample**
  - Detail: **Workout Activity Type**
  - Input: `Repeat Item`
  - Set variable: name it `Activity Type`

  Search: `Text`
  - Add action: **Text**
  - Content: `Workout · ` then insert variable `Activity Type`
  - Set variable: name it `Event Title`

  **4b. Get timing**

  Search: `Get Details of Health Sample`
  - Add action: **Get Details of Health Sample**
  - Detail: **Start Date**
  - Input: `Repeat Item`
  - Set variable: `Workout Start`

  Repeat for:
  - Detail: **End Date** → set variable `Workout End`
  - Detail: **Duration** → set variable `Workout Duration`
  - Detail: **Total Distance** → set variable `Workout Distance`
  - Detail: **Active Energy Burned** → set variable `Workout Calories`

  **4c. Build notes**

  Search: `Text`
  - Add action: **Text**
  - Content (type this out):
    ```
    Duration: [Workout Duration]
    Distance: [Workout Distance]
    Calories: [Workout Calories] kcal
    ```
  - Insert each variable where shown using the variable picker

  **4d. Create calendar event**

  Search: `Add New Event`
  - Add action: **Add New Event**
  - Title: `Event Title` variable
  - Start Date: `Workout Start` variable
  - End Date: `Workout End` variable
  - Calendar: select your **Google Calendar**
  - Notes: the Text from step 4c
  - All Day: **Off**

- End Repeat

---

**Action 5: Notify when done**

Search: `Show Notification`
- Add action: **Show Notification**
- Body: `Workouts logged to calendar`

---

## Shortcut 2 — Sleep → Calendar

Logs last night's sleep as an overnight event.

### Steps

Create a new Shortcut: `Log Sleep to Calendar`

---

**Action 1: Get last night's sleep**

Search: `Find Health Samples`
- Add action: **Find Health Samples**
- Type: **Sleep Analysis**
- Filter: Value → is → **Asleep** (not "In Bed")
- Sort by: Start Date, oldest first
- Limit: **1** sample (the first asleep period = sleep start)

Set variable: `Sleep Start Sample`

Add another **Find Health Samples**:
- Type: **Sleep Analysis**
- Filter: Value → is → **Asleep**
- Sort by: Start Date, **newest** first
- Limit: **1** (the last asleep period = wake time)

Set variable: `Sleep End Sample`

---

**Action 2: Extract start and end times**

Search: `Get Details of Health Sample`
- Detail: **Start Date**
- Input: `Sleep Start Sample`
- Set variable: `Sleep Start`

Search: `Get Details of Health Sample`
- Detail: **End Date**
- Input: `Sleep End Sample`
- Set variable: `Sleep End`

---

**Action 3: Calculate total sleep duration**

Search: `Get Time Between Dates`
- Add action: **Get Time Between Dates**
- First Date: `Sleep Start`
- Second Date: `Sleep End`
- In: **Hours**
- Set variable: `Sleep Hours`

---

**Action 4: Build title and notes**

Search: `Text`
- Content: `😴 Sleep · ` then insert `Sleep Hours` → then type ` h`

Search: `Text` (notes)
- Content:
  ```
  Total sleep: [Sleep Hours] hours
  Bedtime: [Sleep Start]
  Wake: [Sleep End]
  ```

---

**Action 5: Create calendar event**

Search: `Add New Event`
- Title: the title Text from above
- Start Date: `Sleep Start`
- End Date: `Sleep End`
- Calendar: your Google Calendar
- Notes: the notes Text above
- All Day: **Off**

---

## Shortcut 3 — Daily Recovery Score → Calendar

Creates an all-day event with a colour-coded recovery score from HRV and sleep.

### Steps

Create a new Shortcut: `Log Recovery to Calendar`

---

**Action 1: Get last night's HRV**

Search: `Find Health Samples`
- Type: **Heart Rate Variability**
- Sort by: Start Date, newest first
- Limit: **10** (overnight readings)
- Set variable: `Recent HRV Samples`

Search: `Calculate Statistics`
- Add action: **Calculate Statistics**
- Statistic: **Average**
- Input: `Recent HRV Samples`
- Set variable: `HRV Last Night`

---

**Action 2: Get 30-day HRV baseline**

Search: `Find Health Samples`
- Type: **Heart Rate Variability**
- Filter: Start Date → is after → (use `Adjust Date` on current date → -30 days)
- Set variable: `HRV 30 Day Samples`

Search: `Calculate Statistics`
- Statistic: **Average**
- Input: `HRV 30 Day Samples`
- Set variable: `HRV Baseline`

---

**Action 3: Compute HRV ratio (last night vs baseline)**

Search: `Calculate`
- Add action: **Calculate**
- Expression: `HRV Last Night` ÷ `HRV Baseline`
- Set variable: `HRV Ratio`

---

**Action 4: Get total sleep hours (reuse approach from Shortcut 2)**

Find sleep samples, get start of first/end of last, calculate hours.
Set variable: `Sleep Hours`

Compute sleep score (0–100):
- `Calculate`: `Sleep Hours` ÷ 8 × 100
- `Round` to nearest whole number
- Clamp to 100 max: `Calculate`: minimum of (Sleep Score, 100)
- Set variable: `Sleep Score`

---

**Action 5: Calculate composite recovery score**

HRV component (normalise ratio to 0–100):
- `Calculate`: (`HRV Ratio` − 0.7) ÷ 0.6 × 100
- Set variable: `HRV Score`

Weighted composite:
- `Calculate`: (`HRV Score` × 0.55) + (`Sleep Score` × 0.45)
- `Round` to nearest whole number
- Set variable: `Recovery Score`

---

**Action 6: Choose label based on score**

Search: `If`
- Add **If** → `Recovery Score` is greater than or equal to **80**
  - Add **Text**: `🟢 Go hard · Prime training window`
  - Set variable: `Recovery Label`
- Add **Otherwise**
  - Add **If** → `Recovery Score` is greater than or equal to **60**
    - **Text**: `🟡 Train well · Good for steady effort`
    - Set variable: `Recovery Label`
  - **Otherwise**
    - Add **If** → `Recovery Score` is greater than or equal to **40**
      - **Text**: `🟠 Easy session · Keep it aerobic`
      - Set variable: `Recovery Label`
    - **Otherwise**
      - **Text**: `🔴 Rest day · Recovery priority`
      - Set variable: `Recovery Label`
- End all If blocks

---

**Action 7: Build event title and notes**

Title Text:
```
[Recovery Label] ([Recovery Score]/100)
```

Notes Text:
```
HRV last night: [HRV Last Night] ms
HRV baseline (30d): [HRV Baseline] ms
Sleep: [Sleep Hours] hours
Sleep score: [Sleep Score]/100
```

---

**Action 8: Get today's date as all-day event**

Search: `Date` → Current Date
Set variable: `Today`

Search: `Get Start of Day`
- Input: `Today`
- Set variable: `Today Start`

Search: `Adjust Date`
- Input: `Today Start`
- +1 Day
- Set variable: `Today End`

---

**Action 9: Create all-day calendar event**

Search: `Add New Event`
- Title: Recovery title Text
- Start Date: `Today Start`
- End Date: `Today End`
- All Day: **On**
- Calendar: your Google Calendar
- Notes: the notes Text

---

## Automating all 3 Shortcuts (runs every morning at 9 AM)

1. Open **Shortcuts** → tap **Automation** tab (bottom)
2. Tap **+** → **Personal Automation**
3. Choose **Time of Day** → set to **9:00 AM** → **Daily**
4. Add action: **Run Shortcut** → select `Log Workouts to Calendar`
5. Add action: **Run Shortcut** → select `Log Sleep to Calendar`
6. Add action: **Run Shortcut** → select `Log Recovery to Calendar`
7. Turn off **Ask Before Running**
8. Tap **Done**

Your Garmin data will now appear in Google Calendar every morning automatically.

---

## Troubleshooting

**No workout events appearing:**
- Check Garmin Connect → Settings → Health & Wellness → Apple Health → ensure Workouts is toggled on
- Open Apple Health app → Browse → Activity → Workouts — do you see yesterday's workout there?

**No HRV data (recovery score blank):**
- HRV is only recorded during sleep by Garmin. Check Health → Browse → Heart → Heart Rate Variability
- If empty, your Garmin model may not record HRV during sleep (older models)

**Events going to wrong calendar:**
- In the `Add New Event` action, explicitly tap the Calendar field and select your Google Calendar by name
