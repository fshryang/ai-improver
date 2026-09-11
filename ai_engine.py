"""AI 引擎：抽象 provider 接口 + 工厂函数。

所有 provider 实现同一个 async improve(text, mode) 接口，
main.py 通过 get_provider() 拿到当前激活的实例，不关心具体是哪家。
"""
from __future__ import annotations

import importlib
from typing import Protocol, runtime_checkable

import config


@runtime_checkable
class Provider(Protocol):
    """所有 AI provider 的统一接口。"""

    @property
    def name(self) -> str: ...

    async def improve(self, text: str, mode: str) -> str:
        """根据 mode（'improve' 或 'detect'）处理文本，返回 AI 输出。"""
        ...


# provider 名 → 模块路径 映射
# 新增 provider 只需要在这里登记 + 在 providers/ 下写实现
_PROVIDER_MODULES = {
    "deepseek": "providers.openai_provider",  # OpenAI 兼容协议，复用同一实现
    "openai": "providers.openai_provider",
    "anthropic": "providers.anthropic_provider",
    "local": "providers.local_provider",
}


def get_provider(cfg: dict | None = None) -> Provider:
    """返回当前激活 provider 的实例。

    从 config.json 读取 active_provider，加载对应模块并调用其 create() 工厂。
    """
    if cfg is None:
        cfg = config.load()

    name = config.get_active_provider_name(cfg)
    if name not in _PROVIDER_MODULES:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {list(_PROVIDER_MODULES)}"
        )

    module = importlib.import_module(_PROVIDER_MODULES[name])
    provider_cfg = config.get_provider_config(cfg, name)
    # OpenAI-compatible 协议有多个 provider 共用同一模块，把 provider 名传过去做 label
    if name in ("deepseek", "openai"):
        return module.create(provider_cfg, label=name)
    return module.create(provider_cfg)
