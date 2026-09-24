"""Runtime configuration, resolved from the environment."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import lru_cache

DEFAULT_DATABASE_URL = "sqlite:///data/interview.db"
DEFAULT_DOCUMENTS_DIR = "data/documents"
DEFAULT_SESSION_BUDGET_S = 300
DEFAULT_WORKFLOW_MODEL = "google/gemini-2.5-flash"


class ConfigurationError(RuntimeError):
    """Raised when an environment value is present but unusable."""


def _read_optional_str(env: Mapping[str, str], key: str) -> str | None:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def _read_str(env: Mapping[str, str], key: str, default: str) -> str:
    return _read_optional_str(env, key) or default


def _read_positive_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ConfigurationError(f"{key} must be positive, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL
    documents_dir: str = DEFAULT_DOCUMENTS_DIR
    session_budget_s: int = DEFAULT_SESSION_BUDGET_S
    tavily_api_key: str | None = None
    workflow_model: str = DEFAULT_WORKFLOW_MODEL
    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        return cls(
            database_url=_read_str(source, "DATABASE_URL", DEFAULT_DATABASE_URL),
            documents_dir=_read_str(source, "DOCUMENTS_DIR", DEFAULT_DOCUMENTS_DIR),
            session_budget_s=_read_positive_int(
                source, "SESSION_BUDGET_S", DEFAULT_SESSION_BUDGET_S
            ),
            tavily_api_key=_read_optional_str(source, "TAVILY_API_KEY"),
            workflow_model=_read_str(source, "WORKFLOW_MODEL", DEFAULT_WORKFLOW_MODEL),
            livekit_url=_read_optional_str(source, "LIVEKIT_URL"),
            livekit_api_key=_read_optional_str(source, "LIVEKIT_API_KEY"),
            livekit_api_secret=_read_optional_str(source, "LIVEKIT_API_SECRET"),
        )

    def livekit_credentials(self) -> tuple[str, str, str]:
        if not (self.livekit_url and self.livekit_api_key and self.livekit_api_secret):
            raise ConfigurationError(
                "LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET must all be set"
            )
        return self.livekit_url, self.livekit_api_key, self.livekit_api_secret

    def with_overrides(self, **changes: object) -> "Settings":
        return replace(self, **changes)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
