from html.parser import HTMLParser


def test_calendar_keeps_native_required_deadline_and_uses_local_assets(client):
    client.post('/auth/login',data={'email':'supervisor@test.com','password':'password123'})
    response=client.get('/supervisor/task/create')
    html=response.get_data(as_text=True)
    class Fields(HTMLParser):
        def __init__(self): super().__init__(); self.fields=[]; self.dialogs=[]
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='input': self.fields.append(attrs)
            if tag=='dialog': self.dialogs.append(attrs)
    parsed=Fields();parsed.feed(html)
    deadlines=[field for field in parsed.fields if field.get('name')=='deadline']
    assert len(deadlines)==1
    assert deadlines[0]['type']=='datetime-local' and 'required' in deadlines[0]
    assert deadlines[0]['aria-describedby']=='deadline-help'
    time=next(field for field in parsed.fields if field.get('id')=='deadline-picker-time')
    assert 'name' not in time  # dialog must not add another submitted value
    assert any(d.get('id')=='deadline-calendar' for d in parsed.dialogs)
    assert 'Kenya time' in html
    for path in ['/static/js/deadline-calendar.js','/static/css/deadline-calendar.css']:
        assert path in html and client.get(path).status_code==200
