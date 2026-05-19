# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
from app.prompts.chat import build_chat_system_prompt


def test_chat_system_prompt_contains_balanced_tool_and_memory_rules():
    """函数作用：验证系统提示词把记忆作为工具能力之一，并保留关键边界。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    prompt = build_chat_system_prompt()

    assert "主要目标是直接、准确、有帮助地回答用户当前问题" in prompt
    assert "记忆只是可用能力之一" in prompt
    assert "不要为了使用工具而使用工具" in prompt
    assert "如果当前上下文已经足够，直接回答" in prompt
    assert "默认使用 Markdown 组织回答" in prompt
    assert "**加粗小标题**" in prompt
    assert "避免整段大块纯文本" in prompt
    assert "必须调用 save_long_term_memory 或 update_long_term_memory" in prompt
    assert "不能只用自然语言承诺" in prompt
    assert "必须先调用 list_long_term_memory" in prompt
    assert "get_session_messages_by_position" in prompt
    assert "不要用 search_session_memory 猜" in prompt
    assert "先 search_session_memory" in prompt
    assert "只有工具调用成功后" in prompt
    assert "不要说“我已经记住了”" in prompt
    assert "敏感信息" in prompt
    assert "sports_basketball_preference" in prompt
