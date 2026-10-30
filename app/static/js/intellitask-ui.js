document.documentElement.classList.add('it-ui-ready');
(() => {
    const menu = document.querySelector('.it-menu');
    const nav = document.getElementById('it-navigation');
    if (!menu || !nav) return;
    const mobile = window.matchMedia('(max-width: 640px)');
    document.body.classList.add('it-js');
    function setOpen(open, focusFirst = false) {
        document.body.classList.toggle('it-nav-open', open);
        menu.setAttribute('aria-expanded', String(open));
        menu.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
        if (open && focusFirst) nav.querySelector('a[href]')?.focus();
    }
    setOpen(false);
    menu.addEventListener('click', () => {
        const open = !document.body.classList.contains('it-nav-open');
        setOpen(open, open);
    });
    document.addEventListener('keydown', event => {
        if (!mobile.matches || !document.body.classList.contains('it-nav-open')
            || document.querySelector('dialog[open]')) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            setOpen(false);
            menu.focus();
        }
    });
    nav.addEventListener('click', event => {
        const link = event.target.closest('a[href]');
        if (!link || !mobile.matches) return;
        // Same-page task-list links should move focus to the destination.
        const url = new URL(link.href, window.location.href);
        if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) {
            let target;
            try { target = document.getElementById(decodeURIComponent(url.hash.slice(1))); } catch (_) {}
            if (target) {
                event.preventDefault();
                target.setAttribute('tabindex', '-1');
                setOpen(false);
                target.focus();
                target.scrollIntoView({block: 'start'});
                return;
            }
        }
        setOpen(false);
    });
    // This is a disclosure menu, not a modal: Tab may leave it normally.
    document.addEventListener('focusin', event => {
        if (mobile.matches && !nav.contains(event.target) && event.target !== menu) setOpen(false);
    });
    mobile.addEventListener('change', () => {
        const focused = document.activeElement;
        setOpen(false);
        if (mobile.matches && nav.contains(focused)) menu.focus();
        else if (!mobile.matches && focused === menu) nav.querySelector('a[href]')?.focus();
    });
})();
