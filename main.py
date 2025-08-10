import asyncio
from openai import OpenAI
from astrbot import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from astrbot.core.platform.message.message_builder import MessageBuilder


@register(
    "deepseek_chat",
    "Qing",
    "1.0.1",
    "对接 DeepSeek API 的聊天插件，支持设定人格和关键词触发主动回复"
)
class DeepSeekAI(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.context = context
        self.config = config

        # === 基于 _conf_schema.json 的配置项 ===
        self.enabled: bool = self.config.get("enabled", True)
        # 注意：_conf_schema.json 默认是 https://api.deepseek.com（无 /v1）
        # DeepSeek 的 OpenAI 兼容接口路径为 /chat/completions，通常无需在 base_url 追加 /v1
        self.base_url: str = self.config.get("api_url", "https://api.deepseek.com")
        self.api_key: str = self.config.get("api_key", "sk-你的测试APIKey")
        self.model: str = self.config.get("model", "deepseek-chat")
        self.persona: str = self.config.get(
            "persona",
            "你是一个温柔、贴心并且会主动安慰用户的AI助手，聊天时语气友好，回答简洁"
        )
        self.timeout: int = int(self.config.get("timeout", 20))
        self.trigger_words: list[str] = self.config.get(
            "trigger_keywords",
            ["机器人", "帮我", "难过", "你好", "在吗"]
        )

        # DeepSeek API 客户端（OpenAI 兼容）
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    async def initialize(self):
        logger.info(
            f"[DeepSeek] 插件已加载 | Enabled: {self.enabled} | BaseURL: {self.base_url} | "
            f"Model: {self.model} | Timeout: {self.timeout}s | 关键词: {self.trigger_words}"
        )

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event: AiocqhttpMessageEvent):
        if not self.enabled:
            return

        user_message = (getattr(event, "message_str", "") or "").strip()
        if not user_message:
            return

        # 发送者昵称兜底
        sender_name = None
        if hasattr(event, "sender") and getattr(event, "sender", None):
            sender_name = getattr(event.sender, "card", None) or getattr(event.sender, "nickname", None)
        if not sender_name and hasattr(event, "user_id"):
            sender_name = str(event.user_id)
        sender_name = sender_name or "未知用户"

        # 关键词触发
        hit_words = [w for w in self.trigger_words if w and w in user_message]
        if not hit_words:
            return

        logger.info(f"[DeepSeek] 检测到命中词: {hit_words} 来自: {sender_name} 正在提交API")

        try:
            # OpenAI 同步 SDK 放到线程池执行，避免阻塞
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": self.persona},
                    {"role": "user", "content": user_message}
                ],
                stream=False,
                timeout=self.timeout  # 若你们的 SDK 不支持该参数，可去掉
            )

            # 解析回复内容
            reply_text = None
            try:
                reply_text = response.choices[0].message.content
            except AttributeError:
                # 兼容少数返回结构
                choice = response.choices[0]
                reply_text = getattr(choice, "text", str(choice))

            reply_text = (reply_text or "").strip() or "（DeepSeek 没有返回内容）"
            logger.info(f"[DeepSeek] 回复内容: {reply_text}")

            # 使用 MessageBuilder 构建平台消息对象（带 .chain）
            msg = MessageBuilder().text(reply_text).build()
            await event.send(msg)
            event.mark_handled()

        except Exception as e:
            logger.error(f"[DeepSeek] 调用 API 失败: {e}")
            try:
                err_msg = MessageBuilder().text(f"[DeepSeek] 调用失败: {e}").build()
                await event.send(err_msg)
                event.mark_handled()
            except:
                pass
