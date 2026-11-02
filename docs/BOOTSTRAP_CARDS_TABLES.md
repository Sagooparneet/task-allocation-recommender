# Bootstrap cards and tables — issue #57

Extends the existing selective Bootstrap 5.3.8 build with the official card and table Sass components. The source, compiled CSS and asset manifest are updated together. Compilation uses the same Sass 1.93.2 toolchain documented in BOOTSTRAP_CONTROLS.md. No additional runtime dependencies or database changes are introduced.

## Changes

- Supervisor dashboard, recommendation cards, worker task cards and administrator dashboard/profile panels adopt the Bootstrap card class while retaining existing application classes and content.
- Existing worker-directory, worker-history and supervisor-task tables use Bootstrap table styles and table-responsive wrappers.
- Recommendation evidence tables receive a keyboard-focusable, labelled scrolling region while retaining the table caption and column headings.
- Supervisor task-table headers now explicitly identify their column scope.
- Component variables use IntelliTask role colours, light/dark surfaces and border colours. Existing text-size, contrast and keyboard-focus settings remain in control.
- Full Bootstrap Reboot, navigation, modal and progress styles remain excluded to avoid conflicting with unmigrated components.

No routes, form actions, database fields, dataset mappings, counts, recommendation scores, assignments or permissions are changed. Cards and tables continue to show the same real application data.

## Browser checks after installation

1. Supervisor: overview cards, task filters, task links and recorded progress times.
2. Recommendations: expand explanation details and scroll the evidence table at narrow widths.
3. Administrator: worker list, worker profile history, pagination and account-control links.
4. Worker: task cards, filters, details and existing action buttons.
5. Check dark mode, high contrast, larger text and keyboard focus on table regions. Wide tables may scroll horizontally rather than compressing or hiding columns.

Automated workflow tests and template checks cannot establish correct browser rendering. Manual visual checks remain required before expanding integration further. Neon and Render are unchanged.
