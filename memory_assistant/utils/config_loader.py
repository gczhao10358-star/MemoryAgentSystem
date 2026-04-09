"""
配置加载工具
支持从 YAML 文件加载配置，并用环境变量覆盖敏感字段。
"""
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _resolve_env_placeholders(value: Any) -> Any:
    """递归解析配置中的环境变量占位符。"""
    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]

    if isinstance(value, str):
        def replacer(match: re.Match) -> str:
            env_name = match.group(1)
            default_value = match.group(2) or ""
            return os.getenv(env_name, default_value)

        return ENV_PATTERN.sub(replacer, value)

    return value


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并配置。"""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _maybe_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _maybe_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _env_overrides() -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}

    llm_overrides = {
        "api_key": os.getenv("LLM_API_KEY"),
        "base_url": os.getenv("LLM_BASE_URL"),
        "model": os.getenv("LLM_MODEL"),
        "max_tokens": _maybe_int(os.getenv("LLM_MAX_TOKENS")),
        "temperature": _maybe_float(os.getenv("LLM_TEMPERATURE")),
    }
    llm_overrides = {k: v for k, v in llm_overrides.items() if v is not None}
    if llm_overrides:
        overrides["llm"] = llm_overrides

    embedding_overrides = {
        "api_key": os.getenv("EMBEDDING_API_KEY"),
        "base_url": os.getenv("EMBEDDING_BASE_URL"),
        "model": os.getenv("EMBEDDING_MODEL"),
        "dimension": _maybe_int(os.getenv("EMBEDDING_DIMENSION")),
    }
    embedding_overrides = {k: v for k, v in embedding_overrides.items() if v is not None}
    if embedding_overrides:
        overrides["embedding"] = embedding_overrides

    return overrides


def load_config(config_path: str = "config.yaml",
                fallback_path: str = "config.example.yaml") -> Dict[str, Any]:
    """
    加载配置。

    优先使用 config.yaml；若不存在则回退到 config.example.yaml。
    两者都支持 `${ENV_NAME}` / `${ENV_NAME:-default}` 占位符。
    最后再用环境变量覆盖敏感字段。
    """
    primary_path = Path(config_path)
    default_path = Path(fallback_path)

    source_path = primary_path if primary_path.exists() else default_path
    config = _read_yaml(source_path) if source_path.exists() else {}
    config = _resolve_env_placeholders(config)

    return _deep_merge(config, _env_overrides())
