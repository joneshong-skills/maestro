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
Composes model-mentor (routing), team-tasks (coordination), and CLI execution skills into
unified workflows.

**Two execution modes:**

| Mode | Skills Used | Best For |
|------|------------|----------|
| **Headless** (default) | claude-code-headless, codex-cli-headless, gemini-cli-headless | Single-shot tasks, batch processing, cost-efficient |
| **Interactive** | claude-code-interactive, codex-cli-interactive, gemini-cli-interactive | Multi-turn tasks, context-dependent chains, iterative refinement |

Choose interactive when a task requires **continuous context** across multiple exchanges
(e.g., iterative debugging, design exploration, complex refactoring with feedback loops).

**Memory warning**: Interactive sessions accumulate context in tmux. For long-running tasks,
monitor context usage — if an agent approaches its limit, switch to headless for remaining
subtasks or start a fresh interactive session with a summary of prior work.

## Core Principle

**Intelligence layer** (this SKILL.md, read by Claude Code Opus) decides WHAT to do.
**Dispatch layer** (codex-dispatcher / gemini-dispatcher agents) handles HOW to execute externally.
**Mechanics layer** (`scripts/maestro.py`) handles process orchestration.

The three-tier design protects Opus context from CLI dispatch mechanics:
- Opus: task analysis, routing decisions, result synthesis (~200 tokens)
- Sonnet dispatcher agents: CLI command formatting, execution, summarization (~6500 tokens at Sonnet price)
- Codex/Gemini CLIs: actual task execution (separate subscription quota)

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

### Step 3.5: Dispatch via Agents (Preferred)

When routing to Codex or Gemini, prefer **dispatcher agents** over direct CLI execution.
This offloads CLI mechanics from Opus to cheaper Sonnet sub-agents:

| Routed CLI | Dispatch Method | Agent |
|-----------|----------------|-------|
| **Claude Code** | Direct (self) or `claude -p` headless | — (stays in main context) |
| **Codex CLI** | `Task(subagent_type: "codex-dispatcher")` | codex-dispatcher (Sonnet) |
| **Gemini CLI** | `Task(subagent_type: "gemini-dispatcher")` | gemini-dispatcher (Sonnet) |

**Single-CLI dispatcher prompt**:
```
Execute the following task using Codex/Gemini CLI:

Task: {task description}
Working directory: {cwd}
Sandbox: {read-only | workspace-write | full-auto}
Skills to use: {skill name, if applicable}
Output to: {file path, if applicable}

Return: status, summary, files modified, errors.
```

**Multi-CLI foreman prompt** (for Pipeline / multi-step tasks):
```
Task(subagent_type: "foreman", prompt: """
Execute this multi-phase task:

Phase 1 (Codex): {task A description}
  Working directory: {cwd}
Phase 2 (Gemini): {task B description, may use Phase 1 output}
Phase 3 (Codex): {task C description}

Pass results between phases via files. Return consolidated report.
""")
```

**When to use which**:

| Scenario | Dispatch Method | Why |
|----------|----------------|-----|
| Single CLI task | `codex-dispatcher` or `gemini-dispatcher` | Minimal overhead |
| Multi-step, sequential phases | `foreman` | One sub-agent handles all coordination internally, Opus untouched |
| Simple one-liner | Direct `scripts/maestro.py` | No agent overhead needed |
| Independent parallel tasks | Multiple dispatchers in parallel | Each runs independently |

**Key principle**: foreman is preferred for **Pipeline** and multi-step **Solo** patterns.
It keeps ALL coordination in Sonnet's context (~400 tok Opus vs ~1200+ tok without it).

### Step 4: Choose Execution Mode

**Headless** (default) — single-shot, stateless:
```bash
$MAESTRO run [--pattern PATTERN] [--budget BUDGET] [--cwd PATH] "task description"
```

**Interactive** — multi-turn via tmux, context-preserving:
```bash
$MAESTRO run --interactive [--pattern PATTERN] [--budget BUDGET] [--cwd PATH] "task description"
```

| Decision Factor | → Headless | → Interactive |
|----------------|-----------|---------------|
| Task is self-contained | Yes | — |
| Needs iterative feedback | — | Yes |
| Pipeline phases are independent | Yes | — |
| Pipeline phases build on conversation | — | Yes |
| Budget-sensitive | Yes (cheaper) | — |
| Quality-critical multi-turn | — | Yes |

When `--interactive` is set:
- Solo → launches a tmux interactive session with the routed CLI
- Pipeline → each phase runs in an interactive session, passing context forward naturally
- Race → each CLI gets its own interactive session in parallel
- Swarm → each subtask in its own interactive session

The script handles:
- Creating a team-tasks project
- Dispatching to headless OR interactive CLI wrappers (based on `--interactive` flag)
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
  --interactive                     # Use interactive (tmux) mode instead of headless
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

## Continuous Improvement

This skill evolves with each use. After every invocation:

1. **Reflect** — Identify what worked, what caused friction, and any unexpected issues
2. **Record** — Append a concise lesson to `lessons.md` in this skill's directory
3. **Refine** — When a pattern recurs (2+ times), update SKILL.md directly

### lessons.md Entry Format

```
### YYYY-MM-DD — Brief title
- **Friction**: What went wrong or was suboptimal
- **Fix**: How it was resolved
- **Rule**: Generalizable takeaway for future invocations
```

Accumulated lessons signal when to run `/skill-optimizer` for a deeper structural review.

## Additional Resources

### Reference Files
- **`references/pattern-catalog.md`** — Detailed pattern definitions, when-to-use guides, and examples
- **`references/decision-tree.md`** — Full decision logic with worked examples

### Example Files
- **`examples/solo-dispatch.sh`** — Solo pattern end-to-end
- **`examples/pipeline-review.sh`** — Pipeline with plan → implement → review
- **`examples/race-comparison.sh`** — Race 3 CLIs on security review
