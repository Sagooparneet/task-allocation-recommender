# Bootstrap buttons, forms and readable default text — issue #57

This stage extends the locally stored Bootstrap 5.3.8 grid with a selective Sass build containing Bootstrap root variables, buttons, labels, form text, text inputs and selects. Later issue #57 stages extend this same build with cards, tables, badges, pagination, navigation and alerts. Reboot, Bootstrap progress and modal styles remain excluded to preserve existing charts and dialogs. The source and generated CSS are stored together under app/static/vendor/bootstrap-5.3.8; the existing MIT license applies. The asset manifest records hashes for both.

Existing templates use btn, form-control and form-select while retaining application classes, labels, IDs, field names, form tokens, validation attributes, conditional disabled states and POST endpoints. Checkbox/radio controls and the Settings dialog retain their existing implementation. Custom theme variables supply role colours, light/dark surfaces and contrast. No Bootstrap JavaScript validation replaces server-side validation or existing accessible errors.

## Default text

Body and normal controls now use 1rem (normally 16px). Previously undersized secondary labels use at least .875rem (normally 14px). Heading hierarchy is retained. Sizes are relative to the browser root; the accessibility choices Large, Extra large and Huge continue increasing text. No stored preferences are changed. Select Normal in Settings to inspect the new default if an enlarged setting was already saved.

The changes apply across roles through existing shared and page CSS. Check narrow screens and long names because larger text can expose wrapping issues that markup tests cannot detect.

## Rebuilding the selective CSS

The stylesheet was built with bootstrap@5.3.8 and sass@1.93.2. Flask only needs the committed CSS, not Node or Sass. In a separate build directory install these exact packages, then run the Sass CLI with its node_modules as a load path, compressed output and no source map. The input is bootstrap-controls.scss and the output is bootstrap-controls.min.css. Retain the license and update the manifest hash after intentionally rebuilding. Do not commit node_modules.

Example from a project root:

```powershell
npm install --prefix .bootstrap-build --no-audit --no-fund --ignore-scripts --save-exact bootstrap@5.3.8 sass@1.93.2
node .bootstrap-build/node_modules/sass/sass.js --load-path=.bootstrap-build/node_modules --style=compressed --no-source-map --silence-deprecation=import,global-builtin,color-functions app/static/vendor/bootstrap-5.3.8/bootstrap-controls.scss app/static/vendor/bootstrap-5.3.8/bootstrap-controls.min.css
```

## Manual verification after installation

- Login: empty submission, invalid credentials, keyboard focus and password privacy.
- Create Task: blank required fields, linked errors, retained entries and venue selection.
- Administrator: location and worker edit forms, availability and account confirmations.
- Worker: task buttons and filters.
- All roles: Normal text, larger settings, dark/high-contrast modes, reduced motion, mobile navigation, long labels and narrow layouts.

Automated checks exercise existing form validation, role protections and rendered markup; they are not a visual or screen-reader audit. No routes, models, database mappings, recommendation logic, Neon or Render settings are changed by this stage.
