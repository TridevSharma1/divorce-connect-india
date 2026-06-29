"""add_user_role_razorpay

Revision ID: 20230629122000
Revises: 20230629121045
Create Date: 2026-06-29 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20230629122000'
down_revision = '20230629121045'
branch_labels = None
depends_on = None

def upgrade():
    # Check if columns exist before adding them (SQLite doesn't support multiple Column add in one statement or conditional check easily, but standard add works)
    op.add_column('accounts_baseuser', sa.Column('role', sa.String(length=20), nullable=False, server_default='client'))
    op.add_column('accounts_baseuser', sa.Column('razorpay_customer_id', sa.String(length=50), nullable=True))

def downgrade():
    with op.batch_alter_table('accounts_baseuser') as batch_op:
        batch_op.drop_column('role')
        batch_op.drop_column('razorpay_customer_id')
