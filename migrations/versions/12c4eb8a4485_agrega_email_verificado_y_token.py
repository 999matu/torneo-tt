"""agrega email verificado y token

Revision ID: 12c4eb8a4485
Revises: c97f65f4dab1
Create Date: 2026-03-31

"""
from alembic import op
import sqlalchemy as sa

revision = '12c4eb8a4485'
down_revision = 'c97f65f4dab1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verificado', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('token_verificacion', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_column('token_verificacion')
        batch_op.drop_column('email_verificado')