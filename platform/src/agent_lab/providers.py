"""Provider ports, deterministic Mock, and DeepSeek Chat Completions adapter."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Mapping

import httpx
from pydantic import ValidationError

from agent_lab.domain.contracts_v0_1 import (
    DeepSeekProviderConfig,
    GenerationConfig,
    LineageReplayMockProviderConfig,
    MessageFormat,
    ModelRequest,
    ModelResponse,
    ParseStatus,
    ProviderConfig,
    ProviderContractDiagnostic,
    StructuredPayload,
    TokenUsage,
    VllmProviderConfig,
)
from agent_lab.provider_diagnostics import build_contract_diagnostic


class ProviderErrorCode(StrEnum):
    CONFIG = "PROVIDER_CONFIG_ERROR"
    CREDENTIAL_MISSING = "PROVIDER_CREDENTIAL_MISSING"
    CONNECTION = "PROVIDER_CONNECTION_ERROR"
    TIMEOUT = "PROVIDER_TIMEOUT"
    AUTHENTICATION = "PROVIDER_AUTHENTICATION_ERROR"
    RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    CLIENT = "PROVIDER_CLIENT_ERROR"
    SERVER = "PROVIDER_SERVER_ERROR"
    EMPTY_CONTENT = "PROVIDER_EMPTY_CONTENT"
    TRUNCATED_OUTPUT = "PROVIDER_TRUNCATED_OUTPUT"
    MALFORMED_JSON = "PROVIDER_MALFORMED_JSON"
    CONTRACT = "PROVIDER_CONTRACT_ERROR"
    RESPONSE_SHAPE = "PROVIDER_RESPONSE_SHAPE_ERROR"
    OUT_OF_MEMORY = "PROVIDER_OUT_OF_MEMORY"
    THINKING_VIOLATION = "PROVIDER_THINKING_VIOLATION"


class ProviderError(RuntimeError):
    """Sanitized provider error that never retains headers, secrets, or bodies."""

    def __init__(self, code: ProviderErrorCode | str, detail: str, *, status_code: int | None = None,
                 retry_after_seconds: float | None = None,
                 contract_diagnostic: ProviderContractDiagnostic | None = None):
        self.code = ProviderErrorCode(code)
        self.detail = detail
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.contract_diagnostic = contract_diagnostic
        suffix = "" if status_code is None else f" (HTTP {status_code})"
        super().__init__(f"{self.code.value}: {detail}{suffix}")


class ModelProvider(ABC):

    def request_body_sha256(self, request: ModelRequest) -> str:
        """Hash the immutable, non-secret logical provider input."""
        material = json.dumps({
            "model": request.model,
            "messages": [message.model_dump(mode="json") for message in request.messages],
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(material.encode("utf-8")).hexdigest()

    @abstractmethod
    def complete(self, request: ModelRequest) -> ModelResponse: ...


class LineageReplayMockProvider(ModelProvider):
    """Deterministically emits local seed claims, then inherited claims."""

    provider_ref = "lineage_replay_mock:v1"
    request_model = "lineage-replay-mock"
    response_model = "lineage-replay-mock"
    api_style = None
    base_url = None
    accessed_at = None

    def complete(self, request: ModelRequest) -> ModelResponse:
        context = request.request_context
        claims = context.get("local_claims", []) if request.round == 0 else context.get("incoming_claims", [])
        if request.output_format.value == "structured":
            raw = {"payload_type": "structured", "message_status": "content" if claims else "no_new_information",
                   "claims": claims, "summary": None}
            text = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
            parse = ParseStatus.SUCCEEDED
        else:
            incoming_texts = context.get("incoming_texts", []) if request.round > 0 else []
            lines = [str(claim["claim_text"]) for claim in claims]
            text = "\n".join(lines) if lines else "\n".join(str(value) for value in incoming_texts if str(value).strip())
            raw = {"text": text, "claims": claims}
            parse = ParseStatus.NOT_APPLICABLE
        response_id = "resp_" + sha256(request.model_dump_json().encode()).hexdigest()[:20]
        received_at = datetime.now(timezone.utc)
        input_tokens = sum(max(1, (len(message.content) + 3) // 4) for message in request.messages)
        output_tokens = max(1, (len(text) + 3) // 4)
        self.request_model = request.model
        self.response_model = request.model
        return ModelResponse(response_id=response_id, request_id=request.request_id,
            provider_ref=self.provider_ref, model=request.model, raw_response=raw, raw_text=text,
            request_model=request.model, response_model=request.model,
            finish_reason="stop", latency_ms=0, parse_status=parse,
            usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens,
                             total_tokens=input_tokens + output_tokens),
            received_at=received_at)


class DeepSeekOpenAICompatibleProvider(ModelProvider):
    """Stateless, no-retry adapter for DeepSeek's Chat Completions endpoint."""

    def __init__(
        self,
        config: DeepSeekProviderConfig,
        generation: GenerationConfig,
        *,
        client: httpx.Client | None = None,
        environ: Mapping[str, str] | None = None,
    ):
        environment = os.environ if environ is None else environ
        api_key = environment.get(config.api_key_env)
        if api_key is None or not api_key.strip():
            raise ProviderError(
                ProviderErrorCode.CREDENTIAL_MISSING,
                f"credential environment variable {config.api_key_env} is not set",
            )
        if generation.thinking is None:
            raise ProviderError(
                ProviderErrorCode.CONFIG,
                "DeepSeek provider requires explicit generation.thinking",
            )
        self.config = config
        self.generation = generation
        self.endpoint = f"{config.base_url.rstrip('/')}/chat/completions"
        self.provider_ref = f"deepseek_openai_compatible:{config.model}"
        self.request_model = config.model
        self.response_model: str | None = None
        self.api_style = config.api_style
        self.base_url = config.base_url.rstrip("/")
        self.accessed_at: datetime | None = None
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._client = client or httpx.Client(timeout=config.timeout_seconds)

    def _request_body(self, request: ModelRequest) -> dict:
        if request.output_format is not MessageFormat.STRUCTURED:
            raise ProviderError(ProviderErrorCode.CONFIG, "DeepSeek provider accepts structured requests only")
        if request.model != self.config.model:
            raise ProviderError(ProviderErrorCode.CONFIG, "request model differs from frozen provider model")
        return {
            "model": self.config.model,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "thinking": {"type": self.generation.thinking.type},
            "response_format": {"type": self.generation.response_format},
            "temperature": self.generation.temperature,
            "max_tokens": self.generation.max_output_tokens,
            "stream": self.config.stream,
        }

    def request_body_sha256(self, request: ModelRequest) -> str:
        material = json.dumps(
            self._request_body(request), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _http_error(response: httpx.Response) -> ProviderError:
        status_code = response.status_code
        retry_after_seconds = None
        if status_code in {401, 403}:
            code, detail = ProviderErrorCode.AUTHENTICATION, "provider rejected authentication"
        elif status_code == 429:
            code, detail = ProviderErrorCode.RATE_LIMITED, "provider rate limit was reached"
            value = response.headers.get("Retry-After")
            if value is not None:
                try:
                    parsed = float(value.strip())
                    if parsed >= 0:
                        retry_after_seconds = parsed
                except ValueError:
                    pass
        elif 400 <= status_code < 500:
            code, detail = ProviderErrorCode.CLIENT, "provider rejected the request"
        else:
            code, detail = ProviderErrorCode.SERVER, "provider server failed"
        return ProviderError(code, detail, status_code=status_code,
                             retry_after_seconds=retry_after_seconds)

    def complete(self, request: ModelRequest) -> ModelResponse:
        body = self._request_body(request)
        started = perf_counter()
        try:
            response = self._client.post(self.endpoint, headers=self._headers, json=body)
        except httpx.TimeoutException:
            raise ProviderError(ProviderErrorCode.TIMEOUT, "provider request timed out") from None
        except httpx.RequestError:
            raise ProviderError(ProviderErrorCode.CONNECTION, "provider connection failed") from None
        latency_ms = (perf_counter() - started) * 1000
        if response.status_code >= 400:
            raise self._http_error(response)
        try:
            envelope = response.json()
        except (json.JSONDecodeError, ValueError):
            raise ProviderError(ProviderErrorCode.RESPONSE_SHAPE, "provider response is not a JSON envelope") from None
        if not isinstance(envelope, dict):
            raise ProviderError(ProviderErrorCode.RESPONSE_SHAPE, "provider response envelope must be an object")
        choices = envelope.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderError(ProviderErrorCode.RESPONSE_SHAPE, "provider response has no first choice")
        choice = choices[0]
        finish_reason = choice.get("finish_reason")
        if not isinstance(finish_reason, str) or not finish_reason:
            raise ProviderError(ProviderErrorCode.RESPONSE_SHAPE, "provider finish_reason is missing")
        if finish_reason == "length":
            raise ProviderError(ProviderErrorCode.TRUNCATED_OUTPUT, "provider output reached its length limit")
        message = choice.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise ProviderError(ProviderErrorCode.RESPONSE_SHAPE, "provider first choice has no message content")
        content = message["content"]
        if content is None:
            raise ProviderError(ProviderErrorCode.EMPTY_CONTENT, "provider returned empty content")
        if not isinstance(content, str):
            raise ProviderError(ProviderErrorCode.RESPONSE_SHAPE, "provider message content must be a string")
        if not content.strip():
            raise ProviderError(ProviderErrorCode.EMPTY_CONTENT, "provider returned empty content")
        try:
            parsed_json = json.loads(content)
        except json.JSONDecodeError:
            raise ProviderError(ProviderErrorCode.MALFORMED_JSON, "provider content is not valid JSON") from None
        try:
            payload = StructuredPayload.model_validate(parsed_json)
        except ValidationError as error:
            diagnostic = build_contract_diagnostic(error, request, content)
            raise ProviderError(ProviderErrorCode.CONTRACT,
                "provider JSON violates StructuredPayload",
                contract_diagnostic=diagnostic) from None

        response_model = envelope.get("model")
        provider_request_id = envelope.get("id")
        if not isinstance(response_model, str) or not response_model:
            raise ProviderError(ProviderErrorCode.RESPONSE_SHAPE, "provider response model is missing")
        if not isinstance(provider_request_id, str) or not provider_request_id:
            raise ProviderError(ProviderErrorCode.RESPONSE_SHAPE, "provider response id is invalid")
        usage_raw = envelope.get("usage", {})
        if usage_raw is None:
            usage_raw = {}
        if not isinstance(usage_raw, dict):
            raise ProviderError(ProviderErrorCode.RESPONSE_SHAPE, "provider usage must be an object")
        try:
            usage = TokenUsage(
                input_tokens=usage_raw.get("prompt_tokens"),
                output_tokens=usage_raw.get("completion_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )
        except ValidationError:
            raise ProviderError(ProviderErrorCode.RESPONSE_SHAPE, "provider usage fields are invalid") from None
        received_at = datetime.now(timezone.utc)
        self.response_model = response_model
        self.accessed_at = received_at
        canonical = payload.model_dump(mode="json")
        body_material = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        response_id = "resp_" + sha256(
            f"{request.request_id}\x1f{provider_request_id or ''}\x1f{content}".encode("utf-8")
        ).hexdigest()[:20]
        return ModelResponse(
            response_id=response_id,
            request_id=request.request_id,
            provider_ref=self.provider_ref,
            model=response_model,
            raw_response=canonical,
            provider_raw_response=envelope,
            raw_text=content,
            request_model=self.config.model,
            response_model=response_model,
            provider_metadata={
                "api_style": self.config.api_style,
                "base_url": self.base_url,
                "endpoint": self.endpoint,
                "request_body_sha256": sha256(body_material.encode("utf-8")).hexdigest(),
            },
            finish_reason=finish_reason,
            usage=usage,
            latency_ms=latency_ms,
            estimated_cost=None,
            provider_request_id=provider_request_id,
            parse_status=ParseStatus.SUCCEEDED,
            received_at=received_at,
        )


class VllmOpenAICompatibleProvider(ModelProvider):
    """Stateless, single-attempt adapter for the frozen local Qwen3 vLLM service."""

    def __init__(
        self,
        config: VllmProviderConfig,
        generation: GenerationConfig,
        *,
        client: httpx.Client | None = None,
    ):
        if generation.thinking is None or generation.thinking.type != "disabled":
            raise ProviderError(
                ProviderErrorCode.CONFIG,
                "vLLM Qwen3 provider requires explicit disabled thinking",
            )
        manifest_path = Path(config.deployment_manifest_path)
        try:
            manifest_digest = sha256(manifest_path.read_bytes()).hexdigest()
        except OSError:
            raise ProviderError(
                ProviderErrorCode.CONFIG, "deployment manifest is not readable"
            ) from None
        if manifest_digest != config.deployment_manifest_sha256:
            raise ProviderError(
                ProviderErrorCode.CONFIG, "deployment manifest SHA-256 mismatch"
            )
        self.config = config
        self.generation = generation
        self.endpoint = f"{config.base_url.rstrip('/')}/chat/completions"
        self.health_endpoint = config.base_url.removesuffix("/v1") + "/health"
        self.models_endpoint = f"{config.base_url.rstrip('/')}/models"
        self.provider_ref = (
            f"vllm_openai_compatible:{config.model}@{config.model_revision}"
        )
        self.request_model = config.model
        self.response_model: str | None = None
        self.api_style = config.api_style
        self.base_url = config.base_url.rstrip("/")
        self.accessed_at: datetime | None = None
        self._headers = {"Content-Type": "application/json"}
        self._client = client or httpx.Client(timeout=config.timeout_seconds)

    def _request_body(self, request: ModelRequest) -> dict:
        if request.output_format is not MessageFormat.STRUCTURED:
            raise ProviderError(
                ProviderErrorCode.CONFIG, "vLLM provider accepts structured requests only"
            )
        if request.model != self.config.model:
            raise ProviderError(
                ProviderErrorCode.CONFIG, "request model differs from frozen provider model"
            )
        return {
            "model": self.config.model,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": self.generation.response_format},
            "temperature": self.generation.temperature,
            "max_tokens": self.generation.max_output_tokens,
            "stream": self.config.stream,
        }

    def request_body_sha256(self, request: ModelRequest) -> str:
        material = json.dumps(
            self._request_body(request), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _http_error(response: httpx.Response) -> ProviderError:
        status_code = response.status_code
        retry_after_seconds = None
        body_hint = response.text.casefold()
        if status_code >= 500 and (
            "out of memory" in body_hint or "cuda oom" in body_hint
        ):
            code, detail = ProviderErrorCode.OUT_OF_MEMORY, "vLLM reported GPU out of memory"
        elif status_code in {401, 403}:
            code, detail = ProviderErrorCode.AUTHENTICATION, "provider rejected authentication"
        elif status_code == 429:
            code, detail = ProviderErrorCode.RATE_LIMITED, "provider rate limit was reached"
            value = response.headers.get("Retry-After")
            if value is not None:
                try:
                    parsed = float(value.strip())
                    if parsed >= 0:
                        retry_after_seconds = parsed
                except ValueError:
                    pass
        elif 400 <= status_code < 500:
            code, detail = ProviderErrorCode.CLIENT, "provider rejected the request"
        else:
            code, detail = ProviderErrorCode.SERVER, "provider server failed"
        return ProviderError(
            code, detail, status_code=status_code,
            retry_after_seconds=retry_after_seconds,
        )

    def _get(self, endpoint: str) -> httpx.Response:
        try:
            response = self._client.get(endpoint)
        except httpx.TimeoutException:
            raise ProviderError(ProviderErrorCode.TIMEOUT, "provider request timed out") from None
        except httpx.RequestError:
            raise ProviderError(ProviderErrorCode.CONNECTION, "provider connection failed") from None
        if response.status_code >= 400:
            raise self._http_error(response)
        return response

    def healthcheck(self) -> dict[str, object]:
        self._get(self.health_endpoint)
        response = self._get(self.models_endpoint)
        try:
            envelope = response.json()
        except (json.JSONDecodeError, ValueError):
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "models response is not JSON"
            ) from None
        data = envelope.get("data") if isinstance(envelope, dict) else None
        if not isinstance(data, list):
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "models response has no data list"
            )
        served = [item.get("id") for item in data if isinstance(item, dict)]
        if self.config.model not in served:
            raise ProviderError(
                ProviderErrorCode.CONFIG, "frozen served model is absent from /v1/models"
            )
        return {"health_status": 200, "served_model_present": True}

    def complete(self, request: ModelRequest) -> ModelResponse:
        body = self._request_body(request)
        started = perf_counter()
        try:
            response = self._client.post(self.endpoint, headers=self._headers, json=body)
        except httpx.TimeoutException:
            raise ProviderError(ProviderErrorCode.TIMEOUT, "provider request timed out") from None
        except httpx.RequestError:
            raise ProviderError(ProviderErrorCode.CONNECTION, "provider connection failed") from None
        latency_ms = (perf_counter() - started) * 1000
        if response.status_code >= 400:
            raise self._http_error(response)
        try:
            envelope = response.json()
        except (json.JSONDecodeError, ValueError):
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "provider response is not a JSON envelope"
            ) from None
        if not isinstance(envelope, dict):
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "provider response envelope must be an object"
            )
        choices = envelope.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "provider response has no first choice"
            )
        choice = choices[0]
        finish_reason = choice.get("finish_reason")
        if not isinstance(finish_reason, str) or not finish_reason:
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "provider finish_reason is missing"
            )
        if finish_reason == "length":
            raise ProviderError(
                ProviderErrorCode.TRUNCATED_OUTPUT, "provider output reached its length limit"
            )
        message = choice.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "provider first choice has no message content"
            )
        reasoning = message.get("reasoning_content")
        if reasoning not in (None, ""):
            raise ProviderError(
                ProviderErrorCode.THINKING_VIOLATION,
                "vLLM returned reasoning content while thinking was disabled",
            )
        content = message["content"]
        if content is None or (isinstance(content, str) and not content.strip()):
            raise ProviderError(ProviderErrorCode.EMPTY_CONTENT, "provider returned empty content")
        if not isinstance(content, str):
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "provider message content must be a string"
            )
        lowered = content.casefold()
        if "<think>" in lowered or "</think>" in lowered:
            raise ProviderError(
                ProviderErrorCode.THINKING_VIOLATION,
                "vLLM content contains thinking tags while thinking was disabled",
            )
        try:
            parsed_json = json.loads(content)
        except json.JSONDecodeError:
            raise ProviderError(
                ProviderErrorCode.MALFORMED_JSON, "provider content is not valid JSON"
            ) from None
        try:
            payload = StructuredPayload.model_validate(parsed_json)
        except ValidationError as error:
            diagnostic = build_contract_diagnostic(error, request, content)
            raise ProviderError(
                ProviderErrorCode.CONTRACT,
                "provider JSON violates StructuredPayload",
                contract_diagnostic=diagnostic,
            ) from None

        response_model = envelope.get("model")
        provider_request_id = envelope.get("id")
        if response_model != self.config.model:
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "provider response model differs from frozen model"
            )
        if not isinstance(provider_request_id, str) or not provider_request_id:
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "provider response id is invalid"
            )
        usage_raw = envelope.get("usage")
        if not isinstance(usage_raw, dict):
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "provider usage must be an object"
            )
        try:
            usage = TokenUsage(
                input_tokens=usage_raw.get("prompt_tokens"),
                output_tokens=usage_raw.get("completion_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )
        except ValidationError:
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "provider usage fields are invalid"
            ) from None
        if None in (usage.input_tokens, usage.output_tokens, usage.total_tokens):
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "vLLM usage fields must be complete"
            )
        if usage.input_tokens + usage.output_tokens != usage.total_tokens:
            raise ProviderError(
                ProviderErrorCode.RESPONSE_SHAPE, "vLLM usage total is inconsistent"
            )
        received_at = datetime.now(timezone.utc)
        self.response_model = response_model
        self.accessed_at = received_at
        canonical = payload.model_dump(mode="json")
        body_material = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        response_id = "resp_" + sha256(
            f"{request.request_id}\x1f{provider_request_id}\x1f{content}".encode("utf-8")
        ).hexdigest()[:20]
        return ModelResponse(
            response_id=response_id,
            request_id=request.request_id,
            provider_ref=self.provider_ref,
            model=response_model,
            raw_response=canonical,
            provider_raw_response=envelope,
            raw_text=content,
            request_model=self.config.model,
            response_model=response_model,
            provider_metadata={
                "api_style": self.config.api_style,
                "base_url": self.base_url,
                "endpoint": self.endpoint,
                "model_repository": self.config.model_repository,
                "model_revision": self.config.model_revision,
                "deployment_manifest_sha256": self.config.deployment_manifest_sha256,
                "request_body_sha256": sha256(body_material.encode("utf-8")).hexdigest(),
            },
            finish_reason=finish_reason,
            usage=usage,
            latency_ms=latency_ms,
            estimated_cost=None,
            provider_request_id=provider_request_id,
            parse_status=ParseStatus.SUCCEEDED,
            received_at=received_at,
        )


def create_provider(
    config: ProviderConfig,
    generation: GenerationConfig,
    *,
    client: httpx.Client | None = None,
    environ: Mapping[str, str] | None = None,
) -> ModelProvider:
    if isinstance(config, LineageReplayMockProviderConfig):
        return LineageReplayMockProvider()
    if isinstance(config, DeepSeekProviderConfig):
        return DeepSeekOpenAICompatibleProvider(config, generation, client=client, environ=environ)
    if isinstance(config, VllmProviderConfig):
        return VllmOpenAICompatibleProvider(config, generation, client=client)
    raise ProviderError(ProviderErrorCode.CONFIG, "provider kind is not implemented")
