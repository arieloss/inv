"""add config_version updated_by

Revision ID: 5c76e16cd951
Revises: e8c980531c4f
Create Date: 2026-05-21 16:18:00.302319
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c76e16cd951'
down_revision: Union[str, Sequence[str], None] = 'e8c980531c4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Ajouter config_version
    op.add_column(
        'inverter_config',
        sa.Column(
            'config_version',
            sa.Integer(),
            nullable=False,
            server_default='1'
        )
    )

    # Ajouter updated_by
    op.add_column(
        'inverter_config',
        sa.Column(
            'updated_by',
            sa.String(length=10),
            nullable=True
        )
    )

    # Retirer le default après création
    op.alter_column(
        'inverter_config',
        'config_version',
        server_default=None
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column('inverter_config', 'updated_by')
    op.drop_column('inverter_config', 'config_version')