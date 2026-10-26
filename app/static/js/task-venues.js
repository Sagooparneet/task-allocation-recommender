(() => {
    const city = document.getElementById('location');
    const select = document.getElementById('venue_id');
    if (!city || !select) return;
    const hint = document.getElementById('venue-hint');
    const preview = document.getElementById('venue-preview');
    function showAddress() {
        const option = select.selectedOptions[0];
        const selected = option && option.value && !option.disabled;
        preview.hidden = !selected;
        document.getElementById('venue-address').textContent = selected ? option.dataset.address : '';
        document.getElementById('venue-directions').textContent = selected ? option.dataset.directions : '';
    }
    function filterVenues() {
        let count = 0;
        for (const option of select.options) {
            if (!option.value) continue;
            const matches = option.dataset.city === city.value;
            option.hidden = !matches;
            option.disabled = !matches;
            if (matches) count++;
        }
        if (select.selectedOptions[0]?.disabled) select.value = '';
        hint.textContent = !city.value ? 'Choose a city above to see its work locations.'
            : count ? 'Choose the service point where this task will take place.'
            : 'No active locations in this city. Ask your administrator to add or activate one.';
        showAddress();
    }
    city.addEventListener('change', filterVenues);
    select.addEventListener('change', showAddress);
    filterVenues();
})();
