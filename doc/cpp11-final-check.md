# Final C++11 Check Report

Date: 2026-04-07

## Scope

This report validates the C++11 backend behavior across all example diagrams in `examples/` with:

- Direct generation: `python3 -m translator.statecharts <diagram> cpp -o <out>`
- Auto-flatten generation: `python3 -m translator.statecharts <diagram> cpp --auto-flatten -o <out>`
- Compile-smoke (when direct generation succeeds): compile generated implementation with `g++ -std=c++14 -c`
- Generated test execution status

## Summary

- Total diagrams checked: 17
- Direct C++11 generation: 13 OK, 4 FAIL
- C++11 generation with auto-flatten: 16 OK, 1 FAIL
- C++11 compile-smoke (for direct-generation OK cases): 11 OK, 2 FAIL
- Generated test execution: 13 skipped (`gtest/gmock` not available in current environment)

## Per-Diagram Matrix

| Diagram | Direct cpp | Cpp with --auto-flatten | Compile-smoke | Generated tests |
|---|---|---|---|---|
| BadSwitch1 | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |
| BadSwitch2 | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |
| ComplexComposite | FAIL | OK | N/A | N/A |
| DigitalWatch | OK | OK | FAIL | SKIP_GTEST_GMOCK_MISSING |
| EthernetBox | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |
| FixBadSwitch2 | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |
| Gumball | OK | OK | FAIL | SKIP_GTEST_GMOCK_MISSING |
| InfiniteLoop | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |
| LaneKeeping | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |
| Motor | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |
| Pompe | FAIL | OK | N/A | N/A |
| RichMan | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |
| SelfParking | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |
| SimpleComposite | FAIL | OK | N/A | N/A |
| SimpleFSM | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |
| SimpleOrthogonal | FAIL | FAIL | N/A | N/A |
| Triggers | OK | OK | OK | SKIP_GTEST_GMOCK_MISSING |

## Notes

- The direct-generation FAIL set is consistent with unsupported hierarchical/orthogonal features unless flattening is requested.
- `SimpleOrthogonal` still fails even with `--auto-flatten`, which is expected because orthogonal/concurrent regions are not supported.
- Compile-smoke failures:
  - `DigitalWatch`: undeclared symbols from model snippets (e.g., `min`, `hours`) and invalid snippet text in generated code (`show current time`).
  - `Gumball`: model action snippet contains a missing semicolon (`printf("Sorry no more gumballs\\n")`).
- Generated test execution is marked as skipped in this run because `gtest`/`gmock` were not available via `pkg-config` in the current environment.
