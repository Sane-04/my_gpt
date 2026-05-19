from __future__ import annotations

# 模块说明：后端 ORM 模型模块，描述数据库表结构、索引和表关系。

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ToolCallStatus


class ToolCallEvent(Base):
    """类作用：映射 tool_call_events 表。"""

    __tablename__ = "tool_call_events"
    __table_args__ = (
        # 用户维度索引：用于审计某个用户的工具调用历史。
        Index("ix_tool_call_events_user_started_at", "user_id", "started_at"),
        # 会话维度索引：用于回放某个会话内的工具调用顺序。
        Index("ix_tool_call_events_conversation_started_at", "conversation_id", "started_at"),
        # 消息维度索引：定位某条助手消息触发的工具调用。
        Index("ix_tool_call_events_message_id", "message_id"),
        # 工具名称索引：用于统计和排查单个工具。
        Index("ix_tool_call_events_tool_name", "tool_name"),
        {"comment": "工具调用事件表，保存工具调用参数、结果、状态和错误。"},
    )

    # 主键：工具调用事件 UUID。
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="工具调用事件 UUID 主键。",
    )
    # 归属字段：工具调用同时绑定用户和会话。
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
    # 关联消息：工具调用通常由某条助手消息触发，消息删除后置空。
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        comment="关联消息 UUID。",
    )
    # 工具载荷：arguments 和 result 使用 JSONB 保存结构化参数和结果。
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False, comment="工具名称。")
    arguments: Mapped[dict | None] = mapped_column(JSONB, comment="工具调用参数。")
    result: Mapped[dict | None] = mapped_column(JSONB, comment="工具调用结果。")
    status: Mapped[ToolCallStatus] = mapped_column(
        Enum(
            ToolCallStatus,
            name="tool_call_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        server_default=text("'started'"),
        comment="工具调用状态。",
    )
    error: Mapped[str | None] = mapped_column(Text, comment="工具调用失败时的错误信息。")
    # 时间字段：started_at 和 finished_at 可计算工具耗时。
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="工具调用开始时间。",
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="工具调用结束时间。")

    # 关系：工具事件连接用户、会话和触发消息。
    user: Mapped["User"] = relationship(back_populates="tool_call_events")
    conversation: Mapped["Conversation"] = relationship(back_populates="tool_call_events")
    message: Mapped["Message | None"] = relationship(back_populates="tool_call_events")
