/* Server-rendered errors remain readable and linked without JavaScript. */
(() => {
    const summary = document.getElementById('form-error-summary');
    if (!summary) return;
    summary.focus();
    summary.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', event => {
            const target = document.getElementById(link.hash.slice(1));
            if (!target) return;
            event.preventDefault();
            target.focus();
            target.scrollIntoView({block: 'center', behavior: 'instant'});
        });
    });
})();
