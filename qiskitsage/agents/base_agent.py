from abc import ABC, abstractmethod
from typing import List
from ..context_graph import ContextGraph
from ..models import Finding

class BaseAgent(ABC):
    agent_id: str = 'BASE'

    def __init__(self):
        import ollama
        from .. import config
        # Create a client pointing to the specific base url
        host = config.OLLAMA_BASE_URL.replace('/v1', '')
        self.client = ollama.Client(host=host)
        self.model = config.OLLAMA_MODEL
        self.max_tokens = config.LLM_MAX_TOKENS
        self.temperature = config.LLM_TEMPERATURE

    def _llm_call(self, system: str, user_prompt: str) -> str:
        """
        Unified LLM call using native Ollama client.
        Returns the raw text content of the response.
        """
        resp = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            format='json',
            options={
                "temperature": self.temperature,
                "num_predict": self.max_tokens
            }
        )
        content = resp.get('message', {}).get('content', '')
        # print(f"DEBUG LLM OUTPUT: {content}")
        return content

    @abstractmethod
    def review(self, graph: ContextGraph) -> List[Finding]:
        ...

    def _safe_review(self, graph: ContextGraph) -> List[Finding]:
        """Safe wrapper that catches all exceptions."""
        try:
            return self.review(graph)
        except Exception as e:
            print(f'[{self.agent_id}] Error: {e}')
            return []
