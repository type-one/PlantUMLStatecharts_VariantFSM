#!/usr/bin/env python3

"""Legacy test entrypoint.

The test suite has been migrated to pytest-style focused files (`test_*.py`).
Running this file directly keeps backward compatibility with old workflows.
"""

import sys
from pathlib import Path

import pytest


def main() -> int:
    test_dir = Path(__file__).resolve().parent
    return pytest.main([str(test_dir)] + sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
