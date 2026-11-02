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

## Supervisor: implemented locally

Login, task creation, recommendation explanations, assignment, task monitoring and reports are implemented locally.

Issue #60 adds owner-scoped totals, creation-date filters limited to today or earlier in Kenya time, interactive status/priority doughnuts and a paginated task table. Slice and legend selections filter table rows while retaining date filters. All values come from application records; no model accuracy is inferred. The project owner confirmed 33 report tests and browser checks. See README and `docs/SUPERVISOR_REPORTS.md`.

CSV/PDF exports and full event histories are not required for the agreed simple reports scope. Any future expansion needs a separate issue.

## Onboarding agent: remaining issues to create

1. **Consider a full task event history**: issue #54 records the first start and completion timestamps, but does not maintain an event/audit log. Scope any additional transitions separately.

Completed locally under issue #54: Assigned → In progress → Completed, ownership and form-token checks, atomic status/workload changes, repeat-action protection, timestamp display and supervisor progress summaries.
Completed locally under issue #48: worker dashboard with deadline sorting, task counts, filters, pagination and task details. Issue #49 adds saved venue/address/reporting instructions.

Existing: login support, the improved assigned-task dashboard, starting work and protected completion. Selected local demonstration logins can be enabled explicitly; fresh imported accounts remain disabled for login. Production worker identity provisioning is separate work. Never attach a real new account to an unrelated dataset worker's history.

## Administrator: remaining issues to create

1. **Worker management (issue #56, merged)**: local listing, profiles, display names, availability, account controls, three-task capacity, independent registration, password setup, separate matching/assignment and Gmail invitations are implemented. The project owner confirmed real email delivery and the new worker's task lifecycle. The changes and documentation are merged into main; hosted rollout stays separate.
2. **Manage supervisors**: controlled account provisioning, role checks, deactivation and an audit trail.
3. **Manage service catalogue**: controlled editing with validation. The task form now uses a free-text title rather than a task-type catalogue. Display labels alone must not create unsupported ML capabilities or silently change source mappings.

Existing under issue #49: administrator overview, venue listing/filtering, adding/editing and deactivation/reactivation with role checks and form-token protection. A local administrator has been provisioned on port 5001. Fresh setup does not provision an administrator account.

## Authentication: separate issue

**Add verified signup, Google sign-in and email OTP**: decide permitted roles and approval flow; verify Google tokens server-side; use expiring, single-use OTPs, rate limits and secure account linking. Do not allow public signup to select administrator privileges. Provider configuration and email delivery need separate setup and verification.

## Delivery order

1. Issue #49 venue integration and issue #52 accessibility changes have been merged.
2. Issue #54 task progress has been merged. Issue #57 Bootstrap was merged into the issue #56 branch. Issue #56 is merged and its local behavior is verified; see README for the latest full-suite result, targeted checksum fix and 16 passing JavaScript tests.
3. Implement remaining administrator account/service management.
4. Implement verified signup and recovery.
5. Issue #60 simple supervisor reports are locally implemented and verified; finish repository review and merge. Exports are outside the agreed scope.
6. Separately review PostgreSQL migration, hosted configuration and release verification.

Create and link a GitHub issue for each feature before implementing it. Only expose navigation items when their pages and permission checks work. Keep the current Render deployment unchanged while local UI work is reviewed.


## Issue #56 checkpoint boundaries

Availability controls new assignments; account deactivation controls access. Deactivation is refused for unfinished work. Reactivation leaves availability off and preserves existing credentials. Display-name edits are presentation changes only. Local schema is at 56d04a2b7c80. Independent-worker registration, initial password setup, Gmail delivery and separate matching are implemented and locally verified. Neon/Render upgrades, PostgreSQL concurrency testing, hosted email authorization, self-service email/password changes and recovery remain separate. Issue #56 changes have been merged into main.


## Issue #57: Bootstrap frontend integration

Locally implemented: pinned Bootstrap 5.3.8 assets, responsive grids, forms/buttons, cards/tables, badges/pagination, navigation/messages, readable default text, a compact worker filter and a custom accessible deadline calendar. Existing role colours and saved accessibility preferences remain supported. See README for final test results and the Bootstrap component guides for build details.

This presentation work adds no database migration or ML changes. It was merged through the issue #56 worker-management branch into main. Hosted release and PostgreSQL verification remain separate.
