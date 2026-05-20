# 模块说明：后端服务模块，封装 OpenAI Chat Completions 兼容模型调用。
import base64
import binascii
from collections.abc import AsyncIterator
import json

import httpx

from app.core.config import get_settings


class ModelConfigError(Exception):
    """类作用：表示模型客户端配置缺失。"""


class ModelStreamError(Exception):
    """类作用：表示模型流式调用失败。"""


def _parse_arguments(arguments_text: str) -> dict:
    """函数作用：解析工具调用参数 JSON。
    输入参数：arguments_text - 模型返回的参数文本。
    输出参数：解析后的参数字典。
    """
    try:
        return json.loads(arguments_text or "{}")
    except json.JSONDecodeError:
        return {}


def _normalize_tool_call(tool_call: dict) -> dict:
    """函数作用：标准化 Chat Completions 工具调用。
    输入参数：tool_call - 模型返回或流式聚合后的工具调用。
    输出参数：包含解析参数和原始参数文本的工具调用字典。
    """
    function = tool_call.get("function") or {}
    arguments_text = function.get("arguments") or "{}"
    return {
        "id": tool_call.get("id", ""),
        "type": tool_call.get("type", "function"),
        "function": {
            "name": function.get("name", ""),
            "arguments": _parse_arguments(arguments_text),
            "arguments_text": arguments_text,
        },
    }


def build_messages_with_tool_results(
    messages: list[dict],
    assistant_tool_calls: list[dict],
    tool_results: list[dict],
) -> list[dict]:
    """函数作用：把 Chat Completions 工具调用和工具结果回灌为下一轮模型输入。
    输入参数：messages - 原始模型消息；assistant_tool_calls - 本轮 assistant 工具调用；tool_results - 工具执行结果列表。
    输出参数：追加 assistant tool_calls 和 tool 结果后的模型消息。
    """
    return [
        *messages,
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call["id"],
                    "type": tool_call.get("type", "function"),
                    "function": {
                        "name": tool_call.get("function", {}).get("name", ""),
                        "arguments": tool_call.get("function", {}).get("arguments_text", "{}"),
                    },
                }
                for tool_call in assistant_tool_calls
            ],
        },
        *[
            {
                "role": "tool",
                "tool_call_id": result["tool_call_id"],
                "content": result["output"],
            }
            for result in tool_results
        ],
    ]


