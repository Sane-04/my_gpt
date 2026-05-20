# 模块说明：后端 API 路由模块，负责请求校验、鉴权依赖和响应契约转换。
import json
import re
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.db import get_db
from app.models.enums import EmbeddingStatus, MessageRole
from app.models.user import User
from app.repositories.conversations import get_conversation_by_id, update_conversation_title
from app.repositories.long_term_memories import format_long_term_memories_for_prompt, list_long_term_memories
from app.repositories.messages import count_messages, create_message, list_recent_messages, update_message_embedding_result
from app.repositories.prompt_snapshots import create_prompt_snapshot
from app.repositories.tool_call_events import create_tool_call_event, mark_tool_call_failed, mark_tool_call_succeeded
from app.prompts.chat import build_chat_system_prompt, build_long_term_memory_prompt
from app.prompts.image import build_image_edit_prompt, build_image_generation_prompt
from app.prompts.intent import build_image_intent_messages
from app.schemas.chat import ChatImageInput, ChatStreamRequest
from app.services.model_client import (
    ChatCompletionsModelClient,
    ModelConfigError,
    ModelStreamError,
    build_messages_with_tool_results,
)
from app.tools.chat_tools import execute_chat_tool, get_chat_tools


router = APIRouter(prefix="/api/chat", tags=["chat"])
MAX_TOOL_CALL_ROUNDS = 5
IMAGE_INTENTS = {"chat", "image_generate", "image_edit"}


def _encode_stream_event(event: dict) -> bytes:
    """函数作用：把聊天流事件编码为一行 UTF-8 JSON。
    输入参数：event - delta、done 或 error 事件字典。
    输出参数：UTF-8 字节串。
    """
    return f"{json.dumps(event, ensure_ascii=False)}\n".encode("utf-8")


def _format_stream_error_message(exc: Exception, fallback: str) -> str:
    """函数作用：把上游模型或网关错误整理成前端可读提示。
    输入参数：exc - 捕获到的异常；fallback - 默认错误消息。
    输出参数：适合通过聊天流展示给用户的错误文本。
    """
    raw_message = str(exc).strip()
    if not raw_message:
        return fallback

    compact_message = re.sub(r"\s+", " ", raw_message)
    if re.search(r"<\s*html|<\s*body|</\s*[a-zA-Z][^>]*>", compact_message, re.IGNORECASE):
        if "502" in compact_message and "Bad Gateway" in compact_message:
            return "模型服务网关错误（502 Bad Gateway），请检查 OPENAI_BASE_URL 对应服务是否可用，或稍后重试"
        return fallback

    if len(compact_message) > 300:
        return f"{compact_message[:300]}..."

    return compact_message


def _parse_conversation_id(conversation_id: str) -> uuid.UUID:
    """函数作用：解析聊天请求中的会话 UUID。
    输入参数：conversation_id - 前端传入的会话 ID。
    输出参数：解析后的 UUID；格式错误时抛出 AppError。
    """
    try:
        return uuid.UUID(conversation_id)
    except ValueError:
        raise AppError(status_code=400, code="INVALID_CHAT_INPUT", message="会话 ID 格式不正确")


def _build_title(content: str) -> str:
    """函数作用：根据第一条用户消息生成会话标题。
    输入参数：content - 用户消息正文。
    输出参数：不超过 200 字符的标题。
    """
    compact_content = " ".join(content.split())
    return compact_content[:200] or "新的对话"


def _serialize_chat_images(images: list[ChatImageInput]) -> list[dict]:
    """函数作用：把聊天图片输入转换为消息 metadata 和模型输入可复用的字典。
    输入参数：images - 请求中的图片输入列表。
    输出参数：图片字典列表。
    """
    return [
        {
            "name": image.name,
            "mimeType": image.mimeType,
            "size": image.size,
            "dataUrl": image.dataUrl,
        }
        for image in images
    ]


