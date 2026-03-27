#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

formatter="${CLANG_FORMAT:-clang-format}"
if ! command -v "$formatter" >/dev/null 2>&1; then
    echo "error: clang-format not found (set CLANG_FORMAT or install clang-format)" >&2
    exit 1
fi

# Source/template files maintained in this repository (exclude generated build output).
mapfile -t files < <(find include examples translator -type f \( -name '*.hpp' -o -name '*.cpp' \) \
    -not -path '*/build/*' | sort)

if [[ ${#files[@]} -eq 0 ]]; then
    echo "No C++ template files found to format."
    exit 0
fi

"$formatter" -i "${files[@]}"
echo "Formatted ${#files[@]} C++ template files."
