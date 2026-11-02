import hashlib
import json
from pathlib import Path
from html.parser import HTMLParser
import pytest


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.styles = []
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.styles.append(attrs['href'])
        if tag == 'script' and 'src' in attrs:
            self.scripts.append(attrs['src'])


@pytest.mark.parametrize('email,path', [
    (None, '/auth/login'),
    ('supervisor@test.com','/supervisor/dashboard'),
    ('admin@test.com','/admin/workers'),
    ('netease-6376@demo.invalid','/agent/dashboard'),
])
def test_local_assets_and_accessibility_order(app,client,email,path):
    if email:
        assert client.post('/auth/login',data={'email':email,'password':'password123'}).status_code==302
    response=client.get(path)
    assert response.status_code==200
    parsed=Assets(); parsed.feed(response.get_data(as_text=True))
    grid='/static/vendor/bootstrap-5.3.8/bootstrap-grid.min.css'
    bundle='/static/vendor/bootstrap-5.3.8/bootstrap.bundle.min.js'
    assert parsed.styles.count(grid)==1 and parsed.scripts.count(bundle)==1
    assert parsed.styles.index(grid)<parsed.styles.index('/static/css/intellitask-theme.css')
    assert parsed.styles[-1]=='/static/css/role-accessibility.css'
    assert all(url.startswith('/static/') for url in parsed.styles+parsed.scripts)
    for url in (grid,bundle):
        assert client.get(url).status_code==200
    assert b'id="main-content"' in response.data


def test_pinned_vendor_files_match_manifest(app):
    vendor=Path(app.static_folder)/'vendor/bootstrap-5.3.8'
    manifest=json.loads((vendor/'manifest.json').read_text(encoding='utf-8'))
    for name,entry in manifest.items():
        assert hashlib.sha256((vendor/name).read_bytes()).hexdigest()==entry['sha256']
    assert b'MIT' in (vendor/'LICENSE').read_bytes()


def test_supervisor_grid_preserves_total_labels_and_filters(app,client):
    client.post('/auth/login',data={'email':'supervisor@test.com','password':'password123'})
    html=client.get('/supervisor/dashboard').get_data(as_text=True)
    assert 'row-cols-1 row-cols-sm-2 row-cols-xl-5' in html
    assert html.count('<div class="col"><article class="it-metric">')==5
    for label in ('All tasks','Waiting','Assigned','In progress','Completed'):
        assert label in html
    assert 'id="task-search"' in html and 'id="task-status"' in html