def _build_user_model_message(content: str, images: list[dict]) -> dict:
    """函数作用：构造当前用户发给模型的文本或多模态消息。
    输入参数：content - 用户文本内容；images - 当前消息图片列表。
    输出参数：Chat Completions user message。
    """
    if not images:
        return {"role": "user", "content": content}

    text = content.strip() or "请分析这些图片。"
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            *[
                {
                    "type": "image_url",
                    "image_url": {"url": image["dataUrl"]},
                }
                for image in images
            ],
        ],
    }


def _extract_chat_completion_text(response: dict) -> str:
    """函数作用：从非流式 Chat Completions 响应中提取助手文本。
    输入参数：response - 模型响应 JSON。
    输出参数：助手消息文本。
    """
    choices = response.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    return str(message.get("content") or "")


def _parse_image_intent_response(response_text: str) -> dict:
    """函数作用：解析图片意图识别 JSON。
    输入参数：response_text - 模型返回的 JSON 文本。
    输出参数：归一化后的意图识别字典。
    """
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return {"intent": "chat", "confidence": "low", "reason": "意图识别 JSON 解析失败"}

    intent = str(payload.get("intent") or "chat").strip()
    if intent not in IMAGE_INTENTS:
        intent = "chat"

    confidence = str(payload.get("confidence") or "low").strip()
    if confidence not in {"low", "medium", "high"}:
        confidence = "low"

    if confidence == "low":
        intent = "chat"

    return {
        "intent": intent,
        "confidence": confidence,
        "reason": str(payload.get("reason") or "").strip(),
        "requiresPreviousImage": bool(payload.get("requiresPreviousImage")),
        "usesUploadedImages": bool(payload.get("usesUploadedImages")),
    }


def _get_message_images(message) -> list[dict]:
    """函数作用：读取消息 metadata 中的图片列表。
    输入参数：message - 消息模型。
    输出参数：图片字典列表。
    """
    metadata = message.metadata_ or {}
    if not isinstance(metadata, dict):
        return []

    images = metadata.get("images")
    return images if isinstance(images, list) else []


def _has_generated_image(message) -> bool:
    """函数作用：判断消息是否包含助手生成图片。
    输入参数：message - 消息模型。
    输出参数：是否包含生成图片。
    """
    for image in _get_message_images(message):
        if isinstance(image, dict) and image.get("source") == "generated":
            return True

    return False


def _build_intent_recent_messages(messages: list) -> list[dict]:
    """函数作用：构造意图识别使用的最近消息摘要。
    输入参数：messages - 最近消息模型列表。
    输出参数：消息摘要列表，不包含图片 base64。
    """
    summaries = []
    for message in messages:
        images = _get_message_images(message)
        generated_images = [
            image
            for image in images
            if isinstance(image, dict) and image.get("source") == "generated"
        ]
        image_summary = None
        if generated_images:
            generation = generated_images[-1].get("generation") if isinstance(generated_images[-1], dict) else None
            image_summary = {
                "size": generated_images[-1].get("generation", {}).get("size") if isinstance(generation, dict) else None,
                "prompt": generated_images[-1].get("generation", {}).get("prompt") if isinstance(generation, dict) else None,
                "revisedPrompt": generated_images[-1].get("generation", {}).get("revisedPrompt") if isinstance(generation, dict) else None,
            }

        summaries.append(
            {
                "role": message.role.value,
                "content": message.content,
                "hasImages": bool(images),
                "hasGeneratedImage": bool(generated_images),
                "imageSummary": image_summary,
            }
        )

    return summaries


def _find_recent_generated_images(messages: list) -> list[dict]:
    """函数作用：从最近消息中查找最后一组生成图片。
    输入参数：messages - 最近消息模型列表。
    输出参数：可用于 Image API edits 的图片列表。
    """
    for message in reversed(messages):
        generated_images = [
            image
            for image in _get_message_images(message)
            if isinstance(image, dict) and image.get("source") == "generated" and image.get("dataUrl")
        ]
        if generated_images:
            return generated_images

    return []


