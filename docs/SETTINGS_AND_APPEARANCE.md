# Settings and appearance — issue 52

The top-right Settings button opens a keyboard-accessible native dialog on the login page and each role portal. Appearance offers Light, Dark and System default. Accessibility offers Normal, Large, Extra large and Huge text, High contrast, Bold text and Reduce motion. Role colours remain teal, blue and purple.

Preferences apply immediately and persist in this browser, using the existing intellitask.accessibility.v1 key. Earlier preferences remain valid. Reset restores light appearance, normal text and disabled optional overrides; device reduced-motion settings still apply. Preferences are not account-synchronised. Storage failure produces a status message without preventing use.

No database, recommendation, task or authentication logic changes are included. Neon and Render are unchanged. Haptic feedback is not included.

## Manual checks before merging

- Open Settings from login and each role. Test Light, Dark and System default, including changing the device theme while System default is selected.
- Open Accessibility, use Tab and arrow keys on the radio groups, Space on switches, Back, Done and Escape. Closing should return focus to Settings.
- Reload and confirm settings persist. Reset and confirm defaults return.
- Test every text size with all three roles, narrow screens and browser zoom. Check forms, menus, tables, status badges and charts for readable text and overflow.
- Test high contrast with both light and dark appearance; test forced-colour mode and reduced-motion device preferences.
- Check dialog names, radio groups, switches and save announcements with a screen reader.

Automated rendering and preference tests do not establish full accessibility conformance. Accessible form error summaries and field error associations remain the next implementation step.
