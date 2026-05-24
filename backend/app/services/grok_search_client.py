# 模块说明：后端 Grok 搜索客户端，封装聊天联网搜索工具使用的 xAI/Grok 调用。
import json
import re
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.prompts.grok_search import build_grok_search_system_prompt


class GrokSearchConfigError(Exception):
    """类作用：表示 Grok 搜索配置缺失。"""


class GrokSearchRequestError(Exception):
    """类作用：表示 Grok 搜索请求或响应失败。"""


class GrokSearchClient:
    """类作用：封装 Grok 搜索请求。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_results: int | None = None,
    ):
        """函数作用：初始化 Grok 搜索客户端。
        输入参数：api_key - Grok API Key；base_url - Grok API 地址；model - Grok 搜索模型；timeout_seconds - 请求超时；max_results - 来源数量上限。
        输出参数：无返回值。
        """
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.grok_api_key
        self.base_url = base_url if base_url is not None else settings.grok_base_url
        self.model = model if model is not None else settings.grok_search_model
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.grok_search_timeout_seconds
        )
        self.max_results = max_results if max_results is not None else settings.grok_search_max_results

    def _validate_config(self) -> None:
        """函数作用：校验 Grok 搜索配置。
        输入参数：无。
        输出参数：无返回值；配置缺失时抛出 GrokSearchConfigError。
        """
        if not self.api_key:
            raise GrokSearchConfigError("GROK_API_KEY 未配置")
        if not self.base_url:
            raise GrokSearchConfigError("GROK_BASE_URL 未配置")
        if not self.model:
            raise GrokSearchConfigError("GROK_SEARCH_MODEL 未配置")

    def _api_url(self) -> str:
        """函数作用：拼接 Grok Chat Completions 兼容接口地址。
        输入参数：无。
        输出参数：完整 API URL。
        """
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _headers(self) -> dict[str, str]:
        """函数作用：构造 Grok HTTP 请求头。
        输入参数：无。
        输出参数：包含鉴权和 JSON 类型的请求头。
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_tools(self, mode: str) -> list[dict]:
        """函数作用：按搜索模式构造 Grok 搜索工具列表。
        输入参数：mode - web、x 或 auto。
        输出参数：Grok 搜索工具定义列表。
        """
        tool_type = "x_search" if mode == "x" else "web_search"
        return [
            {
                "type": tool_type,
                "search_parameters": {
                    "max_search_results": max(int(self.max_results), 1),
                },
            }
        ]

    def _normalize_source(self, raw_source: dict) -> dict | None:
        """函数作用：把 Grok 返回的来源对象归一化为前端字段。
        输入参数：raw_source - Grok 响应中的来源对象。
        输出参数：来源字典；没有 URL 时返回 None。
        """
        url = str(raw_source.get("url") or raw_source.get("link") or "").strip()
        if not url:
            return None

        title = str(raw_source.get("title") or raw_source.get("name") or "").strip() or None
        snippet = str(raw_source.get("snippet") or raw_source.get("content") or raw_source.get("text") or "").strip()
        domain = str(raw_source.get("domain") or "").strip()
        if not domain:
            domain = urlparse(url).netloc.removeprefix("www.") or None

        return {
            "title": title,
            "url": url,
            "domain": domain,
            "snippet": snippet or None,
        }

    def _extract_json_object_text(self, content: str) -> str | None:
        """函数作用：从 Grok 文本中提取 JSON 对象文本。
        输入参数：content - Grok 返回的原始文本。
        输出参数：JSON 对象字符串；找不到时返回 None。
        """
        stripped_content = content.strip()
        if not stripped_content:
            return None

        if stripped_content.startswith("{") and stripped_content.endswith("}"):
            return stripped_content

        fenced_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", stripped_content, re.IGNORECASE)
        if fenced_match:
            return fenced_match.group(1).strip()

        start_index = stripped_content.find("{")
        end_index = stripped_content.rfind("}")
        if start_index != -1 and end_index > start_index:
            return stripped_content[start_index : end_index + 1]

        return None

    def _normalize_structured_source(self, raw_source: dict, index: int) -> dict | None:
        """函数作用：标准化 Grok 结构化 JSON 中的来源。
        输入参数：raw_source - 来源对象；index - 来源序号。
        输出参数：标准来源字典；缺 URL 时返回 None。
        """
        url = str(raw_source.get("url") or raw_source.get("link") or "").strip()
        if not url:
            return None

        domain = str(raw_source.get("domain") or "").strip()
        if not domain:
            domain = urlparse(url).netloc.removeprefix("www.") or url

        title = str(raw_source.get("title") or "").strip()
        if not title:
            parsed_path = urlparse(url).path.strip("/")
            title = f"{domain}/{parsed_path}" if parsed_path else domain

        return {
            "id": str(raw_source.get("id") or f"src_{index}").strip() or f"src_{index}",
            "title": title,
            "url": url,
            "domain": domain,
            "snippet": str(raw_source.get("snippet") or "").strip(),
        }

    def _parse_structured_content(self, content: str) -> dict | None:
        """函数作用：解析 Grok 按约定返回的结构化 JSON 内容。
        输入参数：content - Grok message content。
        输出参数：包含 answer 和 sources 的字典；解析失败返回 None。
        """
        json_text = self._extract_json_object_text(content)
        if not json_text:
            return None

        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        answer = str(payload.get("answer") or "").strip()
        if not answer:
            return None

        sources = []
        seen_urls = set()
        for index, raw_source in enumerate(payload.get("sources") or [], start=1):
            if not isinstance(raw_source, dict):
                continue

            source = self._normalize_structured_source(raw_source, index)
            if not source or source["url"] in seen_urls:
                continue

            seen_urls.add(source["url"])
            sources.append(source)

        return {
            "answer": answer,
            "sources": sources[: max(int(self.max_results), 1)],
        }

    def _extract_sources(self, response_payload: dict) -> list[dict]:
        """函数作用：从 Grok 响应中尽量提取搜索来源。
        输入参数：response_payload - Grok API JSON 响应。
        输出参数：归一化后的来源列表。
        """
        candidates = []
        for key in ["citations", "search_results", "sources"]:
            raw_items = response_payload.get(key)
            if isinstance(raw_items, list):
                candidates.extend(item for item in raw_items if isinstance(item, dict))

        choices = response_payload.get("choices") or []
        for choice in choices:
            if not isinstance(choice, dict):
                continue

            message = choice.get("message") or {}
            if not isinstance(message, dict):
                continue

            for key in ["citations", "search_results", "sources"]:
                raw_items = message.get(key)
                if isinstance(raw_items, list):
                    candidates.extend(item for item in raw_items if isinstance(item, dict))

        normalized_sources = []
        seen_urls = set()
        for candidate in candidates:
            source = self._normalize_source(candidate)
            if not source or not source["url"] or source["url"] in seen_urls:
                continue

            seen_urls.add(source["url"])
            normalized_sources.append(source)

        return normalized_sources[: max(int(self.max_results), 1)]

    def _extract_answer(self, response_payload: dict) -> str:
        """函数作用：从 Grok Chat Completions 响应中提取回答文本。
        输入参数：response_payload - Grok API JSON 响应。
        输出参数：回答文本。
        """
        choices = response_payload.get("choices") or []
        if not choices:
            return ""

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "".join(parts).strip()

        return ""

    async def search(self, query: str, mode: str) -> dict:
        """函数作用：执行一次 Grok 搜索并返回标准化结果。
        输入参数：query - 搜索问题；mode - web、x 或 auto。
        输出参数：包含 answer、sources 和 model 的字典。
        """
        self._validate_config()
        search_mode = mode if mode in {"web", "x", "auto"} else "web"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": build_grok_search_system_prompt(),
                },
                {"role": "user", "content": query},
            ],
            "tools": self._build_tools(search_mode),
            "tool_choice": "auto",
            "stream": False,
        }
        timeout_seconds = max(float(self.timeout_seconds), 1.0)

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0))) as client:
                response = await client.post(self._api_url(), headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise GrokSearchRequestError("Grok 搜索请求超时") from exc
        except httpx.RequestError as exc:
            raise GrokSearchRequestError(f"Grok 搜索请求失败：{exc}") from exc

        if response.status_code >= 400:
            raise GrokSearchRequestError(response.text or f"Grok 搜索 HTTP 调用失败：{response.status_code}")

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise GrokSearchRequestError("Grok 搜索返回了无法解析的响应") from exc

        answer = self._extract_answer(response_payload)
        if not answer:
            raise GrokSearchRequestError("Grok 搜索响应缺少回答内容")

        structured_result = self._parse_structured_content(answer)
        if structured_result:
            return {
                "answer": structured_result["answer"],
                "sources": structured_result["sources"],
                "model": self.model,
            }

        return {
            "answer": answer,
            "sources": self._extract_sources(response_payload),
            "model": self.model,
        }
