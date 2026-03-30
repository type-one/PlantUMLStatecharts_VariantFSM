"""Backend orchestration entry points.

This package contains lightweight wrappers that choose the right generation
strategy (C++11 or C++20 variant) while delegating shared loop mechanics to
`shared.generate_for_backend`.
"""

from .cpp11_backend import generate_cpp11_backend
from .cpp20_backend import generate_cpp20_backend

__all__ = [
	'generate_cpp11_backend',
	'generate_cpp20_backend',
]
