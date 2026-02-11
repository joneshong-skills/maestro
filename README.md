[English](README.md) | [繁體中文](README.zh.md)

# Maestro

A Claude Code skill that intelligently orchestrates tasks across multiple CLI tools — **Claude Code**, **Codex CLI**, and **Gemini CLI** — selecting the best agent(s) and execution pattern based on CP value.

## What It Does

Maestro analyzes your task and automatically selects the optimal orchestration pattern:

| Pattern | Agents | When to Use |
|---|---|---|
| Solo | 1 | Simple, well-defined, single-scope tasks |
| Pipeline | 2-5 sequential | Multi-phase work (plan, implement, review) |
| Race | 2-3 parallel | Quality-critical; compare outputs from multiple CLIs |
| Swarm | 3+ parallel | Large task decomposable into independent subtasks |
| Escalation | 1 with upgrade | Budget-first; start cheap, upgrade if quality insufficient |

**Key design principle:** Solo is the default and covers ~70% of tasks. More complex patterns are only used when the task genuinely benefits from multi-agent coordination.

## Installation

1. Clone this repository into your Claude skills directory:

   ```bash
   git clone https://github.com/joneshong-skills/maestro.git ~/.claude/skills/maestro
   ```

2. Prerequisites:
   - Python 3.10+
   - At least one headless CLI skill installed (claude-code-headless, codex-headless, or gemini-cli-headless)
   - The `model-mentor` and `team-tasks` skills (used for routing and coordination)

3. The skill activates when you mention orchestration, multi-agent tasks, dispatching, racing CLIs, or use trigger phrases like "orchestrate", "dispatch", "use all three CLIs", etc.

## Usage

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

## Project Structure

```
maestro/
├── SKILL.md                        # Skill definition and orchestration logic
├── README.md                       # This file
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
