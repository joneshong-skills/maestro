# Pattern Catalog

## Solo — Single Agent Dispatch

**When**: Simple, well-defined tasks. One CLI can handle it alone.
**Agents**: 1
**Cost**: Lowest (1x)
**Duration**: Fastest

```bash
$MAESTRO run "Fix the typo in README.md" --cwd /path/to/project
```

**How it works**:
1. Analyze task → identify top category
2. Route to primary CLI for that category
3. Dispatch synchronously
4. Return result

**CLI selection**:
- Code tasks → Claude Code (best quality)
- Long docs → Gemini CLI (1M context)
- Backend/tests → Codex CLI (reliable, long-running)

---

## Pipeline — Sequential Multi-Phase

**When**: Tasks with distinct phases requiring different strengths.
**Agents**: 2-5 (sequential)
**Cost**: Medium (sum of phases)
**Duration**: Medium (sequential)

```bash
$MAESTRO run --pattern pipeline "Build user auth system" --cwd /path/to/project
```

**How it works**:
1. Analyze task → select pipeline template
2. Execute phases sequentially
3. Each phase receives previous phase's output as context
4. Stop on failure; report which phase failed

**Default templates**:

| Task type | Phases |
|-----------|--------|
| Build feature | Claude(plan) → Codex(implement) → Claude(review) |
| Fix bug | Claude(diagnose+fix) → Codex(test) |
| Refactor | Codex(refactor) → Claude(review) |
| Design system | Claude(architecture) → Claude(detail) |

**Key principle**: The "architect-builder-inspector" pattern. The most capable model plans, the most reliable model builds, the most thorough model reviews.

---

## Race — Parallel Competition

**When**: Quality-critical tasks. Worth paying 2-3x for comparison.
**Agents**: 2-3 (parallel)
**Cost**: Highest (2-3x)
**Duration**: Shortest (parallel, limited by slowest)

```bash
$MAESTRO run --pattern race "Review this PR for security issues" --cwd /path/to/project
```

**How it works**:
1. Launch same task to all 3 CLIs in background
2. Wait for all to complete (or timeout)
3. Present all results for comparison
4. User (or Claude Code) picks the best

**When to use race**:
- Security audits (different perspectives catch different issues)
- Code review of critical paths
- Architecture decisions (compare approaches)
- When you're unsure which CLI will perform best

**When NOT to use race**:
- Simple tasks (waste of resources)
- Budget-constrained scenarios
- Tasks where all CLIs would give similar results

---

## Swarm — Distributed Subtasks

**When**: Large task that decomposes into independent subtasks.
**Agents**: 3+ (parallel)
**Cost**: Medium-High (depends on subtask count)
**Duration**: Medium (parallel, limited by slowest subtask)

```bash
# Auto-distribute by category
$MAESTRO run --pattern swarm "Build auth, profiles, and notifications" --cwd /path/to/project

# Explicit ratio
$MAESTRO run --pattern swarm --ratio 3:1:1 "Refactor the entire system" --cwd /path/to/project
```

**How it works (auto)**:
1. Analyze task → identify categories
2. Each category maps to best CLI
3. Launch all subtasks in background
4. Collect results when done

**How it works (ratio)**:
1. Parse ratio (e.g., "3:1:1" = 3 Claude, 1 Codex, 1 Gemini)
2. Create N subtasks, distributed by ratio
3. Launch all in background
4. Collect results

**Ratio guidelines**:
- `3:1:1` — Claude-heavy (quality focus)
- `1:3:1` — Codex-heavy (reliability focus)
- `1:1:3` — Gemini-heavy (context/budget focus)
- `1:1:1` — Balanced

---

## Escalation — Start Cheap, Upgrade If Needed

**When**: Budget is primary concern. Willing to accept slower results.
**Agents**: 1 → upgrade (up to 3 attempts)
**Cost**: Variable (best case: cheapest; worst case: sum of chain)
**Duration**: Variable (best case: fast; worst case: 3x)

```bash
$MAESTRO run --budget minimize "Explain the auth module" --cwd /path/to/project
```

**How it works**:
1. Start with cheapest CLI (Gemini)
2. Check output quality (heuristic: non-empty, no errors, sufficient length)
3. If quality passes → done
4. If quality fails → escalate to Codex
5. If Codex fails → escalate to Claude
6. Claude is the last resort (always succeeds or reports failure)

**Escalation chain**: Gemini ($) → Codex ($$) → Claude ($$$)

**Quality heuristic**:
- Non-empty output (> 50 chars)
- No error signals ("error:", "traceback", "failed")
- This is intentionally simple. For sophisticated quality assessment, use Race pattern instead.

---

## Choosing a Pattern — Quick Guide

| Situation | Pattern |
|-----------|---------|
| "Just do X" | Solo |
| "Plan X, build Y, review Z" | Pipeline |
| "I need the best possible result for X" | Race |
| "Do A, B, C, D independently" | Swarm |
| "Do X as cheaply as possible" | Escalation |
| Not sure | Solo (safe default) |
