# Login and work-location form errors — issue 52

Login now provides linked field errors for missing email and password, plus a focused summary. Incorrect credentials retain the same general message for known and unknown accounts. Email remains populated; passwords are never placed in the returned HTML. Successful sign-in keeps the existing role redirects.

Add/Edit work location uses the existing server validation, with linked error summaries, field messages, and focus handling. Invalid submissions retain entered values; edits are saved only after validation. Existing role restrictions, venue form tokens, duplicate checks, and HTTPS map-link checks are retained.

Both forms use server validation instead of browser validation popups so the full summary is returned. Errors remain visible and links work without JavaScript; automatic focus uses the existing shared script. Shared styling supports light, dark and forced-colour modes and preserves Create Task error styling.

## Manual verification on port 5001

1. Sign out. Submit an empty login form. Confirm two linked errors and summary focus.
2. Submit an incorrect password. Confirm the general error, retained email and empty password. Sign in normally to each role.
3. As administrator, submit Add location with required fields blank. Follow summary links with keyboard Tab/Enter.
4. Enter details but an invalid map link. Confirm entered details stay and the map-link error is associated with that field.
5. Edit a location with an invalid required field. Confirm it is not saved until corrected.
6. Check text enlargement, dark/high-contrast appearance and screen-reader announcements.

Automated tests cover error links, password non-disclosure, role redirects, retained values and database state on invalid and corrected edits. Browser and screen-reader checks remain manual. No migrations or hosted database changes are part of this step.
