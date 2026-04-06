###############################################################################
## PlantUML Statecharts (State Machine) Translator.
## Copyright (c) 2026 Laurent Lardinois <https://github.com/type-one>
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
"""Rust backend MVP regression tests."""

import tempfile
from pathlib import Path


def test_rust_target_generates_mvp_rust_file(run_translator):
    with tempfile.TemporaryDirectory(prefix='fsm_rust_mvp_') as out:
        out_path = Path(out)
        result = run_translator(
            ['examples/SimpleFSM.plantuml', 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        rust_file = out_path / 'simple_fsm.rs'
        assert rust_file.exists()

        content = rust_file.read_text()
        assert 'pub enum State' in content
        assert 'pub struct SimpleFsm' in content
        assert '#![allow(non_snake_case)]' not in content
        assert '#![allow(non_camel_case_types)]' not in content
        assert 'match self.state' in content


def test_rust_ignores_camel_cli_switch_for_identifier_policy(run_translator):
    """Rust backend should keep its own naming policy regardless of -c/--camel.

    For backwards compatibility, the C++ backends honor -c, but Rust output
    should remain idiomatic and deterministic without requiring naming allows.
    """
    with tempfile.TemporaryDirectory(prefix='fsm_rust_camel_ignored_') as out:
        out_path = Path(out)
        result = run_translator(
            ['examples/SimpleFSM.plantuml', 'rust', '-c', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        rust_file = out_path / 'simple_fsm.rs'
        assert rust_file.exists()
        content = rust_file.read_text()

    assert 'pub struct SimpleFsm' in content
    assert '#![allow(non_snake_case)]' not in content
    assert '#![allow(non_camel_case_types)]' not in content


def test_rust_event_transition_sequence_contract(run_translator):
    """Guarded cross-state transition keeps UML action order in Rust output.

    Contract for SimpleFSM event1 (STATE1 -> STATE2 with guard and action):
    guard -> leaving(source) -> transition action -> state assign -> entering(dest).
    """
    with tempfile.TemporaryDirectory(prefix='fsm_rust_contract_') as out:
        out_path = Path(out)
        result = run_translator(
            ['examples/SimpleFSM.plantuml', 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'simple_fsm.rs').read_text()

    event_start = content.index('pub fn event1(&mut self) {')
    event_end = content.index('pub fn event2(&mut self) {')
    event1_block = content[event_start:event_end]

    i_guard = event1_block.index('if self.on_guarding_state1_state2() {')
    i_leave = event1_block.index('self.on_leaving_state1();')
    i_action = event1_block.index('self.on_transitioning_state1_state2();')
    i_assign = event1_block.index('self.state = State::State2;')
    i_enter = event1_block.index('self.on_entering_state2();')

    assert i_guard < i_leave < i_action < i_assign < i_enter


def test_rust_same_state_transition_has_no_state_reassignment_or_enter_leave(run_translator):
    """Same-state transition should only run transition action when guard passes.

    Contract for SimpleFSM event3 (STATE1 -> STATE1 with guard and action):
    - guard and transition action are emitted,
    - no state assignment is emitted,
    - no leaving/entering callbacks are emitted.
    """
    with tempfile.TemporaryDirectory(prefix='fsm_rust_self_transition_') as out:
        out_path = Path(out)
        result = run_translator(
            ['examples/SimpleFSM.plantuml', 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'simple_fsm.rs').read_text()

    event_start = content.index('pub fn event3(&mut self) {')
    event_end = content.index('pub fn event5(&mut self) {')
    event3_block = content[event_start:event_end]

    assert 'if self.on_guarding_state1_state1() {' in event3_block
    assert 'self.on_transitioning_state1_state1();' in event3_block
    assert 'self.state = ' not in event3_block
    assert 'self.on_leaving_state1();' not in event3_block
    assert 'self.on_entering_state1();' not in event3_block


def test_rust_destructor_transition_sets_destructor_without_entering_callback(run_translator):
    """Terminal transition to `*` should assign `State::Destructor` only.

    Contract for SimpleFSM event6 (STATE2 -> *):
    - leaves source state,
    - assigns `State::Destructor`,
    - does not call any entering callback for a terminal state.
    """
    with tempfile.TemporaryDirectory(prefix='fsm_rust_destructor_') as out:
        out_path = Path(out)
        result = run_translator(
            ['examples/SimpleFSM.plantuml', 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'simple_fsm.rs').read_text()

    event_start = content.index('pub fn event6(&mut self) {')
    event_end = content.index('pub fn event3(&mut self) {')
    event6_block = content[event_start:event_end]

    assert 'self.on_leaving_state2();' in event6_block
    assert 'self.state = State::Destructor;' in event6_block
    assert 'self.on_entering_' not in event6_block


def test_rust_noevent_chaining_emitted_for_motor_halt(run_translator):
    """No-event transitions should chain immediately after explicit transitions.

    In `Motor.plantuml`, `halt` sends START/SPINNING to STOP, and STOP has an
    immediate no-event transition to IDLE. Rust output should therefore emit
    the second state assignment in each relevant branch.
    """
    with tempfile.TemporaryDirectory(prefix='fsm_rust_noevent_motor_') as out:
        out_path = Path(out)
        result = run_translator(
            ['examples/Motor.plantuml', 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'motor.rs').read_text()

    event_start = content.index('pub fn halt(&mut self) {')
    event_end = content.index('fn on_guarding_idle_start(&self) -> bool {')
    halt_block = content[event_start:event_end]

    # Explicit transition to STOP remains present.
    assert halt_block.count('self.state = State::Stop;') == 2
    # Immediate no-event chain STOP -> IDLE should be emitted in both branches.
    assert halt_block.count('self.state = State::Idle;') == 2


def test_rust_enter_emits_guarded_initial_state_selection(run_translator):
    """Multiple initial transitions should emit ordered guarded selection.

    This checks generation shape, not runtime guard semantics.
    """
    uml = """@startuml
[*] --> A : [start_in_a]
[*] --> B
A --> B : go
@enduml
"""

    with tempfile.TemporaryDirectory(prefix='fsm_rust_init_guard_') as out:
        out_path = Path(out)
        uml_path = out_path / 'guarded_init.plantuml'
        uml_path.write_text(uml)

        result = run_translator(
            [str(uml_path), 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'guarded_init.rs').read_text()

    enter_start = content.index('pub fn enter(&mut self) {')
    enter_end = content.index('pub fn exit(&mut self) {')
    enter_block = content[enter_start:enter_end]

    assert 'if self.on_guarding_constructor_a() {' in enter_block
    assert 'self.state = State::A;' in enter_block
    assert 'self.state = State::B;' in enter_block
    assert 'return;' in enter_block


def test_rust_noevent_guarded_chain_is_emitted_after_event_transition(run_translator):
    """Guarded no-event chain should be nested after explicit event transition."""
    uml = """@startuml
[*] --> A
A --> B : go
B --> C : [can_chain]
C --> D
@enduml
"""

    with tempfile.TemporaryDirectory(prefix='fsm_rust_noevent_guarded_') as out:
        out_path = Path(out)
        uml_path = out_path / 'guarded_chain.plantuml'
        uml_path.write_text(uml)

        result = run_translator(
            [str(uml_path), 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'guarded_chain.rs').read_text()

    event_start = content.index('pub fn go(&mut self) {')
    event_end = content.index('fn on_guarding_b_c(&self) -> bool {')
    go_block = content[event_start:event_end]

    assert 'self.state = State::B;' in go_block
    assert 'if self.on_guarding_b_c() {' in go_block
    assert 'self.state = State::C;' in go_block
    assert 'self.state = State::D;' in go_block


def test_rust_noevent_cycle_emission_stays_finite(run_translator):
    """No-event cycle should not produce unbounded emitted chaining code."""
    uml = """@startuml
[*] --> A
A --> B : go
B --> C
C --> B
@enduml
"""

    with tempfile.TemporaryDirectory(prefix='fsm_rust_noevent_cycle_') as out:
        out_path = Path(out)
        uml_path = out_path / 'cycle_chain.plantuml'
        uml_path.write_text(uml)

        result = run_translator(
            [str(uml_path), 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'cycle_chain.rs').read_text()

    event_start = content.index('pub fn go(&mut self) {')
    # This minimal diagram has no actions, so no on_transitioning_* methods are
    # generated.  Use the end of the impl block as the upper bound instead.
    event_end = content.rindex('\n}')
    go_block = content[event_start:event_end]

    # Explicit event transition A->B plus finite no-event chain B->C->B.
    assert go_block.count('self.state = State::B;') <= 2
    assert go_block.count('self.state = State::C;') == 1


def test_rust_single_param_event_no_unused_parens(run_translator):
    """Single-parameter events must emit `let _ = param;` without extra parens.

    `let _ = (param);` triggers `unused_parens` in rustc. Regression guard for
    the keep-alive pattern: single param must use bare assignment, two or more
    params keep the tuple form.
    """
    uml = """@startuml
[*] --> A
A --> B : go(speed)
@enduml
"""

    with tempfile.TemporaryDirectory(prefix='fsm_rust_keepalive_') as out:
        out_path = Path(out)
        uml_path = out_path / 'keepalive.plantuml'
        uml_path.write_text(uml)

        result = run_translator(
            [str(uml_path), 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'keepalive.rs').read_text()

    # Bare assignment — no superfluous parentheses.
    assert 'let _ = speed;' in content
    assert 'let _ = (speed);' not in content


def test_rust_extra_code_annotations_emitted_as_comments(run_translator):
    """PlantUML '[header]', '[init]', '[code]', '[footer]' annotations must
    appear in the generated Rust file as fenced comment blocks.

    These sections contain C++ code which cannot be inlined into Rust directly.
    The backend must preserve the original text as comments so the author can
    translate them manually. Generation must still succeed and produce a file
    that compiles as a Rust library.
    """
    uml = """@startuml
'[header] use std::sync::Mutex;
'[init] reset_counters();
'[code] some_field: u32,
'[footer] end_of_module();
[*] --> A
A --> B : go
@enduml
"""

    with tempfile.TemporaryDirectory(prefix='fsm_rust_extracode_') as out:
        out_path = Path(out)
        uml_path = out_path / 'extra.plantuml'
        uml_path.write_text(uml)

        result = run_translator(
            [str(uml_path), 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'extra.rs').read_text()

    assert '// --- from PlantUML [header]' in content
    assert '// use std::sync::Mutex;' in content
    assert '// --- end [header]' in content

    assert '// --- from PlantUML [init]' in content
    assert 'reset_counters();' in content
    assert '// --- end [init]' in content

    assert '// --- from PlantUML [code]' in content
    assert 'some_field: u32,' in content
    assert '// --- end [code]' in content

    assert '// --- from PlantUML [footer]' in content
    assert 'end_of_module();' in content
    assert '// --- end [footer]' in content


def test_rust_c_str_returns_inactive_sentinel_when_not_enabled(run_translator):
    """c_str() must return \"--\" when the FSM is inactive (after exit()).

    Contract matching the C++20 backend: `c_str()` returns `"--"` when
    `m_active` / `enabled` is false, and the real state name when active.
    """
    with tempfile.TemporaryDirectory(prefix='fsm_rust_cstr_inactive_') as out:
        out_path = Path(out)
        result = run_translator(
            ['examples/SimpleFSM.plantuml', 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'simple_fsm.rs').read_text()

    c_str_start = content.index('pub fn c_str(&self) -> &\'static str {')
    c_str_end = content.index('pub fn event1(', c_str_start)
    c_str_block = content[c_str_start:c_str_end]

    # Inactive guard must come first, before the match.
    assert 'if !self.enabled { return "--"; }' in c_str_block
    i_guard = c_str_block.index('if !self.enabled { return "--"; }')
    i_match = c_str_block.index('match self.state {')
    assert i_guard < i_match


def test_rust_triggers_multi_guard_same_event_dispatch(run_translator):
    """Same event with multiple guarded/unguarded destinations must emit
    ordered guard checks that fall through to the unguarded branch.

    Exercises ``Triggers.plantuml``:
    - ``A --> B : e [x == 10]``   guarded, checked first
    - ``A --> C : e``              unguarded fallthrough (no else-if needed)
    - ``A --> D : [x > 10]``       no-event transition from [*] to D (separate)

    Contract for the ``e`` event method:
    * The guarded A->B check appears before the unconditional A->C assignment.
    * Both state assignments are present.
    * No spurious duplicate ``[this](a&)`` lambda (C++20 regression kept here
      as a structural check in Rust: the single ``e`` method covers all arcs).
    """
    with tempfile.TemporaryDirectory(prefix='fsm_rust_triggers_') as out:
        out_path = Path(out)
        result = run_translator(
            ['examples/Triggers.plantuml', 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'triggers.rs').read_text()

    e_start = content.index('pub fn e(&mut self) {')
    e_end = content.index('\n    fn ', e_start)
    e_block = content[e_start:e_end]

    # Guarded branch to B must precede unconditional branch to C.
    assert 'if self.on_guarding_a_b() {' in e_block
    assert 'self.state = State::B;' in e_block
    assert 'self.state = State::C;' in e_block
    i_guard = e_block.index('if self.on_guarding_a_b() {')
    i_c = e_block.index('self.state = State::C;')
    assert i_guard < i_c

    # Only one pub fn named 'e' — no duplication.
    assert content.count('pub fn e(') == 1


def test_rust_internal_transition_is_self_loop_without_state_change(run_translator):
    """'State : on event / action' internal transitions must emit a self-loop
    event method that runs the action (and optional guard) but never reassigns
    ``self.state`` and never calls entering/leaving callbacks.

    Exercises ``SimpleFSM.plantuml``:
    - ``State1 : on event3 [guard3] / action3()``  guarded self-loop
    - ``State2 : on event5 / action5()``            unguarded self-loop
    """
    with tempfile.TemporaryDirectory(prefix='fsm_rust_internal_tr_') as out:
        out_path = Path(out)
        result = run_translator(
            ['examples/SimpleFSM.plantuml', 'rust', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        content = (out_path / 'simple_fsm.rs').read_text()

    # --- event3: guarded self-loop on State1 ---
    e3_start = content.index('pub fn event3(&mut self) {')
    e3_end = content.index('pub fn event5(&mut self) {')
    e3_block = content[e3_start:e3_end]

    assert 'if self.on_guarding_state1_state1() {' in e3_block
    assert 'self.on_transitioning_state1_state1();' in e3_block
    assert 'self.state = ' not in e3_block
    assert 'on_entering_' not in e3_block
    assert 'on_leaving_' not in e3_block

    # --- event5: unguarded self-loop on State2 ---
    e5_start = content.index('pub fn event5(&mut self) {')
    e5_end = content.index('\n    fn ', e5_start)
    e5_block = content[e5_start:e5_end]

    assert 'self.on_transitioning_state2_state2();' in e5_block
    assert 'self.state = ' not in e5_block
    assert 'on_entering_' not in e5_block
    assert 'on_leaving_' not in e5_block


def test_rust_rejects_composite_and_orthogonal_diagrams(run_translator):
    """The Rust backend must reject composite and orthogonal diagrams with a
    non-zero exit code and a descriptive error message, matching the behaviour
    of the C++20 backend.

    Exercises three diagrams:
    - ``ComplexComposite.plantuml`` — deep composite nesting
    - ``Pompe.plantuml``           — shallow composite with entry actions
    - ``SimpleOrthogonal.plantuml``— concurrent/orthogonal regions
    """
    import pytest
    failing = [
        'examples/ComplexComposite.plantuml',
        'examples/Pompe.plantuml',
        'examples/SimpleOrthogonal.plantuml',
    ]

    for source in failing:
        with tempfile.TemporaryDirectory(prefix='fsm_rust_reject_') as out:
            result = run_translator(
                [source, 'rust', '-o', out],
                capture_output=True,
                text=True,
                check=False,
            )

        output = (result.stdout or '') + (result.stderr or '')
        assert result.returncode != 0, f'{source} should have been rejected'
        assert 'Unsupported PlantUML diagram features detected:' in output, (
            f'{source}: expected unsupported-features error, got: {output!r}'
        )
