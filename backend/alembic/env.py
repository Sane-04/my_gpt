# 模块说明：Alembic 迁移环境模块，负责加载模型元数据并执行迁移。
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401


config = context.config

# 日志配置：读取 alembic.ini 中的 logger 设置，方便迁移时输出状态。
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标 metadata：导入 app.models 后，Base.metadata 会包含所有模型表结构。
target_metadata = Base.metadata


def _helper_get_migration_database_url() -> str:
    """函数作用：返回 Alembic 迁移使用的同步数据库连接串。
    输入参数：无。
    输出参数：适用于 SQLAlchemy 同步 engine 的数据库连接串。
    """
    database_url = get_settings().database_url
    # 后端运行使用 asyncpg 异步驱动；Alembic 当前迁移流程使用同步 engine，因此迁移时切换为 psycopg。
    return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    """函数作用：在离线模式下运行 Alembic 迁移。
    输入参数：无。
    输出参数：无返回值。
    """
    # 离线模式只生成 SQL，不建立真实数据库连接。
    context.configure(
        url=_helper_get_migration_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """函数作用：在在线模式下运行 Alembic 迁移。
    输入参数：无。
    输出参数：无返回值。
    """
    # 在线模式使用当前环境变量中的 DATABASE_URL 连接数据库并执行迁移。
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _helper_get_migration_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # 将连接和模型 metadata 交给 Alembic，用于执行 migration 脚本。
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
