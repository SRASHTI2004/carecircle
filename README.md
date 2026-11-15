# CareCircle

**Shared, elder-first care for the people we love.** CareCircle lets an elderly person, their caretakers and family
share one healthcare profile: medicines, doses, adherence, doctor appointments and email reminders, while the elder
stays at the centre of every decision.

**Live demo:** _https://carecircle.onrender.com (placeholder: replace with the deployed URL)_
(The free server sleeps when idle; the first load can take ~30 seconds.)

> CareCircle does not give medical advice and does not replace a doctor or pharmacist.

## Try it in 10 seconds

The login page lists demo passcodes for a ready-made profile (Margaret Sharma, with two weeks of history):

| Role      | Passcode        | Can do                                                                   |
|-----------|-----------------|--------------------------------------------------------------------------|
| Elder     | `DEMO-ELDER24`  | Everything, plus approve others' changes and change settings             |
| Caretaker | `DEMO-CARER24`  | Add/edit medicines and appointments, mark doses, manage reminder contacts |
| Family    | `DEMO-FAMILY24` | View everything, leave notes                                             |

Things to try: mark a dose Taken/Skip on **Today**; open **Elder mode** (large text, high contrast, *Read aloud*);
sign in as the Elder, turn on *Require the elder's approval* in **Settings**, then sign in as Caretaker (another
browser) and add a medicine: it shows as **pending elder approval** until the Elder approves; open
**Email reminders** for the demo outbox; upload a prescription photo under **Medications** (needs `GEMINI_API_KEY`).

## Features

1. **Care profiles and passcode access.** One passcode per role (Elder, Caretaker, Family), stored only as bcrypt
   hashes. Wrong guesses are rate-limited (5 per 15 min per client, 20 per profile). Login issues a random session
   token (only its SHA-256 is stored). Permissions are enforced on every endpoint. Every change goes into an
   **activity log** the elder can read.
2. **Medications.** Name, dose, times per day, start/end dates, instructions, stock. The **Today** view lists each dose
   with large *Taken* / *Skip* buttons. Each dose is classified *taken on time* (within 30 min), *taken late*,
   *skipped* or *missed*; a weekly adherence % is shown. Stock goes down as doses are taken.
3. **Appointments.** Doctor, place, date/time, notes, upcoming list.
4. **Email reminders.** Upcoming dose (elder + caretakers), missed dose after 30 min (caretakers + family),
   appointments one day and two hours before, and low stock. SMTP comes from `.env`; without SMTP the **demo outbox**
   page shows what would have been sent. A scheduler runs every minute, and `POST /api/reminders/run` (header
   `X-Reminder-Token`) lets a free external cron wake the server and trigger reminders. Reminders are idempotent.
5. **Elder-first design.** Elder mode: very large text, high contrast, big buttons, *Read aloud* of today's doses
   (Web Speech API). The elder can require their **approval** before caretakers' changes take effect; the elder's
   own changes always apply immediately.
6. **AI with Gemini (optional, never medical advice).** (a) Prescription photo to a **draft** schedule that a human
   must review and confirm. (b) A plain-language weekly family summary. See below.
7. **Seeded demo profile** with sample medicines, appointments and adherence history (created on first start).

## How AI is used (and kept safe)

* Gemini is called from the backend only (`GEMINI_API_KEY` never reaches the browser or logs).
* **Prescription reader:** the photo goes to Gemini, which must return JSON. The response is validated with a Pydantic
  schema; frequencies are mapped to default times in our code; the result is only a *draft* shown in an editable form.
  Nothing is saved until a person presses *Confirm and save*, which uses the normal permission-checked endpoint.
  Uploads are limited to 5 MB and checked by magic bytes.
* **Weekly summary:** adherence numbers are computed deterministically in Python; Gemini only rewords those facts.
  The prompt forbids advice and the output is schema-validated.
* **Failure handling:** if AI is not configured, times out or returns invalid output, the UI shows a clear message and
  the user enters data by hand (the summary falls back to a plain computed sentence).
