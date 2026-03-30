from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture(scope='session')
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope='session')
def translator_script(repo_root: Path) -> Path:
    return repo_root / 'translator' / 'statecharts.py'


@pytest.fixture(scope='session')
def python_exe() -> str:
    return sys.executable


@pytest.fixture
def run_translator(repo_root: Path, translator_script: Path, python_exe: str):
    def _run(extra_args, **kwargs):
        cmd = [python_exe, str(translator_script)] + list(extra_args)
        return subprocess.run(cmd, cwd=repo_root, **kwargs)

    return _run
