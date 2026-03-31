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
        assert 'pub struct simple_fsm' in content
        assert 'match self.state' in content


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
    event_end = content.index('fn on_transitioning_a_b(&mut self) {')
    go_block = content[event_start:event_end]

    # Explicit event transition A->B plus finite no-event chain B->C->B.
    assert go_block.count('self.state = State::B;') <= 2
    assert go_block.count('self.state = State::C;') == 1
