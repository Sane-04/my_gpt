# 模块说明：后端聊天工具模块，承接模型工具调用分发和具体工具执行逻辑。
import uuid
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import MemoryEventType, MessageRole
from app.repositories.long_term_memories import (
    create_long_term_memory,
    format_long_term_memories_for_prompt,
    get_long_term_memory_by_id,
    get_long_term_memory_by_key,
    get_memory_key,
    get_memory_source,
    get_memory_title,
    list_long_term_memories,
    update_long_term_memory,
)
from app.repositories.memory_events import create_memory_event
from app.repositories.messages import hybrid_search_session_memory
from app.repositories.messages import list_messages_by_chronological_position
from app.services.memory_markdown import sync_long_term_memory_markdown
from app.services.model_client import ChatCompletionsModelClient


CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_session_memory",
            "description": "当最近上下文不足以回答当前会话早先内容，且用户问的是主题、关键词或语义相关内容时，搜索当前会话窗口之外的历史消息。不要用于第一句、最后一句、第几条这类时间线位置问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "用于搜索当前会话历史的具体问题或关键词。"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10, "description": "返回历史消息数量，通常 3 到 5 条。"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_messages_by_position",
            "description": "按当前会话时间线位置读取消息。用户询问第一句、最早、开头、最后一句、最近、倒数第几条、我说的第一句话等确定性顺序问题时使用，不做语义搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "position": {
                        "type": "string",
                        "enum": ["earliest", "latest"],
                        "description": "earliest 表示从会话最早处读取；latest 表示从会话最近处读取。",
                    },
                    "role": {
                        "type": "string",
                        "enum": ["any", "user", "assistant", "tool", "system"],
                        "description": "按消息角色过滤。用户问“我说的”时使用 user；不限定角色时使用 any。",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "从所选边界跳过多少条消息。第一条使用 0，第二条使用 1。",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "description": "返回消息数量。定位第一句通常取 1 到 3 条以便核对。",
                    },
                },
                "required": ["position"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_long_term_memory",
            "description": "列出当前用户已有长期记忆。保存新记忆前若不确定是否重复，或更新记忆前需要查找 memory_id / memory_key 时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "description": "最多返回多少条长期记忆。"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_long_term_memory",
            "description": "保存一条新的长期记忆。用户明确要求记住，或表达稳定偏好、长期兴趣、身份事实、项目背景时使用；不要保存敏感凭据、临时闲聊或未经确认的猜测。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "简短中文标题，例如“运动兴趣”“沟通偏好”。"},
                    "memory_key": {"type": "string", "description": "稳定英文 snake_case 键，例如 sports_basketball_preference。"},
                    "content": {"type": "string", "description": "要长期保存的清晰事实，例如“用户爱打篮球。”"},
                    "source": {"type": "string", "description": "来源，模型自动保存时使用 assistant。"},
                },
                "required": ["title", "memory_key", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_long_term_memory",
            "description": "更新现有长期记忆。用户纠正旧信息、否定旧偏好、替换长期背景，或新信息应合并到已有记忆时使用；优先提供 memory_id，没有时提供 memory_key。",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "description": "要更新的长期记忆 ID。"},
                    "memory_key": {"type": "string", "description": "要更新的长期记忆键；找不到 memory_id 时使用。"},
                    "title": {"type": "string", "description": "更新后的简短中文标题。"},
                    "content": {"type": "string", "description": "更新后的完整长期记忆正文，不要只写增量片段。"},
                    "source": {"type": "string", "description": "来源，模型自动更新时使用 assistant。"},
                },
                "required": ["content"],
            },
        },
    },
]

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "当用户开启联网搜索时，除非问题明显只依赖当前对话、私人记忆或纯创作任务，否则应尽可能先搜索互联网，并返回带来源链接的结果，用于核验事实、补充最新信息和标注来源。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "用于联网搜索的具体问题或关键词。"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 8, "description": "返回搜索结果数量，通常 3 到 5 条。"},
            },
            "required": ["query"],
        },
    },
}


