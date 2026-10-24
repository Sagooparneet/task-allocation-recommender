document.documentElement.classList.add('it-ui-ready');
document.body.classList.add('it-js');
const menu = document.querySelector('.it-menu');
if (menu) {
    menu.addEventListener('click', () => {
        const open = document.body.classList.toggle('it-nav-open');
        menu.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && document.body.classList.contains('it-nav-open')) {
            document.body.classList.remove('it-nav-open');
            menu.setAttribute('aria-expanded', 'false');
            menu.focus();
        }
    });
}
