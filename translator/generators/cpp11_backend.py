"""C++11 backend orchestration.

This module keeps backend-specific wiring decisions while delegating the shared
machine-iteration flow to `shared.generate_for_backend`.
"""

from .shared import generate_for_backend


def generate_cpp11_backend(parser, cxxfile, separated):
    """Generate C++11 artifacts (state machine files and unit tests).

    Notes:
        - `cpp` mode emits split files (`.hpp` + `.cpp`).
        - Non-`cpp` modes emit single-file artifacts.
        - The C++ implementation file is included in the tests list so split
          C++11 builds keep expected linkage behavior.
    """
    generate_for_backend(
        parser,
        cxxfile,
        separated,
        split_mode_builder=parser.generate_state_machine_split,
        single_mode_builder=parser.generate_state_machine,
        unit_tests_builder=parser.generate_unit_tests,
        include_cpp_impl_in_files=True,
    )
