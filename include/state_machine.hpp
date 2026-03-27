// ############################################################################
// MIT License
//
// Copyright (c) 2022 Quentin Quadrat
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
// ############################################################################
//
// NOTE ABOUT LICENSING
// This header is licensed under MIT (see block above).
// It is intentionally not GPL-licensed.

#pragma once

#ifndef STATE_MACHINE_HPP
#define STATE_MACHINE_HPP

#include <cassert>
#include <map>
#include <queue>
#include <stdlib.h>


//-----------------------------------------------------------------------------
//! \brief Verbosity activated in debug mode.
//-----------------------------------------------------------------------------
#include <cstdio>
#if defined(FSM_DEBUG)
#define FSM_LOG printf
#else
#define FSM_LOG(...)
#endif
#define LOGE printf

//-----------------------------------------------------------------------------
//! \brief Return the given state as raw string (they shall not be free).
//! \note implement this function inside the C++ file of the derived class.
//-----------------------------------------------------------------------------
template <class STATES_ID>
const char* stringify(STATES_ID const state);

// *****************************************************************************
//! \brief Base class for depicting and running small Finite State Machine (FSM)
//! by implementing a subset of UML statechart. See this document for more
//! information about them: http://niedercorn.free.fr/iris/iris1/uml/uml09.pdf
//!
//! This class is not made for defining hierarchical state machine (HSM). It
//! also does not implement composites, history, concurrent parts of the FSM.
//! This class is fine for small Finite State Machine (FSM) and is limited due
//! to memory footprint (therefore no complex C++ designs, no dynamic containers
//! and few virtual methods). The code is based on the following link
//! https://www.codeproject.com/Articles/1087619/State-Machine-Design-in-Cplusplus-2
//! For bigger state machines, please use something more robust such as Esterel
//! SyncCharts or directly the Esterel language
//! https://www.college-de-france.fr/media/gerard-berry/UPL8106359781114103786_Esterelv5_primer.pdf
//!
//! This class holds the list of states \c State and the currently active state.
//! Each state holds actions to perform as function pointers 'on entering', 'on
//! leaving', 'on event' and 'do activity'.
//!
//! A state machine is depicted by a graph structure (nodes: states; arcs:
//! transitions) which can be represented by a matrix (states / events) usually
//! sparse. For example the following state machine, in plantuml syntax:
//!
//! @startuml
//! [*] --> Idle
//! Idle --> Starting : set speed
//! Starting --> Stopping : halt
//! Starting -> Spinning : set speed
//! Spinning -> Stopping: halt
//! Spinning --> Spinning : set speed
//! Stopping -> Idle
//! @enduml
//!
//! Can be depicted by the following matrix:
//! +-----------------+------------+-----------+-----------+
//! | States \ Event  | Set Speed  | Halt      |           |
//! +=================+============+===========+===========+
//! | IDLE            | STARTING   |           |           |
//! +-----------------+------------+-----------+-----------+
//! | STOPPING        |            |           | IDLE      |
//! +-----------------+------------+-----------+-----------+
//! | STARTING        | SPINNING   | STOPPING  |           |
//! +-----------------+------------+-----------+-----------+
//! | SPINNING        | SPINNING   | STOPPING  |           |
//! +-----------------+------------+-----------+-----------+
//!
//! The first column contains all states. The first line contains all events.
//! Each column depict a transition: given the current state (i.e. IDLE) and a
//! given event (i.e. Set Speed) the next state of the state machine will be
//! STARTING. Empty cells are forbidden transitions.
//!
//! This class does not hold directly tables for transitioning origin state to
//! destination state when an external event occured (like done in boost
//! lib). Instead, each external event shall be implemented as member function
//! in the derived FSM class and in each member function shall implement the
//! transition table.
//!
//! \tparam FSM the concrete Finite State Machine deriving from this base class.
//! In this class you shall implement external events as public methods,
//! reactions and guards as private methods, and set the first column of the
//! matrix and their guards/reactions in the constructor method. On each event
//! methods, you shall define the table of transition (implicit transition are
//! considered as ignoring the event).
//!
//! \tparam STATES_ID enumerate for giving an unique identifier for each state.
//! In our example:
//!   enum StatesID { IDLE = 0, STOPPING, STARTING, SPINNING,
//!                   IGNORING_EVENT, CANNOT_HAPPEN, MAX_STATES };
//!
//! The 3 last states are mandatory: in the matrix of the control motor of our
//! previous example, holes are implicitely IGNORING_EVENT, but the user can
//! explicitely set to CANNOT_HAPPEN to trap the whole system. Other state enum
//! shall be used to defined the table of states \c m_states which shall be
//! filled with these enums and pointer functions such as 'on entering' ...
//!
//! Transition, like states, can do reaction and have guards as pointer
//! functions.
// *****************************************************************************
template <typename FSM, class STATES_ID>
class state_machine
{
public:
    //! \brief Pointer method with no argument and returning a boolean.
    using bool_function_ptr = bool (FSM::*)();
    //! \brief Pointer method with no argument and returning void.
    using void_function_ptr = void (FSM::*)();
    using bFuncPtr = bool_function_ptr;
    using xFuncPtr = void_function_ptr;

