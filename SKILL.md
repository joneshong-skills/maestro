---
name: maestro
description: >-
  This skill should be used when the user asks to "orchestrate agents",
  "dispatch a task", "run multi-agent", "use all three CLIs",
  "race Claude vs Codex vs Gemini", "pipeline with different models",
  "distribute subtasks", "smart dispatch", "conductor mode",
  "分配任務給不同模型", "多 CLI 協作",
  mentions multi-CLI orchestration, agent routing, parallel execution,
  CP-value dispatch, or multi-model workflows.
version: 0.2.1
tools: Read, Bash, Edit
argument-hint: "<task description> [--pattern solo|pipeline|race|swarm|escalation]"
---

# Maestro

Intelligent conductor that routes tasks to the right CLI tool(s) based on CP value.
Composes model-mentor (routing), team-tasks (coordination), and three headless CLI skills
(claude-code-headless, codex-headless, gemini-cli-headless) into unified workflows.

## Core Principle

**Intelligence layer** (this SKILL.md, read by Claude Code) decides WHAT to do.
**Mechanics layer** (`scripts/maestro.py`) handles HOW to execute it.

The intelligence layer is flexible and principle-based. The mechanics layer is deterministic.
When in doubt, lean toward simpler patterns. Solo covers 70% of tasks.

## Quick Start

```bash
MAESTRO="python3 ~/.claude/skills/maestro/scripts/maestro.py"

# Auto-analyze and dispatch (most common)
$MAESTRO run "Fix the login bug in auth.ts" --cwd /path/to/project

# Explicit pattern
$MAESTRO run --pattern pipeline "Build user registration" --cwd /path/to/project

# Dry-run (show plan only)
$MAESTRO plan "Refactor the entire payments module"

# Check status / view report
$MAESTRO status maestro-20260211-143022
$MAESTRO report maestro-20260211-143022
```

## Five Orchestration Patterns

| Pattern | Agents | When to use |
|---------|--------|-------------|
| **Solo** | 1 | Simple, well-defined, single-scope tasks (may delegate to sub-agent via foreman) |
| **Pipeline** | 2-5 seq | Multi-phase work (plan → implement → review) |
| **Race** | 2-3 parallel | Quality-critical; compare outputs from multiple CLIs |
| **Swarm** | 3+ parallel | Large task decomposable into independent subtasks |
| **Escalation** | 1→upgrade | Budget-first; start cheap, upgrade only if quality insufficient |

## Workflow

### Step 1: Analyze the Task

Classify the user's task description:

1. **Identify task categories** from this table:

| Category | Keywords / Signals |
|----------|--------------------|
| code_generation | build, create, implement, write, add feature |
| code_review | review, check, audit, inspect, PR |
| debugging | fix, bug, error, broken, not working |
| refactoring | refactor, clean up, restructure, optimize |
| architecture | design, plan, architect, system design |
| testing | test, spec, coverage, TDD |
| long_doc_analysis | analyze, summarize, read, 100+ pages |
| frontend | UI, component, React, CSS, layout |
| backend | API, server, database, endpoint |
| security | vulnerability, XSS, SQL injection, auth |
| research | research, compare, investigate, explore |

2. **Assess complexity**:
   - `simple`: single file, clear scope → likely **Solo**
   - `moderate`: multi-file, needs planning → likely **Pipeline** or **Solo**
   - `complex`: multi-component, architectural → likely **Pipeline** or **Swarm**

3. **Check decomposability**:
   - `atomic`: cannot split → **Solo** or **Race**
   - `sequential`: has phases ("first... then... finally...") → **Pipeline**
   - `parallel`: independent subtasks ("X and Y and Z") → **Swarm**

### Step 2: Select Pattern

Apply the decision tree (full version in `references/decision-tree.md`):

```
User specified --pattern? → Use that pattern.

Single well-defined task?
  ├── Quality standard → Solo (cheapest capable CLI)
  └── Quality critical → Race (2-3 CLIs)

Has sequential phases?
  └── Pipeline (assign best CLI per phase)

Decomposable into 3+ independent subtasks?
  └── Swarm (distribute by CLI strength)

Budget is primary concern?
  └── Escalation (Gemini → Codex → Claude)

Default → Solo (primary CLI from routing table)
```

### Step 3: Route to CLI(s)

