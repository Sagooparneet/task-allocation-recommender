from html.parser import HTMLParser
from pathlib import Path
import re

import pytest


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.body = {}
        self.main = {}
        self.styles = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'body': self.body = attrs
        if tag == 'main': self.main = attrs
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.styles.append(attrs['href'])


@pytest.mark.parametrize('email,role,path,label', [
    ('supervisor@test.com', 'supervisor', '/supervisor/task/create', 'Supervisor portal'),
    ('netease-6376@demo.invalid', 'agent', '/agent/dashboard', 'Worker portal'),
    ('admin@test.com', 'administrator', '/admin/venues', 'Administrator portal'),
])
def test_role_theme_comes_from_account_and_loads_after_page_styles(client, email, role, path, label):
    client.post('/auth/login', data={'email': email, 'password': 'password123'})
    response = client.get(path, query_string={'role': 'administrator' if role != 'administrator' else 'agent'})
    assert response.status_code == 200
    page = Page()
    page.feed(response.get_data(as_text=True))
    assert page.body['data-role'] == role
    assert page.main['id'] == 'main-content' and page.main['tabindex'] == '-1'
    assert page.styles[-1] == '/static/css/role-accessibility.css'
    assert label.encode() in response.data
    assert b'Skip to content' in response.data


def test_public_login_uses_neutral_default_and_asset_is_available(client):
    page = Page()
    page.feed(client.get('/auth/login').get_data(as_text=True))
    assert page.body['data-role'] == 'public'
    assert client.get('/static/css/role-accessibility.css').status_code == 200


def luminance(colour):
    channels = [int(colour[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in channels]
    return sum(c*w for c,w in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high+.05)/(low+.05)


def test_role_palette_text_and_control_contrast(app):
    css = (Path(app.static_folder)/'css/role-accessibility.css').read_text(encoding='utf-8')
    blocks = re.findall(r'^body\.it-theme(?:\[data-role="[^"]+"\])?\s*\{([^}]+)\}', css, re.MULTILINE)
    blocks = [block for block in blocks if "--role-accent:" in block]
    assert len(blocks) == 3
    for block in blocks:
        colours = dict(re.findall(r'--([\w-]+):\s*(#[0-9a-f]{6})', block))
        assert contrast(colours['role-accent'], '#ffffff') >= 4.5
        assert contrast(colours['role-accent'], colours['role-soft']) >= 4.5
        assert contrast(colours['role-hover'], '#ffffff') >= 4.5
        assert contrast(colours['role-bright'], colours['role-selected']) >= 4.5
        assert contrast('#c8d9d8', colours['role-sidebar']) >= 4.5
        assert contrast('#344d59', colours['role-soft']) >= 4.5
    assert contrast('#52636a', '#f5f7f6') >= 4.5
    assert contrast('#71847e', '#ffffff') >= 3
    assert contrast('#172f40', '#ffffff') >= 3
