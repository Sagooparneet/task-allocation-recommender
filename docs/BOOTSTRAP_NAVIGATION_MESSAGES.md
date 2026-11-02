# Shared navigation and feedback — issue #57

Adds the official nav and alert components to the local Bootstrap 5.3.8 selective build. Rebuild with the Sass 1.93.2 command documented in BOOTSTRAP_CONTROLS.md and refresh manifest SHA-256 hashes.

Sidebar links retain their routes, aria-current, role visibility, colours and existing mobile disclosure script. Bootstrap collapse/offcanvas is not activated alongside that script. Links wrap and retain 44px minimum targets. The accessibility stylesheet remains last.

Flashed feedback uses Bootstrap alerts with visible meaning labels, escaped message text and the existing polite live region. Unknown categories use information styling; error maps to danger. Messages are not auto-dismissed. Dark, high-contrast and forced-colour styles retain readable borders and text. Inline form errors remain separate and unchanged.

Manual checks on port 5001: log in and inspect the success message; check each role's navigation; at mobile width open the menu by keyboard and close it with Escape; verify focus returns to the opener. Try dark mode, high contrast and the largest text size. Check the workers filter remains compact.

No routes, models, database records, dataset mappings or recommendation logic change. Neon and Render are not accessed.
