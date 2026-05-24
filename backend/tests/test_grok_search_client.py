# 模块说明：后端测试模块，验证 Grok 搜索客户端请求、解析和错误边界。
import asyncio

import pytest

from app.services import grok_search_client as grok_search_client_module
from app.services.grok_search_client import GrokSearchClient, GrokSearchConfigError, GrokSearchRequestError


class FakeHttpResponse:
    """类作用：模拟 Grok HTTP 响应。"""

    def __init__(self, json_data=None, status_code=200, text=""):
        """函数作用：初始化模拟响应。
        输入参数：json_data - JSON 响应；status_code - HTTP 状态码；text - 错误文本。
        输出参数：无返回值。
        """
        self.json_data = json_data
        self.status_code = status_code
        self.text = text

    def json(self):
        """函数作用：返回 JSON 响应。"""
        if isinstance(self.json_data, Exception):
            raise self.json_data
        return self.json_data or {}


class FakeAsyncClient:
    """类作用：模拟 httpx.AsyncClient。"""

    post_responses = []
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
        """函数作用：模拟 POST 请求。"""
        FakeAsyncClient.requests.append(("POST", url, kwargs))
        response = FakeAsyncClient.post_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def install_fake_http(monkeypatch, responses):
    """函数作用：安装 Grok 搜索测试 HTTP 客户端。
    输入参数：monkeypatch - pytest monkeypatch fixture；responses - 模拟响应列表。
    输出参数：无返回值。
    """
    FakeAsyncClient.post_responses = list(responses)
    FakeAsyncClient.requests = []
    FakeAsyncClient.captured_kwargs = None
    monkeypatch.setattr(grok_search_client_module.httpx, "AsyncClient", FakeAsyncClient)


def test_grok_search_client_sends_web_search_request(monkeypatch):
    """函数作用：验证 Grok 搜索客户端发送 web_search 请求并解析来源。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    install_fake_http(
        monkeypatch,
        [
            FakeHttpResponse(
                {
                    "choices": [{"message": {"content": "这是 Grok 搜索回答。"}}],
                    "citations": [
                        {
                            "title": "来源标题",
                            "url": "https://example.com/news",
                            "snippet": "来源摘要",
                        }
                    ],
                }
            )
        ],
    )
    client = GrokSearchClient(
        api_key="grok-key",
        base_url="https://api.x.ai/v1",
        model="grok-4.3",
        max_results=3,
    )

    async def _helper_search():
        return await client.search("今天有什么新闻", "web")

    result = asyncio.run(_helper_search())

    assert result["answer"] == "这是 Grok 搜索回答。"
    assert result["sources"][0]["domain"] == "example.com"
    assert result["model"] == "grok-4.3"
    method, url, kwargs = FakeAsyncClient.requests[0]
    assert method == "POST"
    assert url == "https://api.x.ai/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer grok-key"
    assert kwargs["json"]["tools"][0]["type"] == "web_search"
    assert kwargs["json"]["tools"][0]["search_parameters"]["max_search_results"] == 3
    assert "只返回严格 JSON" in kwargs["json"]["messages"][0]["content"]


def test_grok_search_client_parses_structured_json_content(monkeypatch):
    """函数作用：验证 Grok 结构化 JSON content 能解析出来源标题。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    install_fake_http(
        monkeypatch,
        [
            FakeHttpResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"answer":"OpenAI 发布了新闻。[[cite:src_1]]",'
                                    '"sources":[{"id":"src_1","title":"OpenAI News","url":"https://openai.com/news/","domain":"openai.com","snippet":"官方新闻页"}]}'
                                )
                            }
                        }
                    ]
                }
            )
        ],
    )
    client = GrokSearchClient(api_key="grok-key", base_url="https://api.x.ai/v1", model="grok-4.3")

    async def _helper_search():
        return await client.search("OpenAI 新闻", "web")

    result = asyncio.run(_helper_search())

    assert result["answer"] == "OpenAI 发布了新闻。[[cite:src_1]]"
    assert result["sources"] == [
        {
            "id": "src_1",
            "title": "OpenAI News",
            "url": "https://openai.com/news/",
            "domain": "openai.com",
            "snippet": "官方新闻页",
        }
    ]


