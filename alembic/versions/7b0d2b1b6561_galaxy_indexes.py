"""galaxy_indexes

Revision ID: 7b0d2b1b6561
Revises: 77c4af61eea6
Create Date: 2024-05-15 11:50:48.222457

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '7b0d2b1b6561'
down_revision = 'aa6432209e3e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_galaxys_magb'), 'galaxys', ['magb'], unique=False)
    op.create_index(op.f('ix_galaxys_magk'), 'galaxys', ['magk'], unique=False)
    op.create_index(op.f('ix_galaxys_mstar'), 'galaxys', ['mstar'], unique=False)
    op.create_index(op.f('ix_galaxys_sfr_fuv'), 'galaxys', ['sfr_fuv'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_galaxys_sfr_fuv'), table_name='galaxys')
    op.drop_index(op.f('ix_galaxys_mstar'), table_name='galaxys')
    op.drop_index(op.f('ix_galaxys_magk'), table_name='galaxys')
    op.drop_index(op.f('ix_galaxys_magb'), table_name='galaxys')
    # ### end Alembic commands ###