    //--------------------------------------------------------------------------
    //! \brief Class depicting a state of the state machine and hold pointer
    //! methods for each desired action to perform. In UML states are like
    //! Moore state machine: states can do action.
    //--------------------------------------------------------------------------
    struct state
    {
        //! \brief Call the "on leaving" callback when leavinging for the first
        //! time (AND ONLY THE FIRST TIME) the state. Note: the guard can
        //! prevent calling this function.
        void_function_ptr leaving = nullptr;
        //! \brief Call the "on entry" callback when entering for the first time
        //! (AND ONLY THE FIRST TIME) in the state. Note: the transition guard
        //! can prevent calling this function.
        void_function_ptr entering = nullptr;
        //! \brief The condition validating the event and therefore preventing
        //! the transition to occur.
        void_function_ptr internal = nullptr;
    };
    using State = state;

    //--------------------------------------------------------------------------
    //! \brief Class depicting a transition from a source state to a destination
    //! state. A transition occurs when an event has occured. In UML,
    //! transitions are like Mealey state machine: transition can do action.
    //--------------------------------------------------------------------------
    struct transition
    {
        //! \brief State of destination
        STATES_ID destination = STATES_ID::IGNORING_EVENT;
        //! \brief The condition validating the event and therefore preventing
        //! the transition to occur.
        bool_function_ptr guard = nullptr;
        //! \brief The action to perform when transitioning to the destination
        //! state.
        void_function_ptr action = nullptr;
    };
    using Transition = transition;

    //! \brief Define the type of container holding all stated of the state
    //! machine.
    using states = state[int(STATES_ID::MAX_STATES)];
    //! \brief Define the type of container holding states transitions. Since
    //! a state machine is generally a sparse matrix we use red-back tree.
    using transitions = std::map<STATES_ID, transition>;
    using States = states;
    using Transitions = transitions;

    //--------------------------------------------------------------------------
    //! \brief Default constructor. Pass the number of states the FSM will use,
    //! set the initial state and if mutex shall have to be used.
    //! \param[in] initial the initial state to start with.
    //--------------------------------------------------------------------------
    state_machine(STATES_ID const initial) // FIXME should be ok for constexpr
        : m_current_state(initial)
        , m_initial_state(initial)
    {
        // FIXME static_assert not working
        assert(initial < STATES_ID::MAX_STATES);
    }

    //--------------------------------------------------------------------------
    //! \brief Restore the state machin to its initial state.
    //--------------------------------------------------------------------------
    inline void enter()
    {
        FSM_LOG("[STATE MACHINE] Restart the state machine\n");
        m_current_state = m_initial_state;
        std::queue<Transition const*> empty;
        std::swap(m_nesting, empty);
        m_enabled = true;
    }

    //--------------------------------------------------------------------------
    //! \brief Return the current state.
    //--------------------------------------------------------------------------
    inline void exit()
    {
        m_enabled = false;
    }

    inline void start()
    {
        enter();
    }

    inline void stop()
    {
        exit();
    }

    inline void reset()
    {
        enter();
    }

    //--------------------------------------------------------------------------
    //! \brief Return the current state.
    //--------------------------------------------------------------------------
    inline STATES_ID state() const
    {
        return m_current_state;
    }