def _build_generated_image_metadata(
    result: dict,
    prompt: str,
    intent: str,
    requested_quality: str,
    requested_size: str,
    requested_output_format: str,
) -> dict:
    """函数作用：把 Image API 返回结果转换为消息图片 metadata。
    输入参数：result - Image API 结果；prompt - 实际发送的图片提示词；intent - 图片意图；requested_quality - 请求质量；requested_size - 请求尺寸；requested_output_format - 请求格式。
    输出参数：前端 MessageImage 字典。
    """
    output_format = str(result.get("output_format") or requested_output_format or "png").lower()
    mime_type = f"image/{'jpeg' if output_format in {'jpg', 'jpeg'} else output_format}"
    b64_json = str(result.get("b64_json") or "")
    return {
        "name": f"generated-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.{output_format}",
        "mimeType": mime_type,
        "size": len(b64_json),
        "dataUrl": f"data:{mime_type};base64,{b64_json}",
        "source": "generated",
        "generation": {
            "intent": intent,
            "model": get_settings().image_model,
            "requestedQuality": requested_quality,
            "quality": result.get("quality"),
            "requestedSize": requested_size,
            "size": result.get("size"),
            "requestedOutputFormat": requested_output_format,
            "outputFormat": result.get("output_format") or requested_output_format,
            "background": result.get("background"),
            "prompt": prompt,
            "revisedPrompt": result.get("revised_prompt"),
            "createdFrom": "image_api",
        },
    }


