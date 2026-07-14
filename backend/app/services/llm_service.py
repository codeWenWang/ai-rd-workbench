from app.config import settings
from app.services.openai_client import get_openai_client


class LLMService:
    def __init__(self):
        self.client = get_openai_client()
        self.model = settings.llm_model

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def summarize(self, conversation: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个对话摘要助手。请将以下对话历史压缩为简洁的中文摘要，"
                    "保留关键信息、用户偏好和重要结论，不超过200字。"
                ),
            },
            {"role": "user", "content": conversation},
        ]
        return self.chat(messages, temperature=0.3)

    def rewrite_query(self, query: str, context: str = "") -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个查询改写助手。根据用户原始问题和可选上下文，"
                    "生成一个更适合知识库检索的查询语句。只输出改写后的查询，不要解释。"
                ),
            },
            {
                "role": "user",
                "content": f"原始问题：{query}\n上下文：{context or '无'}",
            },
        ]
        return self.chat(messages, temperature=0.2)

    def generate_answer(
        self,
        query: str,
        rag_context: str,
        long_term_memory: str,
        short_term_context: str,
    ) -> str:
        system_prompt = """你是AI研发赋能平台的智能问答助手。请基于提供的知识库内容、长期记忆和对话历史，准确、专业地回答用户问题。

回答要求：
1. 优先使用检索到的知识库内容
2. 结合用户的长期记忆提供个性化回答
3. 如果知识库中没有相关信息，请诚实说明
4. 使用中文回答，条理清晰"""

        user_content = f"""## 知识库检索结果
{rag_context or '（无相关知识）'}

## 用户长期记忆
{long_term_memory or '（无长期记忆）'}

## 近期对话
{short_term_context or '（无历史对话）'}

## 用户问题
{query}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        return self.chat(messages)


llm_service = LLMService()
