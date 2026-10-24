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
2. **Improve task monitoring and assignment history**: assigned worker, lifecycle timestamps, overdue views and status history. Do not infer dates or outcomes that were never recorded.

Existing: login, task creation, recommendation explanations, assignment, and the task overview. Reports are not implemented yet.

## Onboarding agent: remaining issues to create

1. **Add a complete worker task lifecycle**: allow starting an assigned task, track In Progress and Completed separately, retain event history and enforce ownership, valid transitions, CSRF protection and repeat-action handling.
2. **Improve worker dashboard**: deadline sorting, workload overview, upcoming tasks and task details. Reuse the shared theme.

Existing: login support, assigned-task list and completion. Imported dataset accounts remain disabled for login; production worker identity provisioning is separate work. Never attach a real new account to an unrelated dataset worker's history.

## Administrator: remaining issues to create

1. **Manage onboarding agents**: listing, search, controlled creation/editing and deactivation, preserving source identity bindings.
2. **Manage supervisors**: controlled account provisioning, role checks, deactivation and an audit trail.
3. **Manage skills and task types**: editable operational catalogues with validation. Display labels alone must not create unsupported ML capabilities or silently change source mappings.

Existing: administrator login support and a basic dashboard only. Management routes are not yet implemented. Fresh setup does not provision an administrator account.

## Authentication: separate issue

**Add verified signup, Google sign-in and email OTP**: decide permitted roles and approval flow; verify Google tokens server-side; use expiring, single-use OTPs, rate limits and secure account linking. Do not allow public signup to select administrator privileges. Provider configuration and email delivery need separate setup and verification.

## Delivery order

1. Review issue #46 locally and commit the theme.
2. Implement worker lifecycle and monitoring.
3. Implement administrator management and role provisioning.
4. Implement verified signup and recovery.
5. Add reporting and exports.

Create and link a GitHub issue for each feature before implementing it. Only expose navigation items when their pages and permission checks work. Keep the current Render deployment unchanged while local UI work is reviewed.
