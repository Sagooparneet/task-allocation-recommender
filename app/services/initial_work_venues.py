"""Initial venue directory. No bookings, rooms or worker locations are inferred."""
from app.models import WorkVenue

INITIAL_VENUES = (
    ('kicc-nairobi', 'Nairobi', 'Kenyatta International Convention Centre (KICC)',
     'Harambee Avenue, Nairobi CBD'),
    ('prideinn-nyali', 'Mombasa', 'PrideInn Nyali',
     'Links Road area, behind City Mall, Nyali, Mombasa'),
    ('acacia-premier-kisumu', 'Kisumu', 'Acacia Premier Hotel',
     "Achieng’ Oneko Road, Kisumu"),
    ('merica-nakuru', 'Nakuru', 'Merica Hotel',
     'Kenyatta Avenue, Nakuru'),
    ('boma-inn-eldoret', 'Eldoret', 'Boma Inn Eldoret',
     'Elgon View Drive, off Ramogi Drive, Eldoret'),
)


def add_initial_venues(session):
    """Caller owns the transaction. Repeats never overwrite administrator edits.

    This initial setup operation is intended for a single operator, not concurrent
    requests. Unique constraints also prevent duplicate rows at database level.
    """
    added = 0
    for key, city, name, address in INITIAL_VENUES:
        row = session.query(WorkVenue).filter_by(seed_key=key).first()
        if row is not None:
            continue
        row = session.query(WorkVenue).filter_by(city=city, name=name).first()
        if row is not None:
            # Preserve a manually entered venue without silently taking ownership.
            continue
        session.add(WorkVenue(seed_key=key, city=city, name=name, address=address))
        added += 1
    session.flush()
    return added
