/* Display preferences only. Keep v1 storage compatible with earlier settings. */
(() => {
    const key = 'intellitask.accessibility.v1';
    function normalize(value) {
        const settings = value && typeof value === 'object' ? value : {};
        return {
            textSize: ['default', 'large', 'largest', 'huge'].includes(settings.textSize) ? settings.textSize : 'default',
            contrast: settings.contrast === true,
            reducedMotion: settings.reducedMotion === true,
            bold: settings.bold === true,
            appearance: ['light', 'dark', 'system'].includes(settings.appearance) ? settings.appearance : 'light',
        };
    }
    function read(storage) {
        try { return normalize(JSON.parse(storage.getItem(key))); }
        catch (_) { return normalize(null); }
    }
    function write(storage, settings) {
        try { storage.setItem(key, JSON.stringify(normalize(settings))); return true; }
        catch (_) { return false; }
    }
    function resolveAppearance(settings, systemDark) {
        return settings.appearance === 'system' ? (systemDark ? 'dark' : 'light') : settings.appearance;
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = {key, normalize, read, write, resolveAppearance};
    if (typeof document === 'undefined') return;
    let storage;
    try { storage = window.localStorage; } catch (_) { storage = null; }
    let settings = read(storage);
    const root = document.documentElement;
    const systemScheme = window.matchMedia('(prefers-color-scheme: dark)');
    function apply() {
        root.dataset.textSize = settings.textSize;
        root.dataset.contrast = settings.contrast ? 'strong' : 'standard';
        root.dataset.reducedMotion = settings.reducedMotion ? 'true' : 'false';
        root.dataset.boldText = settings.bold ? 'true' : 'false';
        root.dataset.appearance = resolveAppearance(settings, systemScheme.matches);
    }
    apply();
    systemScheme.addEventListener('change', apply);
    const dialog = document.getElementById('it-accessibility-panel');
    if (!dialog || typeof dialog.showModal !== 'function') return;
    const sizes = [...dialog.querySelectorAll('input[name="text-size"]')];
    const appearances = [...dialog.querySelectorAll('input[name="appearance"]')];
    const contrast = document.getElementById('accessibility-contrast');
    const motion = document.getElementById('accessibility-motion');
    const bold = document.getElementById('accessibility-bold');
    const status = document.getElementById('accessibility-save-status');
    const title = document.getElementById('accessibility-title');
    const home = document.getElementById('settings-home');
    const accessibility = document.getElementById('settings-accessibility');
    const back = document.getElementById('settings-back');
    const openAccessibility = document.getElementById('settings-open-accessibility');
    let opener;
    function sync() {
        sizes.forEach(input => { input.checked = input.value === settings.textSize; });
        appearances.forEach(input => { input.checked = input.value === settings.appearance; });
        contrast.checked = settings.contrast;
        motion.checked = settings.reducedMotion;
        bold.checked = settings.bold;
    }
    function showPage(accessibilityPage, focus = true) {
        home.hidden = accessibilityPage;
        accessibility.hidden = !accessibilityPage;
        back.hidden = !accessibilityPage;
        document.getElementById('settings-heading-icon').hidden = accessibilityPage;
        title.textContent = accessibilityPage ? 'Accessibility' : 'Settings';
        dialog.scrollTop = 0;
        if (focus) title.focus();
    }
    sync();
    document.querySelectorAll('.it-accessibility-button').forEach(button => {
        button.hidden = false;
        button.addEventListener('click', () => {
            if (dialog.open) return;
            opener = button;
            sync();
            showPage(false, false);
            status.textContent = '';
            dialog.showModal();
            title.focus();
        });
    });
    openAccessibility.addEventListener('click', () => showPage(true));
    back.addEventListener('click', () => { showPage(false, false); openAccessibility.focus(); });
    function save() {
        settings = normalize({textSize: sizes.find(input => input.checked)?.value,
            appearance: appearances.find(input => input.checked)?.value,
            contrast: contrast.checked, reducedMotion: motion.checked, bold: bold.checked});
        apply();
        status.textContent = write(storage, settings) ? 'Preferences saved in this browser.'
            : 'Preferences applied for this page. This browser could not save them.';
    }
    [...sizes, ...appearances, contrast, motion, bold].forEach(control => control.addEventListener('change', save));
    dialog.querySelector('.it-accessibility-close').addEventListener('click', () => dialog.close());
    dialog.querySelector('.it-accessibility-done').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { if (opener?.isConnected) opener.focus(); });
    document.getElementById('accessibility-reset').addEventListener('click', () => {
        settings = normalize(null);
        sync();
        apply();
        status.textContent = write(storage, settings) ? 'Default preferences restored.'
            : 'Defaults restored for this page. This browser could not save them.';
    });
})();
