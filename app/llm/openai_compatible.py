from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from ..config import Settings
from ..models import EventsLLM, GapAnalysisLLM, QueryPlanLLM
from ..tools.base import LLMClient, ToolError
from . import prompts

FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


class LLMError(ToolError):
    def __init__(self, message: str, *, transient: bool = False, code: str = "llm_error"):
        super().__init__(message, transient=transient, code=code)


class LLMOutputError(LLMError):
    def __init__(self, message: str):
        super().__init__(message, transient=False, code="llm_output_invalid")


class OpenAICompatibleLLM(LLMClient):
    """Generic chat/completions client. No vendor-specific behaviour."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        missing = [key for key in ("llm_base_url", "llm_api_key", "llm_model") if not getattr(settings, key)]
        if missing:
            raise LLMError("模型服务配置缺失", code="config_missing")
        self.settings = settings
        base = settings.llm_base_url.rstrip("/")
        self.endpoint = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        self._client = httpx.Client(
            timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=8.0),
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "SignalField/0.1",
            },
            transport=transport,
        )

    def _request(self, system: str, user: str, max_tokens: int) -> tuple[dict, dict]:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.settings.llm_temperature,
            "max_tokens": max_tokens,
        }
        if self.settings.llm_json_mode:
            payload["response_format"] = {"type": "json_object"}
        # DeepSeek's optional extended parameter. It is omitted for generic
        # OpenAI-compatible providers unless explicitly configured.
        if self.settings.llm_thinking in {"enabled", "disabled"}:
            payload["thinking"] = {"type": self.settings.llm_thinking}
        try:
            response = self._client.post(self.endpoint, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMError("模型请求超时", transient=True, code="llm_timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMError("无法连接模型服务", transient=True, code="llm_network") from exc

        if response.status_code in {401, 403}:
            raise LLMError("模型服务鉴权失败，请检查服务端配置", code="llm_auth")
        if response.status_code == 429:
            raise LLMError("模型服务触发限流", transient=True, code="llm_rate_limited")
        if response.status_code >= 500:
            raise LLMError("模型服务暂时不可用", transient=True, code="llm_unavailable")
        if response.status_code == 400 and self.settings.llm_json_mode:
            raise LLMError(
                "模型不接受 JSON 模式响应；可在 .env 中设置 LLM_JSON_MODE=false 后重启",
                code="llm_json_mode_unsupported",
            )
        if response.status_code >= 400:
            raise LLMError(f"模型请求失败（HTTP {response.status_code}）", code="llm_bad_request")

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("模型返回结构异常", transient=True, code="llm_bad_response") from exc
        usage = body.get("usage") or {}
        tokens = {
            "tokens_in": int(usage.get("prompt_tokens") or 0),
            "tokens_out": int(usage.get("completion_tokens") or 0),
        }
        if not isinstance(content, str) or not content.strip():
            raise LLMError("模型返回了空内容", transient=True, code="llm_empty")
        cleaned = FENCE.sub("", content.strip()).strip()
        try:
            data = json.loads(cleaned)
        except ValueError as exc:
            raise LLMOutputError("模型输出不是合法 JSON") from exc
        if not isinstance(data, dict):
            raise LLMOutputError("模型输出必须是 JSON 对象")
        return data, tokens

    @staticmethod
    def _validate(schema, data: dict) -> dict:
        try:
            return schema.model_validate(data).model_dump()
        except ValidationError as exc:
            fields = ", ".join(
                ".".join(str(part) for part in err.get("loc", ())) for err in exc.errors()[:4]
            )
            raise LLMOutputError(f"模型输出未通过结构校验：{fields}") from exc

    def plan_queries(self, context: dict[str, Any]) -> tuple[dict, dict]:
        data, tokens = self._request(
            prompts.PLAN_SYSTEM, prompts.plan_user(context), max_tokens=1800
        )
        return self._validate(QueryPlanLLM, data), tokens

    def extract_events(self, context: dict[str, Any]) -> tuple[dict, dict]:
        data, tokens = self._request(
            prompts.EXTRACT_SYSTEM, prompts.extract_user(context), max_tokens=6500
        )
        return self._validate(EventsLLM, data), tokens

    def analyze_gaps(self, context: dict[str, Any]) -> tuple[dict, dict]:
        data, tokens = self._request(
            prompts.GAP_SYSTEM, prompts.gaps_user(context), max_tokens=1800
        )
        return self._validate(GapAnalysisLLM, data), tokens

    def close(self) -> None:
        self._client.close()
