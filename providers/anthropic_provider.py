"""Anthropic Claude provider：调用 Messages API。

注意 Anthropic 的 system prompt 是顶层字段而非 messages 里的一项，
这里把 prompts.build_messages 的输出重新组装成 Anthropic 格式。
"""
from __future__ import annotations

import httpx

import prompts


class AnthropicProvider:
    """Anthropic Messages API 实现。"""

    name = "anthropic"

    def __init__(self, cfg: dict) -> None:
        self.api_key: str = cfg.get("api_key", "")
        self.model: str = cfg.get("model", "claude-3-5-haiku-latest")
        self.base_url: str = cfg.get("base_url", "https://api.anthropic.com").rstrip("/")

        if not self.api_key or self.api_key.startswith("YOUR_"):
            raise RuntimeError(
                "Anthropic API key 未配置。请在 config.json -> providers.anthropic.api_key 填入真实 key。"
            )

    async def improve(self, text: str, mode: str) -> str:
        messages = prompts.build_messages(mode, text)
        # build_messages 返回 [{role: system, ...}, {role: user, ...}]
        # Anthropic 要求 system 在顶层
        system_content = messages[0]["content"]
        user_messages = [{"role": m["role"], "content": m["content"]}
                          for m in messages[1:]]

        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "system": system_content,
            "messages": user_messages,
            "temperature": 0.4 if mode == "improve" else 0.2,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Anthropic 返回 content 是 block 列表，取所有 text block 拼接
        blocks = data.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


def create(cfg: dict) -> AnthropicProvider:
    return AnthropicProvider(cfg)
