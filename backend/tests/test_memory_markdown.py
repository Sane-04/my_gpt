# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import uuid
from datetime import datetime, timezone

from app.models.long_term_memory import LongTermMemory
from app.services.memory_markdown import build_long_term_memory_markdown, sync_long_term_memory_markdown


def build_memory(user_id: uuid.UUID) -> LongTermMemory:
    """函数作用：构造 Markdown 同步测试长期记忆。
    输入参数：user_id - 所属用户 UUID。
    输出参数：LongTermMemory 模型实例。
    """
    memory = LongTermMemory(
        user_id=user_id,
        content="用户喜欢简洁回答",
        metadata_={"title": "沟通偏好", "memory_key": "communication", "source": "manual"},
    )
    memory.id = uuid.uuid4()
    memory.created_at = datetime(2026, 5, 17, 1, 0, tzinfo=timezone.utc)
    memory.updated_at = datetime(2026, 5, 17, 1, 0, tzinfo=timezone.utc)
    return memory


def test_build_long_term_memory_markdown_contains_contract_fields():
    """函数作用：验证 Markdown 内容包含长期记忆契约字段。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    markdown = build_long_term_memory_markdown([build_memory(user_id)])

    assert "# Long Term Memory" in markdown
    assert "## 沟通偏好" in markdown
    assert "memory_key: `communication`" in markdown
    assert "用户喜欢简洁回答" in markdown


def test_sync_long_term_memory_markdown_writes_user_file(tmp_path):
    """函数作用：验证 Markdown 副本写入用户目录。
    输入参数：tmp_path - pytest 临时目录。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    path = sync_long_term_memory_markdown(str(tmp_path), user_id, [build_memory(user_id)])

    assert path == tmp_path / str(user_id) / "long_term_memory.md"
    assert path.exists()
    assert "用户喜欢简洁回答" in path.read_text(encoding="utf-8")
