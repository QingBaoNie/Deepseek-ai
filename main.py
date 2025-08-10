import asyncio
from typing import List
from openai import OpenAI
from astrbot import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
import astrbot.api.message_components as Comp


@register(
    "deepseek_chat",
    "Qing",
    "1.0.5",
    "对接 DeepSeek API 的聊天插件，支持设定人格和关键词触发主动引用回复"
)
class DeepSeekAI(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.context = context
        self.config = config

        self.enabled = bool(self.config.get("enabled", True))
        self.base_url = self.config.get("api_url", "https://api.deepseek.com")
        self.api_key = self.config.get("api_key", "sk-你的测试APIKey")
        self.model = self.config.get("model", "deepseek-chat")
        self.persona = self.config.get(
            "persona",
            "你是一个温柔、贴心并且会主动安慰用户的AI助手，聊天时语气友好，回答简洁"
        )
        self.trigger_words: List[str] = self.config.get(
            "trigger_keywords",
            ["机器人", "帮我", "难过", "你好", "在吗"]
        )

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event: AiocqhttpMessageEvent):
        if not self.enabled:
            return

        user_message = (getattr(event, "message_str", "") or "").strip()
        if not user_message:
            return

        if not any(w in user_message for w in self.trigger_words):
            return

        logger.info(f"[DeepSeek] 命中关键词，调用 API 处理中...")

        try:
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

            # 关键：转换 message_id 为 int，确保 CQHTTP 能引用
            try:
                msg_id = int(event.message_id)
            except ValueError:
                msg_id = event.message_id  # 如果无法转换，直接传原值

            yield event.chain_result([
                Comp.Reply(msg_id),
                Comp.Plain(reply_text)
            ])

        except Exception as e:
            logger.error(f"[DeepSeek] 调用 API 失败: {e}")
            try:
                msg_id = int(event.message_id)
            except ValueError:
                msg_id = event.message_id

            yield event.chain_result([
                Comp.Reply(msg_id),
                Comp.Plain(f"[DeepSeek] 调用失败: {e}")
            ])
