# 模块说明：后端数据库基础设施模块，集中声明 ORM 基类、引擎和会话依赖。
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


# 命名约定：Alembic 自动生成迁移时会使用稳定名称，减少跨环境迁移差异。
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """类作用：为所有 SQLAlchemy 模型提供统一 metadata。"""

    # 全部模型共享同一份 metadata，Alembic env.py 会读取它生成和执行迁移。
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
