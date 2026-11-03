"""Link Google subjects to existing accounts without creating new accounts.

Revision ID: 66c09f702b34
Revises: 66b08e6f1a23
"""

from alembic import op
import sqlalchemy as sa

revision = '66c09f702b34'
down_revision = '66b08e6f1a23'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'google_identities',
        sa.Column('subject', sa.String(255), primary_key=True),
        sa.Column('worker_id', sa.Integer(), sa.ForeignKey('onboarding_agents.id'), unique=True),
        sa.Column('supervisor_id', sa.Integer(), sa.ForeignKey('supervisors.id'), unique=True),
        sa.Column('administrator_id', sa.Integer(), sa.ForeignKey('administrators.id'), unique=True),
        sa.Column('linked_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('length(subject) > 0', name='ck_google_subject_present'),
        sa.CheckConstraint(
            '(worker_id IS NOT NULL AND supervisor_id IS NULL AND administrator_id IS NULL) OR '
            '(worker_id IS NULL AND supervisor_id IS NOT NULL AND administrator_id IS NULL) OR '
            '(worker_id IS NULL AND supervisor_id IS NULL AND administrator_id IS NOT NULL)',
            name='ck_google_identity_one_account',
        ),
    )


def downgrade():
    count = op.get_bind().execute(sa.text('SELECT COUNT(*) FROM google_identities')).scalar_one()
    if count:
        raise RuntimeError('Linked Google identities exist. Preserve them before downgrading.')
    op.drop_table('google_identities')
