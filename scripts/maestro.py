#!/usr/bin/env python3
"""maestro — Intelligent multi-CLI orchestration dispatcher.

Analyzes tasks, selects orchestration patterns, and dispatches work
to Claude Code, Codex CLI, and Gemini CLI via their headless wrappers.

Depends on:
  - team-tasks/scripts/task_manager.py  (project coordination)
  - claude-code-headless/scripts/claude_headless.py
  - codex-headless/scripts/codex_headless.py
  - gemini-cli-headless/scripts/gemini_headless.py

Data dir: ~/.claude/data/maestro/ (override with MAESTRO_DIR)
No external dependencies — Python 3.12+ stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────

SKILLS_DIR = Path.home() / ".claude" / "skills"
DATA_DIR = Path(os.environ.get("MAESTRO_DIR", Path.home() / ".claude" / "data" / "maestro"))
LOG_DIR = Path.home() / ".claude" / "logs" / "headless"

HEADLESS = {
    "claude": str(SKILLS_DIR / "claude-code-headless" / "scripts" / "claude_headless.py"),
    "codex": str(SKILLS_DIR / "codex-headless" / "scripts" / "codex_headless.py"),
    "gemini": str(SKILLS_DIR / "gemini-cli-headless" / "scripts" / "gemini_headless.py"),
}

# ── CLI Routing Table ──────────────────────────────────────────────

CLI_ROUTING: dict[str, dict[str, str]] = {
    "code_generation":  {"primary": "claude", "budget": "gemini", "power": "claude"},
    "code_review":      {"primary": "claude", "budget": "codex",  "power": "claude"},
    "debugging":        {"primary": "claude", "budget": "gemini", "power": "claude"},
    "refactoring":      {"primary": "codex",  "budget": "codex",  "power": "claude"},
    "architecture":     {"primary": "claude", "budget": "claude", "power": "claude"},
    "testing":          {"primary": "codex",  "budget": "codex",  "power": "claude"},
    "long_doc_analysis":{"primary": "gemini", "budget": "gemini", "power": "gemini"},
    "frontend":         {"primary": "claude", "budget": "gemini", "power": "claude"},
    "backend":          {"primary": "codex",  "budget": "codex",  "power": "claude"},
    "security":         {"primary": "claude", "budget": "claude", "power": "claude"},
    "research":         {"primary": "gemini", "budget": "gemini", "power": "gemini"},
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "code_generation":  ["build", "create", "implement", "write", "add feature", "new feature", "generate",
                         "建立", "建置", "實作", "寫", "開發", "產生", "新增"],
    "code_review":      ["review", "check", "audit", "inspect", "PR", "pull request", "code review",
                         "審查", "檢查", "看一下", "review"],
    "debugging":        ["fix", "bug", "error", "broken", "not working", "crash", "issue", "debug",
                         "修", "修復", "修正", "錯誤", "壞了", "除錯"],
    "refactoring":      ["refactor", "clean up", "restructure", "optimize", "reorganize", "simplify",
                         "重構", "整理", "優化", "簡化", "重新架構"],
    "architecture":     ["design", "plan", "architect", "system design", "architecture", "blueprint",
                         "設計", "規劃", "架構"],
    "testing":          ["test", "spec", "coverage", "TDD", "unit test", "integration test", "e2e",
                         "測試", "測試覆蓋", "單元測試", "整合測試"],
    "long_doc_analysis":["analyze", "summarize", "document", "pdf", "report", "100 page",
                         "分析", "摘要", "總結", "文件", "報告"],
    "frontend":         ["UI", "component", "React", "CSS", "layout", "frontend", "page", "form",
                         "前端", "介面", "元件", "頁面", "表單"],
    "backend":          ["API", "server", "database", "endpoint", "backend", "REST", "GraphQL",
                         "後端", "伺服器", "資料庫"],
    "security":         ["vulnerability", "XSS", "SQL injection", "auth", "security", "penetration",
                         "安全", "漏洞", "認證", "授權"],
    "research":         ["research", "compare", "investigate", "explore", "survey", "benchmark",
                         "研究", "比較", "調查", "探索"],
}

# ── Explicit CLI Name Aliases ─────────────────────────────────────
# Maps user-facing names to canonical CLI keys.
CLI_NAME_ALIASES: dict[str, str] = {
    "claude": "claude", "claude code": "claude", "claude-code": "claude",
    "codex": "codex", "codex cli": "codex", "codex-cli": "codex",
    "openai codex": "codex", "openai": "codex",
    "gemini": "gemini", "gemini cli": "gemini", "gemini-cli": "gemini",
    "google gemini": "gemini",
}


def detect_explicit_clis(description: str) -> list[str]:
    """Detect CLI names explicitly mentioned by the user.

    Returns a deduplicated list of canonical CLI keys in the order they appear.
    Longer aliases are checked first to avoid partial matches (e.g., "claude code"
    before "claude").
    """
    desc_lower = description.lower()
    found: dict[str, int] = {}   # canonical name → first position
    # Sort aliases longest-first so "claude code" matches before "claude"
    for alias in sorted(CLI_NAME_ALIASES, key=len, reverse=True):
        pos = desc_lower.find(alias)
        if pos >= 0:
            canon = CLI_NAME_ALIASES[alias]
            if canon not in found:
                found[canon] = pos
    # Return in order of appearance
    return [cli for cli, _ in sorted(found.items(), key=lambda x: x[1])]

# ── Default Pipeline Templates ─────────────────────────────────────

PIPELINE_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "code_generation": [
        {"id": "plan", "cli": "claude", "role": "Plan architecture and design"},
        {"id": "implement", "cli": "codex", "role": "Implement the design"},
        {"id": "review", "cli": "claude", "role": "Review implementation quality"},
    ],
    "debugging": [
        {"id": "diagnose", "cli": "claude", "role": "Diagnose the root cause"},
        {"id": "fix", "cli": "claude", "role": "Implement the fix"},
        {"id": "test", "cli": "codex", "role": "Write and run tests"},
    ],
    "code_review": [
        {"id": "claude-review", "cli": "claude", "role": "Review for quality and logic"},
        {"id": "codex-review", "cli": "codex", "role": "Review for reliability"},
    ],
    "refactoring": [
        {"id": "refactor", "cli": "codex", "role": "Execute the refactoring"},
        {"id": "review", "cli": "claude", "role": "Review the changes"},
    ],
    "security": [
        {"id": "claude-audit", "cli": "claude", "role": "Security audit perspective 1"},
        {"id": "codex-audit", "cli": "codex", "role": "Security audit perspective 2"},
    ],
    "architecture": [
        {"id": "design", "cli": "claude", "role": "High-level architecture design"},
        {"id": "detail", "cli": "claude", "role": "Detailed component design"},
    ],
}

# ── Data Classes ───────────────────────────────────────────────────

@dataclass
class TaskAnalysis:
    description: str
    complexity: str = "simple"          # simple | moderate | complex
    decomposability: str = "atomic"     # atomic | sequential | parallel
    categories: list[str] = field(default_factory=list)
    recommended_pattern: str = "solo"
    phases: list[dict] = field(default_factory=list)

@dataclass
class AgentResult:
    task_id: str
    cli: str
    status: str         # done | failed | timeout
    duration_s: float
    output: str = ""

@dataclass
class MaestroProject:
    name: str
    pattern: str
    task: str
    budget: str
    cwd: str
    phases: list[dict] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    created_at: str = ""
    completed_at: str = ""
    total_duration_s: float = 0

# ── Analysis ───────────────────────────────────────────────────────

def _is_cjk(text: str) -> bool:
    """Check if text contains CJK characters (Chinese/Japanese/Korean)."""
    return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))


def _word_match(pattern: str, text: str) -> bool:
    """Match a keyword: word-boundary for Latin, substring for CJK."""
    if _is_cjk(pattern):
        return pattern in text
    return bool(re.search(r'\b' + re.escape(pattern) + r'\b', text, re.IGNORECASE))


def _effective_word_count(description: str) -> int:
    """Word count with CJK fallback — Chinese chars ÷ 2 as rough word equivalent."""
    words = len(description.split())
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', description))
    if cjk_chars > 5:
        words += cjk_chars // 2
    return words


def analyze_task(description: str, budget: str = "balanced") -> TaskAnalysis:
    """Classify a task description into categories, complexity, and pattern."""
    desc_lower = description.lower()
    analysis = TaskAnalysis(description=description)

    # Identify categories (word-boundary matching)
    scores: dict[str, int] = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if _word_match(kw, desc_lower))
        if score > 0:
            scores[cat] = score
    analysis.categories = sorted(scores, key=scores.get, reverse=True) if scores else ["code_generation"]

    # Assess complexity (with CJK fallback)
    word_count = _effective_word_count(description)
    # Count total occurrences of coordination signals (not just distinct keywords)
    multi_signal_words = ["and", "then", "also", "plus", "with", "including",
                          "並且", "然後", "還有", "以及", "同時"]
    multi_signals = 0
    for w in multi_signal_words:
        if _is_cjk(w):
            multi_signals += desc_lower.count(w)
        else:
            multi_signals += len(re.findall(r'\b' + re.escape(w) + r'\b', desc_lower, re.IGNORECASE))
    if word_count > 50 or multi_signals >= 3:
        analysis.complexity = "complex"
    elif word_count > 20 or multi_signals >= 1:
        analysis.complexity = "moderate"
    else:
        analysis.complexity = "simple"

    # Check decomposability (word-boundary for English, substring for CJK particles)
    seq_signals = any(_word_match(p, desc_lower) for p in [
        "first", "then", "after that", "finally", "step 1", "phase",
    ]) or any(p in desc_lower for p in ["先", "然後", "接著", "最後"])
    par_signals = desc_lower.count(" and ") >= 2 or desc_lower.count("、") >= 2

    if seq_signals:
        analysis.decomposability = "sequential"
    elif par_signals and analysis.complexity != "simple":
        analysis.decomposability = "parallel"
    else:
        analysis.decomposability = "atomic"

    # Select pattern
    analysis.recommended_pattern = select_pattern(analysis, budget)

    # Build phases for pipeline
    if analysis.recommended_pattern == "pipeline":
        primary_cat = analysis.categories[0]
        if primary_cat in PIPELINE_TEMPLATES:
            analysis.phases = PIPELINE_TEMPLATES[primary_cat]
        else:
            analysis.phases = PIPELINE_TEMPLATES["code_generation"]

    return analysis


def select_pattern(analysis: TaskAnalysis, budget: str) -> str:
    """Apply decision tree to select orchestration pattern."""
    if budget == "minimize":
        return "escalation"

    if analysis.decomposability == "sequential":
        return "pipeline"

    if analysis.decomposability == "parallel" and analysis.complexity == "complex":
        return "swarm"

    if analysis.complexity == "simple":
        return "solo"

    if analysis.complexity == "moderate":
        return "solo"

    # complex + atomic = race for quality
    return "race"


def route_to_cli(category: str, budget: str = "balanced") -> str:
    """Map task category + budget to a CLI tool name."""
    tier_map = {"minimize": "budget", "balanced": "primary", "maximize_quality": "power"}
    tier = tier_map.get(budget, "primary")
    routing = CLI_ROUTING.get(category, CLI_ROUTING["code_generation"])
    return routing.get(tier, "claude")

# ── Project Management ─────────────────────────────────────────────

def generate_project_name() -> str:
    return f"maestro-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def save_project(project: MaestroProject) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{project.name}.json"
    path.write_text(json.dumps(asdict(project), indent=2, ensure_ascii=False))
    return path


def load_project(name: str) -> MaestroProject:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        # Try prefix match
        matches = sorted(DATA_DIR.glob(f"{name}*.json"))
        if matches:
            path = matches[-1]
        else:
            print(f"Error: project '{name}' not found", file=sys.stderr)
            sys.exit(1)
    data = json.loads(path.read_text())
    return MaestroProject(**data)


def list_projects() -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    projects = []
    for f in sorted(DATA_DIR.glob("maestro-*.json")):
        try:
            data = json.loads(f.read_text())
            projects.append({
                "name": data.get("name", f.stem),
                "pattern": data.get("pattern", "?"),
                "task": data.get("task", "")[:60],
                "completed": bool(data.get("completed_at")),
            })
        except Exception:
            continue
    return projects

# ── CLI Dispatch ───────────────────────────────────────────────────

def build_cli_cmd(cli: str, prompt: str, cwd: str | None, background: bool) -> list[str]:
    """Build the command list for a headless CLI wrapper."""
    script = HEADLESS.get(cli)
    if not script:
        raise ValueError(f"Unknown CLI: {cli}")

    cmd = [sys.executable, script]

    if cli == "claude":
        cmd += ["-p", prompt, "--output-format", "json", "--allowedTools", "Read,Edit,Bash"]
        if cwd:
            cmd += ["--cwd", cwd]
    elif cli == "codex":
        cmd += [prompt, "--full-auto"]
        if cwd:
            cmd += ["--cd", cwd]
    elif cli == "gemini":
        cmd += ["-p", prompt, "--approval-mode", "yolo"]
        if cwd:
            cmd += ["--cwd", cwd]

    if background:
        cmd.append("--background")

    return cmd


def dispatch_agent(cli: str, prompt: str, cwd: str | None = None,
                   background: bool = False, timeout: int = 300,
                   skip_preflight: bool = False) -> AgentResult:
    """Launch a CLI agent and collect the result."""
    task_id = f"{cli}-{int(time.time())}"

    # Pre-flight resource check
    if not skip_preflight:
        _shared = str(SKILLS_DIR / "_shared")
        if Path(_shared).is_dir():
            sys.path.insert(0, _shared)
            try:
                from preflight import run_preflight, Verdict, format_result
                pf = run_preflight()
                if pf.verdict == Verdict.BLOCK:
                    return AgentResult(
                        task_id=task_id, cli=cli, status="blocked",
                        duration_s=0,
                        output=f"Pre-flight BLOCKED:\n{format_result(pf)}",
                    )
                elif pf.verdict == Verdict.WARN:
                    print(format_result(pf), file=sys.stderr)
            except ImportError:
                pass
            finally:
                if _shared in sys.path:
                    sys.path.remove(_shared)

    cmd = build_cli_cmd(cli, prompt, cwd, background)
    start = time.time()

    try:
        if background:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            # Parse PID and log path from stdout
            pid = None
            log_path = None
            for line in proc.stdout.splitlines():
                if "PID:" in line:
                    pid = line.split("PID:")[-1].strip()
                if "Log:" in line:
                    log_path = line.split("Log:")[-1].strip()
            return AgentResult(
                task_id=task_id, cli=cli, status="running",
                duration_s=0,
                output=json.dumps({"pid": pid, "log": log_path}),
            )
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            elapsed = time.time() - start
            output = proc.stdout.strip()

            # Try to extract result from JSON output (claude)
            if cli == "claude" and output:
                try:
                    # Strip ANSI escape codes (color, cursor, etc.) and control chars
                    clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', output)
                    clean = clean.lstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f')
                    json_start = clean.find('{')
                    if json_start >= 0:
                        clean = clean[json_start:]
                    data = json.loads(clean)
                    output = data.get("result", output)
                except (json.JSONDecodeError, TypeError):
                    pass

            status = "done" if proc.returncode == 0 else "failed"
            return AgentResult(
                task_id=task_id, cli=cli, status=status,
                duration_s=round(elapsed, 1), output=output[:5000],
            )
    except subprocess.TimeoutExpired:
        return AgentResult(
            task_id=task_id, cli=cli, status="timeout",
            duration_s=timeout, output="Agent timed out",
        )
    except Exception as e:
        return AgentResult(
            task_id=task_id, cli=cli, status="failed",
            duration_s=round(time.time() - start, 1),
            output=f"Dispatch error: {e}",
        )


def wait_for_background(pid: str, log_path: str, timeout: int = 300) -> str:
    """Wait for a background process to finish. Returns log content."""
    start = time.time()
    while time.time() - start < timeout:
        # Check if PID is still alive
        try:
            os.kill(int(pid), 0)
        except (OSError, ValueError):
            # Process exited
            break
        time.sleep(3)

    if log_path and Path(log_path).exists():
        return Path(log_path).read_text()[-5000:]
    return "(no log output captured)"

# ── Pattern Executors ──────────────────────────────────────────────

def execute_solo(project: MaestroProject, timeout: int,
                 skip_preflight: bool = False) -> MaestroProject:
    """Single agent, single task."""
    analysis = analyze_task(project.task, project.budget)
    explicit_clis = detect_explicit_clis(project.task)
    cli = explicit_clis[0] if explicit_clis else route_to_cli(analysis.categories[0], project.budget)
    project.phases = [{"id": "main", "cli": cli, "role": "Execute the task"}]

    print(f"[maestro] Pattern: Solo ({cli})")
    print(f"[1/1] {cli.title()}... dispatching")

    result = dispatch_agent(cli, project.task, project.cwd, timeout=timeout,
                            skip_preflight=skip_preflight)
    project.results = [asdict(result)]

    print(f"[1/1] {cli.title()}... {result.status} ({result.duration_s}s)")
    return project


def execute_pipeline(project: MaestroProject, timeout: int,
                     skip_preflight: bool = False) -> MaestroProject:
    """Sequential phases, each building on the previous."""
    analysis = analyze_task(project.task, project.budget)
    phases = analysis.phases or PIPELINE_TEMPLATES["code_generation"]
    project.phases = phases
    total = len(phases)

    print(f"[maestro] Pattern: Pipeline ({total} phases)")
    prev_result = ""

    for i, phase in enumerate(phases, 1):
        cli = phase["cli"]
        role = phase["role"]

        # Build prompt with context from previous phases
        prompt = f"Task: {project.task}\n\nYour role in this phase: {role}"
        if prev_result:
            prompt += f"\n\nContext from previous phase:\n{prev_result[:3000]}"

        print(f"[{i}/{total}] {role} ({cli.title()})... dispatching")
        result = dispatch_agent(cli, prompt, project.cwd, timeout=timeout,
                                skip_preflight=skip_preflight)
        project.results.append(asdict(result))
        prev_result = result.output

        print(f"[{i}/{total}] {role} ({cli.title()})... {result.status} ({result.duration_s}s)")

        if result.status == "failed":
            print(f"[maestro] Pipeline halted at phase {i} due to failure.")
            break

    return project


def execute_race(project: MaestroProject, timeout: int,
                 skip_preflight: bool = False) -> MaestroProject:
    """Same task to multiple CLIs in parallel, compare results."""
    explicit_clis = detect_explicit_clis(project.task)
    clis = explicit_clis if len(explicit_clis) >= 2 else ["claude", "codex", "gemini"]
    project.phases = [{"id": cli, "cli": cli, "role": f"Race participant ({cli})"} for cli in clis]
    total = len(clis)

    print(f"[maestro] Pattern: Race ({total} agents in parallel)")

    # Launch all in background
    bg_info: list[tuple[str, str | None, str | None]] = []
    for cli in clis:
        print(f"  Launching {cli.title()}...")
        result = dispatch_agent(cli, project.task, project.cwd, background=True,
                                skip_preflight=skip_preflight)
        info = json.loads(result.output) if result.output else {}
        bg_info.append((cli, info.get("pid"), info.get("log")))

    # Wait for all to complete
    print(f"[maestro] Waiting for all agents (timeout: {timeout}s)...")
    for cli, pid, log_path in bg_info:
        if pid:
            start = time.time()
            output = wait_for_background(pid, log_path, timeout)
            elapsed = round(time.time() - start, 1)
            project.results.append(asdict(AgentResult(
                task_id=f"{cli}-race", cli=cli,
                status="done", duration_s=elapsed,
                output=output[:5000],
            )))
            print(f"  {cli.title()} completed ({elapsed}s)")
        else:
            project.results.append(asdict(AgentResult(
                task_id=f"{cli}-race", cli=cli,
                status="failed", duration_s=0,
                output="Failed to launch background process",
            )))

    return project


def execute_swarm(project: MaestroProject, timeout: int,
                  ratio: str | None = None,
                  skip_preflight: bool = False) -> MaestroProject:
    """Distribute subtasks across CLIs by category or ratio."""
    analysis = analyze_task(project.task, project.budget)

    if ratio:
        # Parse ratio like "3:1:1" → claude:3, codex:1, gemini:1
        parts = ratio.split(":")
        cli_names = ["claude", "codex", "gemini"]
        task_assignments = []
        for i, count in enumerate(parts):
            cli = cli_names[i] if i < len(cli_names) else cli_names[-1]
            for j in range(int(count)):
                task_assignments.append({
                    "id": f"{cli}-{j+1}",
                    "cli": cli,
                    "role": f"Subtask (assigned to {cli})",
                })
        project.phases = task_assignments
    else:
        # Use categories to distribute
        categories = analysis.categories[:5]  # max 5 subtasks
        project.phases = []
        for cat in categories:
            cli = route_to_cli(cat, project.budget)
            project.phases.append({
                "id": f"{cat}-{cli}",
                "cli": cli,
                "role": f"Handle {cat.replace('_', ' ')} aspect",
            })

    total = len(project.phases)
    print(f"[maestro] Pattern: Swarm ({total} subtasks)")

    # Launch all in background
    bg_info: list[tuple[dict, str | None, str | None]] = []
    for phase in project.phases:
        cli = phase["cli"]
        prompt = f"Task: {project.task}\n\nFocus on: {phase['role']}"
        print(f"  Launching {phase['id']} ({cli})...")
        result = dispatch_agent(cli, prompt, project.cwd, background=True,
                                skip_preflight=skip_preflight)
        info = json.loads(result.output) if result.output else {}
        bg_info.append((phase, info.get("pid"), info.get("log")))

    # Wait for all
    print(f"[maestro] Waiting for all agents (timeout: {timeout}s)...")
    for phase, pid, log_path in bg_info:
        if pid:
            start = time.time()
            output = wait_for_background(pid, log_path, timeout)
            elapsed = round(time.time() - start, 1)
            project.results.append(asdict(AgentResult(
                task_id=phase["id"], cli=phase["cli"],
                status="done", duration_s=elapsed,
                output=output[:5000],
            )))
            print(f"  {phase['id']} completed ({elapsed}s)")

    return project


def execute_escalation(project: MaestroProject, timeout: int,
                       skip_preflight: bool = False) -> MaestroProject:
    """Start cheap, escalate on failure or low quality."""
    chain = ["gemini", "codex", "claude"]  # cheapest → most expensive
    project.phases = [{"id": f"attempt-{cli}", "cli": cli, "role": f"Attempt ({cli})"} for cli in chain]

    print(f"[maestro] Pattern: Escalation (chain: {' → '.join(c.title() for c in chain)})")

    for i, cli in enumerate(chain, 1):
        print(f"[{i}/{len(chain)}] Trying {cli.title()}...")
        result = dispatch_agent(cli, project.task, project.cwd, timeout=timeout,
                                skip_preflight=skip_preflight)
        project.results.append(asdict(result))

        if result.status == "done" and quality_check(result.output):
            print(f"[{i}/{len(chain)}] {cli.title()} succeeded ({result.duration_s}s)")
            break
        else:
            reason = "quality insufficient" if result.status == "done" else result.status
            print(f"[{i}/{len(chain)}] {cli.title()} — {reason}, escalating...")

    return project


def quality_check(output: str) -> bool:
    """Basic heuristic quality check for escalation pattern."""
    if not output or len(output.strip()) < 50:
        return False
    error_signals = ["error:", "traceback", "exception", "failed", "could not"]
    lower = output.lower()
    return not any(sig in lower for sig in error_signals)

# ── Report Generation ──────────────────────────────────────────────

def generate_report(project: MaestroProject, as_json: bool = False) -> str:
    """Generate a structured report from a completed project."""
    if as_json:
        return json.dumps(asdict(project), indent=2, ensure_ascii=False)

    lines = [
        f"=== Maestro Report: {project.name} ===",
        f"Pattern: {project.pattern.title()}",
        f"Task: {project.task[:100]}",
        f"Budget: {project.budget}",
        f"Duration: {project.total_duration_s}s",
        "",
        "--- Agent Results ---",
    ]

    for i, r in enumerate(project.results, 1):
        lines.append(f"\n[{i}] {r.get('cli', '?').title()} ({r.get('task_id', '?')})")
        lines.append(f"    Status: {r.get('status', '?')} ({r.get('duration_s', 0)}s)")
        output = r.get("output", "")
        if output:
            # Truncate for display
            preview = output[:500].replace("\n", "\n    ")
            lines.append(f"    Output: {preview}")
            if len(output) > 500:
                lines.append(f"    ... ({len(output)} chars total)")

    lines.append("\n--- Summary ---")
    done_count = sum(1 for r in project.results if r.get("status") == "done")
    total = len(project.results)
    lines.append(f"Completed: {done_count}/{total} agents")

    if project.pattern == "race":
        lines.append("Recommendation: Compare outputs above and select the best result.")
    elif project.pattern == "escalation":
        for r in reversed(project.results):
            if r.get("status") == "done":
                lines.append(f"Final answer from: {r.get('cli', '?').title()}")
                break

    return "\n".join(lines)

# ── macOS Notification ─────────────────────────────────────────────

def notify(title: str, message: str):
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"'
        ], capture_output=True, timeout=5)
    except Exception:
        pass

# ── Main CLI ───────────────────────────────────────────────────────

def cmd_run(args):
    """Analyze task and execute."""
    task = " ".join(args.task)
    if not task:
        print("Error: task description is required", file=sys.stderr)
        sys.exit(1)

    project = MaestroProject(
        name=args.project or generate_project_name(),
        pattern=args.pattern or "auto",
        task=task,
        budget=args.budget,
        cwd=args.cwd or os.getcwd(),
        created_at=datetime.now().isoformat(),
    )

    # Auto-select pattern if not specified
    if project.pattern == "auto":
        analysis = analyze_task(task, args.budget)
        project.pattern = analysis.recommended_pattern

    print(f"[maestro] Task: {task[:80]}")
    print(f"[maestro] Project: {project.name}")
    save_project(project)

    start = time.time()

    # Execute pattern
    sp = getattr(args, 'skip_preflight', False)
    executors = {
        "solo": execute_solo,
        "pipeline": execute_pipeline,
        "race": execute_race,
        "swarm": lambda p, t, s: execute_swarm(p, t, args.ratio, s),
        "escalation": execute_escalation,
    }

    executor = executors.get(project.pattern, execute_solo)
    project = executor(project, args.timeout, sp)

    project.total_duration_s = round(time.time() - start, 1)
    project.completed_at = datetime.now().isoformat()
    save_project(project)

    print(f"\n[maestro] All done in {project.total_duration_s}s")
    report = generate_report(project, as_json=args.json)
    print(report)

    if args.notify:
        notify("Maestro", f"{project.pattern.title()} completed: {task[:40]}")


def cmd_plan(args):
    """Analyze task and show execution plan (dry-run)."""
    task = " ".join(args.task)
    if not task:
        print("Error: task description is required", file=sys.stderr)
        sys.exit(1)

    analysis = analyze_task(task, args.budget)
    pattern = args.pattern or analysis.recommended_pattern

    # Sync analysis dataclass with the effective pattern so JSON output is consistent
    if args.pattern and args.pattern != analysis.recommended_pattern:
        analysis.recommended_pattern = args.pattern
        # Rebuild phases if pattern was overridden to pipeline
        if args.pattern == "pipeline":
            primary_cat = analysis.categories[0]
            analysis.phases = PIPELINE_TEMPLATES.get(primary_cat, PIPELINE_TEMPLATES["code_generation"])
        elif args.pattern != "pipeline":
            analysis.phases = []

    # Detect explicitly mentioned CLIs
    explicit_clis = detect_explicit_clis(task)

    print(f"=== Maestro Plan (dry-run) ===")
    print(f"Task: {task}")
    print(f"Complexity: {analysis.complexity}")
    print(f"Decomposability: {analysis.decomposability}")
    print(f"Categories: {', '.join(analysis.categories)}")
    print(f"Recommended pattern: {pattern}")
    print(f"Budget: {args.budget}")
    if explicit_clis:
        print(f"Explicit CLIs detected: {', '.join(c.title() for c in explicit_clis)}")
    print()

    if pattern == "solo":
        if explicit_clis:
            cli = explicit_clis[0]
        else:
            cli = route_to_cli(analysis.categories[0], args.budget)
        print(f"Will dispatch to: {cli.title()}")

    elif pattern == "pipeline":
        phases = analysis.phases or PIPELINE_TEMPLATES.get(
            analysis.categories[0], PIPELINE_TEMPLATES["code_generation"]
        )
        print("Pipeline phases:")
        for i, p in enumerate(phases, 1):
            print(f"  {i}. [{p['cli'].title()}] {p['role']}")

    elif pattern == "race":
        if explicit_clis and len(explicit_clis) >= 2:
            print(f"Race participants: {', '.join(c.title() for c in explicit_clis)}")
        else:
            print("Race participants: Claude, Codex, Gemini (all 3 in parallel)")

    elif pattern == "swarm":
        if args.ratio:
            parts = args.ratio.split(":")
            cli_names = ["Claude", "Codex", "Gemini"]
            print(f"Swarm with ratio: {args.ratio}")
            for i, count in enumerate(parts):
                if i < len(cli_names):
                    print(f"  {cli_names[i]}: {count} subtask(s)")
        else:
            print("Swarm subtasks (by category):")
            for cat in analysis.categories[:5]:
                cli = route_to_cli(cat, args.budget)
                print(f"  - {cat}: {cli.title()}")

    elif pattern == "escalation":
        print("Escalation chain: Gemini → Codex → Claude (cheapest first)")

    if args.json:
        plan_data = asdict(analysis)
        if explicit_clis:
            plan_data["explicit_clis"] = explicit_clis
        print(json.dumps(plan_data, indent=2, ensure_ascii=False))


def cmd_status(args):
    """Show status of a maestro project."""
    project = load_project(args.project)
    done = sum(1 for r in project.results if r.get("status") == "done")
    total = len(project.phases)
    completed = "Yes" if project.completed_at else "No"

    print(f"Project: {project.name}")
    print(f"Pattern: {project.pattern}")
    print(f"Task: {project.task[:80]}")
    print(f"Progress: {done}/{total} agents completed")
    print(f"Finished: {completed}")
    if project.completed_at:
        print(f"Duration: {project.total_duration_s}s")


def cmd_list(args):
    """List all maestro projects."""
    projects = list_projects()
    if not projects:
        print("No maestro projects found.")
        return

    if args.json:
        print(json.dumps(projects, indent=2, ensure_ascii=False))
        return

    print(f"{'Name':<30} {'Pattern':<12} {'Done':<6} {'Task'}")
    print("-" * 80)
    for p in projects:
        done = "Yes" if p["completed"] else "No"
        print(f"{p['name']:<30} {p['pattern']:<12} {done:<6} {p['task']}")


def cmd_report(args):
    """Show final report for a completed project."""
    project = load_project(args.project)
    print(generate_report(project, as_json=args.json))


def main():
    parser = argparse.ArgumentParser(
        prog="maestro",
        description="Intelligent multi-CLI orchestration dispatcher",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── run ──
    p_run = sub.add_parser("run", help="Analyze task and execute")
    p_run.add_argument("task", nargs="+", help="Task description")
    p_run.add_argument("--pattern", choices=["solo", "pipeline", "race", "swarm", "escalation"])
    p_run.add_argument("--ratio", help="CLI ratio for swarm (e.g., 3:1:1)")
    p_run.add_argument("--cwd", help="Working directory")
    p_run.add_argument("--budget", default="balanced",
                       choices=["minimize", "balanced", "maximize_quality"])
    p_run.add_argument("--timeout", type=int, default=300)
    p_run.add_argument("--project", help="Custom project name")
    p_run.add_argument("--notify", action="store_true")
    p_run.add_argument("--json", action="store_true")
    p_run.add_argument("--skip-preflight", action="store_true",
                       help="Skip resource pre-flight checks (memory/context)")

    # ── plan ──
    p_plan = sub.add_parser("plan", help="Analyze task (dry-run)")
    p_plan.add_argument("task", nargs="+", help="Task description")
    p_plan.add_argument("--pattern", choices=["solo", "pipeline", "race", "swarm", "escalation"])
    p_plan.add_argument("--ratio", help="CLI ratio for swarm")
    p_plan.add_argument("--budget", default="balanced",
                        choices=["minimize", "balanced", "maximize_quality"])
    p_plan.add_argument("--json", action="store_true")

    # ── status ──
    p_status = sub.add_parser("status", help="Show project status")
    p_status.add_argument("project", help="Project name (or prefix)")

    # ── list ──
    p_list = sub.add_parser("list", help="List all projects")
    p_list.add_argument("--json", action="store_true")

    # ── report ──
    p_report = sub.add_parser("report", help="Show final report")
    p_report.add_argument("project", help="Project name (or prefix)")
    p_report.add_argument("--json", action="store_true")

    args = parser.parse_args()
    cmd_map = {
        "run": cmd_run,
        "plan": cmd_plan,
        "status": cmd_status,
        "list": cmd_list,
        "report": cmd_report,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
