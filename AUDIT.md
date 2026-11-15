# AUDIT

Status key: **done**, **partial**, **missing**. "Start" is the state at the beginning of this pass (12:59 IST);
"Now" is updated as items are fixed (see the final column and the bottom of this file).

## A. Requirements from the challenge text

| # | Requirement | Start | Evidence at start | Now |
|---|-------------|-------|-------------------|-----|
| R1 | Manage daily **medications** | done | `routers/core.py` meds CRUD, `test_api.py` | done |
| R2 | Manage **healthcare routines** (BP/sugar checks, walks, water, physio) | missing | only medicines existed | done (kind=routine) |
| R3 | Manage **medical appointments** | done | appointments CRUD + tests | done |
| R4 | Keep **family and caretakers informed** | partial | email + comments + activity; no per-member preferences | done (notification prefs, feed, check-ins) |
| R5 | **Shared ecosystem** for elder, caretaker, family | done | one profile, 3 roles | done |
| R6 | **Secure passcode access** | partial | bcrypt, rate limit, token expiry, logout; no rotate/revoke | done |
| R7 | **View** profile | done | all roles, `test_family_can_view_and_comment_only` | done |
| R8 | **Add / edit / manage** schedules | partial | no duplicate guard; no routines | done |
| R9 | **Track adherence** | partial | per-dose status + weekly %; no trend, no per-medicine | done |
| R10 | **Upcoming appointments** | done | `/api/appointments` | done |
| R11 | Email: **upcoming doses** | done | `test_reminders.py` | done |
| R12 | Email: **missed medications** | done | `test_reminders.py` | done |
| R13 | Email: **appointments** (1 day, 2 h) | done | `test_appointment_windows` | done |
| R14 | Emails really send (SMTP/Gmail), HTML + text, retries | partial | plain text only, no retry, no test button | done |
| R15 | **Smarter** (beyond a reminder app) | partial | AI prescription draft, AI summary | done (+ emergency card, check-ins, duplicate warning) |
| R16 | More **accessible** | partial | elder mode, read aloud; no automated a11y check | done (axe test) |
| R17 | More **reliable** | partial | idempotent reminders; no retry/backoff, no CI lint/type | done |
| R18 | More **collaborative** | partial | notes, activity log | done |
| R19 | **Elder at the centre** | partial | approval gate, activity log; elder-only emergency card + check-ins missing | done |

## B. Gaps by scoring dimension (at start)

* **Code quality:** no ruff/mypy/ESLint/Prettier config; one 300-line router file.
* **Security:** no X-Frame-Options; no rate limit on AI endpoints; no passcode revocation; dependencies pinned but never audited.
* **Efficiency:** no pagination; AI summary recomputed on every view; a few missing indexes.
* **Testing:** 62 backend tests (good) but no frontend screen tests, no accessibility test; no lint/type steps in CI.
* **Accessibility:** good semantics but unverified by a tool; elder mode contrast not AAA.
* **Problem alignment:** routines, emergency info, wellbeing, per-member preferences missing.
* **UI/UX:** no landing explanation or one-click demo buttons; no trend chart; elder mode functional but plain.
* **Deployment/repo:** live; README lacks traceability table, diagram, screenshots, cron guide.

(The "Now" column and a results section are filled in at the end of the work; see `FINAL_REPORT.md`.)
