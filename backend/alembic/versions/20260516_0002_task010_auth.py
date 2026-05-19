# 模块说明：Alembic 数据库迁移脚本，记录表结构升级和回滚步骤。
"""task010 auth

Revision ID: 20260516_0002
Revises: 20260516_0001
Create Date: 2026-05-16 17:11:22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260516_0002"
down_revision = "20260516_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """函数作用：为用户表增加登录密码哈希字段。
    输入参数：无。
    输出参数：无返回值。
    """
    # 先设置不可登录的占位默认值，兼容开发库里已存在的用户行。
    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=255),
            server_default="!",
            nullable=False,
            comment="用户密码哈希，禁止保存明文密码。",
        ),
    )
    # 新注册用户必须由应用写入真实 bcrypt hash，因此迁移完成后移除默认值。
    op.alter_column("users", "password_hash", server_default=None)


def downgrade() -> None:
    """函数作用：回滚用户表密码哈希字段。
    输入参数：无。
    输出参数：无返回值。
    """
    op.drop_column("users", "password_hash")
