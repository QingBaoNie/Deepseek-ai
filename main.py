import asyncio
from openai import OpenAI
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

# === 硬编码 DeepSeek 配置 ===
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_API_KEY = "sk-710a5dff40774cc79882ce6e3e204e4c"
DEEPSEEK_MODEL = "deepseek-chat"

# === 关键词列表 ===
TRIGGER_WORDS = ["难过", "开心", "无聊", "失眠", "难受"]

# 初始化客户端
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


@register(
    name="deepseek_ai",
    author="Qing",
    version="1.0.0"
)
class DeepSeekAI(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
        self.trigger_words = TRIGGER_WORDS
        self.model = DEEPSEEK_MODEL
        self.logger.info(f"[DeepSeek] 插件已初始化，BaseURL: {DEEPSEEK_BASE_URL}，Model: {self.model}")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event: AiocqhttpMessageEvent):
        try:
            user_message = event.message_str.strip()
            sender_name = event.sender.nickname or str(event.sender.user_id)

            # 检测关键词
            hit_words = [w for w in self.trigger_words if w in user_message]
            if not hit_words:
                return

            # 日志输出
            self.logger.info(f"[DeepSeek] 检测到命中词: {hit_words} 来自: {sender_name} 正在提交API")

            # 调用 DeepSeek API
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个温暖治愈的聊天伙伴"},
                    {"role": "user", "content": user_message}
                ],
                stream=False
            )

            reply_text = response.choices[0].message.content
            self.logger.info(f"[DeepSeek] 回复内容: {reply_text}")

            # 发送回复
            await event.send(reply_text)

        except Exception as e:
            self.logger.error(f"[DeepSeek] 调用 API 失败: {e}")
            try:
                await event.send(f"[DeepSeek] 调用失败: {e}")
            except:
                pass
