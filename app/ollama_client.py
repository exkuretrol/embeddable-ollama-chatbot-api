import httpx

from app.config import Settings
from app.schemas import ChatMessage


class OllamaClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def health_check(self) -> bool:
        url = f"{self._settings.ollama_base_url.rstrip('/')}/api/tags"
        timeout = httpx.Timeout(self._settings.health_timeout)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        models = data.get("models", [])
        names = {
            item.get("name")
            for item in models
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        return self._settings.ollama_model in names

    async def chat(self, messages: list[ChatMessage]) -> str:
        url = f"{self._settings.ollama_base_url.rstrip('/')}/api/chat"
        timeout = httpx.Timeout(self._settings.request_timeout)
        payload = {
            "model": self._settings.ollama_model,
            "stream": False,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        message = data.get("message")
        if not isinstance(message, dict):
            raise ValueError("Ollama response missing 'message'")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama response missing message content")

        return content.strip()
