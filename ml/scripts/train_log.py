"""Shared logging for the train_all pipeline: live terminal + single log file."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_TEE_INSTALLED = False


class _Tee:
    """Mirror writes to the original stream and an append-only log file."""

    def __init__(self, stream, log_path: Path) -> None:
        self._stream = stream
        self._log_path = log_path
        self._file = log_path.open("a", encoding="utf-8", errors="replace")

    def write(self, data: str) -> int:
        self._stream.write(data)
        self._stream.flush()
        self._file.write(data)
        self._file.flush()
        return len(data)

    def flush(self) -> None:
        self._stream.flush()
        self._file.flush()

    def isatty(self) -> bool:
        return self._stream.isatty()

    def fileno(self) -> int:
        return self._stream.fileno()

    @property
    def encoding(self) -> str:
        return getattr(self._stream, "encoding", "utf-8")


def log_path_from_env() -> Path | None:
    raw = os.environ.get("HELIOS_TRAIN_LOG")
    return Path(raw) if raw else None


def append_banner(text: str) -> None:
    path = log_path_from_env()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="replace") as f:
        f.write(text if text.endswith("\n") else text + "\n")


def setup_train_log() -> Path | None:
    """Route stdout, stderr, and logging to terminal + HELIOS_TRAIN_LOG file."""
    global _TEE_INSTALLED

    path = log_path_from_env()
    if path is None:
        return None

    path.parent.mkdir(parents=True, exist_ok=True)

    if not _TEE_INSTALLED:
        sys.stdout = _Tee(sys.__stdout__, path)
        sys.stderr = _Tee(sys.__stderr__, path)
        _TEE_INSTALLED = True

    root = logging.getLogger()
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(path) for h in root.handlers):
        root.setLevel(logging.INFO)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        root.addHandler(file_handler)

        if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(logging.Formatter("%(message)s"))
            root.addHandler(stream_handler)

    return path
