"""LEGACY — not used by the active pipeline_orchestrator flow.

This checkpoint framework predates the current orchestrator and is not
called from main.py or pipeline_orchestrator.py.  Do not add new checks
here; use pipeline_orchestrator instead.

Any module inside this package whose name starts with ``check_`` and
contains a subclass of BaseCheckpoint is loaded automatically when
:func:`load_checkpoints` is called.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path

from checkpoints.base import BaseCheckpoint


def load_checkpoints() -> list[BaseCheckpoint]:
    """Import all check_*.py modules and return instantiated checkpoints."""
    checkpoints: list[BaseCheckpoint] = []
    package_dir = Path(__file__).parent

    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if not module_name.startswith("check_"):
            continue
        module = importlib.import_module(f"checkpoints.{module_name}")
        expected_module = f"checkpoints.{module_name}"
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseCheckpoint) and obj is not BaseCheckpoint and obj.__module__ == expected_module:
                checkpoints.append(obj())

    return checkpoints
