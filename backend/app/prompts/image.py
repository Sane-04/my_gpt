# 模块说明：后端提示词模块，构造 Image API 使用的图片生成与编辑提示词。


def build_image_generation_prompt(user_content: str) -> str:
    """函数作用：构造文生图提示词。
    输入参数：user_content - 用户原始图片需求。
    输出参数：增强后的图片生成提示词。
    """
    return f"""请根据用户需求生成高质量图片。

用户需求：
{user_content.strip()}

图片质量要求：
- high quality, detailed, polished, professional composition
- 主体清晰，构图稳定，光线自然或符合用户指定风格
- 背景干净，不杂乱
- 除非用户明确要求，否则不要出现文字、水印、Logo、签名
- 严格优先满足用户明确指定的主体、风格、颜色、比例和用途
"""


def build_image_edit_prompt(user_content: str) -> str:
    """函数作用：构造图像编辑提示词。
    输入参数：user_content - 用户原始编辑需求。
    输出参数：增强后的图片编辑提示词。
    """
    return f"""请根据用户需求编辑输入图片。

用户编辑需求：
{user_content.strip()}

编辑质量要求：
- 尽可能保留原图主体、构图、身份特征和整体一致性
- 只修改用户明确要求修改的部分
- high quality, detailed, polished, natural integration
- 除非用户明确要求，否则不要新增文字、水印、Logo、签名
- 如果用户要求换风格或换背景，保持主体清晰且边缘自然
"""
