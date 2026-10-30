# Create Task error handling — issue 52

Create Task validates all submitted fields on the server and returns an error summary with links to affected controls. Each invalid field has an error message and aria-invalid/aria-describedby associations. Services use a fieldset and legend, with error information also associated with each checkbox. Entered values are rendered back with template escaping.

JavaScript moves focus to the summary on an invalid response and moves focus to controls when error links are selected. Without JavaScript, the server still validates and the summary links remain available. The form uses novalidate to avoid browser popups intercepting submission before the complete server summary can be returned. Required attributes remain for assistive technology; all requirements are enforced on the server.

Submission-token validation and role checks remain in place. Database save failures get a general summary rather than a false field error. No task, service links or venue snapshot is created if validation fails. Venue records are refreshed before checking activity and city. Recommendations and existing tasks are unchanged.

## Manual checks on port 5001

1. Open Create Task and submit it empty. Confirm the summary gets focus and lists each problem.
2. Use Tab to select a summary link and Enter to focus its field. The services link focuses the group; Tab enters its checkboxes.
3. Enter a title and instructions, leave the deadline blank, then submit. Confirm the text remains and the deadline error appears beside its field.
4. Correct the fields and submit a deliberate test task. Confirm normal creation and recommendations still work.
5. Test light/dark appearance, high contrast, large text, a narrow screen and keyboard-only navigation.
6. With a screen reader, check the summary heading, field labels, error text, and service group. Repeat with JavaScript disabled to check the fallback.

Automated tests cover rendering, linked errors, retained and escaped input, corrected submissions and no writes on invalid input. Browser focus and screen-reader checks still require manual verification. Login and administrator location forms are the next steps; this change only covers Create Task.
