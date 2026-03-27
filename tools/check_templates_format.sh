#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

formatter="${CLANG_FORMAT:-clang-format}"
if ! command -v "$formatter" >/dev/null 2>&1; then
    echo "error: clang-format not found (set CLANG_FORMAT or install clang-format)" >&2
    exit 1
fi

mapfile -t files < <(find include examples translator -type f \( -name '*.hpp' -o -name '*.cpp' \) \
    -not -path '*/build/*' | sort)

if [[ ${#files[@]} -eq 0 ]]; then
    echo "No C++ template files found to check."
    exit 0
fi

"$formatter" --dry-run --Werror "${files[@]}"
echo "Template C++ files are clang-format compliant."
