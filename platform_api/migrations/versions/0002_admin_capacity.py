"""Reserve five distinct administrator slots."""
from alembic import op
import sqlalchemy as sa

revision = "0002_admin_capacity"
down_revision = "0001_phase_one_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admin_accounts", sa.Column("slot", sa.Integer(), nullable=True))
    op.execute("UPDATE admin_accounts SET slot = id WHERE slot IS NULL")
    op.alter_column("admin_accounts", "slot", nullable=False)
    op.create_unique_constraint("uq_admin_accounts_slot", "admin_accounts", ["slot"])
    op.create_check_constraint("ck_admin_slot_range", "admin_accounts", "slot >= 1 AND slot <= 5")


def downgrade():
    op.drop_constraint("ck_admin_slot_range", "admin_accounts", type_="check")
    op.drop_constraint("uq_admin_accounts_slot", "admin_accounts", type_="unique")
    op.drop_column("admin_accounts", "slot")