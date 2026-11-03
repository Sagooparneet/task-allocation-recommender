"""Store expiring reset links and rate-limit records without altering accounts.

Revision ID: 66b08e6f1a23
Revises: 66a07d5e0f12
"""

from alembic import op
import sqlalchemy as sa

revision = '66b08e6f1a23'
down_revision = '66a07d5e0f12'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('worker_id', sa.Integer(), sa.ForeignKey('onboarding_agents.id')),
        sa.Column('supervisor_id', sa.Integer(), sa.ForeignKey('supervisors.id')),
        sa.Column('administrator_id', sa.Integer(), sa.ForeignKey('administrators.id')),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('issued_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime()),
        sa.CheckConstraint(
            '(worker_id IS NOT NULL AND supervisor_id IS NULL AND administrator_id IS NULL) OR '
            '(worker_id IS NULL AND supervisor_id IS NOT NULL AND administrator_id IS NULL) OR '
            '(worker_id IS NULL AND supervisor_id IS NULL AND administrator_id IS NOT NULL)',
            name='ck_password_reset_one_account',
        ),
        sa.CheckConstraint('length(token_hash) = 64', name='ck_password_reset_hash_length'),
        sa.CheckConstraint('expires_at > issued_at', name='ck_password_reset_expiry'),
    )
    op.create_table(
        'password_reset_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email_digest', sa.String(64), nullable=False),
        sa.Column('ip_digest', sa.String(64), nullable=False),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('length(email_digest) = 64', name='ck_password_reset_email_digest'),
        sa.CheckConstraint('length(ip_digest) = 64', name='ck_password_reset_ip_digest'),
    )
    op.create_index('ix_password_reset_requests_email_digest', 'password_reset_requests', ['email_digest'])
    op.create_index('ix_password_reset_requests_ip_digest', 'password_reset_requests', ['ip_digest'])


def downgrade():
    bind = op.get_bind()
    for table in ('password_reset_tokens', 'password_reset_requests'):
        if bind.execute(sa.text(f'SELECT COUNT(*) FROM {table}')).scalar_one():
            raise RuntimeError('Password reset records exist. Preserve them before downgrading.')
    op.drop_index('ix_password_reset_requests_ip_digest', table_name='password_reset_requests')
    op.drop_index('ix_password_reset_requests_email_digest', table_name='password_reset_requests')
    op.drop_table('password_reset_requests')
    op.drop_table('password_reset_tokens')