    //--------------------------------------------------------------------------
    //! \brief Return the current state as string (shall not be free'ed).
    //--------------------------------------------------------------------------
    inline const char* c_str() const
    {
        return m_enabled ? stringify(m_current_state) : "--";
    }

    //--------------------------------------------------------------------------
    //! \brief Internal transition: jump to the desired state from internal
    //! event. This will call the guard, leaving actions, entering actions ...
    //! \param[in] transitions the table of transitions.
    //--------------------------------------------------------------------------
    inline void transition(transitions const& transitions)
    {
        if (!m_enabled)
            return;

        auto const& it = transitions.find(m_current_state);
        if (it != transitions.end())
        {
            transition(&it->second);
        }
        else
        {
            FSM_LOG("[STATE MACHINE] Ignoring external event\n");
            // LOGE("[STATE MACHINE] Unknow transition. Aborting!\n");
            //::exit(EXIT_FAILURE);
        }
    }

protected:
    //--------------------------------------------------------------------------
    //! \brief Internal transition: jump to the desired state from internal
    //! event. This will call the guard, leaving actions, entering actions ...
    //! \param[in] transitions the table of transitions.
    //--------------------------------------------------------------------------
    void transition(Transition const* tr);

protected:
    //! \brief Container of states.
    states m_states;

    //! \brief Current active state.
    STATES_ID m_current_state;

private:
    //! \brief Save the initial state need for restoring initial state.
    STATES_ID m_initial_state;
    //! \brief Temporary variable saving the nesting state (needed for internal
    //! event).
    std::queue<Transition const*> m_nesting;
    //! \brief Enable / disable state machine (TBD: usable for nesting state
    //! machine (that is not generated as flat state machine)).
    bool m_enabled = false;

public:
    inline bool is_active() const
    {
        return m_enabled;
    }

    inline bool isActive() const
    {
        return is_active();
    }
};

template <typename FSM, class STATES_ID>
class StateMachine : public state_machine<FSM, STATES_ID>
{
public:
    using state_machine<FSM, STATES_ID>::state_machine;
    using typename state_machine<FSM, STATES_ID>::bool_function_ptr;
    using typename state_machine<FSM, STATES_ID>::void_function_ptr;
    using typename state_machine<FSM, STATES_ID>::state;
    using typename state_machine<FSM, STATES_ID>::transition;
    using typename state_machine<FSM, STATES_ID>::states;
    using typename state_machine<FSM, STATES_ID>::transitions;
    using typename state_machine<FSM, STATES_ID>::bFuncPtr;
    using typename state_machine<FSM, STATES_ID>::xFuncPtr;
    using typename state_machine<FSM, STATES_ID>::State;
    using typename state_machine<FSM, STATES_ID>::Transition;
    using typename state_machine<FSM, STATES_ID>::States;
    using typename state_machine<FSM, STATES_ID>::Transitions;

    inline void enter()
    {
        state_machine<FSM, STATES_ID>::enter();
    }

    inline void exit()
    {
        state_machine<FSM, STATES_ID>::exit();
    }

    inline void start()
    {
        state_machine<FSM, STATES_ID>::start();
    }

    inline void stop()
    {
        state_machine<FSM, STATES_ID>::stop();
    }

    inline void reset()
    {
        state_machine<FSM, STATES_ID>::reset();
    }

    inline bool isActive() const
    {
        return state_machine<FSM, STATES_ID>::isActive();
    }
};

namespace fsm
{

    template <typename FSM, class STATES_ID>
    using state_machine = ::state_machine<FSM, STATES_ID>;

    template <typename FSM, class STATES_ID>
    using StateMachine = ::StateMachine<FSM, STATES_ID>;

} // namespace fsm

