"""workspaces and auth (Phase 5A)

Every existing user gets a personal workspace (owner) and their ideas move into it;
`ideas.owner_id` becomes `created_by_id`. Existing suppressions are attributed to the workspace
of the message they came from, or to the only workspace when there's just one.

Revision ID: 13f5d5a2b7f9
Revises: c0a552d274cc
Create Date: 2026-11-04 18:47:40.975409

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "13f5d5a2b7f9"
down_revision: str | Sequence[str] | None = "c0a552d274cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = [
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
]


def _ts() -> list[sa.Column]:
    return [c.copy() for c in _TS]


ROLE = sa.Enum("owner", "member", name="role", native_enum=False, length=16)


def upgrade() -> None:
    # users
    op.add_column("users", sa.Column("password_hash", sa.String(length=200), nullable=True))
    op.add_column(
        "users", sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False)
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET email = lower(email)")

    # workspaces, memberships, invitations
    op.create_table(
        "workspaces",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_workspaces_created_by_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
    )
    op.create_table(
        "memberships",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", ROLE, nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_memberships_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_memberships_workspace_id_workspaces"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint("workspace_id", "user_id", name=op.f("uq_memberships_workspace_id")),
    )
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"], unique=False)
    op.create_index(op.f("ix_memberships_workspace_id"), "memberships", ["workspace_id"], unique=False)
    op.create_table(
        "invitations",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", ROLE, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["invited_by_id"], ["users.id"], name=op.f("fk_invitations_invited_by_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_invitations_workspace_id_workspaces"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invitations_token_hash")),
    )
    op.create_index(op.f("ix_invitations_workspace_id"), "invitations", ["workspace_id"], unique=False)

    # sessions, api tokens
    op.create_table(
        "sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("active_workspace_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(length=300), nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["active_workspace_id"], ["workspaces.id"], name=op.f("fk_sessions_active_workspace_id_workspaces"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "api_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_api_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_api_tokens_workspace_id_workspaces"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_api_tokens_token_hash")),
    )
    op.create_index(op.f("ix_api_tokens_user_id"), "api_tokens", ["user_id"], unique=False)

    # one personal workspace per existing user, owned by them
    op.execute(
        """
        INSERT INTO workspaces (id, name, created_by_id)
        SELECT gen_random_uuid(), u.name || '''s workspace', u.id FROM users u
        """
    )
    op.execute(
        """
        INSERT INTO memberships (id, workspace_id, user_id, role)
        SELECT gen_random_uuid(), w.id, w.created_by_id, 'owner' FROM workspaces w
        """
    )

    # ideas: owner -> workspace + created_by
    op.add_column("ideas", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    op.alter_column("ideas", "owner_id", new_column_name="created_by_id", nullable=True)
    op.execute(
        "UPDATE ideas i SET workspace_id = w.id FROM workspaces w WHERE w.created_by_id = i.created_by_id"
    )
    op.alter_column("ideas", "workspace_id", nullable=False)
    op.drop_index(op.f("ix_ideas_owner_id"), table_name="ideas")
    op.drop_constraint(op.f("fk_ideas_owner_id_users"), "ideas", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_ideas_created_by_id_users"), "ideas", "users", ["created_by_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        op.f("fk_ideas_workspace_id_workspaces"), "ideas", "workspaces", ["workspace_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(op.f("ix_ideas_workspace_id"), "ideas", ["workspace_id"], unique=False)

    # suppressions: global block, per-workspace rows
    op.add_column("suppressions", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE suppressions s SET workspace_id = i.workspace_id
        FROM messages m JOIN outreach_campaigns c ON c.id = m.campaign_id JOIN ideas i ON i.id = c.idea_id
        WHERE s.message_id = m.id
        """
    )
    op.execute(
        """
        UPDATE suppressions SET workspace_id = (SELECT id FROM workspaces LIMIT 1)
        WHERE workspace_id IS NULL AND (SELECT count(*) FROM workspaces) = 1
        """
    )
    op.drop_constraint(op.f("uq_suppressions_email"), "suppressions", type_="unique")
    op.create_unique_constraint(op.f("uq_suppressions_email"), "suppressions", ["email", "workspace_id"])
    op.create_index(op.f("ix_suppressions_email"), "suppressions", ["email"], unique=False)
    op.create_index(op.f("ix_suppressions_workspace_id"), "suppressions", ["workspace_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_suppressions_workspace_id_workspaces"), "suppressions", "workspaces", ["workspace_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    # Suppressions: keep one row per address again.
    op.drop_constraint(op.f("fk_suppressions_workspace_id_workspaces"), "suppressions", type_="foreignkey")
    op.drop_index(op.f("ix_suppressions_workspace_id"), table_name="suppressions")
    op.drop_index(op.f("ix_suppressions_email"), table_name="suppressions")
    op.drop_constraint(op.f("uq_suppressions_email"), "suppressions", type_="unique")
    op.execute(
        "DELETE FROM suppressions a USING suppressions b WHERE a.email = b.email AND a.created_at > b.created_at"
    )
    op.create_unique_constraint(op.f("uq_suppressions_email"), "suppressions", ["email"])
    op.drop_column("suppressions", "workspace_id")

    # Ideas go back to the workspace's creator (ideas without one can't be represented).
    op.drop_index(op.f("ix_ideas_workspace_id"), table_name="ideas")
    op.drop_constraint(op.f("fk_ideas_workspace_id_workspaces"), "ideas", type_="foreignkey")
    op.drop_constraint(op.f("fk_ideas_created_by_id_users"), "ideas", type_="foreignkey")
    op.execute(
        "UPDATE ideas i SET created_by_id = w.created_by_id FROM workspaces w "
        "WHERE w.id = i.workspace_id AND i.created_by_id IS NULL"
    )
    op.execute("DELETE FROM ideas WHERE created_by_id IS NULL")
    op.alter_column("ideas", "created_by_id", new_column_name="owner_id", nullable=False)
    op.drop_column("ideas", "workspace_id")
    op.create_foreign_key(op.f("fk_ideas_owner_id_users"), "ideas", "users", ["owner_id"], ["id"], ondelete="CASCADE")
    op.create_index(op.f("ix_ideas_owner_id"), "ideas", ["owner_id"], unique=False)

    op.drop_index(op.f("ix_api_tokens_user_id"), table_name="api_tokens")
    op.drop_table("api_tokens")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_invitations_workspace_id"), table_name="invitations")
    op.drop_table("invitations")
    op.drop_index(op.f("ix_memberships_workspace_id"), table_name="memberships")
    op.drop_index(op.f("ix_memberships_user_id"), table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("workspaces")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
