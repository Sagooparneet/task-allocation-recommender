from datetime import datetime, timezone

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkVenue(db.Model):
    __tablename__ = 'work_venues'
    __table_args__ = (
        db.UniqueConstraint('city', 'name', name='uq_work_venue_city_name'),
        db.CheckConstraint("city IN ('Nairobi','Mombasa','Kisumu','Nakuru','Eldoret')",
                           name='ck_work_venue_city'),
        db.CheckConstraint("length(trim(name)) > 0", name='ck_work_venue_name'),
        db.CheckConstraint("length(trim(address)) > 0", name='ck_work_venue_address'),
        db.Index('ix_work_venues_city_active', 'city', 'is_active'),
    )

    id = db.Column(db.Integer, primary_key=True)
    seed_key = db.Column(db.String(80), unique=True, nullable=True)
    city = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    address = db.Column(db.String(300), nullable=False)
    directions = db.Column(db.Text)
    map_url = db.Column(db.String(1000))
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)


class TaskVenueDetails(db.Model):
    """A location snapshot for one task; legacy city-only tasks have no row.

    Future task-creation code must validate the selected venue and copy these
    fields in the same transaction as the task. Venue edits never refresh them.
    """
    __tablename__ = 'task_venue_details'
    __table_args__ = (
        db.CheckConstraint("city IN ('Nairobi','Mombasa','Kisumu','Nakuru','Eldoret')",
                           name='ck_task_venue_city'),
        db.CheckConstraint("length(trim(reporting_point)) > 0", name='ck_task_venue_reporting_point'),
    )

    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id', ondelete='RESTRICT'), primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('work_venues.id', ondelete='RESTRICT'),
                         nullable=False, index=True)
    city = db.Column(db.String(40), nullable=False)
    venue_name = db.Column(db.String(160), nullable=False)
    address = db.Column(db.String(300), nullable=False)
    directions = db.Column(db.Text)
    map_url = db.Column(db.String(1000))
    reporting_point = db.Column(db.String(200), nullable=False)
    instructions = db.Column(db.Text)
    contact_details = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    # No backref or eager loading on Task: old installations can still query
    # their existing tasks before the venue migration is deliberately applied.
    venue = db.relationship('WorkVenue')
