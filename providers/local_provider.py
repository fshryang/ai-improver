"""本地 provider：兼容 Ollama / LM Studio 的 OpenAI-style API。

不需要 API key。默认指向 http://localhost:11434/v1（Ollama）。
LM Studio 用户把 base_url 改成 http://localhost:1234/v1 即可。
"""
from __future__ import annotations

import httpx

import prompts


class LocalProvider:
    """本地模型 provider，走 OpenAI Chat Completions 协议。"""

    name = "local"

    def __init__(self, cfg: dict) -> None:
        # Ollama 默认暴露 /v1 端点（OpenAI 兼容）
        self.base_url: str = cfg.get(
            "base_url", "http://localhost:11434"
        ).rstrip("/")
        self.model: str = cfg.get("model", "llama3.1:8b")

    async def improve(self, text: str, mode: str) -> str:
        messages = prompts.build_messages(mode, text)
        url = f"{self.base_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.4 if mode == "improve" else 0.2,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"].strip()


def create(cfg: dict) -> LocalProvider:
    return LocalProvider(cfg)
