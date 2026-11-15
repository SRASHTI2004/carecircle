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

## Pass 3: Elder mode redesign (done)
- Light high-contrast default theme + optional "Dark theme" switch (remembered in localStorage), soft navy dark palette.
- Status = slim coloured left border + icon + text badge (no coloured cards). Doses grouped into Now and next / Later today / Done today.
- Done doses show "Taken at 8:02 AM by Margaret" with Undo (new `undo` action in `POST /api/doses`, restores stock); only due/pending doses get big
  Taken/Skip; later doses get a quiet "Mark as taken early" link. Two button styles only. Demo seed keeps today's earlier doses taken.
- Verified in a real browser (Edge) in light and dark at desktop and phone width: 15 views, 0 axe violations (colour contrast included), 0 console errors.
- Tests: backend 98 (96% coverage), frontend 70 (incl. AAA contrast for both themes, grouping, undo, theme switch).
- Screenshots refreshed in docs/screenshots and used in the README.

## Pass 2 log
- 13:07 IST: backend extended (routines, duplicate warning, passcode rotate/revoke, notification prefs, HTML email + retries + test email,
  emergency card, wellbeing check-ins with alerts, trend + per-medicine adherence, pagination, AI rate limit + cache, headers).
  95 backend tests, ruff + mypy clean. Next: frontend redesign, a11y test, docs.
- Frontend redesign done: landing + one-click demo, routines, trend chart, check-ins, emergency card, passcode UI, prefs, test email, AAA elder mode. Frontend 38 tests incl. axe + contrast; ESLint/Prettier clean. Backend 95 tests, 96% coverage, ruff/mypy/pip-audit clean. Next: Render-style run, README, FINAL_REPORT.
- 13:45 IST: README (traceability, mermaid, screenshots, cron guide), AUDIT results, FINAL_REPORT written. Browser e2e: 0 axe violations, 0 console errors. Remaining: confirm Render redeploy.

- Pass 4 (code quality refactor): core router split into auth/medications/doses/appointments/collaboration/common; SettingsTab split into four sections; named constants for limits/windows; docstrings and JSDoc on public functions and components; typed middleware (no type: ignore); audit docs moved to docs/; README Project structure section. All tests/linters green: backend 98 tests (96% coverage), frontend 70.

- Pass 5 (hardening): all frontend deps pinned to exact versions (npm ci verified), HSTS/COOP/CORP headers, request body size limits (64 KB JSON, 6 MB upload), generic 500 handler with no stack traces, tests for each. Browser axe re-run: 15 views, 0 violations, 0 console errors.
