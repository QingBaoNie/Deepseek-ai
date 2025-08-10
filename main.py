import asyncio
from openai import OpenAI
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent


@register(
    "deepseek_chat",  # 和 metadata.yaml 保持一致
    "Qing",
    "1.0.0",
    "对接 DeepSeek API 的聊天插件，支持设定人格和关键词触发主动回复"
)
class DeepSeekAI(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.context = context
        self.config = config

        self.enabled = self.config.get("enabled", True)
        self.base_url = self.config.get("api_url", "https://api.deepseek.com")
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", "deepseek-chat")
        self.persona = self.config.get(
            "persona",
            "你是一个温柔、贴心并且会主动安慰用户的AI助手，聊天时语气友好，回答简洁"
        )
        self.timeout = int(self.config.get("timeout", 20))
        self.trigger_words = self.config.get("trigger_keywords", [])

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    async def on_load(self):
        # 确保 logger 可用后再输出
        self.context.logger.info(
            f"[DeepSeek] 插件已初始化，BaseURL: {self.base_url}，Model: {self.model}，关键词: {self.trigger_words}"
        )

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event: AiocqhttpMessageEvent):
        if not self.enabled:
            return

        try:
            user_message = event.message_str.strip()
            sender_name = event.sender.nickname or str(event.sender.user_id)

            hit_words = [w for w in self.trigger_words if w in user_message]
            if not hit_words:
                return

            self.context.logger.info(
                f"[DeepSeek] 检测到命中词: {hit_words} 来自: {sender_name} 正在提交API"
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.persona},
                    {"role": "user", "content": user_message}
                ],
                stream=False
            )

            reply_text = response.choices[0].message.content
            self.context.logger.info(f"[DeepSeek] 回复内容: {reply_text}")

            await event.send(reply_text)

        except Exception as e:
            self.context.logger.error(f"[DeepSeek] 调用 API 失败: {e}")
            try:
                await event.send(f"[DeepSeek] 调用失败: {e}")
            except:
                pass
