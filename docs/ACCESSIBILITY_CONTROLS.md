# Accessibility controls — issue #52, step 2

An optional Accessibility button appears at the top right for each role and on the sign-in page. It opens a native modal dialog with text size (standard/larger/largest), stronger contrast and reduced motion settings. Close, Done and Escape dismiss it and restore focus to the opener. The browser provides focus containment and keeps the background inactive while the modal is open.

Preferences are stored under intellitask.accessibility.v1 in localStorage. Only the three display choices are stored; no account information is sent or saved by this feature. They apply to this browser/site, including other users of the same browser. Reset restores defaults without clearing unrelated browser storage. Blocked or full storage still allows settings for the current page and displays an explanation. Device reduced-motion preferences remain effective even with the optional switch off.

Pixel-based font-size declarations in the existing stylesheets were converted to equivalent rem units (16px reference). The standard setting preserves their baseline sizes; larger/largest change the root text size to 112.5%/125%. Browser zoom remains available. Review reflow and clipping manually; scaling alone does not establish accessibility conformance.

Mobile navigation is a disclosure, not a modal. Opening moves focus to its first link. Escape closes it and returns focus to the toggle. Focus may leave normally, closing the menu. Same-page task links focus their target. Resize handling prevents focus remaining on a hidden menu toggle or link. Without JavaScript the normal navigation links remain visible and the optional controls are hidden.

Checks: python -m pytest tests ml/tests -q; node --test tests/js/accessibility_preferences.test.cjs. The JavaScript tests cover preference validation, reload/reset and blocked storage; they do not simulate a real browser's keyboard or native dialog behaviour.

Manual checks before completion:
1. Open settings with Enter, move through controls with Tab/Shift+Tab, close with Escape, and confirm focus returns to Accessibility.
2. Change text size/contrast/motion, reload, and verify preferences remain. Reset and verify defaults.
3. At phone width, open navigation with the keyboard, use Escape, then reopen and follow a task-list link. Check that hidden links cannot receive focus.
4. Check desktop/phone layout and 200% browser zoom with the largest text setting.
5. Check using a screen reader and forced-colour/reduced-motion OS settings.

Form-error summaries, field error associations and the remaining chart/table accessibility review are the next step. No backend logic, recommendation inputs, database or Neon changes are included here.
