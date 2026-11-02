# Bootstrap integration — issue #57

Bootstrap 5.3.8 is pinned and served locally under `app/static/vendor/bootstrap-5.3.8/`. The directory contains the official grid CSS and JavaScript bundle, MIT licence, selective Sass source, compiled component CSS and SHA-256 manifest. No runtime CDN fetch is needed.

## Implemented scope

- Responsive supervisor metrics and wrapping layouts.
- Buttons, inputs and selects, preserving existing fields, tokens and accessible validation.
- Cards and horizontally scrollable tables with existing semantic headings.
- Status badges and pagination preserving text, search/filter URLs and page sizes.
- Shared navigation and labelled feedback messages.
- A compact workers filter toolbar, with the conflicting card class removed from the filter form.
- Readable default text and a custom keyboard-operated deadline calendar with native field fallback.

The calendar is a custom IntelliTask component, not supplied by Bootstrap. Existing mobile navigation and native dialogs keep their established scripts. Full Bootstrap Reboot, progress and modal styling is excluded to avoid collisions with existing components. Accessibility CSS loads last; role colours, appearance preferences and reduced-motion settings remain available.

## Validation and boundaries

The README records the final automated results and user-confirmed local browser checks. Automated tests cover workflows, permissions, assets and hashes, forms, calendar date/time helpers and saved preferences. They do not replace a screen-reader or wider browser audit.

No routes, database schema, source mappings, model features or ranking weights change in this issue. Neon and Render are unchanged. The branch builds on the issue #56 worker-management checkpoint, which has unfinished account-management scope.

Build instructions: [BOOTSTRAP_CONTROLS.md](BOOTSTRAP_CONTROLS.md). Component notes: [cards/tables](BOOTSTRAP_CARDS_TABLES.md), [status/pagination](BOOTSTRAP_STATUS_PAGINATION.md), [calendar](DEADLINE_CALENDAR.md), [navigation/messages](BOOTSTRAP_NAVIGATION_MESSAGES.md).

Official sources used for the pinned assets: https://getbootstrap.com/docs/5.3/getting-started/introduction/ and https://getbootstrap.com/docs/5.3/getting-started/download/. Exact asset URLs and checksums are in the local manifest.
