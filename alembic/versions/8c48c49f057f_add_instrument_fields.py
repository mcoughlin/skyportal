"""add instrument fields

Revision ID: 8c48c49f057f
Revises: 1aeb080b0eda
Create Date: 2021-11-30 13:49:31.434111

"""

import healpix_alchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "8c48c49f057f"
down_revision = "1aeb080b0eda"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "instrumentfields",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified", sa.DateTime(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=False),
        sa.Column("contour", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_instrumentfields_created_at"),
        "instrumentfields",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_instrumentfields_field_id"),
        "instrumentfields",
        ["field_id"],
        unique=False,
    )
    op.create_table(
        "instrumentfieldtiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified", sa.DateTime(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("instrument_field_id", sa.Integer(), nullable=False),
        sa.Column("healpix", healpix_alchemy.types.Tile(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_field_id"], ["instrumentfields.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", "healpix"),
    )
    op.create_index(
        op.f("ix_instrumentfieldtiles_created_at"),
        "instrumentfieldtiles",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_instrumentfieldtiles_healpix"),
        "instrumentfieldtiles",
        ["healpix"],
        unique=False,
        postgresql_using="spgist",
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        op.f("ix_instrumentfieldtiles_healpix"),
        table_name="instrumentfieldtiles",
        postgresql_using="spgist",
    )
    op.drop_index(
        op.f("ix_instrumentfieldtiles_created_at"), table_name="instrumentfieldtiles"
    )
    op.drop_table("instrumentfieldtiles")
    op.drop_index(op.f("ix_instrumentfields_field_id"), table_name="instrumentfields")
    op.drop_index(op.f("ix_instrumentfields_created_at"), table_name="instrumentfields")
    op.drop_table("instrumentfields")
    # ### end Alembic commands ###
