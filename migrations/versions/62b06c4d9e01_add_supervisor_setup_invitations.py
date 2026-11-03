"""Store initial supervisor setup invitations separately from worker invitations.

Revision ID: 62b06c4d9e01
Revises: 62a05b3c8d90
"""
from alembic import op
import sqlalchemy as sa

revision = '62b06c4d9e01'
down_revision = '62a05b3c8d90'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('supervisor_setup_invitations',
        sa.Column('supervisor_id', sa.Integer(), sa.ForeignKey('supervisors.id'), primary_key=True),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('created_by_admin_id', sa.Integer(), sa.ForeignKey('administrators.id'), nullable=False),
        sa.Column('issued_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('length(token_hash) = 64', name='ck_supervisor_setup_hash_length'),
        sa.CheckConstraint('expires_at > issued_at', name='ck_supervisor_setup_expiry'))


def downgrade():
    count = op.get_bind().execute(sa.text('SELECT COUNT(*) FROM supervisor_setup_invitations')).scalar_one()
    if count:
        raise RuntimeError('Supervisor invitations exist. Preserve their access and usage records before downgrading.')
    op.drop_table('supervisor_setup_invitations')