* A visible note says the app does not replace a doctor.

## Accessibility

Semantic landmarks (`header`, `nav`, `main`, `footer`), a skip link, a `<label>` on every input, visible focus
outlines, 44 px minimum touch targets, status conveyed with text as well as colour, `aria-live` messages
(`role="status"` / `role="alert"`), descriptive `aria-label`s on repeated buttons, tables with captions/scopes,
WCAG AA colour contrast, responsive down to phone width, `prefers-reduced-motion` respected. Elder mode raises text
size and contrast further (white/yellow on black) and has 84 px action buttons.

## Security notes

* Passcodes hashed with bcrypt; session tokens stored hashed; sessions expire (24 h) and logout deletes them.
* Login rate limiting per client+profile and per profile; profile creation is rate-limited too.
* Pydantic validation on every body (`extra="forbid"`, length/range limits, HH:MM and email checks).
* Parameterised SQL everywhere; table names in the few dynamic queries are constants.
* A session is bound to one profile, and endpoints never take a profile id, so one profile cannot read another.
* CORS restricted to `CORS_ORIGINS`; CSP, `nosniff`, `no-referrer` headers; `Cache-Control: no-store` on the API.
* `/api/reminders/run` requires a secret token (constant-time compare) and is disabled if none is configured.
* Secrets only come from environment variables; `.env` is git-ignored; logs never contain keys or email content.

## Architecture

```
frontend/ (React + TypeScript, Vite)  ->  built to frontend/dist
backend/app/
  main.py          app factory, security headers, scheduler, serves frontend/dist
  routers/         core.py (API), reminders.py (cron endpoint), ai.py (Gemini endpoints)
  services/        adherence.py (dose status + %), changes.py (CRUD + approval gate + activity log),
                   reminders.py (rules), mailer.py (SMTP/outbox), profiles.py, ai.py, seed.py
  permissions.py   role -> permission matrix and FastAPI dependencies
  security.py      bcrypt, tokens, rate limiter     schemas.py  Pydantic models     db.py  SQLite schema
```

One web service: FastAPI serves `/api/*` and the built React app. SQLite file at `DATABASE_PATH`.
Times are stored as local wall-clock time in the elder's timezone (default `Asia/Kolkata`, set `APP_TIMEZONE`).

## Setup

```bash
# backend
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements-dev.txt     # Linux/macOS: .venv/bin/pip
cp .env.example .env                                           # then fill in what you need
# frontend
cd frontend && npm install && npm run build && cd ..
# run (serves API + built UI on http://localhost:8000)
cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

For hot-reload UI development run `npm run dev` in `frontend/` (proxies `/api` to port 8000).

### Environment variables

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Enables AI features (optional) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL` | Real email; unset = demo outbox |
| `REMINDER_TOKEN` | Secret for `POST /api/reminders/run` |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `APP_TIMEZONE` | Timezone of the demo profile (default `Asia/Kolkata`) |
| `DATABASE_PATH` | SQLite file location |

### Deploy on Render

`render.yaml` defines one Docker web service. Create a Blueprint from this repo, then add `GEMINI_API_KEY` (and SMTP
variables if wanted) in the dashboard. Because the free instance sleeps, add a free cron (e.g. cron-job.org) that calls
`POST https://<your-app>/api/reminders/run` every 5 minutes with header `X-Reminder-Token: <REMINDER_TOKEN>`.
The free disk is ephemeral: the demo profile is re-seeded on every start.

## Tests

```bash
cd backend && ../.venv/Scripts/python -m pytest --cov=app     # 60+ tests: permissions, hashing, rate limiting,
                                                              # adherence, reminders, approvals, AI, API
cd frontend && npm test                                       # read-aloud and formatting helpers
cd frontend && npm run build                                  # type-checks (tsc) and builds
```

## Limitations

SQLite on a free instance is not durable; the rate limiter is in-memory (single worker); there is no passcode
rotation UI yet; AI output can be wrong, which is why a human always confirms.

## License

See `LICENSE`.
