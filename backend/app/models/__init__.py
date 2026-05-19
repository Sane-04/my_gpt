# 模块说明：后端 ORM 模型模块，描述数据库表结构、索引和表关系。
# 集中导入全部模型，确保 Alembic 读取 Base.metadata 时能发现所有表。
from app.models.conversation import Conversation
from app.models.enums import EmbeddingStatus, MemoryEventType, MessageRole, ToolCallStatus
from app.models.long_term_memory import LongTermMemory
from app.models.memory_event import MemoryEvent
from app.models.message import Message
from app.models.prompt_snapshot import PromptSnapshot
from app.models.tool_call_event import ToolCallEvent
from app.models.user import User

__all__ = [
    "Conversation",
    "EmbeddingStatus",
    "LongTermMemory",
    "MemoryEvent",
    "MemoryEventType",
    "Message",
    "MessageRole",
    "PromptSnapshot",
    "ToolCallEvent",
    "ToolCallStatus",
    "User",
]
