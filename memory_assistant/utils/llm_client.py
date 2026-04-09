"""
LLM客户端
封装大语言模型API调用
"""
import os
from typing import List, Dict, Optional, AsyncGenerator, Any
import openai


class LLMClient:
    """LLM客户端类"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model = model or os.getenv("LLM_MODEL", "qwen3.5-flash")

        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def chat(self,
                   messages: List[Dict[str, str]],
                   temperature: float = 0.7,
                   max_tokens: int = 4096,
                   stream: bool = False) -> str:
        """
        对话接口

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大token数
            stream: 是否流式输出

        Returns:
            生成的文本
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )

            if stream:
                # 流式输出处理
                full_text = ""
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_text += chunk.choices[0].delta.content
                return full_text
            else:
                return response.choices[0].message.content

        except Exception as e:
            print(f"Error calling LLM: {e}")
            return f"抱歉，调用语言模型时出错: {str(e)}"

    async def chat_stream(self,
                         messages: List[Dict[str, str]],
                         temperature: float = 0.7,
                         max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """
        流式对话接口

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Yields:
            生成的文本片段
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            print(f"Error in stream chat: {e}")
            yield f"抱歉，调用语言模型时出错: {str(e)}"

    async def generate_with_memory(self,
                                   query: str,
                                   memories: List[Dict[str, Any]],
                                   user_profile: Optional[Dict] = None,
                                   system_prompt: str = None) -> str:
        """
        基于记忆生成回复

        Args:
            query: 用户查询
            memories: 相关记忆列表
            user_profile: 用户画像
            system_prompt: 系统提示词

        Returns:
            生成的回复
        """
        # 构建上下文
        context_parts = []

        # 添加系统提示
        if system_prompt:
            context_parts.append(f"系统设定：{system_prompt}")

        # 添加用户画像信息
        if user_profile:
            profile_info = self._format_profile(user_profile)
            if profile_info:
                context_parts.append(f"用户画像：{profile_info}")

        # 添加相关记忆
        if memories:
            context_parts.append("相关记忆：")
            for i, mem in enumerate(memories[:5], 1):
                entry = mem.get('entry')
                if entry:
                    context_parts.append(f"{i}. {entry.content}")

        # 构建完整消息
        messages = [
            {"role": "system", "content": "\n".join(context_parts)},
            {"role": "user", "content": query}
        ]

        return await self.chat(messages)

    def _format_profile(self, profile: Dict) -> str:
        """格式化用户画像"""
        parts = []

        # 话题偏好
        topic_prefs = profile.get('topic_preferences', [])
        if topic_prefs:
            top_topics = [t['topic'] for t in topic_prefs[:3]]
            parts.append(f"感兴趣的话题：{', '.join(top_topics)}")

        # 交互风格
        style = profile.get('interaction_style', {})
        if style:
            parts.append(f"喜欢{style.get('preferred_detail_level', 'balanced')}的回答")

        return "；".join(parts)

    async def extract_entities(self, text: str) -> List[str]:
        """
        从文本中提取实体

        Args:
            text: 输入文本

        Returns:
            实体列表
        """
        prompt = f"""请从以下文本中提取关键实体（人名、地点、组织、时间等），每行一个：

文本：{text}

实体列表："""

        messages = [
            {"role": "user", "content": prompt}
        ]

        response = await self.chat(messages, temperature=0.3)

        # 解析实体列表
        entities = [line.strip('- ').strip()
                    for line in response.split('\n')
                    if line.strip() and not line.startswith('文本')]

        return entities

    async def summarize(self, text: str, max_length: int = 200) -> str:
        """
        文本摘要

        Args:
            text: 输入文本
            max_length: 最大长度

        Returns:
            摘要文本
        """
        prompt = f"""请将以下文本总结为不超过{max_length}字的摘要：

{text}

摘要："""

        messages = [
            {"role": "user", "content": prompt}
        ]

        return await self.chat(messages, temperature=0.5, max_tokens=max_length)
