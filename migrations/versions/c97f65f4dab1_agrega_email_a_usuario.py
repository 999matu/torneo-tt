"""agrega email a usuario

Revision ID: c97f65f4dab1
Revises: 
Create Date: 2026-03-31

"""
from alembic import op
import sqlalchemy as sa


revision = 'c97f65f4dab1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_column('email')