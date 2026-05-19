# 模块说明：后端测试模块，验证模型客户端流式解析、工具调用聚合和核心错误边界。
import asyncio
import json

import pytest

from app.services import model_client as model_client_module
from app.services.model_client import (
    ChatCompletionsModelClient,
    ModelConfigError,
    ModelStreamError,
    build_messages_with_tool_results,
)


class FakeHttpResponse:
    """类作用：模拟 httpx Response 与流式响应上下文。"""

    def __init__(self, json_data=None, lines=None, status_code=200, text=""):
        """函数作用：初始化 HTTP 响应桩。
        输入参数：json_data - JSON 响应；lines - SSE 行；status_code - HTTP 状态码；text - 文本响应。
        输出参数：无返回值。
        """
        self.json_data = json_data or {}
        self.lines = lines or []
        self.status_code = status_code
        self.text = text

    def json(self):
        """函数作用：返回 JSON 响应体。"""
        return self.json_data

    async def aread(self):
        """函数作用：返回流式错误响应体字节。"""
        return self.text.encode("utf-8")

    async def aiter_lines(self):
        """函数作用：逐行产出 SSE 响应。"""
        for line in self.lines:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class FakeAsyncClient:
    """类作用：模拟 httpx.AsyncClient。"""

    post_responses = []
    stream_response = FakeHttpResponse()
    requests = []
    captured_kwargs = None

    def __init__(self, **kwargs):
        """函数作用：记录 AsyncClient 初始化参数。"""
        FakeAsyncClient.captured_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, **kwargs):
        """函数作用：模拟非流式 POST 请求。"""
        FakeAsyncClient.requests.append(("POST", url, kwargs))
        return FakeAsyncClient.post_responses.pop(0)

    def stream(self, method, url, **kwargs):
        """函数作用：模拟流式请求上下文。"""
        FakeAsyncClient.requests.append((method, url, kwargs))
        return FakeAsyncClient.stream_response


def install_fake_http(monkeypatch, post_responses=None, stream_lines=None, stream_status=200, stream_text=""):
    """函数作用：安装模拟 HTTP 客户端。
    输入参数：monkeypatch - pytest monkeypatch fixture；post_responses - 非流式响应列表；stream_lines - SSE 行。
    输出参数：FakeAsyncClient 类。
    """
    FakeAsyncClient.post_responses = list(post_responses or [])
    FakeAsyncClient.stream_response = FakeHttpResponse(
        lines=stream_lines or [],
        status_code=stream_status,
        text=stream_text,
    )
    FakeAsyncClient.requests = []
    FakeAsyncClient.captured_kwargs = None
    monkeypatch.setattr(model_client_module.httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


def sse_data(payload: dict) -> list[str]:
    """函数作用：把 JSON 负载编码成一条 SSE data 事件。"""
    return [f"data: {json.dumps(payload, ensure_ascii=False)}", ""]


def test_model_client_maps_chat_completions_delta_events(monkeypatch):
    """函数作用：验证 Chat Completions SSE 文本块会被映射为 delta 事件。"""
    fake_http = install_fake_http(
        monkeypatch,
        stream_lines=[
            *sse_data({"choices": [{"delta": {"content": "你"}}]}),
            *sse_data({"choices": [{"delta": {"content": "好"}, "finish_reason": "stop"}]}),
            "data: [DONE]",
            "",
        ],
    )

    async def _helper_collect():
        client = ChatCompletionsModelClient(
            api_key="key",
            base_url="https://example.test/v1",
            model="test-model",
        )
        return [event async for event in client.stream_chat_completion([{"role": "user", "content": "hi"}])]

    events = asyncio.run(_helper_collect())

    assert events == [
        {"type": "delta", "delta": "你"},
        {"type": "delta", "delta": "好"},
        {"type": "completed", "content": "你好", "tool_calls": [], "finish_reason": "stop"},
    ]
    assert fake_http.captured_kwargs["timeout"] is not None
    assert fake_http.requests[0][1] == "https://example.test/v1/chat/completions"
    assert fake_http.requests[0][2]["json"] == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }
    assert fake_http.requests[0][2]["headers"]["Authorization"] == "Bearer key"


def test_model_client_aggregates_streaming_tool_call_deltas(monkeypatch):
    """函数作用：验证 Chat Completions 流式 tool call delta 会被聚合成完整工具调用。"""
    fake_http = install_fake_http(
        monkeypatch,
        stream_lines=[
            *sse_data(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call-",
                                        "type": "function",
                                        "function": {"name": "list_", "arguments": '{"limit"'},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ),
            *sse_data(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "1",
                                        "function": {"name": "long_term_memory", "arguments": ": 3}"},
                                    }
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                }
            ),
            "data: [DONE]",
            "",
        ],
    )

    async def _helper_collect():
        client = ChatCompletionsModelClient(
            api_key="key",
            base_url="https://example.test/v1",
            model="test-model",
        )
        return [
            event
            async for event in client.stream_chat_completion(
                [{"role": "user", "content": "hi"}],
                [{"type": "function", "function": {"name": "list_long_term_memory"}}],
            )
        ]

    events = asyncio.run(_helper_collect())

    assert events == [
        {
            "type": "completed",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "list_long_term_memory",
                        "arguments": {"limit": 3},
                        "arguments_text": '{"limit": 3}',
                    },
                }
            ],
            "finish_reason": "tool_calls",
        }
    ]
    assert fake_http.requests[0][2]["json"]["tools"] == [
        {"type": "function", "function": {"name": "list_long_term_memory"}}
    ]
    assert fake_http.requests[0][2]["json"]["tool_choice"] == "auto"


