import asyncio
from openai import OpenAI
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter
from astrbot.core.star.filter.event_message_type import EventMessageType
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

        # 读取配置（如果要直接写死 API Key 可以在这里改）
        self.enabled = self.config.get("enabled", True)
        self.base_url = self.config.get("api_url", "https://api.deepseek.com")
        self.api_key = self.config.get("api_key", "sk-710a5dff40774cc79882ce6e3e204e4c")
        self.model = self.config.get("model", "deepseek-chat")
        self.persona = self.config.get(
            "persona",
            "你是一个温柔、贴心并且会主动安慰用户的AI助手，聊天时语气友好，回答简洁"
        )
        self.timeout = int(self.config.get("timeout", 20))
        self.trigger_words = self.config.get("trigger_keywords", ["bot", "AI", "deepseek"])

        # 初始化 API 客户端
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    async def initialize(self):
        """插件初始化"""
        self.context.logger.info(
            f"[DeepSeek] 插件已加载 | BaseURL: {self.base_url} | Model: {self.model} | 关键词: {self.trigger_words}"
        )

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event: AiocqhttpMessageEvent):
        """被动监听群消息并回复"""
        if not self.enabled:
            return

        user_message = event.message_str.strip()
        sender_name = event.sender.nickname or str(event.sender.user_id)

        # 检查是否命中关键词
        hit_words = [w for w in self.trigger_words if w in user_message]
        if not hit_words:
            return

        self.context.logger.info(
            f"[DeepSeek] 检测到命中词: {hit_words} 来自: {sender_name} 正在提交API"
        )

        try:
            # 调用 API（在线程中执行，防止阻塞异步）
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
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
