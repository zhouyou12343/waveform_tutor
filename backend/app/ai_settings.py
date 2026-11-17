"""Local, single-user model settings. Never return credentials to the browser."""

import json
import os
import tempfile
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from .ai import AIError, AIService, OpenAICompatibleProvider

CONFIG_DIR = Path(__file__).resolve().parents[2] / ".waveform-tutor"
CONFIG_FILE = CONFIG_DIR / "ai-config.json"
DEFAULT_MODEL = "gpt-5.6-sol"


class ModelSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    url: str = Field(min_length=1, max_length=2048)
    api_key: SecretStr = Field(min_length=1, max_length=4096)
    model: str = Field(default=DEFAULT_MODEL, max_length=200)
    api_format: Literal["chat_completions", "responses"] = "responses"


def normalize_settings(body: dict) -> dict:
    value = ModelSettingsInput.model_validate(body)
    url = value.url.strip().rstrip("/")
    protocol = value.api_format
    for suffix, name in (("/chat/completions", "chat_completions"), ("/responses", "responses")):
        if url.endswith(suffix):
            url, protocol = url[: -len(suffix)], name
            break
    key = value.api_key.get_secret_value().strip()
    model = value.model.strip() or DEFAULT_MODEL
    if not key or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise ValueError("Invalid credential format")
    return {"base_url": url, "api_key": key, "model": model, "api_format": protocol}


def make_provider(settings: dict) -> OpenAICompatibleProvider:
    # Keep administrator limits; browser users cannot remove an environment cap.
    budget = os.getenv("AI_REQUEST_BUDGET", "").strip()
    return OpenAICompatibleProvider(
        settings["base_url"],
        settings["api_key"],
        settings["model"],
        timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", "30")),
        max_output_tokens=int(os.getenv("AI_MAX_OUTPUT_TOKENS", "2048")),
        api_format=settings["api_format"],
        max_attempts=1,
        request_budget=int(budget) if budget else None,
    )


def public_config(service: AIService, source: str, error: str = "") -> dict:
    provider = service._provider
    configured = service.configured
    base_url, model, protocol = "", DEFAULT_MODEL, "responses"
    if isinstance(provider, OpenAICompatibleProvider):
        suffix = "/responses" if provider._api_format == "responses" else "/chat/completions"
        base_url = provider._url[: -len(suffix)]
        model, protocol = provider._model, provider._api_format
    return {
        "configured": configured,
        "base_url": base_url,
        "model": model,
        "api_format": protocol,
        "has_key": configured,
        "source": source,
        "saved_locally": source in {"local", "disabled"},
        "revision": uuid4().hex,
        "error": error,
    }


def load_configuration() -> tuple[AIService, dict]:
    """Saved UI settings take precedence; a disabled marker suppresses env fallback."""
    try:
        if CONFIG_FILE.exists():
            if CONFIG_FILE.is_symlink() or CONFIG_FILE.stat().st_size > 32768:
                raise ValueError("Invalid local configuration file")
            stored = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if stored.get("disabled") is True:
                service = AIService(load_environment=False)
                return service, public_config(service, "disabled")
            settings = normalize_settings(
                {
                    "url": stored["base_url"],
                    "api_key": stored["api_key"],
                    "model": stored["model"],
                    "api_format": stored["api_format"],
                }
            )
            service = AIService(make_provider(settings))
            return service, public_config(service, "local")
        service = AIService()
        return service, public_config(service, "environment" if service.configured else "none")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ValidationError, AIError):
        service = AIService(load_environment=False)
        return service, public_config(service, "none", "本机模型配置无法读取，请重新填写并保存。")


def persist_configuration(settings: dict) -> None:
    """Atomic local write. POSIX owner-only file; no provider request is made."""
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if CONFIG_DIR.is_symlink():
        raise OSError("Configuration directory must not be a symlink")
    fd, temporary = tempfile.mkstemp(prefix=".ai-config-", dir=CONFIG_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, CONFIG_FILE)
    finally:
        Path(temporary).unlink(missing_ok=True)
