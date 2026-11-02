# Bootstrap status badges and pagination — issue #57

Adds the official badge and pagination Sass components to the pinned Bootstrap 5.3.8 subset. Uses the same Sass 1.93.2 build procedure as BOOTSTRAP_CONTROLS.md. Source, generated CSS and manifest hashes are updated together.

Task status, priority, result-count and venue-status labels retain their existing text and semantic colour classes. Bootstrap badge styling provides consistent layout; labels wrap instead of being clipped. Status meaning is not conveyed by colour alone.

Supervisor tasks, worker assignments, administrator worker lists/history and venue lists use Bootstrap pagination list markup. Existing Previous/Next URLs, filters, anchors and conditional visibility are preserved. The current page is text with aria-current, not a misleading clickable control. Pagination links have a minimum height of 44px, wrap on narrow screens and inherit role colours, focus indicators and dark-mode surfaces.

No routes, record ordering, page sizes, permissions, saved data, recommendations or dataset mappings change. Existing calendar and form templates are not replaced by this stage.

Validation uses the existing pagination/filtering and role tests, dashboard summaries and vendor-integrity checks. Manual browser checks remain necessary: navigate the administrator worker list across pages; retain a search/filter while paging; check badges and pagination in dark/high-contrast modes and at enlarged text sizes. Pages with only one page of results intentionally show no pagination controls.

Neon and Render remain unchanged. This stage is part of the local Bootstrap integration, not a deployment.
