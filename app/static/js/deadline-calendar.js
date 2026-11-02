/* Calendar dates are civil dates; never convert the submitted deadline to UTC. */
(function () {
    'use strict';
    const pad = n => String(n).padStart(2, '0');
    function dateParts(value) {
        const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || '');
        if (!match) return null;
        const [year, month, day] = match.slice(1).map(Number);
        if (year < 1000 || month < 1 || month > 12 || day < 1 || day > new Date(Date.UTC(year, month, 0)).getUTCDate()) return null;
        return {year, month, day};
    }
    function iso(year, month, day) { return `${year}-${pad(month)}-${pad(day)}`; }
    function shiftDay(value, offset) {
        const p = dateParts(value);
        if (!p) return null;
        const date = new Date(Date.UTC(p.year, p.month - 1, p.day + offset));
        const result = iso(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
        return dateParts(result) ? result : null;
    }
    function shiftMonth(value, offset) {
        const p = dateParts(value);
        if (!p) return null;
        const date = new Date(Date.UTC(p.year, p.month - 1 + offset, 1));
        const y = date.getUTCFullYear(), m = date.getUTCMonth() + 1;
        const result = iso(y, m, Math.min(p.day, new Date(Date.UTC(y, m, 0)).getUTCDate()));
        return dateParts(result) ? result : null;
    }
    function kenyaToday(now = new Date()) {
        const values = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
            timeZone: 'Africa/Nairobi', year: 'numeric', month: '2-digit', day: '2-digit'
        }).formatToParts(now).map(part => [part.type, part.value]));
        return `${values.year}-${values.month}-${values.day}`;
    }
    function combine(day, time, minimum) {
        return dateParts(day) && /^([01]\d|2[0-3]):[0-5]\d$/.test(time || '') && day >= minimum ? `${day}T${time}` : null;
    }
    function readable(value) {
        const p = dateParts(value);
        return p ? new Intl.DateTimeFormat('en-GB', {timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'}).format(new Date(Date.UTC(p.year, p.month - 1, p.day))) : '';
    }
    const api = {dateParts, shiftDay, shiftMonth, kenyaToday, combine};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    if (typeof document === 'undefined') return;
    const field = document.getElementById('deadline');
    const dialog = document.getElementById('deadline-calendar');
    const opener = document.getElementById('deadline-open');
    if (!field || !dialog || !opener || typeof dialog.showModal !== 'function') return;
    const days = document.getElementById('deadline-days');
    const time = document.getElementById('deadline-picker-time');
    const title = document.getElementById('deadline-month');
    const selection = document.getElementById('deadline-selection');
    const error = document.getElementById('deadline-calendar-error');
    const preview = document.getElementById('deadline-preview');
    const previous = document.getElementById('deadline-previous');
    const next = document.getElementById('deadline-next');
    let minimum, selected, view;
    function minDate() {
        const server = field.min.slice(0, 10);
        const today = kenyaToday();
        return server > today ? server : today;
    }
    function updatePreview() {
        const [day, clock] = field.value.split('T');
        preview.textContent = dateParts(day) && clock ? `${readable(day)} at ${clock} EAT` : '';
    }
    function clearError() { error.textContent = ''; time.removeAttribute('aria-invalid'); }
    function draw(focusDate) {
        const p = dateParts(view);
        title.textContent = new Intl.DateTimeFormat('en-GB', {timeZone: 'UTC', month: 'long', year: 'numeric'}).format(new Date(Date.UTC(p.year, p.month - 1, 1)));
        days.replaceChildren();
        const start = (new Date(Date.UTC(p.year, p.month - 1, 1)).getUTCDay() + 6) % 7;
        const count = new Date(Date.UTC(p.year, p.month, 0)).getUTCDate();
        const first = iso(p.year, p.month, 1);
        const last = iso(p.year, p.month, count);
        const candidate = focusDate || (selected >= first && selected <= last ? selected : (minimum > first ? minimum : first));
        for (let i = 0; i < start; i++) { const gap = document.createElement('span'); gap.setAttribute('aria-hidden', 'true'); days.append(gap); }
        for (let day = 1; day <= count; day++) {
            const value = iso(p.year, p.month, day);
            const button = document.createElement('button');
            button.type = 'button'; button.className = 'btn'; button.textContent = String(day); button.dataset.day = value;
            button.disabled = value < minimum;
            button.tabIndex = value === candidate ? 0 : -1;
            button.setAttribute('aria-label', readable(value));
            button.setAttribute('aria-pressed', String(value === selected));
            if (value === kenyaToday()) button.setAttribute('aria-current', 'date');
            button.addEventListener('click', () => { selected = value; clearError(); draw(value); });
            days.append(button);
        }
        previous.disabled = first.slice(0, 7) <= minimum.slice(0, 7);
        next.disabled = p.year === 9999 && p.month === 12;
        selection.textContent = selected ? `Selected: ${readable(selected)}` : 'No date selected';
        if (focusDate) days.querySelector(`[data-day="${focusDate}"]`)?.focus();
    }
    opener.hidden = false;
    opener.addEventListener('click', () => {
        minimum = minDate(); selected = null;
        const [day, clock] = field.value.split('T');
        if (dateParts(day) && day >= minimum) selected = day;
        view = selected || minimum;
        time.value = /^([01]\d|2[0-3]):[0-5]\d$/.test(clock || '') ? clock : '';
        clearError(); draw(); dialog.showModal(); days.querySelector('[tabindex="0"]')?.focus();
    });
    previous.addEventListener('click', () => { view = shiftMonth(view, -1); draw(); });
    next.addEventListener('click', () => { view = shiftMonth(view, 1); draw(); });
    days.addEventListener('keydown', event => {
        const current = event.target.dataset.day;
        if (!current) return;
        const offsets = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7};
        let target;
        if (event.key in offsets) target = shiftDay(current, offsets[event.key]);
        else if (event.key === 'PageUp' || event.key === 'PageDown') target = shiftMonth(current, event.key === 'PageUp' ? -1 : 1);
        else if (event.key === 'Home' || event.key === 'End') {
            const p = dateParts(current), weekday = (new Date(Date.UTC(p.year, p.month - 1, p.day)).getUTCDay() + 6) % 7;
            target = shiftDay(current, event.key === 'Home' ? -weekday : 6 - weekday);
        } else return;
        event.preventDefault();
        if (!target) return;
        if (target < minimum) target = minimum;
        view = target; draw(target);
    });
    dialog.querySelectorAll('[data-deadline-close]').forEach(button => button.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('close', () => opener.focus());
    time.addEventListener('input', clearError);
    document.getElementById('deadline-apply').addEventListener('click', () => {
        minimum = minDate();
        const value = combine(selected, time.value, minimum);
        if (!value) {
            error.textContent = !selected || selected < minimum ? 'Choose today or a later date.' : 'Choose a valid time in Kenya.';
            if (!selected || selected < minimum) { view = minimum; draw(minimum); }
            else { time.setAttribute('aria-invalid', 'true'); time.focus(); }
            return;
        }
        field.value = value;
        field.dispatchEvent(new Event('input', {bubbles: true}));
        field.dispatchEvent(new Event('change', {bubbles: true}));
        dialog.close();
    });
    field.addEventListener('input', updatePreview);
    updatePreview();
}());
