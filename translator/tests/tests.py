#!/usr/bin/env python3
###############################################################################
## PlantUML Statecharts (State Machine) Translator.
## Copyright (c) 2022 Quentin Quadrat <lecrapouille@gmail.com>
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
