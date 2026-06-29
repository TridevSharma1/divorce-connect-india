"""add_reminder_model

Revision ID: 20230629121045
Revises: 20230629120001
Create Date: 2026-06-29 12:20:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20230629121045'
down_revision = '20230629120001'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'reminders',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('accounts_baseuser.id'), nullable=False),
        sa.Column('case_request_id', sa.Integer, sa.ForeignKey('lawyers_caserequest.id'), nullable=True),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('remind_at', sa.DateTime, nullable=False),
        sa.Column('sent', sa.Boolean, nullable=False, server_default=sa.sql.expression.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table('reminders')
