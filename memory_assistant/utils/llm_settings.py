"""
运行时 LLM 配置存取与热应用。

存储于 data/llm_runtime.json，独立于 config.yaml 与 .env。
启动时若文件存在，会覆盖到 agent 的 LLMClient / EmbeddingModel。
保存时直接重建客户端，无需重启服务。
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import openai

from .llm_client import LLMClient
from .embedding import EmbeddingModel


# -- 文件路径 --------------------------------------------------------------

_DEFAULT_PATH = Path("data") / "llm_runtime.json"
_LOCK = threading.Lock()


def _resolve_path(data_dir: Optional[str] = None) -> Path:
    if data_dir:
        return Path(data_dir) / "llm_runtime.json"
    return _DEFAULT_PATH


# -- 读写 ------------------------------------------------------------------

def load_runtime_settings(data_dir: Optional[str] = None) -> Dict[str, Any]:
    """读取 llm_runtime.json，文件不存在时返回 {}。"""
    path = _resolve_path(data_dir)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as exc:
        print(f"[llm_settings] 读取失败: {exc}")
        return {}


def save_runtime_settings(settings: Dict[str, Any],
                          data_dir: Optional[str] = None) -> None:
    """保存到 llm_runtime.json（线程安全，原子写入）。"""
    path = _resolve_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _LOCK:
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def mask_api_key(api_key: Optional[str]) -> str:
    """脱敏：只保留前 4 位和后 4 位。"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"


# -- 热应用 ----------------------------------------------------------------

def apply_settings_to_agent(agent: Any, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    把配置应用到 agent.llm_client / agent.embedding_model。

    settings 字段（全部可选，缺省则保持当前值）：
      - llm_api_key, llm_base_url, llm_model
      - embedding_api_key, embedding_base_url, embedding_model, embedding_dimension

    返回当前生效的（脱敏）配置。
    """
    if not settings:
        return current_effective_settings(agent)

    llm = agent.llm_client
    if "llm_api_key" in settings and settings["llm_api_key"]:
        llm.api_key = settings["llm_api_key"]
    if "llm_base_url" in settings and settings["llm_base_url"]:
        llm.base_url = settings["llm_base_url"]
    if "llm_model" in settings and settings["llm_model"]:
        llm.model = settings["llm_model"]

    # 重建 LLM client
    llm.client = openai.AsyncOpenAI(api_key=llm.api_key, base_url=llm.base_url)

    emb = agent.embedding_model
    if "embedding_api_key" in settings and settings["embedding_api_key"]:
        emb.api_key = settings["embedding_api_key"]
    if "embedding_base_url" in settings and settings["embedding_base_url"]:
        emb.base_url = settings["embedding_base_url"]
    if "embedding_model" in settings and settings["embedding_model"]:
        emb.model = settings["embedding_model"]
    if "embedding_dimension" in settings and settings["embedding_dimension"]:
        try:
            emb.dimension = int(settings["embedding_dimension"])
        except (TypeError, ValueError):
            pass

    emb.client = openai.OpenAI(api_key=emb.api_key, base_url=emb.base_url)

    return current_effective_settings(agent)


def current_effective_settings(agent: Any) -> Dict[str, Any]:
    """读出当前 agent 实际使用的（脱敏）配置。"""
    llm = getattr(agent, "llm_client", None)
    emb = getattr(agent, "embedding_model", None)
    return {
        "llm": {
            "api_key": mask_api_key(getattr(llm, "api_key", None)) if llm else "",
            "base_url": getattr(llm, "base_url", "") if llm else "",
            "model": getattr(llm, "model", "") if llm else "",
        },
        "embedding": {
            "api_key": mask_api_key(getattr(emb, "api_key", None)) if emb else "",
            "base_url": getattr(emb, "base_url", "") if emb else "",
            "model": getattr(emb, "model", "") if emb else "",
            "dimension": getattr(emb, "dimension", 1024) if emb else 1024,
        },
    }


# -- 测试 ------------------------------------------------------------------

async def test_llm_connection(api_key: str, base_url: str, model: str) -> Dict[str, Any]:
    """用临时配置发一次最小请求验证连通性。"""
    try:
        client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            temperature=0,
        )
        content = resp.choices[0].message.content or ""
        return {"success": True, "message": f"连接成功（模型回复 {len(content)} 字符）"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}
