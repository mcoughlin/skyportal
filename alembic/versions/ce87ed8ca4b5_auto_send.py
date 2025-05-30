"""Observation plan automatic send migration

Revision ID: ce87ed8ca4b5
Revises: 9e231893b992
Create Date: 2024-06-01 10:36:44.076381

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "ce87ed8ca4b5"
down_revision = "9e231893b992"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "defaultobservationplanrequests",
        sa.Column("auto_send", sa.Boolean(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("defaultobservationplanrequests", "auto_send")
    # ### end Alembic commands ###
