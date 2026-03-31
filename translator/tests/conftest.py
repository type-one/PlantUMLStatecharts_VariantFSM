###############################################################################
## PlantUML Statecharts (State Machine) Translator.
## Copyright (c) 2026 Laurent Lardinois <https://github.com/type-one>
## Original author: Quentin Quadrat <lecrapouille@gmail.com>
##
## This file is part of PlantUML Statecharts (State Machine) Translator.
##
## This tool is free software: you can redistribute it and/or modify it
## under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see http://www.gnu.org/licenses/.
###############################################################################
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
