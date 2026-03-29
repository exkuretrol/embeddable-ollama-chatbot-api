from typing import Protocol

import httpx

from app.config import Settings
from app.ollama_client import OllamaClient
from app.schemas import ChatMessage


class LLMClient(Protocol):
    async def health_check(self) -> bool:
        ...

    async def chat(self, messages: list[ChatMessage]) -> str:
        ...


class OpenWebUIClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    @property
    def _base_url(self) -> str:
        return self._settings.openwebui_base_url.rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.openwebui_api_key}",
            "Content-Type": "application/json",
        }

    async def health_check(self) -> bool:
        timeout = httpx.Timeout(self._settings.health_timeout)
        models_url = f"{self._base_url}/api/models"
        chat_path = self._settings.openwebui_chat_path.strip()

        async with httpx.AsyncClient(timeout=timeout) as client:
            models_response = await client.get(models_url, headers={"Authorization": self._headers["Authorization"]})
            if models_response.status_code == 404:
                chat_url = f"{self._base_url}{chat_path}"
                payload = {
                    "model": self._settings.openwebui_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": False,
                    "max_tokens": 1,
                }
                response = await client.post(chat_url, headers=self._headers, json=payload)
                response.raise_for_status()
                return True

            models_response.raise_for_status()
            data = models_response.json()

        model_names: set[str] = set()
        if isinstance(data, dict):
            payload_data = data.get("data")
            if isinstance(payload_data, list):
                for item in payload_data:
                    if not isinstance(item, dict):
                        continue
                    model_id = item.get("id")
                    model_name = item.get("name")
                    if isinstance(model_id, str):
                        model_names.add(model_id)
                    if isinstance(model_name, str):
                        model_names.add(model_name)

        return self._settings.openwebui_model in model_names

    async def chat(self, messages: list[ChatMessage]) -> str:
        chat_path = self._settings.openwebui_chat_path.strip()
        url = f"{self._base_url}{chat_path}"
        timeout = httpx.Timeout(self._settings.request_timeout)
        payload = {
            "model": self._settings.openwebui_model,
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
            response = await client.post(url, headers=self._headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("OpenWebUI response missing 'choices'")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("OpenWebUI response contains invalid choice")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("OpenWebUI response missing choice message")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenWebUI response missing message content")

        return content.strip()


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "openwebui":
        return OpenWebUIClient(settings)
    return OllamaClient(settings)
