from __future__ import annotations

# 模块说明：后端 ORM 模型模块，描述数据库表结构、索引和表关系。

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EmbeddingStatus, MessageRole


class Message(Base):
    """类作用：映射 messages 表。"""

    __tablename__ = "messages"
    __table_args__ = (
        # 会话时间线索引：读取单个会话消息历史时使用。
        Index("ix_messages_conversation_created_at", "conversation_id", "created_at"),
        # 用户时间线索引：按用户做审计或跨会话检索时使用。
        Index("ix_messages_user_created_at", "user_id", "created_at"),
        # 后台 embedding 任务按状态扫描待处理或失败消息。
        Index("ix_messages_embedding_status", "embedding_status"),
        # 全文检索索引：fts_vector 由 PostgreSQL FTS 触发器维护。
        Index("ix_messages_fts_vector", "fts_vector", postgresql_using="gin"),
        # 向量检索索引：使用 pgvector HNSW + cosine 距离做语义召回。
        Index(
            "ix_messages_embedding_vector",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"comment": "消息表，保存会话消息、PostgreSQL FTS 内容和 pgvector embedding。"},
    )

    # 主键：消息 UUID。
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="消息 UUID 主键。",
    )
    # 归属字段：同时保存 conversation_id 和 user_id，便于用户隔离和跨会话查询。
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属会话 UUID。",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户 UUID。",
    )
    # 消息角色：区分系统、用户、助手和工具消息。
    role: Mapped[MessageRole] = mapped_column(
        Enum(
            MessageRole,
            name="message_role",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        comment="消息角色。",
    )
    # 原始文本：FTS 触发器会基于该字段生成 fts_vector。
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息正文。")
    # 向量字段：维度与当前 embedding 模型约定为 1536。
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), comment="消息 embedding 向量。")
    embedding_status: Mapped[EmbeddingStatus] = mapped_column(
        Enum(
            EmbeddingStatus,
            name="embedding_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        server_default=text("'pending'"),
        comment="消息 embedding 处理状态。",
    )
    embedding_error: Mapped[str | None] = mapped_column(Text, comment="embedding 失败时的错误信息。")
    fts_vector: Mapped[str | None] = mapped_column(TSVECTOR, comment="PostgreSQL FTS 检索向量。")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, comment="消息扩展元数据。")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="消息创建时间。",
    )

    # 关系：消息可被记忆事件、工具调用和 prompt 快照引用。
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    user: Mapped["User"] = relationship(back_populates="messages")
    memory_events: Mapped[list["MemoryEvent"]] = relationship(back_populates="message")
    tool_call_events: Mapped[list["ToolCallEvent"]] = relationship(back_populates="message")
    prompt_snapshots: Mapped[list["PromptSnapshot"]] = relationship(back_populates="request_message")
