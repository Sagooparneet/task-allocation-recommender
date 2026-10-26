from conftest import task_venue_fields
from html.parser import HTMLParser

from app.services.recommendation_presentation import worker_summary


def evidence(successful, total, neighbors=0):
    return {'graph': {'category_successes': successful, 'category_count': total,
                      'shared_task_neighbors': neighbors}}


def test_selected_skill_results_do_not_double_count_aliases():
    result = worker_summary({'53': evidence(39, 57, 75), '69': evidence(8, 8),
                             '50': evidence(100, 100)}, ['53', '69', '53'])
    assert result['successful'] == 47
    assert result['total'] == 65
    assert result['with_history'] == 2
    assert result['shared_history_used'] is True
    assert [row['label'] for row in result['skills']] == ['M-PESA Onboarding', 'Account Activation']


def test_unknown_history_is_not_presented_as_success():
    result = worker_summary({'56': evidence(0, 0)}, ['56'])
    assert result['total'] == result['successful'] == result['with_history'] == 0
    assert result['shared_history_used'] is False


class Details(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'details' and attrs.get('class') == 'it-rec-details':
            self.cards.append(attrs)


def test_compact_card_keeps_assignment_and_collapses_evidence(app, client):
    from datetime import datetime, timedelta
    from app.models import Skill, Task
    from app.services.netease_recommendation_service import NetEaseRecommendationService

    client.post('/auth/login', data={'email': 'supervisor@test.com', 'password': 'password123'})
    with app.app_context():
        skill_id = Skill.query.filter_by(name='NetEase capability 56').one().id
    response = client.post('/supervisor/task/create', data={**task_venue_fields(client, location='Nairobi'),
        'task_type': 'KYC Verification', 'location': 'Nairobi', 'priority': 'Medium',
        'required_skills': str(skill_id),
        'deadline': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
    })
    assert response.status_code == 302
    with app.app_context():
        task_id = Task.query.one().id
        rows = NetEaseRecommendationService().get_recommendations(task_id)
    response = client.get(f'/supervisor/task/{task_id}/recommendations')
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    parser = Details()
    parser.feed(page)
    assert len(parser.cards) == len(rows) > 0
    assert all('open' not in attrs for attrs in parser.cards)
    assert 'Assign worker' in page
    assert 'assignment_csrf_token' in page
    assert f'name="agent_id" value="{rows[0]["agent_id"]}"' in page
    assert 'Related past task history contributes to this recommendation.' not in page
    assert 'Successful / recorded' in page
    assert f'{rows[0]["match_percentage"]:.2f}/100' in page
