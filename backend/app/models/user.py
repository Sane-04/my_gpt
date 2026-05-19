from __future__ import annotations

# 模块说明：后端 ORM 模型模块，描述数据库表结构、索引和表关系。

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """类作用：映射 users 表。"""

    __tablename__ = "users"
    __table_args__ = (
        # 用户邮箱用于登录和唯一身份识别，必须全局唯一。
        Index("ix_users_email", "email", unique=True),
        # 创建时间索引用于后台管理或审计按时间扫描用户。
        Index("ix_users_created_at", "created_at"),
        {"comment": "用户表，保存登录身份和用户级数据隔离根节点。"},
    )

    # 主键：所有核心表统一使用数据库侧生成的 UUID。
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="用户 UUID 主键。",
    )
    # 基础资料：邮箱唯一，展示名允许为空，password_hash 只保存哈希后的密码。
    email: Mapped[str] = mapped_column(String(320), nullable=False, comment="用户邮箱，登录身份标识。")
    display_name: Mapped[str | None] = mapped_column(String(120), comment="用户展示名称。")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="用户密码哈希，禁止保存明文密码。")
    # 账号状态：is_active 用于软禁用账号，禁用后即使 token 有效也不能继续访问。
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="用户是否启用。",
    )
    # 审计时间：created_at 记录创建时间，updated_at 记录最近更新。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="用户创建时间。",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="用户最近更新时间。",
    )

    # 关系：所有用户私有数据都从 user_id 关联，保证后续查询可按用户隔离。
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")
    messages: Mapped[list["Message"]] = relationship(back_populates="user")
    long_term_memories: Mapped[list["LongTermMemory"]] = relationship(back_populates="user")
    memory_events: Mapped[list["MemoryEvent"]] = relationship(back_populates="user")
    tool_call_events: Mapped[list["ToolCallEvent"]] = relationship(back_populates="user")
    prompt_snapshots: Mapped[list["PromptSnapshot"]] = relationship(back_populates="user")
