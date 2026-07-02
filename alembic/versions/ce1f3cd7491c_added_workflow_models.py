"""Added workflow models

Revision ID: ce1f3cd7491c
Revises: 20230629122000
Create Date: 2026-07-02 23:14:01.817473

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce1f3cd7491c'
down_revision: Union[str, None] = '20230629122000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('support_contactrequest',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_support_contactrequest_id'), 'support_contactrequest', ['id'], unique=False)
    op.create_table('accounts_admindeleterequest',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['accounts_baseuser.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_accounts_admindeleterequest_id'), 'accounts_admindeleterequest', ['id'], unique=False)
    op.create_table('accounts_profileeditrequest',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('requested_data', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['accounts_baseuser.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_accounts_profileeditrequest_id'), 'accounts_profileeditrequest', ['id'], unique=False)
    op.create_table('support_bugreport',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reporter_id', sa.Integer(), nullable=False),
    sa.Column('issue_text', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['reporter_id'], ['accounts_baseuser.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_support_bugreport_id'), 'support_bugreport', ['id'], unique=False)
    op.create_table('support_userreport',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reporter_id', sa.Integer(), nullable=False),
    sa.Column('reported_user_id', sa.Integer(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('proof_file_url', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('action_taken', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['reported_user_id'], ['accounts_baseuser.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reporter_id'], ['accounts_baseuser.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_support_userreport_id'), 'support_userreport', ['id'], unique=False)
    op.create_table('cases_chatmessage',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('case_request_id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('file_url', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['case_request_id'], ['lawyers_caserequest.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sender_id'], ['accounts_baseuser.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cases_chatmessage_id'), 'cases_chatmessage', ['id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_cases_chatmessage_id'), table_name='cases_chatmessage')
    op.drop_table('cases_chatmessage')
    op.drop_index(op.f('ix_support_userreport_id'), table_name='support_userreport')
    op.drop_table('support_userreport')
    op.drop_index(op.f('ix_support_bugreport_id'), table_name='support_bugreport')
    op.drop_table('support_bugreport')
    op.drop_index(op.f('ix_accounts_profileeditrequest_id'), table_name='accounts_profileeditrequest')
    op.drop_table('accounts_profileeditrequest')
    op.drop_index(op.f('ix_accounts_admindeleterequest_id'), table_name='accounts_admindeleterequest')
    op.drop_table('accounts_admindeleterequest')
    op.drop_index(op.f('ix_support_contactrequest_id'), table_name='support_contactrequest')
    op.drop_table('support_contactrequest')
