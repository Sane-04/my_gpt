# 模块说明：后端 ORM 模型模块，描述数据库表结构、索引和表关系。
from enum import Enum


class MessageRole(str, Enum):
    """类作用：限定消息角色。"""

    # 系统提示词消息。
    SYSTEM = "system"
    # 用户输入消息。
    USER = "user"
    # 模型回复消息。
    ASSISTANT = "assistant"
    # 工具调用或工具返回消息。
    TOOL = "tool"


class EmbeddingStatus(str, Enum):
    """类作用：限定消息向量化状态。"""

    # 等待后台任务生成 embedding。
    PENDING = "pending"
    # 明确跳过向量化，例如空内容或不需要检索的内容。
    SKIPPED = "skipped"
    # 正在生成 embedding。
    PROCESSING = "processing"
    # embedding 已成功写入。
    COMPLETED = "completed"
    # embedding 生成失败，错误写入 embedding_error。
    FAILED = "failed"


class MemoryEventType(str, Enum):
    """类作用：限定长期记忆事件类型。"""

    # 新增长期记忆。
    CREATED = "created"
    # 更新长期记忆。
    UPDATED = "updated"
    # 删除长期记忆。
    DELETED = "deleted"
    # 从普通消息提炼或提升为长期记忆。
    PROMOTED = "promoted"


class ToolCallStatus(str, Enum):
    """类作用：限定工具调用状态。"""

    # 工具调用已开始。
    STARTED = "started"
    # 工具调用成功完成。
    SUCCEEDED = "succeeded"
    # 工具调用失败，错误写入 error。
    FAILED = "failed"
