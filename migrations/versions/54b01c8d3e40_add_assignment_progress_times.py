"""Add optional assignment progress timestamps, preserving legacy records.

Revision ID: 54b01c8d3e40
Revises: 49a01b7c2d30
"""
from alembic import op
import sqlalchemy as sa

revision = '54b01c8d3e40'
down_revision = '49a01b7c2d30'
branch_labels = None
depends_on = None


def upgrade():
    # UTC, stored without a timezone for consistent SQLite/PostgreSQL handling.
    # No defaults or backfill: unknown historical times must stay unknown.
    op.add_column('task_assignments', sa.Column('started_at', sa.DateTime(), nullable=True))
    op.add_column('task_assignments', sa.Column('completed_at', sa.DateTime(), nullable=True))


def downgrade():
    recorded = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM task_assignments '
        'WHERE started_at IS NOT NULL OR completed_at IS NOT NULL'
    )).scalar_one()
    if recorded:
        raise RuntimeError('Progress timestamps exist. Preserve them before planning a downgrade.')
    with op.batch_alter_table('task_assignments') as batch:
        batch.drop_column('completed_at')
        batch.drop_column('started_at')
