# 模块说明：后端提示词模块，构造图片意图识别请求。
import json


def build_image_intent_messages(recent_messages: list[dict], current_message: dict) -> list[dict]:
    """函数作用：构造图片意图识别模型消息。
    输入参数：recent_messages - 最近会话消息摘要；current_message - 当前用户消息摘要。
    输出参数：Chat Completions 消息列表。
    """
    system_prompt = """你是聊天请求路由器，只能返回严格 JSON，不要输出 Markdown 或解释。

请判断当前用户请求属于哪一种：
- chat：普通聊天、解释、代码、分析图片但不要求生成或修改图片、搜索、记忆、闲聊。
- image_generate：用户明确要求生成、画、制作、设计一张新图片、海报、头像、插画、产品图等。
- image_edit：用户要求修改、调整、换背景、换风格、加元素、去元素、继续改上一张图，且当前消息上传了图片或最近上下文存在可编辑图片。

保守规则：
1. 不确定时返回 chat。
2. 用户只是问“这张图是什么/分析一下图片/图片里有什么”时返回 chat。
3. 用户说“上一张、刚才那张、把它、继续、再换成、改成”且最近上下文有生成图时返回 image_edit。
4. 用户上传图片并要求修改、换背景、换风格、生成参考图时返回 image_edit。

返回 JSON 格式：
{"intent":"chat|image_generate|image_edit","confidence":"low|medium|high","reason":"简短中文原因","requiresPreviousImage":false,"usesUploadedImages":false}
"""
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "recentMessages": recent_messages,
                    "currentMessage": current_message,
                },
                ensure_ascii=False,
            ),
        },
    ]
