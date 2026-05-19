# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import asyncio
import uuid

from app.models.prompt_snapshot import PromptSnapshot
from app.repositories.prompt_snapshots import create_prompt_snapshot


class FakeSession:
    """类作用：模拟异步数据库会话。"""

    def __init__(self):
        """函数作用：初始化模拟 Session。
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
        """函数作用：记录刷新对象。
        输入参数：item - 待刷新对象。
        输出参数：无返回值。
        """
        self.refreshed.append(item)


def test_create_prompt_snapshot_persists_payload():
    """函数作用：验证 Prompt 快照仓储会保存调试载荷。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    session = FakeSession()
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    request_message_id = uuid.uuid4()
    messages = [{"role": "user", "content": "你好"}]

    snapshot = asyncio.run(
        create_prompt_snapshot(
            session=session,
            user_id=user_id,
            conversation_id=conversation_id,
            request_message_id=request_message_id,
            model="test-model",
            prompt="你好",
            messages=messages,
            metadata={"source": "test"},
        )
    )

    assert isinstance(snapshot, PromptSnapshot)
    assert snapshot.user_id == user_id
    assert snapshot.conversation_id == conversation_id
    assert snapshot.request_message_id == request_message_id
    assert snapshot.model == "test-model"
    assert snapshot.prompt == "你好"
    assert snapshot.messages == messages
    assert session.added == [snapshot]
    assert session.committed is True
    assert session.refreshed == [snapshot]
