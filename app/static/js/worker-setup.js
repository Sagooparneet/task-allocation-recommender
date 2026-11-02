/* The invitation secret stays in the fragment, never a query string. */
(() => {
    const link = document.getElementById('invitation-link');
    if (link) {
        link.value = new URL(link.dataset.setupPath, window.location.href).href;
        link.addEventListener('focus', () => link.select());
    }
    const input = document.getElementById('setup_token');
    if (!input || !window.location.hash) return;
    const token = window.location.hash.slice(1);
    // Remove the fragment from this history entry without persisting it elsewhere.
    try { window.history.replaceState(null, '', window.location.pathname + window.location.search); } catch (_) {}
    if (/^[A-Za-z0-9_-]{43}$/.test(token)) input.value = token;
})();
