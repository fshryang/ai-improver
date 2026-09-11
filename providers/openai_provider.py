"""OpenAI provider：兼容 OpenAI Chat Completions API（含自建代理 / Azure OpenAI）。

通过 base_url 可指向任何 OpenAI 兼容端点（vLLM / OpenRouter / 本地代理等）。
"""
from __future__ import annotations

import httpx

import prompts


class OpenAIProvider:
    """OpenAI Chat Completions 实现（兼容任意 OpenAI 协议端点：OpenAI / DeepSeek / 自建代理）。"""

    def __init__(self, cfg: dict, label: str = "OpenAI-compatible") -> None:
        self.label = label
        self.api_key: str = cfg.get("api_key", "")
        self.model: str = cfg.get("model", "")
        self.base_url: str = cfg.get("base_url", "").rstrip("/")

        # 允许 api_key 为空（local provider 不需要 key），但必须有 model 和 base_url
        if not self.model:
            raise RuntimeError(f"{label} model 未配置。请在 Settings 里填写 model 字段。")
        if not self.base_url:
            raise RuntimeError(f"{label} base_url 未配置。请在 Settings 里填写 base_url 字段。")
        if self.api_key.startswith("YOUR_"):
            raise RuntimeError(
                f"{label} API key 未配置。请在 Settings -> {label} 填入真实 key。"
            )

    async def improve(self, text: str, mode: str) -> str:
        messages = prompts.build_messages(mode, text)
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:  # local provider 不需要 Bearer
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.4 if mode == "improve" else 0.2,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"].strip()


def create(cfg: dict, label: str = "OpenAI") -> OpenAIProvider:
    """工厂函数：ai_engine 通过这个函数构造实例。"""
    return OpenAIProvider(cfg, label=label)
