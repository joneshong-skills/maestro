#!/usr/bin/env bash
# Example: Synthesis pattern — cross-validate a design with codex + gemini,
# then claude synthesizes a unified answer.
#
# Demonstrates:
#   1. Auto-routing via natural-language signal ("cross-validate")
#   2. Explicit pattern override
#   3. Custom advisor list

set -euo pipefail

MAESTRO="${MAESTRO:-python3 $HOME/.claude/skills/maestro/scripts/maestro.py}"

echo "=== Example 1: Auto-route via signal ==="
echo "(Natural-language 'cross-validate' should auto-select synthesis)"
echo
$MAESTRO plan "Cross-validate this rate-limit design — codex for backend correctness, gemini for UX edge cases"

echo
echo "=== Example 2: Explicit --pattern synthesis ==="
echo
$MAESTRO plan --pattern synthesis "Review the new auth flow: backend security and user-facing error handling"

echo
echo "=== Example 3: Custom advisors + synthesizer ==="
echo "(3 advisors → claude synthesizes)"
echo
$MAESTRO plan --pattern synthesis \
  --advisors codex,gemini,qwen \
  --synthesizer claude \
  "Design the public API rate limiter — minutely + daily windows"

echo
echo "=== To actually run (will dispatch to real CLIs): ==="
echo
echo "  $MAESTRO run --pattern synthesis 'Review this PR for arch + UX'"
echo
echo "Output will contain (in this order):"
echo "  - Advisor 1 (codex) raw output"
echo "  - Advisor 2 (gemini) raw output"
echo "  - Synthesizer output with sections:"
echo "      ## Consensus"
echo "      ## Conflicts"
echo "      ## Final Direction"
echo "      ## Action Checklist"
