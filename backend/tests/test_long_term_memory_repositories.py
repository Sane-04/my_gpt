# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import asyncio
import uuid
from datetime import datetime, timezone

from app.models.long_term_memory import LongTermMemory
from app.repositories.long_term_memories import (
    create_long_term_memory,
    format_long_term_memories_for_prompt,
    get_memory_key,
    get_memory_source,
    get_memory_title,
)


class FakeSession:
    """类作用：模拟长期记忆仓储测试 Session。"""

    def __init__(self):
        """函数作用：初始化 Session 状态。
        输入参数：无。
        输出参数：无返回值。
        """
        self.added = []
        self.committed = False
        self.refreshed = []

    def add(self, item):
        """函数作用：记录新增对象。
        输入参数：item - 待新增对象。
        输出参数：无返回值。
        """
        self.added.append(item)

    async def commit(self):
        """函数作用：记录事务提交。
        输入参数：无。
        输出参数：无返回值。
        """
        self.committed = True

    async def refresh(self, item):
        """函数作用：模拟刷新长期记忆字段。
        输入参数：item - 待刷新对象。
        输出参数：无返回值。
        """
        item.id = uuid.uuid4()
        item.created_at = datetime(2026, 5, 17, 1, 0, tzinfo=timezone.utc)
        item.updated_at = datetime(2026, 5, 17, 1, 0, tzinfo=timezone.utc)
        self.refreshed.append(item)


def build_memory(content: str) -> LongTermMemory:
    """函数作用：构造长期记忆模型。
    输入参数：content - 记忆正文。
    输出参数：LongTermMemory 模型实例。
    """
    memory = LongTermMemory(
        user_id=uuid.uuid4(),
        content=content,
        metadata_={"title": "偏好", "memory_key": "preference", "source": "manual"},
    )
    memory.id = uuid.uuid4()
    return memory


def test_create_long_term_memory_stores_contract_fields_in_metadata():
    """函数作用：验证长期记忆契约字段写入 metadata。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    session = FakeSession()
    user_id = uuid.uuid4()

    memory = asyncio.run(
        create_long_term_memory(session, user_id, " 偏好 ", " preference ", " 喜欢简洁回答 ", "manual")
    )

    assert memory.user_id == user_id
    assert memory.content == "喜欢简洁回答"
    assert memory.metadata_ == {"title": "偏好", "memory_key": "preference", "source": "manual"}
    assert session.added == [memory]
    assert session.committed is True
    assert session.refreshed == [memory]


def test_memory_metadata_helpers_and_prompt_limit():
    """函数作用：验证 metadata 读取和长期记忆 prompt 截断。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    memory = build_memory("abcdefg")

    assert get_memory_title(memory) == "偏好"
    assert get_memory_key(memory) == "preference"
    assert get_memory_source(memory) == "manual"
    assert "已按字符上限截断" in format_long_term_memories_for_prompt([memory], 8)
