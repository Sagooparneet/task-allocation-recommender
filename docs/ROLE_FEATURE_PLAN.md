# IntelliTask role feature plan

Based on the supplied use-case diagram. This is an implementation checklist, not a list of live features.

## Issue #46: shared theme and supervisor overview

- Shared navy, teal and neutral styling, responsive navigation, and an IntelliTask SVG logo.
- Branded login page using the existing authentication flow.
- Supervisor-owned task counts, progress chart, priority bars and overdue indicators.
- Task-name search, status filters and ten-row pagination.
- Links to existing task creation, recommendations and assignment workflows.
- Worker snapshot using existing display names, skill labels and recorded results.
- No database migration or new runtime dependencies.

Automated tests cover empty dashboards, owner-scoped metrics, literal search, filtering, pagination, asset availability and role navigation. A real desktop/mobile browser review is still required before publishing. The automated preview attempt timed out before visual inspection.

## Supervisor: remaining issues to create

1. **Add supervisor reports and CSV export**: task status, completion and deadlines, date filters, and owner-scoped exports. Keep application activity separate from offline ML evaluation.
2. **Extend task monitoring and assignment history**: assigned-worker details and a full status-event history. Issue #54 already adds in-progress totals/filters and recorded start/completion times. Do not infer dates or outcomes that were never recorded.

Existing: login, task creation, recommendation explanations, assignment, and the task overview. Reports are not implemented yet.

## Onboarding agent: remaining issues to create

1. **Consider a full task event history**: issue #54 records the first start and completion timestamps, but does not maintain an event/audit log. Scope any additional transitions separately.

Completed locally under issue #54: Assigned → In progress → Completed, ownership and form-token checks, atomic status/workload changes, repeat-action protection, timestamp display and supervisor progress summaries.
Completed locally under issue #48: worker dashboard with deadline sorting, task counts, filters, pagination and task details. Issue #49 adds saved venue/address/reporting instructions.

Existing: login support, the improved assigned-task dashboard, starting work and protected completion. Selected local demonstration logins can be enabled explicitly; fresh imported accounts remain disabled for login. Production worker identity provisioning is separate work. Never attach a real new account to an unrelated dataset worker's history.

## Administrator: remaining issues to create

1. **Finish onboarding-agent management (issue #56)**: listing, search, profiles, display-name editing, availability and account deactivation/reactivation are implemented locally. Controlled new-worker creation and production identity provisioning remain pending; preserve source identity bindings and never borrow dataset history for a new person.
2. **Manage supervisors**: controlled account provisioning, role checks, deactivation and an audit trail.
3. **Manage service catalogue**: controlled editing with validation. The task form now uses a free-text title rather than a task-type catalogue. Display labels alone must not create unsupported ML capabilities or silently change source mappings.

Existing under issue #49: administrator overview, venue listing/filtering, adding/editing and deactivation/reactivation with role checks and form-token protection. A local administrator has been provisioned on port 5001. Fresh setup does not provision an administrator account.

## Authentication: separate issue

**Add verified signup, Google sign-in and email OTP**: decide permitted roles and approval flow; verify Google tokens server-side; use expiring, single-use OTPs, rate limits and secure account linking. Do not allow public signup to select administrator privileges. Provider configuration and email delivery need separate setup and verification.

## Delivery order

1. Issue #49 venue integration and issue #52 accessibility changes have been merged.
2. Issue #54 task progress has been merged. Issue #56 worker management is at a tested local checkpoint (202 Python tests and 6 JavaScript tests on 31 October 2026).
3. Implement remaining administrator account/service management.
4. Implement verified signup and recovery.
5. Add reporting and exports.
6. Separately review PostgreSQL migration, hosted configuration and release verification.

Create and link a GitHub issue for each feature before implementing it. Only expose navigation items when their pages and permission checks work. Keep the current Render deployment unchanged while local UI work is reviewed.


## Issue #56 checkpoint boundaries

Availability controls new assignments; account deactivation controls access. Deactivation is refused for unfinished work. Reactivation leaves availability off and preserves existing credentials. Display-name edits are presentation changes only. Local migration revision is 56b02e0f5a60. Neon/Render upgrades, PostgreSQL concurrency testing, new-worker provisioning and self-service email/password management remain separate pending work. Keep issue #56 open while its remaining scope is reviewed.


## Issue #57: Bootstrap frontend integration

Locally implemented: pinned Bootstrap 5.3.8 assets, responsive grids, forms/buttons, cards/tables, badges/pagination, navigation/messages, readable default text, a compact worker filter and a custom accessible deadline calendar. Existing role colours and saved accessibility preferences remain supported. See README for final test results and the Bootstrap component guides for build details.

This presentation work adds no database migration or ML changes. It builds on the issue #56 checkpoint and does not close that issue's pending account-management work. Hosted release and PostgreSQL verification remain separate.
