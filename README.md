<h1 align="center">Maestro</h1>

<p align="center">
  <a href="README.md"><kbd><strong>English</strong></kbd></a>
  <a href="README.zh.md"><kbd>繁體中文</kbd></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/joneshong-skills/maestro/main/logo.png" alt="Maestro Logo" width="200"/>
</p>

<p align="center">
  <a href="https://github.com/joneshong-skills/maestro">
    <img alt="GitHub" src="https://img.shields.io/github/stars/joneshong-skills/maestro?style=social">
  </a>
  <a href="https://deepwiki.com/joneshong-skills/maestro">
    <img alt="DeepWiki" src="https://img.shields.io/badge/DeepWiki-docs-blue">
  </a>
  <a href="https://github.com/joneshong-skills/maestro/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/badge/license-MIT-green.svg">
  </a>
</p>

<p align="center">
  <strong>Multi-CLI orchestration conductor for Claude Code</strong>
</p>

<p align="center">
  Intelligently routes tasks to the right CLI tool(s) -- Claude Code, Codex CLI, and Gemini CLI --
  selecting the best agent(s) and execution pattern based on CP value.
</p>

## Features

- **Five Orchestration Patterns** -- Solo, Pipeline, Race, Swarm, and Escalation to match any task shape
- **Smart Routing** -- Automatic CLI selection based on task category, complexity, and budget constraints
- **Foreman Integration** -- Prefers lightweight sub-agents over full CLI processes for read-only tasks
- **Budget Modes** -- Minimize cost, balance quality/cost, or maximize quality with explicit budget controls
- **Pipeline Templates** -- Pre-configured phase sequences for common workflows (build, review, refactor, etc.)
- **Structured Reports** -- JSON-based project tracking with status monitoring and final reports

## Usage

Trigger phrases: "orchestrate agents", "dispatch a task", "run multi-agent", "use all three CLIs", "race Claude vs Codex vs Gemini"

```bash
MAESTRO="python3 ~/.claude/skills/maestro/scripts/maestro.py"

# Auto-analyze and dispatch (most common)
$MAESTRO run "Fix the login bug in auth.ts" --cwd /path/to/project

# Explicit pattern selection
$MAESTRO run --pattern pipeline "Build user registration" --cwd /path/to/project

# Dry-run to preview the plan
$MAESTRO plan "Refactor the entire payments module"

# Check status and view report
$MAESTRO status maestro-20260211-143022
$MAESTRO report maestro-20260211-143022
```

## Orchestration Patterns

| Pattern | Agents | When to Use |
|---------|--------|-------------|
| **Solo** | 1 | Simple, well-defined, single-scope tasks (may delegate to sub-agent via foreman) |
| **Pipeline** | 2-5 sequential | Multi-phase work (plan, implement, review) |
| **Race** | 2-3 parallel | Quality-critical; compare outputs from multiple CLIs |
| **Swarm** | 3+ parallel | Large task decomposable into independent subtasks |
| **Escalation** | 1 with upgrade | Budget-first; start cheap, upgrade if quality insufficient |

**Key design principle:** Solo is the default and covers ~70% of tasks.

## Foreman Integration

Maestro integrates with the **foreman** skill to prefer lightweight sub-agents over full CLI processes:

```
Solo dispatch flow:
  Task -> check_agent_match() -> agent found? -> dispatch_via_agent() (fast, cheap)
                               -> no agent?   -> dispatch_via_cli() (full CLI)
```

When agents are preferred over CLIs:
- Read-only analysis tasks (no sandbox needed)
- A matching agent exists with score >= 0.15
- The task does not require cross-CLI capabilities

## Workflow

1. **Analyze** -- Classify the task by category, complexity, and decomposability
2. **Select Pattern** -- Apply decision tree to choose Solo/Pipeline/Race/Swarm/Escalation
3. **Route** -- Map to the best CLI(s) using the routing table and budget mode
4. **Execute** -- Dispatch via `maestro.py` with background execution for parallel patterns
5. **Review** -- Generate structured reports with per-phase results

## Integration

| Skill | Relationship |
|-------|-------------|
| **foreman** | Lightweight sub-agent dispatch layer for read-only tasks within pipelines |
| **model-mentor** | Provides CLI routing intelligence and model comparison data |
| **team-tasks** | Coordination layer for multi-agent project management |
| **claude-code-headless** | Headless execution wrapper for Claude Code |
| **codex-cli-headless** | Headless execution wrapper for Codex CLI |
| **gemini-cli-headless** | Headless execution wrapper for Gemini CLI |

## Installation

Clone this repository into your Claude skills directory:

```bash
git clone https://github.com/joneshong-skills/maestro.git ~/.claude/skills/maestro
```

Prerequisites:
- Python 3.10+
- At least one headless CLI skill installed (claude-code-headless, codex-headless, or gemini-cli-headless)
- The `model-mentor` and `team-tasks` skills (used for routing and coordination)

## Project Structure

```
maestro/
├── SKILL.md                        # Skill definition and orchestration logic
├── README.md                       # English documentation
├── README.zh.md                    # Traditional Chinese documentation
├── scripts/
│   └── maestro.py                  # Core dispatcher and execution engine
├── references/
│   ├── decision-tree.md            # Full pattern selection decision tree
│   └── pattern-catalog.md          # Detailed pattern definitions and guides
└── examples/
    ├── solo-dispatch.sh            # Solo pattern end-to-end example
    ├── pipeline-review.sh          # Pipeline with plan/implement/review phases
    └── race-comparison.sh          # Race 3 CLIs on security review
```

## License

MIT