def get_chat_tools(enable_web_search: bool = False) -> list[dict]:
    """函数作用：按用户开关返回当前聊天可用工具列表。
    输入参数：enable_web_search - 是否允许本次聊天联网搜索。
    输出参数：工具定义列表。
    """
    if enable_web_search:
        return [*CHAT_TOOLS, WEB_SEARCH_TOOL]

    return [*CHAT_TOOLS]


def _serialize_memory(memory) -> dict:
    """函数作用：把长期记忆模型序列化为工具结果。
    输入参数：memory - 长期记忆模型。
    输出参数：工具结果字典。
    """
    return {
        "id": str(memory.id),
        "title": get_memory_title(memory),
        "memory_key": get_memory_key(memory),
        "content": memory.content,
        "source": get_memory_source(memory),
    }


async def execute_chat_tool(
    session: AsyncSession,
    model_client: ChatCompletionsModelClient,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    tool_name: str,
    arguments: dict,
    exclude_message_ids: set[uuid.UUID] | None = None,
) -> dict:
    """函数作用：执行模型请求的聊天工具并返回结构化结果。
    输入参数：session - 异步数据库会话；model_client - 模型客户端；user_id - 当前用户 UUID；conversation_id - 会话 UUID；tool_name - 工具名；arguments - 工具参数；exclude_message_ids - 排除消息 ID。
    输出参数：工具执行结果。
    """
    settings = get_settings()

    if tool_name == "search_session_memory":
        query = str(arguments.get("query") or "").strip()
        limit = int(arguments.get("limit") or 5)
        query_embedding = None
        try:
            query_embedding = await model_client.create_embedding(query)
        except Exception:
            query_embedding = None

        messages = await hybrid_search_session_memory(
            session=session,
            query=query,
            conversation_id=conversation_id,
            user_id=user_id,
            limit=limit,
            query_embedding=query_embedding,
            exclude_message_ids=exclude_message_ids,
        )
        return {
            "messages": [
                {
                    "id": str(message.id),
                    "role": message.role.value,
                    "content": message.content,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                }
                for message in messages
            ]
        }

    if tool_name == "get_session_messages_by_position":
        position = str(arguments.get("position") or "earliest").strip()
        role_value = str(arguments.get("role") or "any").strip()
        offset = max(int(arguments.get("offset") or 0), 0)
        limit = min(max(int(arguments.get("limit") or 5), 1), 20)
        if position not in {"earliest", "latest"}:
            return {"error": "position 只能是 earliest 或 latest"}
        try:
            role = None if role_value == "any" else MessageRole(role_value)
        except ValueError:
            return {"error": "role 只能是 any、user、assistant、tool 或 system"}

        messages = await list_messages_by_chronological_position(
            session=session,
            user_id=user_id,
            conversation_id=conversation_id,
            position=position,
            limit=limit,
            offset=offset,
            role=role,
        )
        return {
            "position": position,
            "role": role_value,
            "offset": offset,
            "messages": [
                {
                    "id": str(message.id),
                    "role": message.role.value,
                    "content": message.content,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                    "relative_position": offset + index,
                }
                for index, message in enumerate(messages, start=1)
            ],
        }

    if tool_name == "web_search":
        query = str(arguments.get("query") or "").strip()
        limit = min(max(int(arguments.get("limit") or 5), 1), 8)
        if not query:
            return {"error": "query 不能为空"}
        if not settings.serpapi_api_key:
            return {"error": "SERPAPI_API_KEY 未配置"}

        timeout_seconds = max(float(getattr(settings, "serpapi_timeout_seconds", 15.0)), 1.0)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 5.0))) as client:
                response = await client.get(
                    "https://serpapi.com/search.json",
                    params={
                        "engine": "google",
                        "q": query,
                        "api_key": settings.serpapi_api_key,
                        "num": limit,
                        "hl": "zh-cn",
                    },
                )
        except httpx.TimeoutException:
            return {
                "error": {
                    "code": "WEB_SEARCH_TIMEOUT",
                    "message": f"SerpApi 在 {timeout_seconds:g} 秒内没有响应",
                },
                "instruction": "联网搜索超时。这是内部工具状态，不要向用户提及搜索超时或工具失败；如可回答，基于已有知识作答；如果问题依赖最新外部事实，只说明当前无法核验最新信息。",
            }
        except httpx.RequestError as exc:
            return {"error": f"联网搜索请求失败：{exc}"}

        if response.status_code >= 400:
            return {"error": f"SerpApi 请求失败：{response.status_code}"}

        try:
            payload = response.json()
        except ValueError:
            return {"error": "SerpApi 返回了无法解析的响应"}
        if payload.get("error"):
            return {"error": f"SerpApi 错误：{payload['error']}"}

        results = []
        for index, item in enumerate(payload.get("organic_results") or [], start=1):
            url = str(item.get("link") or "").strip()
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if not url:
                continue

            parsed_url = urlparse(url)
            displayed_link = str(item.get("displayed_link") or "").strip()
            domain = displayed_link or parsed_url.netloc.removeprefix("www.") or url
            results.append(
                {
                    "id": f"src_{index}",
                    "title": title or url,
                    "url": url,
                    "domain": domain,
                    "snippet": snippet,
                    "source": "serpapi",
                }
            )
            if len(results) >= limit:
                break

        return {
            "query": query,
            "results": results,
            "instruction": "请基于联网搜索结果综合回答；优先使用编号分点组织答案；引用来源时不要输出 [1] 或裸链接，而是在相关句段后插入内部标记，例如 [[cite:src_1]] 或 [[cite:src_1,src_2]]。",
        }

    if tool_name == "list_long_term_memory":
        limit = int(arguments.get("limit") or 50)
        memories = await list_long_term_memories(session, user_id)
        return {
            "memories": [_serialize_memory(memory) for memory in memories[:limit]],
            "prompt_text": format_long_term_memories_for_prompt(memories, settings.long_term_memory_max_chars),
        }

    if tool_name == "save_long_term_memory":
        memory = await create_long_term_memory(
            session=session,
            user_id=user_id,
            title=str(arguments.get("title") or "").strip(),
            memory_key=str(arguments.get("memory_key") or "").strip(),
            content=str(arguments.get("content") or "").strip(),
            source=str(arguments.get("source") or "assistant").strip(),
        )
        await create_memory_event(
            session,
            user_id,
            MemoryEventType.CREATED,
            memory_id=memory.id,
            payload={"source": "tool", "memory": _serialize_memory(memory)},
        )
        memories = await list_long_term_memories(session, user_id)
        sync_long_term_memory_markdown(settings.memory_dir, user_id, memories)
        return {"memory": _serialize_memory(memory)}

    if tool_name == "update_long_term_memory":
        memory = None
        memory_id = arguments.get("memory_id")
        memory_key = arguments.get("memory_key")
        if memory_id:
            memory = await get_long_term_memory_by_id(session, user_id, uuid.UUID(str(memory_id)))
        if memory is None and memory_key:
            memory = await get_long_term_memory_by_key(session, user_id, str(memory_key))
        if memory is None:
            return {"error": "长期记忆不存在"}

        updated_memory = await update_long_term_memory(
            session=session,
            user_id=user_id,
            memory_id=memory.id,
            title=str(arguments.get("title") or get_memory_title(memory)).strip(),
            memory_key=str(arguments.get("memory_key") or get_memory_key(memory)).strip(),
            content=str(arguments.get("content") or "").strip(),
            source=str(arguments.get("source") or get_memory_source(memory)).strip(),
        )
        await create_memory_event(
            session,
            user_id,
            MemoryEventType.UPDATED,
            memory_id=memory.id,
            payload={"source": "tool", "memory": _serialize_memory(updated_memory)},
        )
        memories = await list_long_term_memories(session, user_id)
        sync_long_term_memory_markdown(settings.memory_dir, user_id, memories)
        return {"memory": _serialize_memory(updated_memory)}

    return {"error": f"未知工具：{tool_name}"}
