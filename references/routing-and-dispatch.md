# Routing Table & Dispatch Details

## CLI Routing Table (from model-mentor)

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

**Budget selection logic**:
- `--budget minimize` → Budget CLI column
- `--budget balanced` (default) → Primary CLI column
- `--budget maximize_quality` → Power CLI column

When a Sub-Agent is available, Solo mode **prefers the agent** over CLI (faster + cheaper for read-only).

## Dispatcher Agent Mapping

| Routed CLI | Dispatch Method | Agent |
|-----------|----------------|-------|
| **Claude Code** | Direct (self) or `claude -p` headless | — (stays in main context) |
| **Codex CLI** | `Task(subagent_type: "codex-dispatcher")` | codex-dispatcher (Sonnet) |
| **Gemini CLI** | `Task(subagent_type: "gemini-dispatcher")` | gemini-dispatcher (Sonnet) |

### Sub-Agent Dispatch (when routing table specifies a sub-agent)

When the routing table's Sub-Agent column has a value (e.g., `code-reviewer`, `security-scanner`):

```
Task(subagent_type: "reviewer", prompt: "Review {code path}: {task description}")
Task(subagent_type: "general-purpose", prompt: "Security scan: {task description}")
```

Sub-agents are preferred over CLIs for read-only analysis tasks (faster + cheaper). If the sub-agent returns insufficient results, fall back to the Primary CLI.

### Single-CLI Dispatcher Prompt
```
Execute the following task using Codex/Gemini CLI:

Task: {task description}
Working directory: {cwd}
Sandbox: {read-only | workspace-write | full-auto}
Skills to use: {skill name, if applicable}
Output to: {file path, if applicable}

Return: status, summary, files modified, errors.
```

### Multi-CLI Foreman Prompt (Pipeline / multi-step)
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

### Dispatch Method Selection

| Scenario | Dispatch Method | Why |
|----------|----------------|-----|
| Single CLI task | `codex-dispatcher` or `gemini-dispatcher` | Minimal overhead |
| Multi-step, sequential phases | `foreman` | One sub-agent handles all coordination, Opus untouched |
| Simple one-liner | Direct `maestro` CLI | No agent overhead needed |
| Independent parallel tasks | Multiple dispatchers in parallel | Each runs independently |

**Key**: foreman preferred for **Pipeline** and multi-step **Solo** — keeps ALL coordination in Sonnet (~400 tok Opus vs ~1200+).

## Execution Tier Details

**Tier 1: Headless** (default) — single-shot, stateless subprocess:
```bash
~/.local/bin/maestro run [--tier headless] [--pattern PATTERN] [--budget BUDGET] [--cwd PATH] "task description"
```
Dispatch via `dispatch_agent()` — runs CLI wrappers (`claude -p`, `codex exec`, `gemini -p`) as subprocesses. Supports all three CLIs.

**Tier 2: Relay** — local tmux pane pool, full MCP/skill/tool access:
```bash
~/.local/bin/maestro run --tier relay [--pattern PATTERN] [--budget BUDGET] [--cwd PATH] "task description"
```
Dispatch via `dispatch_relay()` → `TmuxRelayClient`. Agents run in persistent tmux panes with full skill and MCP tool access.

**Tier 3: Fleet** — remote node execution (GPU, cross-platform):
```bash
~/.local/bin/maestro run --tier fleet [--pattern PATTERN] [--budget BUDGET] [--cwd PATH] "task description"
```
Dispatch via `dispatch_fleet()` → `FleetClient`. Tasks run on remote machines (e.g., Windows RTX 3090 via Tailscale). Polls for completion with exponential backoff (5s → 10s → 20s → cap 30s).
**Note**: Fleet currently dispatches Claude Code only (`cli="claude"` hardcoded). Codex/Gemini selection applies to headless tier only.
See `~/.claude/skills/fleet/SKILL.md` for node capabilities, safety rules, and fleet CLI commands.

| Decision Factor | → Headless | → Relay | → Fleet |
|----------------|-----------|---------|---------|
| Task is self-contained | Yes | — | — |
| Needs full skill/MCP/tool access | — | Yes | — |
| Needs browser/Playwright | — | Yes | — |
| GPU/training workload | — | — | Yes |
| Multi-file refactoring | — | — | Yes |
| Budget-sensitive | Yes | — | — |
| Explicit `--tier` override | Yes | Yes | Yes |

**Auto-detection signals** (from `routing_table.yaml` tier_keywords):
- GPU keywords (CUDA, RTX, finetune, inference, batch) → fleet
- MCP/skill keywords (MCP, skill, memvault, capture) → relay
- Browser keywords (Playwright, scrape, screenshot) → relay
- Multi-file keywords (refactor, migration, across modules) → fleet

**Category defaults**: debugging → relay, refactoring → fleet, most others → headless.
**Fallback chain**: fleet → [relay, headless], relay → [headless]. Engine auto-falls back if a tier backend is unreachable.

When `--tier relay` or `--tier fleet` is used with multi-agent patterns:
- Solo → single dispatch to the selected tier backend
- Pipeline → each phase dispatched to the tier backend sequentially
- Race → each CLI dispatched to the tier backend in parallel
- Swarm → each subtask dispatched to the tier backend in parallel

## Foreman Integration

```
Solo dispatch flow:
  Task → check_agent_match() → agent found? → dispatch_via_agent() (fast, cheap)
                              → no agent?   → dispatch_via_cli() (full CLI)
```

Two-step routing check:
1. **Static routing** (`AGENT_ROUTING` in `maestro.py`) — category → preferred agents
2. **Dynamic matching** (foreman `match --json`) — scores all agents against task

Both must agree. When no agent matches, standard CLI routing applies.

**Agent preferred when**: read-only tasks, score >= 0.15, no cross-CLI needs.

## Dispatch Reaction Protocol

```
Agent reports failure
  │
  ├─ Deterministic failure (exit code, CI error, type error)
  │   ├─ Attempt ≤ 2 → Re-dispatch with error context
  │   └─ Attempt > 2 → Escalate to user
  │
  ├─ Agent timeout (no output within --timeout)
  │   ├─ Attempt 1 → Kill + re-dispatch simplified
  │   └─ Attempt 2 → Escalate to user
  │
  └─ Ambiguous failure (confused, scope drift)
      └─ Escalate immediately — do NOT retry
```

**Re-dispatch prompt**: `Previous attempt failed with: {error_summary}. Fix and complete: {original_task}. CWD: {cwd}`

**Rules**:
- Max 2 auto-retries per agent per task
- Append failure context only, not full previous output
- Log to `~/.claude/data/maestro/{project}/reactions.jsonl`
- Race/Swarm: if one agent fails but others succeed, use successful result — don't retry
