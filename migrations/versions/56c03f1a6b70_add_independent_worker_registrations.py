"""Track administrator-added workers separately from dataset identities.

Revision ID: 56c03f1a6b70
Revises: 56b02e0f5a60
"""
from alembic import op
import sqlalchemy as sa

revision = '56c03f1a6b70'
down_revision = '56b02e0f5a60'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'independent_worker_registrations',
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('onboarding_agents.id'), primary_key=True),
        sa.Column('created_by_admin_id', sa.Integer(), sa.ForeignKey('administrators.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )


def downgrade():
    count = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM independent_worker_registrations'
    )).scalar_one()
    if count:
        raise RuntimeError('Independent worker registrations exist. Preserve their origin records before planning a downgrade.')
    op.drop_table('independent_worker_registrations')
