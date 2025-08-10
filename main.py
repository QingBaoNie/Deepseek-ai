import aiohttp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.star.filter.event_message_type import EventMessageType


@register(
    "deepseek_chat",
    "YourName",
    "对接 DeepSeek API 的聊天插件，支持设定人格和主动回复",
    "v1.1.2"
)
class DeepSeekPlugin(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.api_url = config.get("api_url", "https://api.deepseek.com")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "deepseek-chat")
        self.persona = config.get("persona", "你是一个温柔的暖心机器人，会在聊天中主动安慰别人")
        self.timeout = config.get("timeout", 15)
        self.enabled = config.get("enabled", True)
        self.trigger_keywords = config.get("trigger_keywords", ["机器人", "帮我", "难过"])

    async def initialize(self):
        logger.info("[DeepSeek] 插件已初始化")

    @filter.command("chat")
    async def chat_command(self, event: AstrMessageEvent):
        """主动指令对话"""
        if not self.enabled:
            yield event.plain_result("❌ DeepSeek 对话功能已关闭")
            return

        user_input = event.message_str.strip()
        if not user_input:
            yield event.plain_result("请输入内容，例如：/chat 今天天气怎么样？")
            return

        reply = await self.get_deepseek_reply(user_input)
        yield event.plain_result(reply or "⚠️ 对话失败，请稍后再试")

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def passive_reply(self, event: AstrMessageEvent):
        """群聊内关键词 / @ 触发"""
        if not self.enabled:
            return

        text = event.message_str.strip()

        # 检查是否 @ 了 bot（兼容 OneBot v11）
        is_at_bot = any(
            m.type == "at" and str(m.data.get("qq")) == str(event.self_id)
            for m in event.message_obj.message_chain
        )

        # 只在 @ 或关键词时响应
        if is_at_bot or any(kw in text for kw in self.trigger_keywords):
            reply = await self.get_deepseek_reply(text)
            if reply:
                yield event.plain_result(reply)

    async def get_deepseek_reply(self, user_input: str) -> str:
        """调用 DeepSeek API 获取回复"""
        endpoint = f"{self.api_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.persona},
                {"role": "user", "content": user_input}
            ],
            "stream": False
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(endpoint, headers=headers, json=payload) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        logger.error(f"[DeepSeek] API 错误 {resp.status}: {data}")
                        return ""
                    if "choices" in data and data["choices"]:
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        logger.error(f"[DeepSeek] API 响应异常: {data}")
                        return ""
        except Exception as e:
            logger.error(f"[DeepSeek] API 调用失败: {e}")
            return ""

    async def terminate(self):
        logger.info("[DeepSeek] 插件已卸载")
