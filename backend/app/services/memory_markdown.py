# 模块说明：后端服务模块，封装外部模型调用或跨模块业务处理。
from pathlib import Path
import uuid

from app.models.long_term_memory import LongTermMemory
from app.repositories.long_term_memories import get_memory_key, get_memory_source, get_memory_title


def build_long_term_memory_markdown(memories: list[LongTermMemory]) -> str:
    """函数作用：构造长期记忆 Markdown 副本文本。
    输入参数：memories - 长期记忆列表。
    输出参数：Markdown 文本。
    """
    lines = ["# Long Term Memory", ""]
    for memory in memories:
        lines.extend(
            [
                f"## {get_memory_title(memory)}",
                "",
                f"- memory_key: `{get_memory_key(memory)}`",
                f"- source: `{get_memory_source(memory)}`",
                f"- id: `{memory.id}`",
                "",
                memory.content,
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def sync_long_term_memory_markdown(memory_dir: str, user_id: uuid.UUID, memories: list[LongTermMemory]) -> Path:
    """函数作用：把当前用户长期记忆同步为 Markdown 副本。
    输入参数：memory_dir - 记忆根目录；user_id - 当前用户 UUID；memories - 长期记忆列表。
    输出参数：写入的 Markdown 文件路径。
    """
    user_dir = Path(memory_dir) / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    memory_path = user_dir / "long_term_memory.md"
    memory_path.write_text(build_long_term_memory_markdown(memories), encoding="utf-8")
    return memory_path
