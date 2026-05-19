from __future__ import annotations

# 模块说明：后端 ORM 模型模块，描述数据库表结构、索引和表关系。

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PromptSnapshot(Base):
    """类作用：映射 prompt_snapshots 表，仅用于开发调试。"""

    __tablename__ = "prompt_snapshots"
    __table_args__ = (
        # 用户维度索引：用于调试某个用户的 prompt 组装结果。
        Index("ix_prompt_snapshots_user_created_at", "user_id", "created_at"),
        # 会话维度索引：用于按时间查看某个会话内的 prompt 快照。
        Index("ix_prompt_snapshots_conversation_created_at", "conversation_id", "created_at"),
        # 请求消息索引：定位某条用户消息对应的 prompt 快照。
        Index("ix_prompt_snapshots_request_message_id", "request_message_id"),
        {"comment": "Prompt 快照表，仅用于开发调试，生产默认关闭写入。"},
    )

    # 主键：prompt 快照 UUID。
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Prompt 快照 UUID 主键。",
    )
    # 归属字段：快照必须绑定用户和会话，便于隔离调试数据。
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户 UUID。",
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属会话 UUID。",
    )
    # 请求消息：记录是哪条消息触发了本次模型请求。
    request_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        comment="触发本次请求的消息 UUID。",
    )
    # 调试载荷：prompt 保存最终文本，messages 保存结构化消息数组。
    model: Mapped[str] = mapped_column(String(120), nullable=False, comment="请求使用的模型名称。")
    prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="最终发送给模型的 prompt 文本。")
    messages: Mapped[list | None] = mapped_column(JSONB, comment="最终发送给模型的结构化消息。")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, comment="Prompt 快照扩展元数据。")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="快照创建时间。",
    )

    # 关系：快照连接用户、会话和触发请求的消息。
    user: Mapped["User"] = relationship(back_populates="prompt_snapshots")
    conversation: Mapped["Conversation"] = relationship(back_populates="prompt_snapshots")
    request_message: Mapped["Message | None"] = relationship(back_populates="prompt_snapshots")
