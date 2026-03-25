// ############################################################################
// MIT License
//
// Copyright (c) 2026 Laurent Lardinois (with the help of Copilot)
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

#ifndef STATE_MACHINE_VARIANT_HPP
#  define STATE_MACHINE_VARIANT_HPP

// C++20 std::variant / std::visit runtime support for generated FSMs.
// No base class is needed: the generated class is self-contained.
// This header supplies only the helpers shared by all generated FSMs.

#  include <variant>
#  include <optional>
#  include <cstdio>
#  include <cstring>

//-----------------------------------------------------------------------------
//! \brief Verbosity activated when compiled with -DFSM_DEBUG.
//-----------------------------------------------------------------------------
#  if defined(FSM_DEBUG)
#    define LOGD printf
#  else
#    define LOGD(...)
#  endif
#  define LOGE printf

namespace fsm {

// ---------------------------------------------------------------------------
//! \brief Overloaded-lambda visitor helper (C++17/20).
//!
//! Aggregates multiple lambdas into a single visitor type so they can be
//! passed directly to std::visit.  Example usage:
//!
//!   std::visit(fsm::overloaded{
//!       [](StateA const&) { /* handle A */ },
//!       [](StateB const&) { /* handle B */ },
//!       [](auto  const&) { /* fallback  */ },
//!   }, my_variant);
// ---------------------------------------------------------------------------
template<typename... Ts>
struct overloaded : Ts...
{
    using Ts::operator()...;
};

// Deduction guide — required in C++17, optional but harmless in C++20.
template<typename... Ts>
overloaded(Ts...) -> overloaded<Ts...>;

} // namespace fsm

#endif // STATE_MACHINE_VARIANT_HPP
