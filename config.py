"""配置加载与保存。所有设置存放在 config.json 中。

路径策略：
- 开发态：config.json 与源码同目录
- PyInstaller 打包后：config.json 放在 exe 同目录（%exe_dir%/config.json）
  这样用户可以直接编辑，也能持久化保存
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _resolve_config_path() -> Path:
    """返回 config.json 的绝对路径，打包后指向 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        # PyInstaller onefile: sys.executable 是 exe 路径
        exe_dir = Path(sys.executable).resolve().parent
        return exe_dir / "config.json"
    # 开发态：源码同目录
    return Path(__file__).resolve().parent / "config.json"


CONFIG_PATH = _resolve_config_path()

# 打包后如果 config.json 不存在，从内置默认值生成一份
_DEFAULT_CONFIG: dict[str, Any] = {
    "active_provider": "deepseek",
    "providers": {
        "deepseek": {"api_key": "", "model": "deepseek-v4-flash", "base_url": "https://api.deepseek.com/v1"},
        "openai": {"api_key": "", "model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
        "anthropic": {"api_key": "", "model": "claude-3-5-haiku-latest", "base_url": "https://api.anthropic.com"},
        "local": {"base_url": "http://localhost:11434", "model": "llama3.1:8b"},
    },
    "mode": "improve",
    "min_text_length": 12,
}


def ensure_config() -> None:
    """确保 config.json 存在且字段完整。

    核心规则：**永远不覆盖非空的 api_key**（那是用户填的）。
    只补 model / base_url / active_provider / 缺 provider 这些结构性字段。

    每次启动都调用，不只是首次。放在 main.py 的启动入口里。
    """
    cfg = load()
    changed = False

    if not cfg:
        try:
            save(_DEFAULT_CONFIG)
            return
        except OSError:
            return

    # 补缺失的顶层键（跳过 active_provider 如果已有值）
    for key, val in _DEFAULT_CONFIG.items():
        if key not in cfg:
            cfg[key] = val
            changed = True

    # 补缺失的 provider 及其结构性字段（永远不覆盖已有 api_key）
    providers = cfg.setdefault("providers", {})
    for pname, pfields in _DEFAULT_CONFIG["providers"].items():
        pcfg = providers.setdefault(pname, {})
        for key, val in pfields.items():
            if key == "api_key":
                continue  # api_key 是用户资产，绝不自动改
            if not pcfg.get(key):  # None / 空字符串才补
                pcfg[key] = val
                changed = True

    if changed:
        try:
            save(cfg)
        except OSError:
            pass


def load() -> dict[str, Any]:
    """加载配置。文件不存在时返回空 dict，由调用方处理缺失字段。"""
    if not CONFIG_PATH.exists():
        return {}
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save(cfg: dict[str, Any]) -> None:
    """保存配置到 config.json（覆盖）。保存前补全 active_provider 对应的结构性字段。"""
    active = cfg.get("active_provider", "")
    providers = cfg.get("providers", {})
    if active in providers and active in _DEFAULT_CONFIG["providers"]:
        defaults = _DEFAULT_CONFIG["providers"][active]
        pcfg = providers.setdefault(active, {})
        for key, val in defaults.items():
            if key == "api_key":
                continue  # api_key 是用户资产，绝不自动改
            if not pcfg.get(key):
                pcfg[key] = val
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_active_provider_name(cfg: dict[str, Any]) -> str:
    """返回当前激活的 provider 名（如 'openai'）。"""
    return cfg.get("active_provider", "openai")


def get_provider_config(cfg: dict[str, Any], name: str) -> dict[str, Any]:
    """返回某个 provider 的配置 dict。"""
    return cfg.get("providers", {}).get(name, {})


def get_active_provider_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """返回当前激活 provider 的配置 dict。"""
    return get_provider_config(cfg, get_active_provider_name(cfg))

