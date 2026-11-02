import pytest


@pytest.mark.parametrize('category,tone,label', [
    ('success', 'success', 'Success'),
    ('warning', 'warning', 'Please note'),
    ('danger', 'danger', 'Something went wrong'),
    ('error', 'danger', 'Something went wrong'),
    ('unrecognised', 'info', 'Information'),
])
def test_feedback_is_labelled_escaped_and_consumed_once(client, category, tone, label):
    with client.session_transaction() as session:
        session['_flashes'] = [(category, '<script>unsafe()</script> Saved message')]
    response = client.get('/auth/login')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert f'alert alert-{tone} message {tone} it-feedback' in html
    assert f'<strong>{label}</strong>' in html
    assert 'aria-live="polite"' in html
    assert '&lt;script&gt;unsafe()&lt;/script&gt; Saved message' in html
    assert '<script>unsafe()</script>' not in html
    assert 'Saved message' not in client.get('/auth/login').get_data(as_text=True)