Use this routing table (derived from model-mentor's cli-comparison):

| Task category | Primary CLI | Budget CLI | Power CLI | Sub-Agent |
|---------------|------------|-----------|-----------|-----------|
| code_generation | Claude Code | Gemini CLI | Claude Code | — |
| code_review | Claude Code | Codex CLI | Claude Code | `code-reviewer` |
| debugging | Claude Code | Gemini CLI | Claude Code | — |
| refactoring | Codex CLI | Codex CLI | Claude Code | — |
| architecture | Claude Code | Claude Code | Claude Code | — |
| testing | Codex CLI | Codex CLI | Claude Code | — |
| long_doc_analysis | Gemini CLI | Gemini CLI | Gemini CLI | — |
| frontend | Claude Code | Gemini CLI | Claude Code | — |
| backend | Codex CLI | Codex CLI | Claude Code | — |
| security | Claude Code | Claude Code | Claude Code | `security-scanner` |
| research | Gemini CLI | Gemini CLI | Gemini CLI | — |

When a Sub-Agent is available for a category, Solo mode will **prefer the agent** over
spinning up a full CLI process. This is faster and cheaper for read-only tasks.

**Budget selection logic**:
- `--budget minimize` → use Budget CLI column
- `--budget balanced` (default) → use Primary CLI column
- `--budget maximize_quality` → use Power CLI column

### Step 4: Execute

Run the dispatcher:

```bash
$MAESTRO run [--pattern PATTERN] [--budget BUDGET] [--cwd PATH] "task description"
```

The script handles:
- Creating a team-tasks project
- Dispatching to appropriate headless CLI wrapper(s)
- Background execution for parallel patterns
- Monitoring progress and collecting results
- Generating a structured report

### Step 5: Review Results

```bash
$MAESTRO report <project-name>
```

For Race pattern, compare outputs and recommend the best.
For Pipeline, show results per phase with pass/fail status.
For Swarm, aggregate all subtask results.

## Default Pipeline Templates

When Pipeline mode is selected, use these defaults unless the user specifies otherwise:

| Task type | Default phases |
|-----------|---------------|
| Build feature | Claude(plan) → Codex(implement) → Claude(review) |
| Fix bug | Claude(diagnose+fix) → Codex(test) |
| Review PR/code | Race: Claude + Codex + Gemini |
| Refactor module | Codex(refactor) → Claude(review) |
| Analyze codebase | Solo: Gemini (1M context) |
| Write tests | Solo: Codex |
| Security audit | Race: Claude + Codex |
| Design system | Claude(architecture) → Claude(detail design) |

## CLI Reference

```bash
MAESTRO="python3 ~/.claude/skills/maestro/scripts/maestro.py"

$MAESTRO run TASK [OPTIONS]         # Analyze + execute
$MAESTRO plan TASK [OPTIONS]        # Analyze only (dry-run)
$MAESTRO status PROJECT             # Show progress
$MAESTRO list                       # List all maestro projects
$MAESTRO report PROJECT             # Show final report

Options:
  --pattern PATTERN                 # Force: solo|pipeline|race|swarm|escalation
  --ratio RATIO                     # Swarm ratio: "3:1:1" (claude:codex:gemini)
  --cwd PATH                        # Working directory for agents
  --budget BUDGET                   # minimize|balanced|maximize_quality
  --timeout SECONDS                 # Per-agent timeout (default: 300)
  --notify                          # macOS notification on completion
  --json                            # Machine-readable JSON output
```

## Foreman Integration (Sub-Agent Dispatch)

Maestro integrates with the **foreman** skill to prefer lightweight sub-agents over full CLI
processes when a matching agent exists.

```
Solo dispatch flow:
  Task → check_agent_match() → agent found? → dispatch_via_agent() (fast, cheap)
                              → no agent?   → dispatch_via_cli() (full CLI)
```

The routing uses a two-step check:
1. **Static routing** (`AGENT_ROUTING` table in `maestro.py`) — maps categories to preferred agents
2. **Dynamic matching** (foreman `match --json`) — scores all agents against the task description

Both must agree for agent dispatch to trigger. When no agent matches, standard CLI routing applies.

**When agents are preferred over CLIs:**
- Read-only analysis tasks (no sandbox needed)
- A matching agent exists with score >= 0.15
- The task doesn't require cross-CLI capabilities

See `/foreman` for agent discovery and management.

## Important Notes

- **Solo is the default**. Most tasks don't need multi-agent orchestration.
- Solo may delegate to a sub-agent via foreman for read-only tasks (faster + cheaper than CLI).
- Pipeline phases pass results forward as context. Each phase builds on the previous.
- Race mode costs 2-3x more. Only use when quality justifies the cost.
- Swarm requires the task to be genuinely decomposable. Do not force-split atomic tasks.
- Escalation saves money but adds latency (multiple attempts).
- All projects are stored as JSON in `~/.claude/data/maestro/`.
- When the dispatcher is uncertain, it defaults to Solo with Claude Code (safest choice).

## Additional Resources

### Reference Files
- **`references/pattern-catalog.md`** — Detailed pattern definitions, when-to-use guides, and examples
- **`references/decision-tree.md`** — Full decision logic with worked examples

### Example Files
- **`examples/solo-dispatch.sh`** — Solo pattern end-to-end
- **`examples/pipeline-review.sh`** — Pipeline with plan → implement → review
- **`examples/race-comparison.sh`** — Race 3 CLIs on security review