//------------------------------------------------------------------------------
template <class FSM, class STATES_ID>
void state_machine<FSM, STATES_ID>::transition(typename state_machine<FSM, STATES_ID>::Transition const* tr)
{
#if defined(THREAD_SAFETY)
    // If try_lock failed it is not important: it just means that we have called
    // an internal event from this method and internal states are still
    // protected.
    m_mutex.try_lock();
#endif

    // Reaction from internal event (therefore coming from this method called by
    // one of the action functions: memorize and leave the function: it will
    // continue thank to the while loop. This avoids recursion.
    if (m_nesting.size())
    {
        FSM_LOG("[STATE MACHINE] Internal event. Memorize state %s\n", stringify(tr->destination));
        m_nesting.push(tr);
        if (m_nesting.size() >= 16u)
        {
            LOGE("[STATE MACHINE] Infinite loop detected. Abort!\n");
            ::exit(EXIT_FAILURE);
        }
        return;
    }

    m_nesting.push(tr);
    typename state_machine<FSM, STATES_ID>::Transition const* current_transition;
    do
    {
        // Consum the current state
        current_transition = m_nesting.front();

        FSM_LOG("[STATE MACHINE] React to event from state %s\n", stringify(m_current_state));

        // Forbidden event: kill the system
        if (current_transition->destination == STATES_ID::CANNOT_HAPPEN)
        {
            LOGE("[STATE MACHINE] Forbidden event. Aborting!\n");
            ::exit(EXIT_FAILURE);
        }

        // Do not react to this event
        else if (current_transition->destination == STATES_ID::IGNORING_EVENT)
        {
            FSM_LOG("[STATE MACHINE] Ignoring external event\n");
            return;
        }

        // Unknown state: kill the system
        else if (current_transition->destination >= STATES_ID::MAX_STATES)
        {
            LOGE("[STATE MACHINE] Unknown state. Aborting!\n");
            ::exit(EXIT_FAILURE);
        }

        // Reaction: call the member function associated to the current state
        typename state_machine<FSM, STATES_ID>::State const& cst = m_states[int(m_current_state)];
        typename state_machine<FSM, STATES_ID>::State const& nst = m_states[int(current_transition->destination)];

        // Call the guard
        bool guard_res = (current_transition->guard == nullptr);
        if (!guard_res)
        {
            FSM_LOG("[STATE MACHINE] Call the guard %s -> %s\n", stringify(m_current_state),
                stringify(current_transition->destination));
            guard_res = (static_cast<FSM*>(this)->*current_transition->guard)();
        }

        if (!guard_res)
        {
            FSM_LOG("[STATE MACHINE] Transition refused by the %s guard. Stay"
                    " in state %s\n",
                stringify(current_transition->destination), stringify(m_current_state));
        }
        else
        {
            // The guard allowed the transition to the next state
            FSM_LOG("[STATE MACHINE] Transitioning to new state %s\n", stringify(current_transition->destination));

            // Transition
            STATES_ID previous_state = m_current_state;
            m_current_state = current_transition->destination;

            // Transitioning to a new state ?
            if (previous_state != current_transition->destination)
            {
                // Do reactions when leaving the current state
                if (cst.leaving != nullptr)
                {
                    FSM_LOG("[STATE MACHINE] Call the state %s 'on leaving' action\n", stringify(previous_state));
                    (static_cast<FSM*>(this)->*cst.leaving)();
                }
            }

            // Do transitiona ction
            if (current_transition->action != nullptr)
            {
                FSM_LOG("[STATE MACHINE] Call the transition %s -> %s action\n", stringify(previous_state),
                    stringify(current_transition->destination));
                (static_cast<FSM*>(this)->*current_transition->action)();
            }

            // Transitioning to a new state ?
            if (previous_state != current_transition->destination)
            {
                // Do reactions when entring into the new state
                if (nst.entering != nullptr)
                {
                    FSM_LOG("[STATE MACHINE] Call the state %s 'on entry' action\n",
                        stringify(current_transition->destination));
                    (static_cast<FSM*>(this)->*nst.entering)();
                }

                // Do internal transitions when no event are present
                if (nst.internal != nullptr)
                {
                    FSM_LOG("[STATE MACHINE] Call the state %s 'on internal' action\n",
                        stringify(current_transition->destination));
                    (static_cast<FSM*>(this)->*nst.internal)();
                }
            }
            else
            {
                FSM_LOG("[STATE MACHINE] Stay in the same state %s\n", stringify(current_transition->destination));
            }
        }

        m_nesting.pop();
    } while (!m_nesting.empty());

#if defined(THREAD_SAFETY)
    m_mutex.unlock();
#endif
}

#endif // STATE_MACHINE_HPP
