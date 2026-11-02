from html.parser import HTMLParser
import pytest
from test_admin_workers import login, worker

class Controls(HTMLParser):
    def __init__(self):
        super().__init__(); self.items=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('input','textarea','select','button'):
            self.items.append((tag,dict(attrs)))

@pytest.mark.parametrize('role,page',[
    (None,'/auth/login'),
    ('supervisor@test.com','/supervisor/task/create'),
    ('admin@test.com','/admin/venues/new'),
    ('admin@test.com','worker-edit'),
    ('admin@test.com','worker-account'),
])
def test_controls_keep_labels_ids_and_hidden_tokens(app,client,role,page):
    if role: login(client,role)
    if page=='worker-edit': page=f'/admin/workers/{worker().id}/edit'
    if page=='worker-account': page=f'/admin/workers/{worker().id}/account-status'
    response=client.get(page)
    assert response.status_code==200
    parsed=Controls();parsed.feed(response.get_data(as_text=True))
    fields=[(tag,attrs) for tag,attrs in parsed.items if attrs.get('name')]
    assert fields
    for tag,attrs in fields:
        if attrs.get('type') in ('hidden','checkbox','radio'):
            assert 'form-control' not in attrs.get('class','').split()
        elif tag in ('input','select','textarea'):
            expected='form-select' if tag=='select' else 'form-control'
            assert expected in attrs.get('class','').split()
            assert attrs.get('id')
    # The native settings dialog remains on the page and keeps its own controls.
    assert b'<dialog' in response.data
