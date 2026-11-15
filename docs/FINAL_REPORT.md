# FINAL REPORT

Live: https://carecircle-d9ia.onrender.com  |  Repo: SRASHTI2004/carecircle

## Done
Everything in the brief: routines + medicines + appointments with full CRUD and archive, adherence (status, weekly %, 7-day
chart, per medicine), passcode access with rotate/revoke, lockout and expiry, elder approval workflow, activity feed,
per-member email preferences, HTML + text reminder emails (upcoming, missed, appointment 1 day + 2 h, routine, low stock,
wellbeing) with idempotency, IST handling, retries with backoff and a demo outbox, test-email button, cron endpoint,
emergency card with Show to doctor + print, daily check-in with alerts, duplicate-medicine warning, Gemini prescription
draft and weekly summary with fallbacks and rate limits, landing page with one-click demo, AAA Elder mode, read aloud.

## Numbers
* Elder mode redesigned (light default + dark theme, grouped doses, Undo): verified in light and dark at desktop and phone width, 0 axe violations.
* Backend: 98 tests, 96% coverage (CI gate 90%), ruff + mypy strict clean, pip-audit clean.
* Frontend: 70 tests (incl. axe on every screen and WCAG contrast), ESLint + Prettier + tsc clean, `npm audit --omit=dev` clean.
* Real-browser check (Edge, `npm run e2e`): 12 views x 4 roles/viewports, **0 axe violations (with colour contrast), 0 console errors**,
  no horizontal scroll at 390 px. Screenshots in `docs/screenshots`, raw result in `docs/browser-check.json`.
* Real email: a test email through Gmail SMTP (STARTTLS 587, app password) was delivered from a local production-mode run.

## Accessibility result
0 axe violations. One genuine issue found by the browser run (standard view had no level-one heading) was fixed.
Elder mode contrast is AAA (about 17:1 text, 11:1 accent).

## Not done / caveats
* The Dockerfile cannot be built on this machine (no Docker); the same steps were run manually (npm build, pip install of
  pinned requirements, uvicorn serving `frontend/dist`). Render builds it on push.
* Real Gemini calls were not exercised in this pass (no sample prescription); AI paths are covered with mocked responses
  (valid, invalid, HTTP failure, rate limit, cache).
* SQLite on Render's free disk is ephemeral; the demo profile re-seeds on every start. Emails are only really sent if
  `SMTP_*` variables are set in the Render dashboard; otherwise the demo outbox is used.
* The rate limiter is in memory (single worker).
* Dev-only npm advisories (vite/esbuild toolchain) remain; they are not shipped in the production bundle.
