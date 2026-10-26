"""Add work venues and task location snapshots without changing legacy tasks.

Revision ID: 49a01b7c2d30
Revises: 4baace48147a
"""
from alembic import op
import sqlalchemy as sa

revision = '49a01b7c2d30'
down_revision = '4baace48147a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('work_venues',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('seed_key', sa.String(80), nullable=True, unique=True),
        sa.Column('city', sa.String(40), nullable=False),
        sa.Column('name', sa.String(160), nullable=False),
        sa.Column('address', sa.String(300), nullable=False),
        sa.Column('directions', sa.Text(), nullable=True),
        sa.Column('map_url', sa.String(1000), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('city', 'name', name='uq_work_venue_city_name'),
        sa.CheckConstraint("city IN ('Nairobi','Mombasa','Kisumu','Nakuru','Eldoret')", name='ck_work_venue_city'),
        sa.CheckConstraint('length(trim(name)) > 0', name='ck_work_venue_name'),
        sa.CheckConstraint('length(trim(address)) > 0', name='ck_work_venue_address'),
    )
    op.create_index('ix_work_venues_city_active', 'work_venues', ['city', 'is_active'])
    op.create_table('task_venue_details',
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('venue_id', sa.Integer(), sa.ForeignKey('work_venues.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('city', sa.String(40), nullable=False),
        sa.Column('venue_name', sa.String(160), nullable=False),
        sa.Column('address', sa.String(300), nullable=False),
        sa.Column('directions', sa.Text(), nullable=True),
        sa.Column('map_url', sa.String(1000), nullable=True),
        sa.Column('reporting_point', sa.String(200), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('contact_details', sa.String(250), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("city IN ('Nairobi','Mombasa','Kisumu','Nakuru','Eldoret')", name='ck_task_venue_city'),
        sa.CheckConstraint('length(trim(reporting_point)) > 0', name='ck_task_venue_reporting_point'),
    )
    op.create_index('ix_task_venue_details_venue_id', 'task_venue_details', ['venue_id'])


def downgrade():
    op.drop_index('ix_task_venue_details_venue_id', table_name='task_venue_details')
    op.drop_table('task_venue_details')
    op.drop_index('ix_work_venues_city_active', table_name='work_venues')
    op.drop_table('work_venues')
