"""Isolate tests that write site builds or data snapshots."""

import shutil
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def temporary_project(add_cleanup, *directories: str) -> Path:
    workspace = tempfile.TemporaryDirectory()
    add_cleanup(workspace.cleanup)
    root = Path(workspace.name)
    for directory in directories:
        shutil.copytree(PROJECT_ROOT / directory, root / directory)
    return root
