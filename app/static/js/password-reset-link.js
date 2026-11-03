(() => {
    'use strict';
    const field = document.getElementById('reset_token');
    if (!field || !window.location.hash) return;
    const token = window.location.hash.slice(1);
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    if (/^[A-Za-z0-9_-]{43}$/.test(token)) field.value = token;
})();
