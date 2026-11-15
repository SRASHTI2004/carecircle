# PROGRESS

## BLOCKED: needs the owner (deployment)
I cannot create the Render service from here (it needs your Render account). To deploy (about 3 minutes):
1. Render dashboard -> New -> **Blueprint** -> pick this GitHub repo (it reads `render.yaml`).
2. In the service's Environment tab add `GEMINI_API_KEY` (and optionally `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
   `SMTP_PASSWORD`, `FROM_EMAIL`). `REMINDER_TOKEN` is generated automatically.
3. If Render gives a URL other than `https://carecircle.onrender.com`, update `CORS_ORIGINS` (same-origin requests work
   regardless) and the live link in `README.md`.
4. Optional: free cron (cron-job.org) -> `POST <url>/api/reminders/run` with header `X-Reminder-Token: <REMINDER_TOKEN>`.
Docker is not installed on the dev machine, so the Dockerfile has not been built locally (the same steps were run
manually: `npm run build`, then uvicorn serving `frontend/dist`, smoke-tested OK).

## Done
- **Features 1-4, 7 (backend)**: FastAPI + SQLite. Profiles with bcrypt passcodes per role, rate-limited login,
  session tokens, role permissions, activity log, medications + dose/adherence tracking, appointments, reminders
  (upcoming / missed / appointment 1d + 2h / low stock), `/api/reminders/run`, demo outbox, `DEMO` seed profile.
- **Feature 5**: Elder mode (large text, high contrast, Read aloud), elder-approval workflow ("pending elder approval").
- **Feature 6**: Gemini prescription-photo draft + weekly family summary, schema-validated with fallbacks.
- React + TypeScript frontend served by FastAPI. Dockerfile, render.yaml, CI workflow, README.

## How to test
```
python -m venv .venv && .venv/Scripts/pip install -r backend/requirements-dev.txt
cd backend && ../.venv/Scripts/python -m pytest --cov=app      # 62 tests, ~93% coverage
cd frontend && npm ci && npm test && npm run build              # 5 unit tests + typecheck + build
```
Run locally: build the frontend, then `cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --port 8000`
and open http://localhost:8000 (demo passcodes are on the login page).

## Next
1. Deploy on Render (see top) and put the live URL in README.
2. Polish: manual a11y pass in a browser, screenshots, try real Gemini key with a sample prescription.

## Pass 2 log
- 13:07 IST: backend extended (routines, duplicate warning, passcode rotate/revoke, notification prefs, HTML email + retries + test email,
  emergency card, wellbeing check-ins with alerts, trend + per-medicine adherence, pagination, AI rate limit + cache, headers).
  95 backend tests, ruff + mypy clean. Next: frontend redesign, a11y test, docs.
- Frontend redesign done: landing + one-click demo, routines, trend chart, check-ins, emergency card, passcode UI, prefs, test email, AAA elder mode. Frontend 38 tests incl. axe + contrast; ESLint/Prettier clean. Backend 95 tests, 96% coverage, ruff/mypy/pip-audit clean. Next: Render-style run, README, FINAL_REPORT.
