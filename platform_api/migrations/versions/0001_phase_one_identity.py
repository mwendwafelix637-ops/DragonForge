"""Phase 1 identity, access-control, sessions and audit schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_phase_one_identity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("account_type", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("totp_secret_encrypted", sa.Text()),
        sa.Column("totp_setup_expires_at", sa.DateTime(timezone=True)),
        sa.Column("totp_enabled_at", sa.DateTime(timezone=True)),
        sa.Column("recovery_code_hashes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("uq_single_owner", "users", ["account_type"], unique=True,
                    postgresql_where=sa.text("account_type = 'owner'"),
                    sqlite_where=sa.text("account_type = 'owner'"))

    op.create_table("roles", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(length=40), nullable=False, unique=True))
    op.create_table("permissions", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(length=80), nullable=False, unique=True),
                    sa.Column("description", sa.String(length=240), nullable=False))
    op.create_table("user_roles",
                    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("role_permissions",
                    sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True))

    op.create_table("devices",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("label", sa.String(length=120), nullable=False),
                    sa.Column("user_agent", sa.String(length=512)),
                    sa.Column("ip_address", sa.String(length=64)),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_devices_user_id", "devices", ["user_id"])

    op.create_table("sessions",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="SET NULL")),
                    sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
                    sa.Column("user_agent", sa.String(length=512)),
                    sa.Column("ip_address", sa.String(length=64)),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table("audit_logs",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
                    sa.Column("event_type", sa.String(length=80), nullable=False),
                    sa.Column("target_type", sa.String(length=80)),
                    sa.Column("target_id", sa.String(length=120)),
                    sa.Column("details", sa.JSON(), nullable=False),
                    sa.Column("ip_address", sa.String(length=64)),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table("login_attempts",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("subject", sa.String(length=384), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("succeeded", sa.Boolean(), nullable=False))
    op.create_index("ix_login_attempts_subject_created", "login_attempts", ["subject", "created_at"])

    op.create_table("platform_configuration",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("settings", sa.JSON(), nullable=False),
                    sa.Column("version", sa.Integer(), nullable=False),
                    sa.Column("published_at", sa.DateTime(timezone=True)),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("admin_accounts",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
                    sa.Column("created_by_owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("admin_accounts")
    op.drop_table("platform_configuration")
    op.drop_index("ix_login_attempts_subject_created", table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_token_hash", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_devices_user_id", table_name="devices")
    op.drop_table("devices")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_index("uq_single_owner", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")