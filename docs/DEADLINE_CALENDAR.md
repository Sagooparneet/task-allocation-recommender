# Supervisor deadline calendar — issue #57

Adds an optional themed calendar dialog beside the existing required datetime-local deadline input. It uses the project's Bootstrap button/form styles and a small local script; it is an IntelliTask component, not a built-in Bootstrap datepicker. No external datepicker dependency or CDN request is introduced.

The original input retains its name, ID, required flag, server minimum and validation links. With JavaScript unavailable, or without native dialog support, the enhancement button stays hidden and the original input remains usable. The dialog is outside the task form; its time field has no name, so it does not introduce an extra submitted value.

## Behaviour

- Previous/next month navigation, Monday-first calendar, today outline and selected-day highlight.
- Required explicit date and time selection; no time is silently prefilled for a blank deadline.
- A 24-hour time field labelled Kenya time (EAT, UTC+3).
- Apply writes YYYY-MM-DDTHH:MM directly to the existing input, without timezone conversion. Cancel/Escape leave its value intact.
- The minimum date is the later of the server-provided minimum and today's Nairobi date. Apply checks it again if the dialog stayed open across midnight.
- Existing backend policy remains today-or-later by date; this does not introduce a new rule rejecting an earlier time on the same day.
- Native dialog supplies modal focus containment. Arrow keys move between dates, Home/End move within a week and Page Up/Down move by month. Date buttons have full spoken date labels and a selected state. Focus returns to the opener after closing.
- Users can still type directly into the original native field. Settings and role colours are inherited.

## Verification

JavaScript tests cover leap years, invalid dates, month-end navigation, day movement, Nairobi midnight, unchanged submission format and invalid time rejection. Flask tests preserve the native field and existing required-deadline/task validation workflows. Browser interaction and screen-reader behaviour still need manual review; tests alone are not accessibility certification.

Check: open/select/apply; open/change/cancel; Escape; keyboard arrows; time-only errors; past-day disabling; manual input; retained deadline after other form errors; dark/high-contrast modes and enlarged text on narrow screens. No databases, task records, recommendation logic, Neon or Render settings are changed.
