from __future__ import annotations

# 模块说明：后端 ORM 模型模块，描述数据库表结构、索引和表关系。

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LongTermMemory(Base):
    """类作用：映射 long_term_memories 表。"""

    __tablename__ = "long_term_memories"
    __table_args__ = (
        # 用户记忆列表索引：按用户和更新时间读取长期记忆。
        Index("ix_long_term_memories_user_updated_at", "user_id", "updated_at"),
        # 溯源索引：可从消息追踪提炼出的长期记忆。
        Index("ix_long_term_memories_source_message_id", "source_message_id"),
        # 全文检索索引：用于关键词召回长期记忆。
        Index("ix_long_term_memories_fts_vector", "fts_vector", postgresql_using="gin"),
        # 向量索引：使用 pgvector HNSW，便于后续语义召回扩展。
        Index(
            "ix_long_term_memories_embedding_vector",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"comment": "长期记忆表，保存用户级稳定记忆和检索字段。"},
    )

    # 主键：长期记忆 UUID。
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="长期记忆 UUID 主键。",
    )
    # 用户隔离字段：长期记忆必须绑定用户。
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户 UUID。",
    )
    # 来源字段：记录该记忆最初来自哪条消息，源消息删除后置空。
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        comment="来源消息 UUID。",
    )
    # 记忆内容和检索字段：content 为可注入模型上下文的正文。
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="长期记忆正文。")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), comment="长期记忆 embedding 向量。")
    fts_vector: Mapped[str | None] = mapped_column(TSVECTOR, comment="PostgreSQL FTS 检索向量。")
    importance: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"), comment="记忆重要性评分。")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, comment="长期记忆扩展元数据。")
    # 审计时间：用于记忆排序和增量同步。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="长期记忆创建时间。",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="长期记忆最近更新时间。",
    )

    # 关系：长期记忆归属用户，并可关联多条变更事件。
    user: Mapped["User"] = relationship(back_populates="long_term_memories")
    source_message: Mapped["Message | None"] = relationship()
    memory_events: Mapped[list["MemoryEvent"]] = relationship(back_populates="memory")
