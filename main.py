import aiohttp
from astrbot import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter
from astrbot.core.star.filter.event_message_type import EventMessageType
from openai import OpenAI

@register(
    "deepseek_chat",
    "YourName",
    "对接 DeepSeek API 的聊天插件，支持设定人格和主动回复",
    "v1.1.1"
)

class DeepSeekChat(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.enabled = config.get("enabled", True)
        self.api_url = config.get("api_url", "https://api.deepseek.com")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "deepseek-chat")
        self.persona = config.get("persona", "你是一个温柔的暖心机器人")
        self.timeout = config.get("timeout", 15)
        self.trigger_keywords = config.get("trigger_keywords", [])

        # 初始化 DeepSeek 客户端
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_url)

        masked_key = self.api_key[:8] + "****" + self.api_key[-4:] if self.api_key else "未设置"
        logger.info(f"[DeepSeek] 插件已初始化，BaseURL: {self.api_url}，Model: {self.model}，API Key: {masked_key}")

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event):
        if not self.enabled:
            return

        text = str(event.message_obj)
        matched_keywords = [kw for kw in self.trigger_keywords if kw in text]

        if not matched_keywords:
            return

        logger.info(f"[DeepSeek] 命中关键词: {matched_keywords} | 消息: {text}")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.persona},
                    {"role": "user", "content": text}
                ],
                timeout=self.timeout
            )

            reply_text = response.choices[0].message.content
            logger.info(f"[DeepSeek] 回复内容: {reply_text}")

            await event.reply(reply_text)

        except Exception as e:
            logger.error(f"[DeepSeek] 调用 API 失败: {e}")
            await event.reply(f"[DeepSeek] 调用失败: {e}")
