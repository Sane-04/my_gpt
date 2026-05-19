# 模块说明：Alembic 数据库迁移脚本，记录表结构升级和回滚步骤。
"""task009 initial schema

Revision ID: 20260516_0001
Revises:
Create Date: 2026-05-16 00:00:00
"""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260516_0001"
down_revision = None
branch_labels = None
depends_on = None


message_role = postgresql.ENUM(
    "system",
    "user",
    "assistant",
    "tool",
    name="message_role",
    create_type=False,
)
embedding_status = postgresql.ENUM(
    "pending",
    "skipped",
    "processing",
    "completed",
    "failed",
    name="embedding_status",
    create_type=False,
)
memory_event_type = postgresql.ENUM(
    "created",
    "updated",
    "deleted",
    "promoted",
    name="memory_event_type",
    create_type=False,
)
tool_call_status = postgresql.ENUM(
    "started",
    "succeeded",
    "failed",
    name="tool_call_status",
    create_type=False,
)


def upgrade() -> None:
    """函数作用：创建 TASK009 初始数据库结构。
    输入参数：无。
    输出参数：无返回值。
    """
    bind = op.get_bind()

    # PostgreSQL 扩展：pgcrypto 提供 gen_random_uuid，vector 提供 pgvector 向量检索。
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 枚举类型：用数据库枚举约束消息角色、embedding 状态、记忆事件和工具调用状态。
    message_role.create(bind, checkfirst=True)
    embedding_status.create(bind, checkfirst=True)
    memory_event_type.create(bind, checkfirst=True)
    tool_call_status.create(bind, checkfirst=True)

    # users 表：用户身份根表，其他用户私有数据都通过 user_id 关联到这里。
    op.create_table(
        "users",
        # UUID 主键由数据库生成，避免应用侧生成策略不一致。
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # 邮箱用于后续登录鉴权，唯一索引在表创建后单独创建。
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        comment="用户表，保存登录身份和用户级数据隔离根节点。",
    )
    # 用户表索引：邮箱唯一，创建时间便于审计或后台扫描。
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_created_at", "users", ["created_at"])

    # conversations 表：保存用户的一组连续对话上下文。
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_conversations_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
        comment="会话表，保存用户的一组连续对话上下文。",
    )
    # 会话索引：支持按用户读取会话列表，并按更新时间排序。
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_user_updated_at", "conversations", ["user_id", "updated_at"])

    # messages 表：保存原始消息、向量化状态、PostgreSQL FTS 向量和 pgvector embedding。
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_status", embedding_status, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("embedding_error", sa.Text(), nullable=True),
        sa.Column("fts_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_messages_conversation_id_conversations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_messages_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        comment="消息表，保存会话消息、PostgreSQL FTS 内容和 pgvector embedding。",
    )
    # 消息索引：覆盖会话时间线、用户时间线、embedding 后台任务、全文检索和 HNSW 向量检索。
    op.create_index("ix_messages_conversation_created_at", "messages", ["conversation_id", "created_at"])
    op.create_index("ix_messages_user_created_at", "messages", ["user_id", "created_at"])
    op.create_index("ix_messages_embedding_status", "messages", ["embedding_status"])
    op.create_index("ix_messages_fts_vector", "messages", ["fts_vector"], postgresql_using="gin")
    op.create_index(
        "ix_messages_embedding_vector",
        "messages",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # long_term_memories 表：保存用户级长期记忆，支持中文全文检索和后续语义检索扩展。
    op.create_table(
        "long_term_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("fts_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("importance", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], name=op.f("fk_long_term_memories_source_message_id_messages"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_long_term_memories_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_long_term_memories")),
        comment="长期记忆表，保存用户级稳定记忆和检索字段。",
    )
    # 长期记忆索引：覆盖用户记忆列表、来源消息、PostgreSQL FTS 和 HNSW 向量召回。
    op.create_index("ix_long_term_memories_user_updated_at", "long_term_memories", ["user_id", "updated_at"])
    op.create_index("ix_long_term_memories_source_message_id", "long_term_memories", ["source_message_id"])
    op.create_index("ix_long_term_memories_fts_vector", "long_term_memories", ["fts_vector"], postgresql_using="gin")
    op.create_index(
        "ix_long_term_memories_embedding_vector",
        "long_term_memories",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # memory_events 表：记录长期记忆的创建、更新、删除和提升事件。
    op.create_table(
        "memory_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", memory_event_type, nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["memory_id"], ["long_term_memories.id"], name=op.f("fk_memory_events_memory_id_long_term_memories"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], name=op.f("fk_memory_events_message_id_messages"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_memory_events_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_events")),
        comment="长期记忆事件表，记录记忆创建、更新、删除和提升过程。",
    )
    # 记忆事件索引：支持按用户、记忆和来源消息追踪事件。
    op.create_index("ix_memory_events_user_created_at", "memory_events", ["user_id", "created_at"])
    op.create_index("ix_memory_events_memory_id", "memory_events", ["memory_id"])
    op.create_index("ix_memory_events_message_id", "memory_events", ["message_id"])

    # tool_call_events 表：审计工具调用参数、结果、状态、错误和耗时。
    op.create_table(
        "tool_call_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", tool_call_status, server_default=sa.text("'started'"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_tool_call_events_conversation_id_conversations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], name=op.f("fk_tool_call_events_message_id_messages"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_tool_call_events_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_call_events")),
        comment="工具调用事件表，保存工具调用参数、结果、状态和错误。",
    )
    # 工具调用索引：支持按用户、会话、消息和工具名称排查调用历史。
    op.create_index("ix_tool_call_events_user_started_at", "tool_call_events", ["user_id", "started_at"])
    op.create_index("ix_tool_call_events_conversation_started_at", "tool_call_events", ["conversation_id", "started_at"])
    op.create_index("ix_tool_call_events_message_id", "tool_call_events", ["message_id"])
    op.create_index("ix_tool_call_events_tool_name", "tool_call_events", ["tool_name"])

    # prompt_snapshots 表：仅用于开发调试，生产默认关闭写入。
    op.create_table(
        "prompt_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_prompt_snapshots_conversation_id_conversations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["request_message_id"], ["messages.id"], name=op.f("fk_prompt_snapshots_request_message_id_messages"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_prompt_snapshots_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_snapshots")),
        comment="Prompt 快照表，仅用于开发调试，生产默认关闭写入。",
    )
    # Prompt 快照索引：支持按用户、会话和请求消息定位调试数据。
    op.create_index("ix_prompt_snapshots_user_created_at", "prompt_snapshots", ["user_id", "created_at"])
    op.create_index("ix_prompt_snapshots_conversation_created_at", "prompt_snapshots", ["conversation_id", "created_at"])
    op.create_index("ix_prompt_snapshots_request_message_id", "prompt_snapshots", ["request_message_id"])

    # messages FTS 触发器：写入或更新 content 时，用 PostgreSQL 内置 simple 配置生成 tsvector。
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_messages_fts_vector()
        RETURNS trigger AS $$
        BEGIN
            NEW.fts_vector := to_tsvector('simple', coalesce(NEW.content, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    # long_term_memories FTS 触发器：长期记忆内容变化时同步更新 PostgreSQL FTS tsvector。
    op.execute(
        """
        CREATE TRIGGER trg_messages_fts_vector
        BEFORE INSERT OR UPDATE OF content ON messages
        FOR EACH ROW EXECUTE FUNCTION update_messages_fts_vector()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_long_term_memories_fts_vector()
        RETURNS trigger AS $$
        BEGIN
            NEW.fts_vector := to_tsvector('simple', coalesce(NEW.content, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_long_term_memories_fts_vector
        BEFORE INSERT OR UPDATE OF content ON long_term_memories
        FOR EACH ROW EXECUTE FUNCTION update_long_term_memories_fts_vector()
        """
    )


def downgrade() -> None:
    """函数作用：回滚 TASK009 初始数据库结构。
    输入参数：无。
    输出参数：无返回值。
    """
    # 降级顺序：先删除依赖表的触发器和函数，再按外键依赖反向删除表和枚举类型。
    op.execute("DROP TRIGGER IF EXISTS trg_long_term_memories_fts_vector ON long_term_memories")
    op.execute("DROP FUNCTION IF EXISTS update_long_term_memories_fts_vector()")
    op.execute("DROP TRIGGER IF EXISTS trg_messages_fts_vector ON messages")
    op.execute("DROP FUNCTION IF EXISTS update_messages_fts_vector()")

    op.drop_index("ix_prompt_snapshots_request_message_id", table_name="prompt_snapshots")
    op.drop_index("ix_prompt_snapshots_conversation_created_at", table_name="prompt_snapshots")
    op.drop_index("ix_prompt_snapshots_user_created_at", table_name="prompt_snapshots")
    op.drop_table("prompt_snapshots")

    op.drop_index("ix_tool_call_events_tool_name", table_name="tool_call_events")
    op.drop_index("ix_tool_call_events_message_id", table_name="tool_call_events")
    op.drop_index("ix_tool_call_events_conversation_started_at", table_name="tool_call_events")
    op.drop_index("ix_tool_call_events_user_started_at", table_name="tool_call_events")
    op.drop_table("tool_call_events")

    op.drop_index("ix_memory_events_message_id", table_name="memory_events")
    op.drop_index("ix_memory_events_memory_id", table_name="memory_events")
    op.drop_index("ix_memory_events_user_created_at", table_name="memory_events")
    op.drop_table("memory_events")

    op.drop_index("ix_long_term_memories_embedding_vector", table_name="long_term_memories")
    op.drop_index("ix_long_term_memories_fts_vector", table_name="long_term_memories")
    op.drop_index("ix_long_term_memories_source_message_id", table_name="long_term_memories")
    op.drop_index("ix_long_term_memories_user_updated_at", table_name="long_term_memories")
    op.drop_table("long_term_memories")

    op.drop_index("ix_messages_embedding_vector", table_name="messages")
    op.drop_index("ix_messages_fts_vector", table_name="messages")
    op.drop_index("ix_messages_embedding_status", table_name="messages")
    op.drop_index("ix_messages_user_created_at", table_name="messages")
    op.drop_index("ix_messages_conversation_created_at", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_conversations_user_updated_at", table_name="conversations")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")

    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    tool_call_status.drop(op.get_bind(), checkfirst=True)
    memory_event_type.drop(op.get_bind(), checkfirst=True)
    embedding_status.drop(op.get_bind(), checkfirst=True)
    message_role.drop(op.get_bind(), checkfirst=True)
