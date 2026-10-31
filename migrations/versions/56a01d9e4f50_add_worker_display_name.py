"""Add an optional presentation name without changing worker source identity.

Revision ID: 56a01d9e4f50
Revises: 54b01c8d3e40
"""
from alembic import op
import sqlalchemy as sa

revision = '56a01d9e4f50'
down_revision = '54b01c8d3e40'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('onboarding_agents', sa.Column('profile_display_name', sa.String(100), nullable=True))


def downgrade():
    count = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM onboarding_agents WHERE profile_display_name IS NOT NULL'
    )).scalar_one()
    if count:
        raise RuntimeError('Edited display names exist. Preserve them before planning a downgrade.')
    # Native DROP COLUMN avoids rebuilding a table referenced by assignments,
    # skills and source bindings. Require SQLite's native support explicitly.
    connection = op.get_bind()
    if connection.dialect.name == 'sqlite':
        version = tuple(int(part) for part in connection.execute(sa.text('SELECT sqlite_version()')).scalar_one().split('.'))
        if version < (3, 35, 0):
            raise RuntimeError('This downgrade requires SQLite 3.35 or newer; keep the existing schema.')
    op.drop_column('onboarding_agents', 'profile_display_name')
