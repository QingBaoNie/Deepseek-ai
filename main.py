import asyncio
from typing import List
from openai import OpenAI
from astrbot import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.filter.event_message_type import EventMessageType
import astrbot.api.message_components as Comp


@register(
    "deepseek_chat",
    "Qing",
    "DeepSeek 群聊关键词回复插件",
    "1.0.3",
    "https://github.com/QingBaoNie/Deepseek-ai"
)
class DeepSeekAI(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.context = context
        self.config = config

        # 插件配置（_conf_schema.json 支持）
        self.enabled = bool(config.get("enabled", True))
        self.base_url = config.get("api_url", "https://api.deepseek.com")
        self.api_key = config.get("api_key", "sk-your-key")
        self.model = config.get("model", "deepseek-chat")
        self.persona = config.get(
            "persona",
            "你是一个温柔、贴心并且会主动安慰用户的AI助手，聊天时语气友好，回答简洁"
        )
        self.trigger_words: List[str] = config.get(
            "trigger_keywords",
            ["机器人", "帮我", "难过", "你好", "在吗"]
        )

        # DeepSeek API 客户端
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event: AstrMessageEvent):
        """群聊关键词触发"""
        if not self.enabled:
            return

        user_message = event.message_str.strip()
        if not user_message:
            return

        # 检查关键词触发
        if not any(w in user_message for w in self.trigger_words):
            return

        logger.info(f"[DeepSeek] 命中关键词，调用 API 处理中...")

        try:
            # 调用 DeepSeek API（使用线程池避免阻塞）
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": self.persona},
                    {"role": "user", "content": user_message}
                ],
                stream=False
            )

            reply_text = (
                response.choices[0].message.content.strip()
                if hasattr(response.choices[0], "message")
                else getattr(response.choices[0], "text", "").strip()
            ) or "（DeepSeek 没有返回内容）"

            logger.info(f"[DeepSeek] 回复内容: {reply_text}")

            # 发送消息
            yield event.chain_result([Comp.Plain(reply_text)])
            event.mark_handled()

        except Exception as e:
            logger.error(f"[DeepSeek] 调用 API 失败: {e}")
            yield event.plain_result(f"[DeepSeek] 调用失败: {e}")
            event.mark_handled()
