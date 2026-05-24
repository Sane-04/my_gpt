# 模块说明：Grok 搜索提示词模块，集中管理聊天联网搜索 provider 使用的提示词。


def build_grok_search_system_prompt() -> str:
    """函数作用：构造 Grok 搜索工具的系统提示词。
    输入参数：无。
    输出参数：要求 Grok 返回结构化 JSON 来源的系统提示词。
    """
    return (
        "你是聊天系统的 Grok 搜索工具。请基于搜索结果直接回答，并且只返回严格 JSON，不要使用 Markdown 代码块以外的解释。"
        "JSON 格式必须是：{\"answer\":\"回答正文，引用来源时使用 [[cite:src_1]]\",\"sources\":[{\"id\":\"src_1\",\"title\":\"来源标题\",\"url\":\"https://example.com\",\"domain\":\"example.com\",\"snippet\":\"一句话摘要\"}]}。"
        "sources 必须尽量包含真实网页标题、URL、域名和摘要；如果引用了来源，answer 中必须使用对应的 [[cite:src_n]] 标记。"
    )
