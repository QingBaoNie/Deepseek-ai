import asyncio
import json
from openai import OpenAI
from astrbot import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent


@register(
    "deepseek_chat",
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
        self.base_url = self.config.get("api_url", "https://api.deepseek.com/v1")
        self.api_key = self.config.get("api_key", "sk-xxxxxxxxxxxxxxxx")
        self.model = self.config.get("model", "deepseek-chat")
        self.persona = self.config.get(
            "persona",
            "你是一个温柔、贴心并且会主动安慰用户的AI助手，聊天时语气友好，回答简洁"
        )
        self.timeout = int(self.config.get("timeout", 20))
        self.trigger_words = self.config.get("trigger_keywords", ["机器人", "帮我", "难过"])

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    async def initialize(self):
        logger.info(f"[DeepSeek] 插件已加载 | BaseURL: {self.base_url} | Model: {self.model} | 关键词: {self.trigger_words}")

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event: AiocqhttpMessageEvent):
        if not self.enabled:
            return

        user_message = (event.message_str or "").strip()

        sender_name = None
        if hasattr(event, "sender") and getattr(event, "sender", None):
            sender_name = getattr(event.sender, "nickname", None)
        if not sender_name and hasattr(event, "user_id"):
            sender_name = str(event.user_id)
        if not sender_name:
            sender_name = "未知用户"

        hit_words = [w for w in self.trigger_words if w in user_message]
        if not hit_words:
            return

        logger.info(f"[DeepSeek] 检测到命中词: {hit_words} 来自: {sender_name} 正在提交API")

        try:
            raw_response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": self.persona},
                    {"role": "user", "content": user_message}
                ],
                stream=False
            )

            # 兼容 AstrBot hook 返回 str 的情况
            if isinstance(raw_response, str):
                raw_response = json.loads(raw_response)

            reply_text = None
            if isinstance(raw_response, dict):
                reply_text = raw_response.get("choices", [{}])[0].get("message", {}).get("content")
            else:
                try:
                    reply_text = raw_response.choices[0].message.content
                except AttributeError:
                    choice = raw_response.choices[0]
                    reply_text = getattr(choice, "text", str(choice))

            reply_text = (reply_text or "").strip()
            if not reply_text:
                reply_text = "（DeepSeek 没有返回内容）"

            logger.info(f"[DeepSeek] 回复内容: {reply_text}")

            await event.send(reply_text)
            event.mark_handled()

        except Exception as e:
            logger.error(f"[DeepSeek] 调用 API 失败: {e}")
            try:
                await event.send(f"[DeepSeek] 调用失败: {e}")
                event.mark_handled()
            except:
                pass
