#!/usr/bin/env python3
"""Run MSTAR -> YOLO -> BIT -> Triton export sequentially."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = REPO_ROOT / ".venv-train" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

LOG_DIR = REPO_ROOT / "ml" / "artifacts" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LATEST_LOG = LOG_DIR / "train_all_latest.log"

SCRIPTS = [
    ("organize", REPO_ROOT / "ml" / "scripts" / "organize_datasets.py", []),
    ("mstar", REPO_ROOT / "ml" / "scripts" / "train_mstar.py", []),
    ("yolo", REPO_ROOT / "ml" / "scripts" / "train_yolov8.py", []),
    ("bit", REPO_ROOT / "ml" / "scripts" / "train_bit_simple.py", []),
    ("export", REPO_ROOT / "ml" / "scripts" / "export_triton.py", []),
]


def _log_line(log_path: Path, text: str) -> None:
    line = text if text.endswith("\n") else text + "\n"
    with log_path.open("a", encoding="utf-8", errors="replace") as f:
        f.write(line)
    print(line, end="", flush=True)


def run_step(name: str, script: Path, extra: list[str], log_path: Path) -> None:
    banner = f"\n{'=' * 60}\nSTEP: {name}\n{'=' * 60}\n"
    _log_line(log_path, banner)

    cmd = [str(PYTHON), "-u", str(script), *extra]
    env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "HELIOS_TRAIN_LOG": str(log_path),
    }

    # Inherit stdout/stderr so progress bars and live output appear in the terminal.
    # Each child script tees the same streams into HELIOS_TRAIN_LOG.
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT), env=env)


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"train_all_{stamp}.log"
    log_path.write_text("", encoding="utf-8")

    header = (
        f"train_all started at {datetime.now(timezone.utc).isoformat()}\n"
        f"python: {PYTHON}\n"
        f"log file: {log_path}\n"
    )
    _log_line(log_path, header)

    try:
        for name, script, extra in SCRIPTS:
            run_step(name, script, extra, log_path)
        _log_line(log_path, "\nAll training and export steps complete.\n")
    except subprocess.CalledProcessError as exc:
        _log_line(log_path, f"\nFAILED (exit {exc.returncode}): {' '.join(exc.cmd)}\n")
        raise SystemExit(exc.returncode) from exc
    except KeyboardInterrupt:
        _log_line(log_path, "\nInterrupted by user.\n")
        raise SystemExit(130) from None
    finally:
        try:
            LATEST_LOG.write_text(log_path.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass
        print(f"\nFull log saved to: {log_path}", flush=True)
        print(f"Latest copy at:    {LATEST_LOG}", flush=True)


if __name__ == "__main__":
    main()
