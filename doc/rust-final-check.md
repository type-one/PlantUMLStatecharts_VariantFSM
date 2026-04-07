# Final Rust Check Report

Date: 2026-04-07

## Scope

This report validates Rust backend behavior across all example diagrams in `examples/` with:

- Direct generation: `python3 -m translator.statecharts <diagram> rust -o <out>`
- Auto-flatten generation: `python3 -m translator.statecharts <diagram> rust --auto-flatten -o <out>`
- Compile-check (when direct generation succeeds): compile generated machine source with `rustc --crate-type lib`
- Generated tests execution (when direct generation succeeds): compile and run `*_tests.rs` using `rustc --test`

## Summary

- Total diagrams checked: 17
- Direct Rust generation: 13 OK, 4 FAIL
- Rust generation with auto-flatten: 16 OK, 1 FAIL
- Rust compile-check (for direct-generation OK cases): 13 OK, 0 FAIL
- Generated tests execution (for direct-generation OK cases): 8 OK, 5 FAIL, 0 SKIP

## Per-Diagram Matrix

| Diagram | Direct generation | Generation with --auto-flatten | Compile-check | Generated tests execution |
|---|---|---|---|---|
| BadSwitch1 | OK | OK | OK | FAIL |
| BadSwitch2 | OK | OK | OK | FAIL |
| ComplexComposite | FAIL | OK | N/A | N/A |
| DigitalWatch | OK | OK | OK | FAIL |
| EthernetBox | OK | OK | OK | OK |
| FixBadSwitch2 | OK | OK | OK | FAIL |
| Gumball | OK | OK | OK | OK |
| InfiniteLoop | OK | OK | OK | OK |
| LaneKeeping | OK | OK | OK | OK |
| Motor | OK | OK | OK | OK |
| Pompe | FAIL | OK | N/A | N/A |
| RichMan | OK | OK | OK | OK |
| SelfParking | OK | OK | OK | OK |
| SimpleComposite | FAIL | OK | N/A | N/A |
| SimpleFSM | OK | OK | OK | OK |
| SimpleOrthogonal | FAIL | FAIL | N/A | N/A |
| Triggers | OK | OK | OK | FAIL |

## Notes

- The direct-generation FAIL set is consistent with unsupported hierarchical/orthogonal features unless flattening is requested.
- `SimpleOrthogonal` still fails even with `--auto-flatten`, which is expected because orthogonal/concurrent regions are not supported.
- Test FAIL entries are assertion mismatches in generated test expectations, not code-generation failures.
