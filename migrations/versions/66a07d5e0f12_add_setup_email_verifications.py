"""Store short-lived first-time email challenges without changing existing accounts.

Revision ID: 66a07d5e0f12
Revises: 62b06c4d9e01
"""

from alembic import op
import sqlalchemy as sa

revision = '66a07d5e0f12'
down_revision = '62b06c4d9e01'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'setup_email_verifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('worker_id', sa.Integer(), sa.ForeignKey('independent_worker_registrations.agent_id'), unique=True),
        sa.Column('supervisor_id', sa.Integer(), sa.ForeignKey('supervisors.id'), unique=True),
        sa.Column('invitation_token_hash', sa.String(64), nullable=False),
        sa.Column('code_hash', sa.String(255), nullable=False),
        sa.Column('issued_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('last_sent_at', sa.DateTime(), nullable=False),
        sa.Column('send_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.CheckConstraint(
            '(worker_id IS NOT NULL AND supervisor_id IS NULL) OR '
            '(worker_id IS NULL AND supervisor_id IS NOT NULL)',
            name='ck_setup_email_one_account',
        ),
        sa.CheckConstraint('length(invitation_token_hash) = 64', name='ck_setup_email_invitation_hash'),
        sa.CheckConstraint('expires_at > issued_at', name='ck_setup_email_expiry'),
        sa.CheckConstraint('last_sent_at >= issued_at', name='ck_setup_email_last_sent'),
        sa.CheckConstraint('send_count >= 1', name='ck_setup_email_send_count'),
        sa.CheckConstraint('failed_attempts >= 0', name='ck_setup_email_failed_attempts'),
    )


def downgrade():
    count = op.get_bind().execute(sa.text('SELECT COUNT(*) FROM setup_email_verifications')).scalar_one()
    if count:
        raise RuntimeError('Email verification records exist. Preserve them before downgrading.')
    op.drop_table('setup_email_verifications')
