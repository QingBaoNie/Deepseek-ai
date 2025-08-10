import re
import json
from openai import OpenAI
from astrbot import logger
from astrbot.api.star import Context, Star, register
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from astrbot.api.event import filter
@register(
    "deepseek_chat",
    "YourName",
    "对接 DeepSeek API 的聊天插件，支持设定人格和主动回复",
    "v1.1.1"
)

class DeepSeekAI(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.base_url = config.get("base_url", "https://api.deepseek.com")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "deepseek-chat")
        self.keywords = config.get("keywords", [])
        logger.info(f"[DeepSeek] 插件已初始化，BaseURL: {self.base_url}，Model: {self.model}，API Key: {self.api_key[:8]}****")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event: AiocqhttpMessageEvent):
        """群聊消息关键词触发"""
        try:
            msg_text = event.message_str.strip()
            matched = [kw for kw in self.keywords if kw in msg_text]
            if not matched:
                return  # 无匹配关键词

            sender_name = event.sender.nickname or str(event.sender.user_id)
            logger.info(f"[DeepSeek] 命中关键词: {matched} | 发送者: {sender_name} | 消息: {msg_text}")

            prompt_messages = [
                {"role": "system", "content": "你是一个温柔、治愈、善解人意的暖心陪伴AI，会用温柔细腻的语言安慰和鼓励用户。"},
                {"role": "user", "content": msg_text}
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=prompt_messages,
                stream=False
            )

            reply_text = response.choices[0].message.content
            logger.info(f"[DeepSeek] 回复内容: {reply_text}")
            await event.send(f"[触发关键词: {', '.join(matched)} | 来自: {sender_name}]\n{reply_text}")

        except Exception as e:
            logger.error(f"[DeepSeek] 调用 API 失败: {e}")
            await event.send(f"[DeepSeek] 调用失败: {e}")
