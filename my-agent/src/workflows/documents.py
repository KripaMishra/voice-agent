"""Reading resumes and job descriptions from the local document store.

References reach here straight from API input, so a reference that climbs out
of the store is refused rather than read.
"""

from dataclasses import dataclass
from pathlib import Path


class DocumentNotFoundError(LookupError):
    """Raised when a reference does not point at a readable document."""


@dataclass(frozen=True)
class DocumentStore:
    root: Path

    def read(self, ref: str) -> str:
        path = (self.root / ref).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise DocumentNotFoundError(f"{ref!r} points outside the document store")
        if not path.is_file():
            raise DocumentNotFoundError(f"no document at {ref!r}")
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise DocumentNotFoundError(f"document {ref!r} is empty")
        return text
