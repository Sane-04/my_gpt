from __future__ import annotations

# 模块说明：后端 ORM 模型模块，描述数据库表结构、索引和表关系。

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Conversation(Base):
    """类作用：映射 conversations 表。"""

    __tablename__ = "conversations"
    __table_args__ = (
        # 用户维度索引：后续会话列表按 user_id 查询。
        Index("ix_conversations_user_id", "user_id"),
        # 会话列表常按最近更新时间倒序展示。
        Index("ix_conversations_user_updated_at", "user_id", "updated_at"),
        {"comment": "会话表，保存用户的一组连续对话上下文。"},
    )

    # 主键：会话 UUID。
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="会话 UUID 主键。",
    )
    # 用户隔离字段：会话必须归属某个用户。
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户 UUID。",
    )
    # 展示字段：标题可由用户输入或模型自动生成。
    title: Mapped[str | None] = mapped_column(String(200), comment="会话标题。")
    # 时间字段：archived_at 为空表示当前仍在普通列表中。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="会话创建时间。",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="会话最近更新时间。",
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="会话归档时间。")

    # 关系：会话向下关联消息、工具调用和调试快照。
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")
    tool_call_events: Mapped[list["ToolCallEvent"]] = relationship(back_populates="conversation")
    prompt_snapshots: Mapped[list["PromptSnapshot"]] = relationship(back_populates="conversation")
