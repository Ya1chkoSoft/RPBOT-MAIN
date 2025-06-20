"""START

Revision ID: 5c3a7b12dee9
Revises: 
Create Date: 2025-06-02 05:37:06.538102

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c3a7b12dee9'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('users',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('userfullname', sa.String(), nullable=True),
    sa.Column('username', sa.String(), nullable=True),
    sa.Column('points', sa.Integer(), nullable=True),
    sa.Column('adminlevel', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('admins',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('userfullname', sa.String(), nullable=True),
    sa.Column('username', sa.String(), nullable=True),
    sa.Column('adminlevel', sa.Integer(), nullable=False),
    sa.CheckConstraint('adminlevel BETWEEN 0 AND 4', name='check_admin_level'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('admin_id', sa.Integer(), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.Column('points', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['target_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('history')
    op.drop_table('admins')
    op.drop_table('users')
    # ### end Alembic commands ###
