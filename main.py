import aiohttp
import asyncio
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register(
    "deepseek_chat",
    "YourName",
    "对接 DeepSeek API 的聊天插件，支持设定人格和主动回复",
    "v1.0.0"
)
class DeepSeekPlugin(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.api_url = config.get("api_url", "https://api.deepseek.com/v1/chat/completions")
        self.api_key = config.get("api_key", "")
        self.persona = config.get("persona", "你是一个温柔的暖心机器人，会在聊天中主动安慰别人")
        self.timeout = config.get("timeout", 15)
        self.enabled = config.get("enabled", True)


    async def initialize(self):
        logger.info("[DeepSeek] 插件已初始化")
    
    @filter.command("chat")
    async def chat_command(self, event: AstrMessageEvent):
        """与 DeepSeek 对话"""
        if not self.enabled:
            yield event.plain_result("❌ DeepSeek 对话功能已关闭")
            return
        
        user_input = event.message_str.strip()
        if not user_input:
            yield event.plain_result("请输入内容，例如：/chat 今天天气怎么样？")
            return

        reply = await self.get_deepseek_reply(user_input)
        if reply:
            yield event.plain_result(reply)
        else:
            yield event.plain_result("⚠️ 对话失败，请稍后再试")

    @filter.event_message_type("group_message")  # 群聊内的被动回复
    async def passive_reply(self, event: AstrMessageEvent):
        """在群里触发被动对话"""
        if not self.enabled:
            return

        text = event.message_str.strip()
        # 简单触发条件：被 @ 或包含关键字
        if event.is_at_me() or "机器人" in text:
            reply = await self.get_deepseek_reply(text)
            if reply:
                yield event.plain_result(reply)

    async def get_deepseek_reply(self, user_input: str) -> str:
        """调用 DeepSeek API 获取回复"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": self.persona},
                {"role": "user", "content": user_input}
            ]
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.api_url, headers=headers, json=payload) as resp:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"[DeepSeek] API 调用失败: {e}")
            return ""

    async def terminate(self):
        logger.info("[DeepSeek] 插件已卸载")
