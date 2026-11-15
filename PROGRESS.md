# PROGRESS

## Blocked / needs the owner
_Nothing yet._ (Deploying on Render needs the owner to connect the GitHub repo in the Render dashboard and set GEMINI_API_KEY / SMTP vars there.)

## Done
- **Step 1-4, 7 (backend)**: FastAPI + SQLite. Profiles with bcrypt passcodes per role, rate-limited login, session tokens,
  role permissions, activity log, medications + dose/adherence tracking, appointments, reminder engine
  (upcoming / missed / appointment 1d+2h / low stock), `/api/reminders/run`, demo outbox, demo seed (`DEMO` profile).
- Dockerfile + render.yaml (single web service).

## How to test
```
python -m venv .venv && .venv/Scripts/pip install -r backend/requirements-dev.txt
cd backend && ../.venv/Scripts/python -m pytest --cov=app
```
50 tests pass, ~93% coverage.

## Next
1. React + TypeScript frontend (login, Today, medications, appointments, outbox)
2. Elder mode, read aloud, approvals UI
3. Gemini features
4. README, accessibility polish, deploy
