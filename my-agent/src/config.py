"""Runtime configuration, resolved from the environment."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import lru_cache

DEFAULT_DATABASE_URL = "sqlite:///data/interview.db"
DEFAULT_SESSION_BUDGET_S = 300


class ConfigurationError(RuntimeError):
    """Raised when an environment value is present but unusable."""


def _read_str(env: Mapping[str, str], key: str, default: str) -> str:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


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
    session_budget_s: int = DEFAULT_SESSION_BUDGET_S

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        return cls(
            database_url=_read_str(source, "DATABASE_URL", DEFAULT_DATABASE_URL),
            session_budget_s=_read_positive_int(
                source, "SESSION_BUDGET_S", DEFAULT_SESSION_BUDGET_S
            ),
        )

    def with_overrides(self, **changes: object) -> "Settings":
        return replace(self, **changes)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