def test_grok_search_client_parses_fenced_json_content(monkeypatch):
    """函数作用：验证 fenced JSON content 能被解析。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    install_fake_http(
        monkeypatch,
        [
            FakeHttpResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    "```json\n"
                                    '{"answer":"带代码块的回答。[[cite:src_1]]","sources":[{"title":"Example","url":"https://example.com/a","snippet":"摘要"}]}'
                                    "\n```"
                                )
                            }
                        }
                    ]
                }
            )
        ],
    )
    client = GrokSearchClient(api_key="grok-key", base_url="https://api.x.ai/v1", model="grok-4.3")

    async def _helper_search():
        return await client.search("测试", "web")

    result = asyncio.run(_helper_search())

    assert result["answer"] == "带代码块的回答。[[cite:src_1]]"
    assert result["sources"][0]["id"] == "src_1"
    assert result["sources"][0]["title"] == "Example"
    assert result["sources"][0]["domain"] == "example.com"


def test_grok_search_client_structured_source_fallbacks(monkeypatch):
    """函数作用：验证结构化来源缺 title/domain 时使用 URL 兜底。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    install_fake_http(
        monkeypatch,
        [
            FakeHttpResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"answer":"兜底来源。[[cite:src_1]]",'
                                    '"sources":[{"url":"https://www.example.com/path/to/article"}]}'
                                )
                            }
                        }
                    ]
                }
            )
        ],
    )
    client = GrokSearchClient(api_key="grok-key", base_url="https://api.x.ai/v1", model="grok-4.3")

    async def _helper_search():
        return await client.search("测试", "web")

    result = asyncio.run(_helper_search())

    assert result["sources"][0]["id"] == "src_1"
    assert result["sources"][0]["domain"] == "example.com"
    assert result["sources"][0]["title"] == "example.com/path/to/article"


def test_grok_search_client_sends_x_search_request(monkeypatch):
    """函数作用：验证 x 模式使用 x_search 工具。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    install_fake_http(monkeypatch, [FakeHttpResponse({"choices": [{"message": {"content": "X 搜索回答"}}]})])
    client = GrokSearchClient(api_key="grok-key", base_url="https://api.x.ai/v1", model="grok-4.3")

    async def _helper_search():
        return await client.search("AI 圈在讨论什么", "x")

    asyncio.run(_helper_search())

    assert FakeAsyncClient.requests[0][2]["json"]["tools"][0]["type"] == "x_search"


def test_grok_search_client_requires_api_key():
    """函数作用：验证 Grok API Key 缺失时抛出配置错误。
    输入参数：无。
    输出参数：无返回值。
    """
    client = GrokSearchClient(api_key="", base_url="https://api.x.ai/v1", model="grok-4.3")

    with pytest.raises(GrokSearchConfigError):
        client._validate_config()


def test_grok_search_client_http_error_raises_request_error(monkeypatch):
    """函数作用：验证 Grok HTTP 错误会转为请求错误。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    install_fake_http(monkeypatch, [FakeHttpResponse(status_code=500, text="upstream error")])
    client = GrokSearchClient(api_key="grok-key", base_url="https://api.x.ai/v1", model="grok-4.3")

    async def _helper_search():
        return await client.search("测试", "web")

    with pytest.raises(GrokSearchRequestError, match="upstream error"):
        asyncio.run(_helper_search())


def test_grok_search_client_invalid_response_raises_request_error(monkeypatch):
    """函数作用：验证缺少回答内容时返回响应错误。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    install_fake_http(monkeypatch, [FakeHttpResponse({"choices": [{"message": {"content": ""}}]})])
    client = GrokSearchClient(api_key="grok-key", base_url="https://api.x.ai/v1", model="grok-4.3")

    async def _helper_search():
        return await client.search("测试", "web")

    with pytest.raises(GrokSearchRequestError, match="缺少回答内容"):
        asyncio.run(_helper_search())
