import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import WorkVenue
from app.services.initial_work_venues import add_initial_venues


def test_migration_preserves_legacy_tasks_and_supports_snapshots(tmp_path):
    from scripts.check_venue_schema import verify_in_temporary_directory
    verify_in_temporary_directory(tmp_path)


def test_seed_preserves_manually_entered_venue(app):
    with app.app_context():
        existing = WorkVenue(city='Nakuru', name='Merica Hotel', address='Administrator supplied address', is_active=False)
        db.session.add(existing)
        db.session.commit()
        assert add_initial_venues(db.session) == 4
        db.session.commit()
        assert add_initial_venues(db.session) == 0
        assert WorkVenue.query.count() == 5
        assert existing.address == 'Administrator supplied address'
        assert not existing.is_active


@pytest.mark.parametrize('field,value', [('city','Unlisted city'), ('name','   '), ('address','')])
def test_database_rejects_invalid_venue_fields(app, field, value):
    with app.app_context():
        fields = dict(city='Nairobi', name='Test venue', address='Test address')
        fields[field] = value
        db.session.add(WorkVenue(**fields))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_duplicate_venue_name_in_city_rejected(app):
    with app.app_context():
        db.session.add(WorkVenue(city='Nairobi', name='Test venue', address='Address one'))
        db.session.commit()
        db.session.add(WorkVenue(city='Nairobi', name='Test venue', address='Address two'))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
