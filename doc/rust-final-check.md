# Final Rust Check Report

Date: 2026-04-07

## Scope

This report validates Rust backend behavior across all example diagrams in `examples/` with:

- Direct generation: `python3 -m translator.statecharts <diagram> rust -o <out>`
- Auto-flatten generation: `python3 -m translator.statecharts <diagram> rust --auto-flatten -o <out>`
- Generated test execution (when direct generation succeeds): compile and run `*_tests.rs` using `rustc --test`

## Summary

- Total diagrams checked: 17
- Direct Rust generation: 13 OK, 4 FAIL
- Rust generation with auto-flatten: 16 OK, 1 FAIL
- Generated Rust tests (for direct-generation OK cases): 8 OK, 5 FAIL

## Per-Diagram Matrix

| Diagram | Direct rust | Rust with --auto-flatten | Generated tests |
|---|---|---|---|
| BadSwitch1 | OK | OK | FAIL |
| BadSwitch2 | OK | OK | FAIL |
| ComplexComposite | FAIL | OK | N/A |
| DigitalWatch | OK | OK | FAIL |
| EthernetBox | OK | OK | OK |
| FixBadSwitch2 | OK | OK | FAIL |
| Gumball | OK | OK | OK |
| InfiniteLoop | OK | OK | OK |
| LaneKeeping | OK | OK | OK |
| Motor | OK | OK | OK |
| Pompe | FAIL | OK | N/A |
| RichMan | OK | OK | OK |
| SelfParking | OK | OK | OK |
| SimpleComposite | FAIL | OK | N/A |
| SimpleFSM | OK | OK | OK |
| SimpleOrthogonal | FAIL | FAIL | N/A |
| Triggers | OK | OK | FAIL |

## Notes

- The direct-generation FAIL set is consistent with unsupported hierarchical/orthogonal features unless flattening is requested.
- `SimpleOrthogonal` still fails even with `--auto-flatten`, which is expected because orthogonal/concurrent regions are not supported.
- Test FAIL entries are assertion mismatches in generated test expectations, not code-generation failures.
