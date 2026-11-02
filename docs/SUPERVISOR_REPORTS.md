# Simple supervisor reports â€” issue 60

`GET /supervisor/reports` is a read-only, supervisor-only page. The navigation
link is shown only to supervisors. No migration, new dependency, model change,
email action, or change to existing task workflows is required.

## Included

- Current totals for the supervisor's tasks: total, waiting (stored as Pending),
  assigned, in progress, completed and overdue.
- Optional start/end filters on the task's recorded creation date, inclusive of
  both complete calendar days. The same filters apply to counts and table rows.
- Ten tasks per page, newest recorded creation first, with ID as a tie-breaker.
- Task title, currently recorded assigned worker(s), status and deadline.
- Missing assignments say Not assigned; missing deadlines say Not set. Unknown
  legacy statuses remain visible and contribute to the total and an Other note.
- Clear empty results, retained date filters, linked validation errors and
  keyboard-accessible table scrolling. Existing role and accessibility settings
  remain in effect. Interactive charts are described below; exports are not included.

## Data and time semantics

Report counts use tasks rather than joined assignment rows, so duplicate legacy
assignments cannot multiply totals. Worker display names use the existing
directory resolver for both independent and dataset-bound accounts. The report
does not run inference or invent performance/accuracy figures.

Dates select when tasks were created, not when they were completed. Statuses
are current statuses, not reconstructed historical snapshots. An overdue task
is unfinished and has a recorded deadline earlier than current Kenya civil time.
Completed tasks and missing deadlines are excluded from overdue counts. Overdue
is an overlapping count, not an additional workflow state.

The existing `Task.created_at` uses timezone-naive server-local timestamps.
Filters compare those stored dates directly; historical timezone offsets cannot
be inferred safely. This stage does not relabel or convert them. On deployment,
review timestamp consistency before interpreting creation dates as Kenya dates.
Deadlines already represent Kenya civil time and retain their existing meaning.

## Isolation and deployment

Every task query starts with the authenticated supervisor ID. A supplied
supervisor_id argument cannot select another user's tasks. Assignment rows are
also restricted to that owner and the visible task IDs. The page issues no
database writes. Invalid dates produce a 422 response and accessible errors,
not an unfiltered report. Non-supervisor accounts receive 403; signed-out users
are redirected to login.

Date filters use bound Python datetimes and standard SQLAlchemy comparisons,
counts and grouping. No SQLite-specific date functions, hardcoded local file
paths or hardcoded website URLs are introduced. SQLite tests are not proof of
hosted PostgreSQL behavior; verify the report with Neon during the later release.
Neon and Render are unchanged by this installation.

## Local checks

Run `python -m pytest tests/test_supervisor_reports.py tests/test_dashboard_overview.py tests/test_supervisor_progress.py tests/test_role_theme.py -q`.

In the supervisor portal on port 5001:

1. Open Reports and compare its unfiltered counts with the task overview.
2. Select dates covering a known task and confirm totals and rows change together.
3. Clear dates and confirm all your tasks return.
4. Try an end date earlier than the start; follow the error link and correct it.
5. Check names, Not assigned, deadlines and overdue labels against actual tasks.
6. Check a narrow window and large-text/dark-mode preferences.

The automated checks cover ownership, date boundaries, open-ended/invalid dates,
pagination, empty reports, deadline comparisons, duplicate assignments, escaped
names, role restrictions, read-only behavior and existing dashboard regressions.
Browser appearance and hosted verification must be reported separately.


## Interactive doughnut charts
- Bootstrap responsive cards contain server-rendered SVG doughnuts for task status and priority. No external library, network asset or JavaScript is required.
- Clicking a slice or its labelled legend link filters the task table to that category, preserving creation dates. Selecting another slice replaces the category. Show all tasks clears the category while retaining dates.
- Charts and headline totals always describe the complete selected date period; the table heading and selection message show the drill-down result count.
- Pagination preserves category and dates. Unsupported category parameters are rejected, and all queries remain restricted to the signed-in supervisor.
- Counts, percentages and keyboard-accessible links provide equivalent information and actions outside the decorative SVG. Geometry uses exact proportions; display percentages are rounded.
- Unknown values are grouped as Other, empty reports show an empty message, and overdue is not plotted as a mutually exclusive status.
- Manual review: slice selection, keyboard legend links, reset, pagination, mobile layout, large text, dark mode and high contrast.

## Creation-date limits
Both report date fields allow today or earlier, using the current Kenya date. HTML max attributes guide the calendar; server-side checks reject manually entered future dates with linked field errors. Blank dates remain supported. Task deadline calendars are unaffected.

## Issue #60 verification checkpoint

The project owner confirmed 33 report tests passed after adding the future-date limit. Browser checks on port 5001 confirmed totals, creation-date filtering, doughnut charts, drill-down and blocking future dates. These are focused local results; the final combined application/ML and JavaScript run must be recorded separately. No hosted verification or formal accessibility conformance is claimed.
