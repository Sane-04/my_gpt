# 模块说明：Alembic 迁移环境模块，负责加载模型元数据并执行迁移。
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}


revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """函数作用：执行数据库升级迁移。
    输入参数：无。
    输出参数：无返回值。
    """
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """函数作用：执行数据库降级迁移。
    输入参数：无。
    输出参数：无返回值。
    """
    ${downgrades if downgrades else "pass"}
