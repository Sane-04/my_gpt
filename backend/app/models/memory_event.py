from __future__ import annotations

# 模块说明：后端 ORM 模型模块，描述数据库表结构、索引和表关系。

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MemoryEventType


class MemoryEvent(Base):
    """类作用：映射 memory_events 表。"""

    __tablename__ = "memory_events"
    __table_args__ = (
        # 用户事件流索引：按用户查看记忆变化历史。
        Index("ix_memory_events_user_created_at", "user_id", "created_at"),
        # 记忆维度索引：查看某条长期记忆的所有事件。
        Index("ix_memory_events_memory_id", "memory_id"),
        # 消息维度索引：追踪某条消息触发的记忆事件。
        Index("ix_memory_events_message_id", "message_id"),
        {"comment": "长期记忆事件表，记录记忆创建、更新、删除和提升过程。"},
    )

    # 主键：事件 UUID。
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="记忆事件 UUID 主键。",
    )
    # 用户隔离字段：所有事件必须归属用户。
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户 UUID。",
    )
    # 关联记忆：记忆删除后事件保留，memory_id 置空。
    memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("long_term_memories.id", ondelete="SET NULL"),
        comment="关联长期记忆 UUID。",
    )
    # 关联消息：用于追踪由哪条消息触发。
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        comment="关联消息 UUID。",
    )
    # 事件类型：限定为创建、更新、删除、提升。
    event_type: Mapped[MemoryEventType] = mapped_column(
        Enum(
            MemoryEventType,
            name="memory_event_type",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        comment="记忆事件类型。",
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, comment="记忆事件附加数据。")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="事件创建时间。",
    )

    # 关系：事件同时连接用户、记忆和来源消息。
    user: Mapped["User"] = relationship(back_populates="memory_events")
    memory: Mapped["LongTermMemory | None"] = relationship(back_populates="memory_events")
    message: Mapped["Message | None"] = relationship(back_populates="memory_events")
