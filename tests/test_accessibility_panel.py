from html.parser import HTMLParser
from pathlib import Path
import re
import pytest


class Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}
        self.buttons = []
        self.labels = []
        self.inputs = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            assert attrs['id'] not in self.ids, 'Duplicate HTML ID'
            self.ids[attrs['id']] = (tag, attrs)
        if tag == 'input': self.inputs.append(attrs)
        if tag == 'button': self.buttons.append(attrs)
        if tag == 'label': self.labels.append(attrs.get('for'))


@pytest.mark.parametrize('email,path', [
    (None, '/auth/login'),
    ('supervisor@test.com', '/supervisor/task/create'),
    ('netease-6376@demo.invalid', '/agent/dashboard'),
    ('admin@test.com', '/admin/venues/new'),
])
def test_preferences_panel_on_all_roles_and_login(client, email, path):
    if email:
        client.post('/auth/login', data={'email': email, 'password': 'password123'})
    response = client.get(path)
    assert response.status_code == 200
    parser = Controls()
    parser.feed(response.get_data(as_text=True))
    tag, dialog = parser.ids['it-accessibility-panel']
    assert tag == 'dialog' and 'open' not in dialog
    assert dialog['aria-labelledby'] in parser.ids
    assert dialog['aria-describedby'] in parser.ids
    triggers = [b for b in parser.buttons if b.get('aria-controls') == 'it-accessibility-panel']
    assert len(triggers) == 1 and triggers[0]['aria-haspopup'] == 'dialog'
    assert 'hidden' in triggers[0]  # JavaScript enables it only after initialization.
    assert parser.ids['accessibility-text-size'][0] == 'fieldset'
    assert {i['value'] for i in parser.inputs if i.get('name') == 'text-size'} == {'default', 'large', 'largest', 'huge'}
    assert {i['value'] for i in parser.inputs if i.get('name') == 'appearance'} == {'light', 'dark', 'system'}
    for name in ('contrast', 'bold', 'motion'):
        control = parser.ids['accessibility-' + name][1]
        assert control['role'] == 'switch'
        assert control['aria-labelledby'] in parser.ids
        assert control['aria-describedby'] in parser.ids
    assert 'hidden' in parser.ids['settings-accessibility'][1]
    assert parser.ids['accessibility-contrast'][1]['type'] == 'checkbox'
    assert parser.ids['accessibility-motion'][1]['type'] == 'checkbox'
    if email:
        menu = next(b for b in parser.buttons if 'it-menu' in b.get('class', '').split())
        assert menu['aria-controls'] == 'it-navigation'
        assert parser.ids['it-navigation'][0] == 'nav'


def test_preference_asset_and_relative_text_sizes(app, client):
    assert client.get('/static/js/accessibility-preferences.js').status_code == 200
    for path in (Path(app.static_folder)/'css').glob('*.css'):
        assert not re.search(r'font-size\s*:\s*[\d.]+px', path.read_text(encoding='utf-8')), path.name
