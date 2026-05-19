# 模块说明：后端聊天工具模块，承接模型工具调用分发和具体工具执行逻辑。
import ast
import calendar
import re
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
            "name": "get_current_datetime",
            "description": "获取指定时区的当前日期、时间、星期和 UTC 偏移。用户询问今天几号、今天星期几、现在几点、当前年份等实时日期时间问题时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "IANA 时区名称，例如 Asia/Shanghai、UTC、America/New_York。默认 Asia/Shanghai。",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["full", "date", "time"],
                        "description": "返回信息粒度。full 返回完整日期时间；date 偏日期；time 偏时间。",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_expression",
            "description": "安全计算确定性数学表达式。用户询问四则运算、百分比、括号、幂、取模等精确计算时使用；不要使用模型心算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，例如 398 * 17.5 / 100、(12 + 8) * 3、2 ** 10。",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_units",
            "description": "进行确定性单位换算。支持常见长度、重量、面积、体积、数据大小和温度单位。",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {"type": "number", "description": "要换算的数值。"},
                    "from_unit": {"type": "string", "description": "源单位，例如 cm、厘米、kg、摄氏度、MB。"},
                    "to_unit": {"type": "string", "description": "目标单位，例如 m、米、lb、华氏度、GB。"},
                },
                "required": ["value", "from_unit", "to_unit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calendar_info",
            "description": "查询日期对应星期、闰年、当月天数，或进行日期加减。用户询问某天星期几、下周几是哪天、几天后日期等日历问题时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "基准日期，格式 YYYY-MM-DD；不传则按 timezone 取今天。",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "未传 date 时用于确定今天的 IANA 时区。默认 Asia/Shanghai。",
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["info", "add_days"],
                        "description": "info 返回日期信息；add_days 在基准日期上加减天数。",
                    },
                    "days_delta": {
                        "type": "integer",
                        "description": "operation 为 add_days 时使用；正数表示往后，负数表示往前。",
                    },
                },
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

    def _helper_decimal_to_text(value: Decimal) -> str:
        """函数作用：把 Decimal 结果格式化为适合工具返回的字符串。
        输入参数：value - Decimal 数值。
        输出参数：去掉无意义尾零后的字符串。
        """
        normalized = value.normalize()
        if normalized == normalized.to_integral():
            return str(normalized.quantize(Decimal("1")))
        return format(normalized, "f")

    def _helper_eval_decimal_expression(expression_text: str) -> Decimal:
        """函数作用：安全解析并计算数学表达式。
        输入参数：expression_text - 用户或模型传入的数学表达式。
        输出参数：Decimal 计算结果。
        """
        normalized_expression = expression_text.replace("×", "*").replace("÷", "/").replace("^", "**")
        normalized_expression = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", normalized_expression)
        tree = ast.parse(normalized_expression, mode="eval")

        def _helper_eval_node(node) -> Decimal:
            if isinstance(node, ast.Expression):
                return _helper_eval_node(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
                return Decimal(str(node.value))
            if isinstance(node, ast.UnaryOp):
                operand = _helper_eval_node(node.operand)
                if isinstance(node.op, ast.UAdd):
                    return operand
                if isinstance(node.op, ast.USub):
                    return -operand
            if isinstance(node, ast.BinOp):
                left = _helper_eval_node(node.left)
                right = _helper_eval_node(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Div):
                    if right == 0:
                        raise ValueError("除数不能为 0")
                    return left / right
                if isinstance(node.op, ast.Mod):
                    if right == 0:
                        raise ValueError("取模除数不能为 0")
                    return left % right
                if isinstance(node.op, ast.Pow):
                    if right != right.to_integral():
                        raise ValueError("幂运算指数必须是整数")
                    if abs(int(right)) > 1000:
                        raise ValueError("幂运算指数过大")
                    return left**int(right)
            raise ValueError("表达式包含不支持的内容")

        return _helper_eval_node(tree)

    def _helper_parse_decimal(value) -> Decimal:
        """函数作用：把工具参数中的数字转为 Decimal。
        输入参数：value - 数字或数字字符串。
        输出参数：Decimal 数值。
        """
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError("value 必须是有效数字") from None

    def _helper_normalize_unit(unit_text: str) -> str:
        """函数作用：归一化单位别名。
        输入参数：unit_text - 原始单位文本。
        输出参数：内部标准单位名。
        """
        aliases = {
            "毫米": "mm",
            "millimeter": "mm",
            "millimeters": "mm",
            "厘米": "cm",
            "公分": "cm",
            "centimeter": "cm",
            "centimeters": "cm",
            "米": "m",
            "公尺": "m",
            "meter": "m",
            "meters": "m",
            "公里": "km",
            "千米": "km",
            "kilometer": "km",
            "kilometers": "km",
            "英寸": "in",
            "inch": "in",
            "inches": "in",
            "英尺": "ft",
            "foot": "ft",
            "feet": "ft",
            "码": "yd",
            "yard": "yd",
            "yards": "yd",
            "英里": "mi",
            "mile": "mi",
            "miles": "mi",
            "毫克": "mg",
            "milligram": "mg",
            "milligrams": "mg",
            "克": "g",
            "gram": "g",
            "grams": "g",
            "千克": "kg",
            "公斤": "kg",
            "kilogram": "kg",
            "kilograms": "kg",
            "磅": "lb",
            "pound": "lb",
            "pounds": "lb",
            "盎司": "oz",
            "ounce": "oz",
            "ounces": "oz",
            "平方米": "m2",
            "平米": "m2",
            "平方厘米": "cm2",
            "平方公里": "km2",
            "平方英尺": "ft2",
            "毫升": "ml",
            "milliliter": "ml",
            "milliliters": "ml",
            "升": "l",
            "liter": "l",
            "liters": "l",
            "立方米": "m3",
            "加仑": "gal",
            "gallon": "gal",
            "gallons": "gal",
            "摄氏度": "c",
            "摄氏": "c",
            "celsius": "c",
            "华氏度": "f",
            "华氏": "f",
            "fahrenheit": "f",
            "开尔文": "k",
            "kelvin": "k",
        }
        cleaned_unit = unit_text.strip().lower().replace("²", "2").replace("³", "3")
        return aliases.get(cleaned_unit, cleaned_unit)

    def _helper_convert_units(value: Decimal, from_unit: str, to_unit: str) -> dict:
        """函数作用：执行常见单位换算。
        输入参数：value - 待换算数值；from_unit - 源单位；to_unit - 目标单位。
        输出参数：换算结果字典。
        """
        unit_groups = {
            "length": {
                "mm": Decimal("0.001"),
                "cm": Decimal("0.01"),
                "m": Decimal("1"),
                "km": Decimal("1000"),
                "in": Decimal("0.0254"),
                "ft": Decimal("0.3048"),
                "yd": Decimal("0.9144"),
                "mi": Decimal("1609.344"),
            },
            "mass": {
                "mg": Decimal("0.000001"),
                "g": Decimal("0.001"),
                "kg": Decimal("1"),
                "lb": Decimal("0.45359237"),
                "oz": Decimal("0.028349523125"),
            },
            "area": {
                "cm2": Decimal("0.0001"),
                "m2": Decimal("1"),
                "km2": Decimal("1000000"),
                "ft2": Decimal("0.09290304"),
            },
            "volume": {
                "ml": Decimal("0.001"),
                "l": Decimal("1"),
                "m3": Decimal("1000"),
                "gal": Decimal("3.785411784"),
            },
            "data_size": {
                "b": Decimal("1"),
                "kb": Decimal("1024"),
                "mb": Decimal("1048576"),
                "gb": Decimal("1073741824"),
                "tb": Decimal("1099511627776"),
            },
        }

        if from_unit in {"c", "f", "k"} or to_unit in {"c", "f", "k"}:
            if from_unit not in {"c", "f", "k"} or to_unit not in {"c", "f", "k"}:
                raise ValueError("温度单位只能与温度单位互相换算")
            kelvin = value + Decimal("273.15")
            if from_unit == "f":
                kelvin = (value - Decimal("32")) * Decimal("5") / Decimal("9") + Decimal("273.15")
            if from_unit == "k":
                kelvin = value
            result = kelvin - Decimal("273.15")
            if to_unit == "f":
                result = (kelvin - Decimal("273.15")) * Decimal("9") / Decimal("5") + Decimal("32")
            if to_unit == "k":
                result = kelvin
            return {"category": "temperature", "result": result}

        for category, units in unit_groups.items():
            if from_unit in units and to_unit in units:
                base_value = value * units[from_unit]
                return {"category": category, "result": base_value / units[to_unit]}

        raise ValueError("不支持的单位或源单位与目标单位类型不一致")

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

    if tool_name == "get_current_datetime":
        timezone_name = str(arguments.get("timezone") or "Asia/Shanghai").strip()
        response_format = str(arguments.get("format") or "full").strip()
        if response_format not in {"full", "date", "time"}:
            return {"error": "format 只能是 full、date 或 time"}
        try:
            current_datetime = datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            return {"error": "timezone 必须是有效的 IANA 时区名称"}

        weekday_zh_list = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return {
            "timezone": timezone_name,
            "format": response_format,
            "iso_datetime": current_datetime.isoformat(),
            "date": current_datetime.date().isoformat(),
            "time": current_datetime.strftime("%H:%M:%S"),
            "year": current_datetime.year,
            "month": current_datetime.month,
            "day": current_datetime.day,
            "weekday": current_datetime.strftime("%A"),
            "weekday_zh": weekday_zh_list[current_datetime.weekday()],
            "utc_offset": current_datetime.strftime("%z")[:3] + ":" + current_datetime.strftime("%z")[3:],
        }

    if tool_name == "calculate_expression":
        expression = str(arguments.get("expression") or "").strip()
        if not expression:
            return {"error": "expression 不能为空"}
        try:
            result = _helper_eval_decimal_expression(expression)
        except (SyntaxError, ValueError, InvalidOperation, OverflowError) as exc:
            return {"error": f"表达式无法计算：{exc}"}
        return {
            "expression": expression,
            "result": _helper_decimal_to_text(result),
        }

    if tool_name == "convert_units":
        try:
            value = _helper_parse_decimal(arguments.get("value"))
            from_unit = _helper_normalize_unit(str(arguments.get("from_unit") or ""))
            to_unit = _helper_normalize_unit(str(arguments.get("to_unit") or ""))
            if not from_unit or not to_unit:
                return {"error": "from_unit 和 to_unit 不能为空"}
            conversion = _helper_convert_units(value, from_unit, to_unit)
        except ValueError as exc:
            return {"error": str(exc)}
        return {
            "value": _helper_decimal_to_text(value),
            "from_unit": from_unit,
            "to_unit": to_unit,
            "category": conversion["category"],
            "result": _helper_decimal_to_text(conversion["result"]),
        }

    if tool_name == "calendar_info":
        timezone_name = str(arguments.get("timezone") or "Asia/Shanghai").strip()
        operation = str(arguments.get("operation") or "info").strip()
        if operation not in {"info", "add_days"}:
            return {"error": "operation 只能是 info 或 add_days"}

        date_text = str(arguments.get("date") or "").strip()
        try:
            if date_text:
                base_date = date.fromisoformat(date_text)
            else:
                base_date = datetime.now(ZoneInfo(timezone_name)).date()
        except ValueError:
            return {"error": "date 必须是 YYYY-MM-DD 格式"}
        except ZoneInfoNotFoundError:
            return {"error": "timezone 必须是有效的 IANA 时区名称"}

        target_date = base_date
        days_delta = 0
        if operation == "add_days":
            days_delta = int(arguments.get("days_delta") or 0)
            target_date = base_date + timedelta(days=days_delta)

        weekday_zh_list = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        _, days_in_month = calendar.monthrange(target_date.year, target_date.month)
        return {
            "operation": operation,
            "base_date": base_date.isoformat(),
            "days_delta": days_delta,
            "date": target_date.isoformat(),
            "year": target_date.year,
            "month": target_date.month,
            "day": target_date.day,
            "weekday": target_date.strftime("%A"),
            "weekday_zh": weekday_zh_list[target_date.weekday()],
            "is_leap_year": calendar.isleap(target_date.year),
            "days_in_month": days_in_month,
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
