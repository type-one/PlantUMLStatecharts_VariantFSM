"""
Shared pytest fixtures for the translator test suite.

All fixtures that are used across multiple test modules live here.
The ``run_translator`` factory fixture is the primary entry-point: it
shells out to ``statecharts.py`` exactly as a real user would from the
repository root, so every subprocess test exercises the full CLI path.
"""

from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture(scope='session')
def repo_root() -> Path:
    """Absolute path to the repository root (two levels above this file)."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope='session')
def translator_script(repo_root: Path) -> Path:
    """Absolute path to the main translator entry-point (statecharts.py)."""
    return repo_root / 'translator' / 'statecharts.py'


@pytest.fixture(scope='session')
def python_exe() -> str:
    """The Python interpreter that is currently running the test suite.

    Using ``sys.executable`` ensures the same virtual-environment (and
    therefore the same installed packages) is used for the spawned
    subprocess, rather than whatever ``python`` resolves to on PATH.
    """
    return sys.executable


@pytest.fixture
def run_translator(repo_root: Path, translator_script: Path, python_exe: str):
    """Factory fixture that invokes the translator as a subprocess.

    Returns a callable ``_run(extra_args, **kwargs)`` that prepends the
    Python interpreter and the translator script path, then delegates to
    ``subprocess.run`` with the repository root as the working directory.
    Extra keyword arguments (e.g. ``check=True``, ``capture_output=True``)
    are forwarded verbatim to ``subprocess.run``.
    """
    def _run(extra_args, **kwargs):
        cmd = [python_exe, str(translator_script)] + list(extra_args)
        return subprocess.run(cmd, cwd=repo_root, **kwargs)

    return _run
