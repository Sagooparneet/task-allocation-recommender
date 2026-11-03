"""Allow administrators to disable supervisor access without deleting history.

Revision ID: 62a05b3c8d90
Revises: 56d04a2b7c80
"""
from alembic import op
import sqlalchemy as sa

revision = '62a05b3c8d90'
down_revision = '56d04a2b7c80'
branch_labels = None
depends_on = None


def upgrade():
    # Existing supervisors retain their current access.
    op.add_column('supervisors', sa.Column(
        'account_disabled', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    count = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM supervisors WHERE account_disabled = true')).scalar_one()
    if count:
        raise RuntimeError('Disabled supervisors exist. Preserve their access restrictions before downgrading.')
    if op.get_bind().dialect.name == 'sqlite':
        version = tuple(int(part) for part in op.get_bind().execute(
            sa.text('SELECT sqlite_version()')).scalar_one().split('.'))
        if version < (3, 35, 0):
            raise RuntimeError('This downgrade needs SQLite 3.35 or newer.')
    op.drop_column('supervisors', 'account_disabled')
