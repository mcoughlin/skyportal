"""Display t0 on source page

Revision ID: 0e29de8df22c
Revises: 3eb663b5c3e0
Create Date: 2025-01-24 20:23:15.398744

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0e29de8df22c"
down_revision = "3eb663b5c3e0"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("objs", sa.Column("t0", sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("objs", "t0")
    # ### end Alembic commands ###