def test_model_client_requires_api_key():
    """函数作用：验证缺少 API Key 时抛出配置错误。"""
    async def _helper_collect():
        client = ChatCompletionsModelClient(
            api_key="",
            base_url="https://example.test/v1",
            model="test-model",
        )
        return [event async for event in client.stream_chat_completion([{"role": "user", "content": "hi"}])]

    with pytest.raises(ModelConfigError):
        asyncio.run(_helper_collect())


def test_model_client_maps_http_stream_error(monkeypatch):
    """函数作用：验证 HTTP 流式错误会转换为模型流错误。"""
    install_fake_http(monkeypatch, stream_status=500, stream_text="boom")

    async def _helper_collect():
        client = ChatCompletionsModelClient(
            api_key="key",
            base_url="https://example.test/v1",
            model="test-model",
        )
        return [event async for event in client.stream_chat_completion([{"role": "user", "content": "hi"}])]

    with pytest.raises(ModelStreamError):
        asyncio.run(_helper_collect())


def test_model_client_creates_embedding(monkeypatch):
    """函数作用：验证模型客户端能调用 Embeddings HTTP API。"""
    fake_http = install_fake_http(
        monkeypatch,
        post_responses=[FakeHttpResponse(json_data={"data": [{"embedding": [0.4, 0.5, 0.6]}]})],
    )

    async def _helper_create():
        client = ChatCompletionsModelClient(
            api_key="chat-key",
            base_url="https://chat.example.test/v1",
            model="test-model",
            embedding_api_key="embedding-key",
            embedding_base_url="https://embedding.example.test/v1",
            embedding_model="embedding-model",
        )
        return await client.create_embedding("你好")

    embedding = asyncio.run(_helper_create())

    assert embedding == [0.4, 0.5, 0.6]
    assert fake_http.requests[0][1] == "https://embedding.example.test/v1/embeddings"
    assert fake_http.requests[0][2]["headers"]["Authorization"] == "Bearer embedding-key"
    assert fake_http.requests[0][2]["json"] == {"model": "embedding-model", "input": "你好"}


def test_model_client_requires_embedding_api_key():
    """函数作用：验证缺少 Embedding API Key 时抛出配置错误。"""
    async def _helper_create():
        client = ChatCompletionsModelClient(
            api_key="chat-key",
            base_url="https://chat.example.test/v1",
            model="test-model",
            embedding_api_key="",
            embedding_base_url="https://embedding.example.test/v1",
            embedding_model="embedding-model",
        )
        return await client.create_embedding("你好")

    with pytest.raises(ModelConfigError, match="EMBEDDING_API_KEY 未配置"):
        asyncio.run(_helper_create())


def test_model_client_requires_embedding_base_url():
    """函数作用：验证缺少 Embedding base URL 时抛出配置错误。"""
    async def _helper_create():
        client = ChatCompletionsModelClient(
            api_key="chat-key",
            base_url="https://chat.example.test/v1",
            model="test-model",
            embedding_api_key="embedding-key",
            embedding_base_url="",
            embedding_model="embedding-model",
        )
        return await client.create_embedding("你好")

    with pytest.raises(ModelConfigError, match="EMBEDDING_BASE_URL 未配置"):
        asyncio.run(_helper_create())


def test_model_client_embedding_http_error_raises_model_stream_error(monkeypatch):
    """函数作用：验证 Embeddings HTTP 错误会抛出模型调用错误。"""
    install_fake_http(monkeypatch, post_responses=[FakeHttpResponse(status_code=500, text="embedding boom")])

    async def _helper_create():
        client = ChatCompletionsModelClient(
            api_key="chat-key",
            base_url="https://chat.example.test/v1",
            model="test-model",
            embedding_api_key="embedding-key",
            embedding_base_url="https://embedding.example.test/v1",
            embedding_model="embedding-model",
        )
        return await client.create_embedding("你好")

    with pytest.raises(ModelStreamError):
        asyncio.run(_helper_create())


def test_build_messages_with_tool_results_for_chat_completions():
    """函数作用：验证工具结果会生成 Chat Completions 所需的 assistant/tool 消息。"""
    messages = [{"role": "user", "content": "hi"}]
    assistant_tool_calls = [
        {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "list_long_term_memory",
                "arguments": {"limit": 1},
                "arguments_text": '{"limit": 1}',
            },
        }
    ]
    tool_results = [
        {
            "tool_call_id": "call-1",
            "output": '{"memories": []}',
        }
    ]

    next_messages = build_messages_with_tool_results(messages, assistant_tool_calls, tool_results)

    assert next_messages == [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "list_long_term_memory", "arguments": '{"limit": 1}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": '{"memories": []}'},
    ]
