# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import asyncio
import uuid

from app.models.conversation import Conversation
from app.models.enums import MessageRole
from app.models.message import Message
from app.repositories.conversations import create_conversation, delete_conversation_by_id
from app.repositories.messages import create_message, list_recent_messages


class FakeScalarResult:
    """类作用：模拟 SQLAlchemy scalar 结果。"""

    def __init__(self, items):
        """函数作用：初始化模拟标量结果。
        输入参数：items - 标量列表。
        输出参数：无返回值。
        """
        self.items = items

    def all(self):
        """函数作用：返回全部标量结果。
        输入参数：无。
        输出参数：返回列表。
        """
        return self.items


class FakeExecuteResult:
    """类作用：模拟 SQLAlchemy execute 返回值。"""

    def __init__(self, item=None, items=None):
        """函数作用：初始化模拟执行结果。
        输入参数：item - 单条结果；items - 多条结果。
        输出参数：无返回值。
        """
        self.item = item
        self.items = items or []

    def scalar_one_or_none(self):
        """函数作用：返回单条或空结果。
        输入参数：无。
        输出参数：返回单条对象或 None。
        """
        return self.item

    def scalars(self):
        """函数作用：返回标量结果包装器。
        输入参数：无。
        输出参数：FakeScalarResult。
        """
        return FakeScalarResult(self.items)


class FakeSession:
    """类作用：模拟异步数据库会话。"""

    def __init__(self, execute_result=None, get_result=None):
        """函数作用：初始化模拟 Session。
        输入参数：execute_result - execute 返回值；get_result - get 返回值。
        输出参数：无返回值。
        """
        self.added = []
        self.committed = False
        self.deleted = []
        self.executed_statements = []
        self.execute_result = execute_result or FakeExecuteResult()
        self.get_result = get_result
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

    async def execute(self, statement):
        """函数作用：记录 SQLAlchemy 语句并返回模拟结果。
        输入参数：statement - SQLAlchemy 语句。
        输出参数：FakeExecuteResult。
        """
        self.executed_statements.append(statement)
        return self.execute_result

    async def delete(self, item):
        """函数作用：记录删除对象。
        输入参数：item - 待删除对象。
        输出参数：无返回值。
        """
        self.deleted.append(item)

    async def get(self, _model, _item_id):
        """函数作用：返回预置 get 结果。
        输入参数：_model - 模型类；_item_id - 主键。
        输出参数：预置对象。
        """
        return self.get_result


def test_create_conversation_defaults_blank_title():
    """函数作用：验证创建会话会为缺省标题兜底。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    session = FakeSession()
    user_id = uuid.uuid4()

    conversation = asyncio.run(create_conversation(session, user_id, "  "))

    assert conversation.title == "新的对话"
    assert conversation.user_id == user_id
    assert session.added == [conversation]
    assert session.committed is True
    assert session.refreshed == [conversation]


def test_delete_conversation_hard_deletes_messages_and_conversation():
    """函数作用：验证硬删除会先删除会话级子记录再删除会话。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    conversation = Conversation(user_id=user_id, title="测试会话")
    conversation.id = conversation_id
    session = FakeSession(execute_result=FakeExecuteResult(item=conversation))

    deleted = asyncio.run(delete_conversation_by_id(session, user_id, conversation_id))

    assert deleted is True
    assert session.deleted == [conversation]
    assert session.committed is True
    assert len(session.executed_statements) == 4


def test_create_message_updates_owned_conversation_updated_at():
    """函数作用：验证新增消息时会更新当前用户自己的会话更新时间。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    conversation = Conversation(user_id=user_id, title="测试会话")
    conversation.id = conversation_id
    session = FakeSession(get_result=conversation)

    message = asyncio.run(create_message(session, user_id, conversation_id, MessageRole.USER, "你好"))

    assert isinstance(message, Message)
    assert message.user_id == user_id
    assert message.conversation_id == conversation_id
    assert conversation.updated_at is not None
    assert session.added == [message]
    assert session.committed is True
    assert session.refreshed == [message]


def test_list_recent_messages_returns_recent_items_in_ascending_order():
    """函数作用：验证最近 N 条消息会恢复为创建时间正序。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    older_message = Message(user_id=user_id, conversation_id=conversation_id, role=MessageRole.USER, content="较早")
    newer_message = Message(user_id=user_id, conversation_id=conversation_id, role=MessageRole.ASSISTANT, content="较新")
    session = FakeSession(execute_result=FakeExecuteResult(items=[newer_message, older_message]))

    messages = asyncio.run(list_recent_messages(session, user_id, conversation_id, 2))

    assert messages == [older_message, newer_message]
    assert len(session.executed_statements) == 1
