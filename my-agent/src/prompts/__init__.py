"""Prompt catalog. Prompt text lives in markdown files alongside this module."""

from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROMPT_DIR = Path(__file__).parent
PROMPT_SUFFIX = ".md"


class PromptNotFoundError(LookupError):
    """Raised when a prompt name has no usable file in the catalog."""


@dataclass(frozen=True)
class PromptCatalog:
    directory: Path

    def names(self) -> list[str]:
        return sorted(path.stem for path in self.directory.glob(f"*{PROMPT_SUFFIX}"))

    def load(self, name: str) -> str:
        path = self.directory / f"{name}{PROMPT_SUFFIX}"
        if not path.is_file():
            available = ", ".join(self.names()) or "none"
            raise PromptNotFoundError(
                f"no prompt named {name!r}; available: {available}"
            )
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise PromptNotFoundError(f"prompt {name!r} is empty")
        return text


catalog = PromptCatalog(DEFAULT_PROMPT_DIR)
