# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
from app.db.base import Base
import app.models  # noqa: F401


def test_core_tables_registered_in_metadata():
    """函数作用：验证核心数据库表已注册到 SQLAlchemy metadata。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    # 这 7 张表是 TASK009 明确要求的核心数据库表。
    expected_tables = {
        "users",
        "conversations",
        "messages",
        "long_term_memories",
        "memory_events",
        "tool_call_events",
        "prompt_snapshots",
    }

    # Alembic 依赖 Base.metadata 发现表结构，因此这里直接校验 metadata 注册结果。
    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_users_table_has_password_hash_column():
    """函数作用：验证 users 表包含密码哈希字段。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    # TASK010 要求密码必须哈希保存，因此 users 表需要 password_hash 字段。
    users = Base.metadata.tables["users"]

    assert "password_hash" in users.c


def test_core_tables_use_uuid_primary_keys():
    """函数作用：验证核心表都使用 UUID 主键。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    for table_name in (
        "users",
        "conversations",
        "messages",
        "long_term_memories",
        "memory_events",
        "tool_call_events",
        "prompt_snapshots",
    ):
        # 每张核心表的 id 字段都必须是 UUID 主键，满足跨表统一主键策略。
        id_column = Base.metadata.tables[table_name].c.id

        assert id_column.primary_key
        assert id_column.type.python_type.__name__ == "UUID"


def test_messages_table_has_embedding_and_fts_columns():
    """函数作用：验证 messages 表包含向量、向量化状态、错误和 FTS 字段。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    # messages 是检索核心表，必须同时具备向量检索和中文全文检索字段。
    messages = Base.metadata.tables["messages"]

    assert "embedding" in messages.c
    assert "embedding_status" in messages.c
    assert "embedding_error" in messages.c
    assert "fts_vector" in messages.c
    assert "VECTOR(1536)" in str(messages.c.embedding.type)


def test_required_indexes_exist():
    """函数作用：验证 TASK009 要求的关键索引存在。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    # 关键索引覆盖登录身份、消息检索、长期记忆检索、工具审计和 prompt 调试。
    index_names = {
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }

    assert "ix_users_email" in index_names
    assert "ix_messages_conversation_created_at" in index_names
    assert "ix_messages_fts_vector" in index_names
    assert "ix_messages_embedding_vector" in index_names
    assert "ix_long_term_memories_fts_vector" in index_names
    assert "ix_tool_call_events_user_started_at" in index_names
    assert "ix_prompt_snapshots_user_created_at" in index_names


def test_embedding_indexes_use_hnsw():
    """函数作用：验证 embedding 向量索引使用 HNSW。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    # HNSW 是当前向量检索索引策略，避免后续误改回 IVFFlat。
    embedding_indexes = {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
        if index.name
        in {
            "ix_messages_embedding_vector",
            "ix_long_term_memories_embedding_vector",
        }
    }

    assert embedding_indexes["ix_messages_embedding_vector"].dialect_options["postgresql"]["using"] == "hnsw"
    assert embedding_indexes["ix_long_term_memories_embedding_vector"].dialect_options["postgresql"]["using"] == "hnsw"
