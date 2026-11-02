"""Store hashed initial-setup invitations for independent workers only.

Revision ID: 56d04a2b7c80
Revises: 56c03f1a6b70
"""
from alembic import op
import sqlalchemy as sa

revision = '56d04a2b7c80'
down_revision = '56c03f1a6b70'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'worker_setup_invitations',
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('independent_worker_registrations.agent_id'), primary_key=True),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('created_by_admin_id', sa.Integer(), sa.ForeignKey('administrators.id'), nullable=False),
        sa.Column('issued_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('length(token_hash) = 64', name='ck_worker_setup_hash_length'),
        sa.CheckConstraint('expires_at > issued_at', name='ck_worker_setup_expiry'),
    )


def downgrade():
    count = op.get_bind().execute(sa.text('SELECT COUNT(*) FROM worker_setup_invitations')).scalar_one()
    if count:
        raise RuntimeError('Worker setup invitations exist. Preserve their access and usage records before planning a downgrade.')
    op.drop_table('worker_setup_invitations')
