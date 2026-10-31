"""Add explicit worker account deactivation without changing existing access.

Revision ID: 56b02e0f5a60
Revises: 56a01d9e4f50
"""
from alembic import op
import sqlalchemy as sa

revision = '56b02e0f5a60'
down_revision = '56a01d9e4f50'
branch_labels = None
depends_on = None


def upgrade():
    # False preserves current credentials and availability. It does not enable
    # imported accounts with unusable passwords or provision new credentials.
    op.add_column('onboarding_agents', sa.Column(
        'account_disabled', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    connection = op.get_bind()
    count = connection.execute(sa.text(
        'SELECT COUNT(*) FROM onboarding_agents WHERE account_disabled = true'
    )).scalar_one()
    if count:
        raise RuntimeError('Deactivated worker accounts exist. Preserve access restrictions before planning a downgrade.')
    if connection.dialect.name == 'sqlite':
        version = tuple(int(part) for part in connection.execute(
            sa.text('SELECT sqlite_version()')).scalar_one().split('.'))
        if version < (3, 35, 0):
            raise RuntimeError('This downgrade requires SQLite 3.35 or newer; keep the existing schema.')
    op.drop_column('onboarding_agents', 'account_disabled')
