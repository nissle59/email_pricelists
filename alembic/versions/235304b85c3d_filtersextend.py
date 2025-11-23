"""FiltersExtend

Revision ID: 235304b85c3d
Revises: bd3cfc1856f1
Create Date: 2025-11-03 14:28:48.257503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '235304b85c3d'
down_revision: Union[str, None] = 'bd3cfc1856f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use batch mode for SQLite
    with op.batch_alter_table('emailfilters') as batch_op:
        batch_op.add_column(sa.Column('vendor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_emailfilters_vendor_id',
            'vendors',
            ['vendor_id'],
            ['id']
        )


def downgrade() -> None:
    # Use batch mode for SQLite
    with op.batch_alter_table('emailfilters') as batch_op:
        batch_op.drop_constraint('fk_emailfilters_vendor_id', type_='foreignkey')
        batch_op.drop_column('vendor_id')