async def _stream_chat_events(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    content: str,
    enable_web_search: bool = False,
    images: list[ChatImageInput] | None = None,
) -> AsyncIterator[bytes]:
    """函数作用：保存用户消息、调用模型流并产出前端聊天事件。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID；content - 用户消息；enable_web_search - 是否允许本次联网搜索；images - 当前消息图片输入。
    输出参数：异步产出 NDJSON 字节块。
    """
    async def _helper_embed_message(model_client: ChatCompletionsModelClient, message) -> None:
        """函数作用：为消息同步生成 embedding，并在失败时记录错误。
        输入参数：model_client - 模型客户端；message - 已保存的消息模型。
        输出参数：无返回值。
        """
        try:
            embedding = await model_client.create_embedding(message.content)
            await update_message_embedding_result(
                session,
                message.id,
                user_id,
                embedding,
                EmbeddingStatus.COMPLETED,
                None,
            )
        except Exception as exc:
            await update_message_embedding_result(
                session,
                message.id,
                user_id,
                None,
                EmbeddingStatus.FAILED,
                str(exc),
            )

    async def _helper_run_model_with_chat_tools(
        model_client: ChatCompletionsModelClient,
        messages: list[dict],
        exclude_message_ids: set[uuid.UUID],
        tools: list[dict],
    ) -> AsyncIterator[dict]:
        """函数作用：流式运行模型并按需多轮执行聊天工具。
        输入参数：model_client - 模型客户端；messages - 当前模型消息；exclude_message_ids - 已在上下文窗口里的消息 ID，检索时需要排除；tools - 本次允许模型调用的工具。
        输出参数：异步产出前端流事件和最终消息上下文。
        """
        for round_index in range(MAX_TOOL_CALL_ROUNDS):
            completed_event = None
            async for event in model_client.stream_chat_completion(messages, tools):
                if event.get("type") == "delta" and event.get("delta"):
                    yield {"type": "delta", "delta": event["delta"]}
                    continue

                if event.get("type") == "completed":
                    completed_event = event

            if completed_event is None:
                yield {"type": "final_messages", "messages": messages}
                return

            tool_calls = completed_event.get("tool_calls") or []
            if not tool_calls:
                yield {"type": "final_messages", "messages": messages}
                return

            tool_results = []
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name", "")
                arguments = function.get("arguments") or {}
                yield {"type": "tool_call_started", "toolName": tool_name}
                event = await create_tool_call_event(
                    session,
                    user_id,
                    conversation_id,
                    tool_name,
                    arguments,
                )
                try:
                    result = await execute_chat_tool(
                        session=session,
                        model_client=model_client,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        tool_name=tool_name,
                        arguments=arguments,
                        exclude_message_ids=exclude_message_ids,
                    )
                    await mark_tool_call_succeeded(session, event, result)
                except Exception as exc:
                    result = {"error": str(exc)}
                    await mark_tool_call_failed(session, event, str(exc))

                if tool_name == "web_search" and isinstance(result, dict):
                    yield {"type": "web_search_sources", "sources": result.get("results") or []}

                tool_call_id = tool_call.get("id") or str(event.id)
                tool_call["id"] = tool_call_id
                tool_call_output = json.dumps(result, ensure_ascii=False)
                tool_results.append(
                    {
                        "tool_call_id": tool_call_id,
                        "output": tool_call_output,
                    }
                )
                yield {"type": "tool_call_finished", "toolName": tool_name}

            messages = build_messages_with_tool_results(messages, tool_calls, tool_results)

            if round_index == MAX_TOOL_CALL_ROUNDS - 1:
                raise ModelStreamError("工具调用轮数超过限制")

        yield {"type": "final_messages", "messages": messages}

    async def _helper_detect_image_intent(
        model_client: ChatCompletionsModelClient,
        recent_context_messages: list,
        current_content: str,
        current_images: list[dict],
    ) -> dict:
        """函数作用：识别当前用户请求是否需要图片生成或编辑。
        输入参数：model_client - 模型客户端；recent_context_messages - 最近历史消息；current_content - 当前用户文本；current_images - 当前上传图片。
        输出参数：意图识别结果字典；失败时返回 chat。
        """
        settings = get_settings()
        recent_messages = recent_context_messages[-max(int(getattr(settings, "image_intent_context_size", 5)), 0) :]
        current_message = {
            "content": current_content,
            "uploadedImageCount": len(current_images),
            "hasUploadedImages": bool(current_images),
            "recentHasGeneratedImage": any(_has_generated_image(message) for message in recent_messages),
        }
        try:
            intent_messages = build_image_intent_messages(_build_intent_recent_messages(recent_messages), current_message)
            try:
                response = await model_client.create_chat_completion(
                    intent_messages,
                    response_format={"type": "json_object"},
                )
            except ModelStreamError:
                response = await model_client.create_chat_completion(intent_messages)
            return _parse_image_intent_response(_extract_chat_completion_text(response))
        except Exception:
            return {"intent": "chat", "confidence": "low", "reason": "意图识别失败"}

    settings = get_settings()
    assistant_content = ""
    web_search_sources = []
    image_payloads = _serialize_chat_images(images or [])
    stored_content = content.strip() or "请分析这些图片。"

    try:
        existing_message_count = await count_messages(session, user_id, conversation_id)
        user_metadata = {"images": image_payloads} if image_payloads else None
        user_message = await create_message(
            session,
            user_id,
            conversation_id,
            MessageRole.USER,
            stored_content,
            metadata=user_metadata,
        )
        model_client = ChatCompletionsModelClient()
        await _helper_embed_message(model_client, user_message)

        recent_messages = await list_recent_messages(
            session,
            user_id,
            conversation_id,
            max(settings.context_window_size, int(getattr(settings, "image_intent_context_size", 5))) + 1,
        )
        context_messages = [message for message in recent_messages if message.id != user_message.id]
        context_messages = context_messages[-settings.context_window_size :]
        intent_context_messages = [message for message in recent_messages if message.id != user_message.id]
        yield _encode_stream_event({"type": "intent_started"})
        image_intent = await _helper_detect_image_intent(
            model_client,
            intent_context_messages,
            stored_content,
            image_payloads,
        )
        yield _encode_stream_event(
            {
                "type": "intent_finished",
                "intent": image_intent["intent"],
                "confidence": image_intent.get("confidence"),
                "message": image_intent.get("reason") or "已完成用户意图识别",
            }
        )
        long_term_memories = await list_long_term_memories(session, user_id)
        memory_text = format_long_term_memories_for_prompt(
            long_term_memories,
            getattr(settings, "long_term_memory_max_chars", 20000),
        )
        tools = get_chat_tools(enable_web_search)
        current_user_model_message = _build_user_model_message(stored_content, image_payloads)
        messages = [
            {"role": "system", "content": build_chat_system_prompt()},
            {"role": "system", "content": build_long_term_memory_prompt(memory_text)},
            *[
                {"role": message.role.value, "content": message.content}
                for message in context_messages
            ],
            current_user_model_message,
        ]
        exclude_message_ids = {message.id for message in context_messages}

        if image_intent["intent"] in {"image_generate", "image_edit"}:
            image_action = "image_generation" if image_intent["intent"] == "image_generate" else "image_edit"
            yield _encode_stream_event({"type": "tool_call_started", "toolName": image_action})
            if image_intent["intent"] == "image_generate":
                image_prompt = build_image_generation_prompt(stored_content)
                image_result = await model_client.generate_image(
                    image_prompt,
                    settings.image_model,
                    settings.image_size,
                    settings.image_quality,
                    settings.image_output_format,
                )
            else:
                edit_source_images = image_payloads or _find_recent_generated_images(intent_context_messages)
                if not edit_source_images:
                    assistant_content = "请先上传一张图片，或先生成一张图片后再继续编辑。"
                    yield _encode_stream_event({"type": "delta", "delta": assistant_content})
                    if existing_message_count == 0:
                        await update_conversation_title(session, user_id, conversation_id, _build_title(stored_content))

                    assistant_message = await create_message(
                        session,
                        user_id,
                        conversation_id,
                        MessageRole.ASSISTANT,
                        assistant_content,
                        metadata={"imageIntent": image_intent},
                    )
                    await _helper_embed_message(model_client, assistant_message)
                    yield _encode_stream_event({"type": "tool_call_finished", "toolName": image_action})
                    yield _encode_stream_event({"type": "done"})
                    return

                image_prompt = build_image_edit_prompt(stored_content)
                image_result = await model_client.edit_image(
                    image_prompt,
                    edit_source_images,
                    settings.image_model,
                    settings.image_size,
                    settings.image_quality,
                    settings.image_output_format,
                )

            generated_image = _build_generated_image_metadata(
                image_result,
                image_prompt,
                image_intent["intent"],
                settings.image_quality,
                settings.image_size,
                settings.image_output_format,
            )
            assistant_content = "已生成图片。"
            assistant_metadata = {
                "images": [generated_image],
                "imageIntent": image_intent,
            }
            yield _encode_stream_event({"type": "image", "image": generated_image, "message": assistant_content})
            yield _encode_stream_event({"type": "tool_call_finished", "toolName": image_action})
            if existing_message_count == 0:
                await update_conversation_title(session, user_id, conversation_id, _build_title(stored_content))

            assistant_message = await create_message(
                session,
                user_id,
                conversation_id,
                MessageRole.ASSISTANT,
                assistant_content,
                metadata=assistant_metadata,
            )
            await _helper_embed_message(model_client, assistant_message)
            yield _encode_stream_event({"type": "done"})
            return

        final_messages = messages
        async for event in _helper_run_model_with_chat_tools(model_client, messages, exclude_message_ids, tools):
            event_type = event.get("type")
            delta = event.get("delta") or ""
            tool_name = event.get("toolName")

            if event_type == "delta" and delta:
                assistant_content += delta
                yield _encode_stream_event({"type": "delta", "delta": delta})

            if event_type == "tool_call_started":
                yield _encode_stream_event({"type": "tool_call_started", "toolName": tool_name})

            if event_type == "tool_call_finished":
                yield _encode_stream_event({"type": "tool_call_finished", "toolName": tool_name})

            if event_type == "web_search_sources":
                for source in event.get("sources") or []:
                    if isinstance(source, dict) and source.get("id") and source.get("url"):
                        web_search_sources.append(source)

            if event_type == "final_messages":
                final_messages = event.get("messages") or messages

        if existing_message_count == 0:
            await update_conversation_title(session, user_id, conversation_id, _build_title(stored_content))

        if settings.save_prompt_snapshots:
            await create_prompt_snapshot(
                session=session,
                user_id=user_id,
                conversation_id=conversation_id,
                request_message_id=user_message.id,
                model=settings.chat_model,
                prompt=content,
                messages=final_messages,
                metadata={"source": "chat_stream"},
            )

        if assistant_content.strip():
            assistant_metadata = None
            if web_search_sources:
                sources_by_id = {}
                for source in web_search_sources:
                    source_id = str(source.get("id") or "").strip()
                    if source_id and source_id not in sources_by_id:
                        sources_by_id[source_id] = source

                citation_groups = []
                seen_citation_keys = set()
                for match in re.finditer(r"\[\[cite:([a-zA-Z0-9_,\-\s]+)\]\]", assistant_content):
                    source_ids = [
                        source_id.strip()
                        for source_id in match.group(1).split(",")
                        if source_id.strip() in sources_by_id
                    ]
                    citation_key = ",".join(source_ids)
                    if not source_ids or citation_key in seen_citation_keys:
                        continue

                    seen_citation_keys.add(citation_key)
                    first_source = sources_by_id[source_ids[0]]
                    first_label = (
                        str(first_source.get("title") or "").strip()
                        or str(first_source.get("domain") or "").strip()
                        or "来源"
                    )
                    citation_groups.append(
                        {
                            "id": f"cite_{len(citation_groups) + 1}",
                            "label": f"{first_label} +{len(source_ids) - 1}" if len(source_ids) > 1 else first_label,
                            "sourceIds": source_ids,
                        }
                    )

                assistant_metadata = {
                    "sources": list(sources_by_id.values()),
                    "citationGroups": citation_groups,
                }
                yield _encode_stream_event(
                    {
                        "type": "sources",
                        "sources": assistant_metadata["sources"],
                        "citationGroups": assistant_metadata["citationGroups"],
                    }
                )

            assistant_message = await create_message(
                session,
                user_id,
                conversation_id,
                MessageRole.ASSISTANT,
                assistant_content,
                metadata=assistant_metadata,
            )
            await _helper_embed_message(model_client, assistant_message)

        yield _encode_stream_event({"type": "done"})
    except ModelConfigError as exc:
        yield _encode_stream_event({"type": "error", "message": _format_stream_error_message(exc, "模型配置错误")})
    except ModelStreamError as exc:
        yield _encode_stream_event({"type": "error", "message": _format_stream_error_message(exc, "模型流式调用失败")})
    except Exception:
        yield _encode_stream_event({"type": "error", "message": "流式生成失败"})


@router.post("/stream")
async def stream_chat(
    request: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """函数作用：处理聊天流式请求。
    输入参数：request - 聊天请求体；current_user - 当前登录用户；session - 异步数据库会话。
    输出参数：StreamingResponse，每行一个聊天事件 JSON。
    """
    conversation_id = _parse_conversation_id(request.conversationId)
    content = request.content.strip()

    if not content and not request.images:
        raise AppError(status_code=400, code="INVALID_CHAT_INPUT", message="消息内容不能为空")

    conversation = await get_conversation_by_id(session, current_user.id, conversation_id)
    if conversation is None:
        raise AppError(status_code=404, code="CONVERSATION_NOT_FOUND", message="会话不存在")

    return StreamingResponse(
        _stream_chat_events(
            session,
            current_user.id,
            conversation_id,
            content,
            request.enableWebSearch,
            request.images,
        ),
        media_type="application/x-ndjson",
    )
