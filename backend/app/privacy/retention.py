"""Retention operates on stored PDF bytes; audit evidence remains intact."""

import time
from pathlib import Path

from backend.app.config import get_settings


def purge(directory: Path, days: int, *, now: float | None = None) -> int:
    """Delete expired regular PDFs without following symbolic links."""
    cutoff = (time.time() if now is None else now) - days * 86400
    removed = 0
    for path in directory.glob("*.pdf"):
        if not path.is_symlink() and path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed


def main() -> None:
    """Apply POP_RETENTION_DAYS to the configured proof directory."""
    settings = get_settings()
    print(
        f"Purged {purge(settings.pop_directory, settings.pop_retention_days)} expired proof files"
    )


if __name__ == "__main__":
    main()
