# Deployment status and verification boundary

This page distinguishes the live Render sign-in page from protected IntelliTask
features captured in a disposable local installation. It reflects the
documentation review on 16 November 2026. It is not a live health monitor.

## What was observed

| Area | Evidence | Scope |
|---|---|---|
| Render website | `https://intellitask-v5nc.onrender.com/auth/login` responded over HTTPS and displayed the branded email/password sign-in page. Genuine browser captures were taken at 1440 × 900, 768 × 1024 and 390 × 844 viewports. | Public login only. |
| Hosted Google option | No Google sign-in button appeared in the captured hosted login page. | The repository contains the route, but the button depends on a separately configured OAuth client. |
| Protected role pages | Supervisor, worker and administrator pages were rendered through the real Flask app against a disposable copy of the local SQLite installation, after replacing displayed names, emails, venues and task text with synthetic values. | Local implementation, not hosted verification. |
| Recommendation results | The local recommendation page loaded saved model artifacts and rendered five source-backed suggestions plus a separate independent-worker match for an existing task. | Demonstration of local inference; scores are not real-world success probabilities. |
| Neon data | The preceding deployment work migrated the Neon production schema, added venues and selectively imported accounts, tasks and assignments after rehearsal and backup. | Those migration/import checks do not verify every current hosted route. |

The hosted site is account-restricted. There is no unrestricted public signup.
Google sign-in is designed for existing approved accounts. Password recovery and
initial setup need functioning email delivery; a Windows DPAPI-protected Gmail
token from the local installation is not usable by Render.

## Operational boundaries

- Do not run port-5001 SQLite upgrade helpers against Neon, reset the production
  database or run seeding during a Render build/start.
- Keep database URLs, OAuth credentials, Gmail tokens and passwords outside Git.
- Render runs `gunicorn --config gunicorn.conf.py wsgi:app`; Neon stores hosted
  application records. Saved ML artifacts come from the repository.
- The free hosting instance may sleep after inactivity. An accessible login
  response does not establish availability of the complete authenticated
  workflow, Google sign-in, invitation delivery or password recovery.
- Full hosted verification should use approved test accounts to check role
  sign-in, task creation, recommendation, assignment, worker progress and
  reports, without using private credentials in documentation captures.

Detailed earlier setup and migration instructions remain in
[Implementation history](IMPLEMENTATION_HISTORY.md). Many statements there
describe historical development checkpoints and should be read with their
original context.
