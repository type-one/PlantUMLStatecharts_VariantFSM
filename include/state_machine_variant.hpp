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
//
// NOTE ABOUT LICENSING
// This header is licensed under MIT (see block above).
// It is intentionally not GPL-licensed.

#pragma once

#ifndef STATE_MACHINE_VARIANT_HPP
#define STATE_MACHINE_VARIANT_HPP

// C++20 std::variant / std::visit runtime support for generated FSMs.
// No base class is needed: the generated class is self-contained.
// This header supplies only the helpers shared by all generated FSMs.

#include <cstdio>
#include <cstring>
#include <optional>
#include <type_traits>
#include <utility>
#include <variant>
#if defined(FSM_THREAD_SAFETY)
#include <mutex>
#endif

//-----------------------------------------------------------------------------
//! \brief Verbosity activated when compiled with -DFSM_DEBUG.
//-----------------------------------------------------------------------------
#if defined(FSM_DEBUG)
#define FSM_LOGD std::printf // NOLINT(cppcoreguidelines-macro-usage)
#else
#define FSM_LOGD(...) // NOLINT(cppcoreguidelines-macro-usage)
#endif
#define FSM_LOGE(...) std::fprintf(stderr, __VA_ARGS__) // NOLINT(cppcoreguidelines-macro-usage)

namespace fsm
{

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
    template <typename... Ts>
    struct overloaded : Ts...
    {
        using Ts::operator()...;

        constexpr explicit overloaded(Ts... ts) noexcept((std::is_nothrow_move_constructible_v<Ts> && ...))
            : Ts(std::move(ts))...
        {
        }
    };

    // Deduction guide — required in C++17, optional but harmless in C++20.
    template <typename... Ts>
    overloaded(Ts...) -> overloaded<Ts...>;

    template <typename... Ts>
    constexpr auto make_overloaded(Ts&&... ts) noexcept((std::is_nothrow_constructible_v<std::decay_t<Ts>, Ts> && ...))
        -> overloaded<std::decay_t<Ts>...>
    {
        return overloaded<std::decay_t<Ts>...>{std::forward<Ts>(ts)...};
    }

} // namespace fsm

#endif // STATE_MACHINE_VARIANT_HPP
