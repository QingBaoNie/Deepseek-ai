import asyncio
import time
from typing import List, Dict
from openai import OpenAI
from astrbot import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent


@register(
    "deepseek_chat",
    "Qing",
    "1.1.2",
    "对接 DeepSeek API 的聊天插件，支持关键词、@触发和连续 5 秒跟进对话（自动刷新）"
)
class DeepSeekAI(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.context = context
        self.config = config

        self.enabled = bool(self.config.get("enabled", True))
        self.base_url = self.config.get("api_url", "https://api.deepseek.com")
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", "deepseek-chat")
        self.persona = self.config.get(
            "persona",
            "你叫萌物，是一个温柔、贴心、懂得倾听的朋友。"
            "你关心别人时会用简短而真诚的话，让人感到被理解和接纳。"
            "你表达关怀的方式自然、不做作，就像一个关心朋友的普通人一样。"
        )
        self.trigger_words: List[str] = self.config.get(
            "trigger_keywords",
            ["机器人", "帮我", "难过", "你好", "在吗"]
        )

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        # 记录最近触发用户的过期时间戳
        self.last_active: Dict[int, float] = {}

    def _get_message_id(self, event: AiocqhttpMessageEvent):
        """兼容不同版本 AstrBot / CQHTTP 的 message_id 获取"""
        if hasattr(event, "raw_event") and "message_id" in event.raw_event:
            return event.raw_event["message_id"]
        elif hasattr(event, "message") and hasattr(event.message, "message_id"):
            return event.message.message_id
        elif hasattr(event, "source") and hasattr(event.source, "message_id"):
            return event.source.message_id
        return None

    def _is_at_me(self, event: AiocqhttpMessageEvent) -> bool:
        """检测是否 @ 了机器人"""
        raw = getattr(event, "message_str", "") or ""
        if "[CQ:at" in raw:
            return True
        if "萌物" in raw:
            return True
        return False

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event: AiocqhttpMessageEvent):
        if not self.enabled:
            return

        user_message = (getattr(event, "message_str", "") or "").strip()
        if not user_message:
            return

        user_id = getattr(event, "user_id", None)
        now = time.time()

        # 判断触发条件：关键词 / @机器人 / 在 5 秒会话窗口内
        should_reply = False
        if any(w in user_message for w in self.trigger_words):
            should_reply = True
        elif self._is_at_me(event):
            should_reply = True
        elif user_id in self.last_active and now <= self.last_active[user_id]:
            should_reply = True

        if not should_reply:
            return

        # 刷新会话窗口为当前时间 + 5 秒
        if user_id:
            self.last_active[user_id] = now + 5

        logger.info(f"[DeepSeek] 触发条件满足，调用 API 处理中...")

        msg_id = self._get_message_id(event)

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

            if msg_id:
                yield event.plain_result(f"[CQ:reply,id={msg_id}]{reply_text}")
            else:
                yield event.plain_result(reply_text)

        except Exception as e:
            logger.error(f"[DeepSeek] 调用 API 失败: {e}")
            if msg_id:
                yield event.plain_result(f"[CQ:reply,id={msg_id}][DeepSeek] 调用失败: {e}")
            else:
                yield event.plain_result(f"[DeepSeek] 调用失败: {e}")
