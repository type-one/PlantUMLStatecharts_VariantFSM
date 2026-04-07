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
"""Backend orchestration entry points.

This package contains lightweight wrappers that choose the right generation
strategy (C++11 or C++20 variant) while delegating shared loop mechanics to
`shared.generate_for_backend`.
"""

from .cpp11_backend import generate_cpp11_backend
from .cpp20_backend import generate_cpp20_backend
from .rust_backend import generate_rust_backend

__all__ = [
	'generate_cpp11_backend',
	'generate_cpp20_backend',
	'generate_rust_backend',
]
