# Accessibility and role colours — issue #52

## Step 1 implemented

- Account-derived data-role on the shared page shell: teal supervisor, blue agent, purple administrator. Public login keeps the default brand palette.
- Role labels remain visible. Status colours keep their meanings independently of the role accent.
- Role stylesheet loads after page styles to cover the administrator forms as well as shared dashboards.
- White inner/dark outer keyboard focus ring; distinguishable control borders; larger small-text labels; minimum 44px height for key navigation and action controls.
- The skip-link target can receive focus without joining the regular tab sequence.
- Existing reduced-motion rules remain in the shared theme; forced-colour focus/current-page borders are provided.

Automated checks calculate contrast from the declared role palette for button text, accent text on soft surfaces, sidebar navigation, muted text and control borders. They also check role selection from the authenticated account, stylesheet order and focusable main landmarks. These checks are not a complete accessibility audit or a conformance claim.

## Manual checks for this step

1. Sign in separately as supervisor, agent and administrator. Confirm teal/blue/purple accents and correct role labels.
2. Use Tab and Shift+Tab through links, forms and actions. Confirm focus is always visible, including on the dark sidebar.
3. From the top of a page, Tab to Skip to content and press Enter. Confirm navigation moves to the main content.
4. Check Create Task, an agent assignment and administrator venue forms at desktop and phone widths and 200% zoom. Record any clipping or hidden controls.

Manual browser checks have not yet been completed for this update.

## Remaining issue #52 work

- Review and improve mobile menu keyboard focus order and closing behaviour.
- Review form error associations, summaries and required service-group labels.
- Check tables, chart alternatives and reading order with a screen reader.
- Complete real-browser zoom/reflow, reduced-motion and forced-colour checks.
- Record results and fix any remaining contrast problems, including semantic status/priority colours.

No database changes, role permissions, task transitions, source mappings, ML features, or recommendation scoring changes are included. Test and review on port 5001; Neon and Render remain unchanged.