class ChatCompletionsModelClient:
    """类作用：封装 OpenAI Chat Completions 兼容模型调用。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        embedding_api_key: str | None = None,
        embedding_base_url: str | None = None,
        embedding_model: str | None = None,
    ):
        """函数作用：初始化 Chat Completions 兼容模型客户端。
        输入参数：api_key - OpenAI API Key；base_url - OpenAI 兼容服务地址；model - 聊天模型名；embedding_api_key - Embedding 服务 API Key；embedding_base_url - Embedding 服务地址；embedding_model - Embedding 模型名。
        输出参数：无返回值。
        """
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.base_url = base_url if base_url is not None else settings.openai_base_url
        self.model = model if model is not None else settings.chat_model
        self.embedding_api_key = embedding_api_key if embedding_api_key is not None else settings.embedding_api_key
        self.embedding_base_url = embedding_base_url if embedding_base_url is not None else settings.embedding_base_url
        self.embedding_model = embedding_model if embedding_model is not None else settings.embedding_model

    def _api_url(self, path: str) -> str:
        """函数作用：拼接 OpenAI 兼容 HTTP API 地址。
        输入参数：path - 以 / 开头的 API 路径。
        输出参数：完整 URL。
        """
        return f"{self.base_url.rstrip('/')}{path}"

    def _headers(self) -> dict[str, str]:
        """函数作用：构造 OpenAI 兼容 HTTP 请求头。
        输入参数：无。
        输出参数：包含 Authorization 和 Content-Type 的请求头。
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _auth_headers(self) -> dict[str, str]:
        """函数作用：构造只包含鉴权信息的 HTTP 请求头。
        输入参数：无。
        输出参数：包含 Authorization 的请求头。
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

    def _embedding_api_url(self, path: str) -> str:
        """函数作用：拼接 Embedding HTTP API 地址。
        输入参数：path - 以 / 开头的 API 路径。
        输出参数：完整 URL。
        """
        return f"{self.embedding_base_url.rstrip('/')}{path}"

    def _embedding_headers(self) -> dict[str, str]:
        """函数作用：构造 Embedding HTTP 请求头。
        输入参数：无。
        输出参数：包含 Authorization 和 Content-Type 的请求头。
        """
        return {
            "Authorization": f"Bearer {self.embedding_api_key}",
            "Content-Type": "application/json",
        }

    def _validate_config(self) -> None:
        """函数作用：校验模型调用配置。
        输入参数：无。
        输出参数：无返回值；配置缺失时抛出 ModelConfigError。
        """
        if not self.api_key:
            raise ModelConfigError("OPENAI_API_KEY 未配置")

    def _validate_embedding_config(self) -> None:
        """函数作用：校验 Embedding 调用配置。
        输入参数：无。
        输出参数：无返回值；配置缺失时抛出 ModelConfigError。
        """
        if not self.embedding_api_key:
            raise ModelConfigError("EMBEDDING_API_KEY 未配置")
        if not self.embedding_base_url:
            raise ModelConfigError("EMBEDDING_BASE_URL 未配置")

    async def _post_json(self, path: str, payload: dict) -> dict:
        """函数作用：发送非流式 JSON 请求并返回 JSON 响应。
        输入参数：path - API 路径；payload - 请求体。
        输出参数：响应 JSON 字典。
        """
        settings = get_settings()
        timeout_seconds = max(float(getattr(settings, "model_http_timeout_seconds", 60.0)), 1.0)
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0))) as client:
            response = await client.post(self._api_url(path), headers=self._headers(), json=payload)

        if response.status_code >= 400:
            raise ModelStreamError(response.text or f"模型 HTTP 调用失败：{response.status_code}")

        return response.json()

    async def create_chat_completion(
        self,
        messages: list[dict],
        response_format: dict | None = None,
    ) -> dict:
        """函数作用：非流式调用 Chat Completions，适合意图识别等短请求。
        输入参数：messages - 模型消息列表；response_format - 可选响应格式约束。
        输出参数：响应 JSON 字典。
        """
        self._validate_config()
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            return await self._post_json("/chat/completions", payload)
        except ModelConfigError:
            raise
        except ModelStreamError:
            raise
        except Exception as exc:
            raise ModelStreamError(str(exc)) from exc

    async def generate_image(
        self,
        prompt: str,
        model: str,
        size: str,
        quality: str,
        output_format: str,
    ) -> dict:
        """函数作用：调用 Image API 根据文本生成图片。
        输入参数：prompt - 图片提示词；model - 图片模型名；size - 图片尺寸；quality - 请求质量；output_format - 输出格式。
        输出参数：包含图片 base64 和返回元信息的字典。
        """
        self._validate_config()
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "n": 1,
        }
        response = await self._post_json("/images/generations", payload)
        data = response.get("data") or []
        if not data or not isinstance(data[0], dict) or not data[0].get("b64_json"):
            raise ModelStreamError("图片生成响应缺少 data[0].b64_json")

        return {
            "b64_json": data[0]["b64_json"],
            "revised_prompt": data[0].get("revised_prompt"),
            "quality": response.get("quality"),
            "size": response.get("size"),
            "output_format": response.get("output_format") or output_format,
            "background": response.get("background"),
            "usage": response.get("usage"),
        }

    async def edit_image(
        self,
        prompt: str,
        images: list[dict],
        model: str,
        size: str,
        quality: str,
        output_format: str,
    ) -> dict:
        """函数作用：调用 Image API 根据输入图片执行编辑或参考图生成。
        输入参数：prompt - 图片编辑提示词；images - data URL 图片列表；model - 图片模型名；size - 图片尺寸；quality - 请求质量；output_format - 输出格式。
        输出参数：包含图片 base64 和返回元信息的字典。
        """
        self._validate_config()
        if not images:
            raise ModelStreamError("图片编辑需要至少一张输入图片")

        files = []
        for index, image in enumerate(images, start=1):
            data_url = str(image.get("dataUrl") or "")
            mime_type = str(image.get("mimeType") or "image/png")
            prefix = f"data:{mime_type};base64,"
            if not data_url.startswith(prefix):
                raise ModelStreamError("图片 dataUrl 格式不正确")

            try:
                image_bytes = base64.b64decode(data_url.removeprefix(prefix), validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ModelStreamError("图片 base64 数据无法解析") from exc

            extension = mime_type.split("/")[-1].replace("jpeg", "jpg") or "png"
            filename = str(image.get("name") or f"image-{index}.{extension}")
            files.append(("image[]", (filename, image_bytes, mime_type)))

        settings = get_settings()
        timeout_seconds = max(float(getattr(settings, "model_http_timeout_seconds", 60.0)), 1.0)
        data = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "n": "1",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0))) as client:
            response = await client.post(
                self._api_url("/images/edits"),
                headers=self._auth_headers(),
                data=data,
                files=files,
            )

        if response.status_code >= 400:
            raise ModelStreamError(response.text or f"模型 HTTP 调用失败：{response.status_code}")

        response_payload = response.json()
        response_data = response_payload.get("data") or []
        if not response_data or not isinstance(response_data[0], dict) or not response_data[0].get("b64_json"):
            raise ModelStreamError("图片编辑响应缺少 data[0].b64_json")

        return {
            "b64_json": response_data[0]["b64_json"],
            "revised_prompt": response_data[0].get("revised_prompt"),
            "quality": response_payload.get("quality"),
            "size": response_payload.get("size"),
            "output_format": response_payload.get("output_format") or output_format,
            "background": response_payload.get("background"),
            "usage": response_payload.get("usage"),
        }

    async def _stream_sse(self, path: str, payload: dict) -> AsyncIterator[dict]:
        """函数作用：发送流式请求并解析 SSE JSON 数据。
        输入参数：path - API 路径；payload - 请求体。
        输出参数：异步产出 JSON 数据。
        """
        settings = get_settings()
        read_timeout_seconds = max(float(getattr(settings, "model_stream_timeout_seconds", 180.0)), 1.0)
        timeout = httpx.Timeout(
            connect=min(read_timeout_seconds, 10.0),
            read=read_timeout_seconds,
            write=30.0,
            pool=30.0,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", self._api_url(path), headers=self._headers(), json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ModelStreamError(body.decode("utf-8", errors="ignore") or f"模型 HTTP 调用失败：{response.status_code}")

                data_lines = []
                async for line in response.aiter_lines():
                    if line == "":
                        if not data_lines:
                            continue

                        data_text = "\n".join(data_lines)
                        data_lines = []
                        if data_text == "[DONE]":
                            continue

                        try:
                            yield json.loads(data_text)
                        except json.JSONDecodeError:
                            continue
                        continue

                    if line.startswith("data:"):
                        data_lines.append(line.removeprefix("data:").strip())
                # 兜底异常情况：如果流式结束时还有未处理的 data_lines，尝试解析最后一次数据。
                if data_lines:
                    data_text = "\n".join(data_lines)
                    if data_text != "[DONE]":
                        try:
                            yield json.loads(data_text)
                        except json.JSONDecodeError:
                            return

    async def create_embedding(self, text: str) -> list[float]:
        """函数作用：调用 OpenAI 兼容 Embeddings API 生成文本向量。
        输入参数：text - 需要生成 embedding 的文本。
        输出参数：embedding 浮点数组。
        """
        self._validate_embedding_config()
        settings = get_settings()
        timeout_seconds = max(float(getattr(settings, "model_http_timeout_seconds", 60.0)), 1.0)
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0))) as client:
            response = await client.post(
                self._embedding_api_url("/embeddings"),
                headers=self._embedding_headers(),
                json={
                    "model": self.embedding_model,
                    "input": text,
                },
            )

        if response.status_code >= 400:
            raise ModelStreamError(response.text or f"模型 HTTP 调用失败：{response.status_code}")

        response = response.json()
        return list(response["data"][0]["embedding"])

    async def stream_chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """函数作用：流式调用 Chat Completions，并聚合本轮工具调用。
        输入参数：messages - 模型消息列表；tools - 可选工具定义列表。
        输出参数：异步产出 delta 事件，并在本轮结束时产出 completed 事件。
        """
        self._validate_config()
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        content_parts = []
        tool_call_buffers: dict[int, dict] = {}
        finish_reason = None

        try:
            async for chunk in self._stream_sse("/chat/completions", payload):
                choices = chunk.get("choices", [])
                for choice in choices:
                    delta = choice.get("delta") or {}
                    finish_reason = choice.get("finish_reason") or finish_reason

                    content = delta.get("content")
                    if content:
                        content_parts.append(content)
                        yield {"type": "delta", "delta": content}

                    for tool_call_delta in delta.get("tool_calls") or []:
                        index = int(tool_call_delta.get("index") or 0)
                        buffer = tool_call_buffers.setdefault(
                            index,
                            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                        )
                        if tool_call_delta.get("id"):
                            buffer["id"] += str(tool_call_delta.get("id"))
                        if tool_call_delta.get("type"):
                            buffer["type"] = str(tool_call_delta.get("type"))

                        function_delta = tool_call_delta.get("function") or {}
                        if function_delta.get("name"):
                            buffer["function"]["name"] += str(function_delta.get("name"))
                        if function_delta.get("arguments"):
                            buffer["function"]["arguments"] += str(function_delta.get("arguments"))

            tool_calls = [
                _normalize_tool_call(tool_call_buffers[index])
                for index in sorted(tool_call_buffers)
                if tool_call_buffers[index].get("id") and tool_call_buffers[index].get("function", {}).get("name")
            ]
            yield {
                "type": "completed",
                "content": "".join(content_parts),
                "tool_calls": tool_calls,
                "finish_reason": finish_reason,
            }
        except ModelConfigError:
            raise
        except ModelStreamError:
            raise
        except Exception as exc:
            raise ModelStreamError(str(exc)) from exc

    async def stream_text(self, messages: list[dict]) -> AsyncIterator[str]:
        """函数作用：按 Chat Completions 协议逐段产出文本增量。
        输入参数：messages - 发送给模型的结构化消息列表。
        输出参数：异步迭代返回文本 delta。
        """
        async for event in self.stream_chat_completion(messages):
            if event.get("type") == "delta" and event.get("delta"):
                yield event["delta"]
