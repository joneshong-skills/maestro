#!/usr/bin/env python3
"""Role routing — declarative role → provider × tier config layer.

Inspired by oh-my-claudecode (OMC) team.roleRouting (cannibalized 2026-05-08).
Adds a config layer above the existing CLI_ROUTING table so users can
declare role assignments in jsonc instead of editing maestro.py.

Config precedence (highest → lowest):
  1. env MAESTRO_ROLE_OVERRIDES   (JSON string)
  2. <cwd>/.claude/maestro.jsonc  (project)
  3. ~/.claude/maestro.jsonc      (user)
  4. Built-in defaults            (mirrors CLI_ROUTING)

Tier abstraction (HIGH/MEDIUM/LOW) decouples role config from model names.
Loud fallback: missing CLI → fallback to claude + visible warning (never silent).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Defaults ───────────────────────────────────────────────────────

DEFAULT_TIER_MODELS: dict[str, dict[str, str]] = {
    "claude": {"HIGH": "opus", "MEDIUM": "sonnet", "LOW": "haiku"},
    "codex":  {"HIGH": "gpt-5", "MEDIUM": "gpt-5-codex", "LOW": "gpt-5-codex"},
    "gemini": {"HIGH": "gemini-2.5-pro", "MEDIUM": "gemini-2.5-flash", "LOW": "gemini-2.5-flash"},
}

# Maps category → {provider, model_tier}. Mirrors maestro.CLI_ROUTING but with tier abstraction.
DEFAULT_ROLE_ROUTING: dict[str, dict[str, str]] = {
    "code_generation":   {"provider": "codex",  "model": "MEDIUM"},
    "code_review":       {"provider": "claude", "model": "MEDIUM"},
    "debugging":         {"provider": "claude", "model": "MEDIUM"},
    "refactoring":       {"provider": "codex",  "model": "MEDIUM"},
    "architecture":      {"provider": "claude", "model": "HIGH"},
    "testing":           {"provider": "codex",  "model": "MEDIUM"},
    "long_doc_analysis": {"provider": "gemini", "model": "HIGH"},
    "frontend":          {"provider": "gemini", "model": "MEDIUM"},
    "backend":           {"provider": "codex",  "model": "MEDIUM"},
    "security":          {"provider": "claude", "model": "HIGH"},
    "research":          {"provider": "gemini", "model": "MEDIUM"},
}

# User-friendly aliases → canonical category names
ROLE_ALIASES: dict[str, str] = {
    "reviewer":          "code_review",
    "code-reviewer":     "code_review",
    "harsh-critic":      "code_review",
    "critic":            "code_review",
    "tester":            "testing",
    "test-engineer":     "testing",
    "fixer":             "debugging",
    "build-fixer":       "debugging",
    "debugger":          "debugging",
    "frontend-dev":      "frontend",
    "backend-dev":       "backend",
    "researcher":        "research",
    "analyst":           "research",
    "security-auditor":  "security",
    "security-reviewer": "security",
    "docs":              "long_doc_analysis",
    "writer":            "long_doc_analysis",
    "document-specialist": "long_doc_analysis",
    "executor":          "code_generation",
    "implementer":       "code_generation",
    "architect":         "architecture",
    "planner":           "architecture",
}

# Tier shorthand for "balanced/minimize/maximize_quality" budget compatibility
BUDGET_TIER_MAP: dict[str, str] = {
    "minimize":         "LOW",
    "balanced":         "MEDIUM",
    "maximize_quality": "HIGH",
}

CONFIG_PATHS = {
    "user": Path.home() / ".claude" / "maestro.jsonc",
    "project_subpath": ".claude/maestro.jsonc",  # joined with cwd
}


# ── Data Classes ───────────────────────────────────────────────────

@dataclass
class ResolvedRouting:
    """Resolved routing decision for a single role."""
    role: str
    provider: str           # claude | codex | gemini
    model: str              # explicit model id (tier resolved)
    tier: str               # HIGH / MEDIUM / LOW (or "explicit" if user passed model id)
    sources: list[str] = field(default_factory=list)  # which config layers contributed
    fallback: bool = False
    fallback_reason: str = ""

    def as_dict(self) -> dict:
        return {
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "tier": self.tier,
            "sources": self.sources,
            "fallback": self.fallback,
            "fallback_reason": self.fallback_reason,
        }


# ── JSONC Parser (stdlib only) ─────────────────────────────────────

_JSONC_LINE_COMMENT = re.compile(r'//[^\n]*')
_JSONC_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)
_JSONC_TRAILING_COMMA = re.compile(r',(\s*[}\]])')


def _strip_jsonc(text: str) -> str:
    """Strip JSONC comments and trailing commas, return parseable JSON."""
    # Order matters: block first (may contain //), then line, then trailing comma
    text = _JSONC_BLOCK_COMMENT.sub('', text)
    text = _JSONC_LINE_COMMENT.sub('', text)
    text = _JSONC_TRAILING_COMMA.sub(r'\1', text)
    return text


def _load_jsonc(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding='utf-8')
        return json.loads(_strip_jsonc(text))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[role-routing] WARN: failed to load {path}: {e}", file=sys.stderr)
        return None


# ── Config Resolution ──────────────────────────────────────────────

def _load_layer(env_var: str, project_cwd: Path | None) -> tuple[dict | None, dict | None, dict | None]:
    """Load env / project / user config layers."""
    env_cfg = None
    raw_env = os.environ.get(env_var, "").strip()
    if raw_env:
        try:
            env_cfg = json.loads(raw_env)
        except json.JSONDecodeError as e:
            print(f"[role-routing] WARN: invalid {env_var} JSON ignored: {e}", file=sys.stderr)

    project_cfg = None
    if project_cwd:
        candidate = project_cwd / CONFIG_PATHS["project_subpath"]
        project_cfg = _load_jsonc(candidate)

    user_cfg = _load_jsonc(CONFIG_PATHS["user"])
    return env_cfg, project_cfg, user_cfg


def _extract_section(cfg: dict | None, key: str) -> dict:
    """Pull `maestro.<key>` (OMC-style) or `<key>` (flat) from a config dict."""
    if not cfg:
        return {}
    if "maestro" in cfg and isinstance(cfg["maestro"], dict):
        return cfg["maestro"].get(key, {}) or {}
    return cfg.get(key, {}) or {}


def normalize_role(role: str) -> str:
    """Map alias → canonical category. Returns the input unchanged if not aliased."""
    if not role:
        return role
    role = role.strip()
    return ROLE_ALIASES.get(role, role)


def check_cli_available(provider: str) -> bool:
    """Probe whether a CLI is on PATH. Always True for 'claude' (assumed available)."""
    if provider == "claude":
        return True  # Claude Code self-host
    binary = {"codex": "codex", "gemini": "gemini"}.get(provider)
    if not binary:
        return False
    return shutil.which(binary) is not None


def resolve_routing(
    role: str,
    budget: str = "balanced",
    project_cwd: str | Path | None = None,
    *,
    enable_fallback: bool = True,
    env_var: str = "MAESTRO_ROLE_OVERRIDES",
) -> ResolvedRouting:
    """Resolve a single role to provider × model, applying config layers.

    Args:
        role: canonical category name OR alias (will be normalized)
        budget: minimize/balanced/maximize_quality (only used if config has no explicit model)
        project_cwd: project root for project-level config lookup (None = skip)
        enable_fallback: if True, missing CLI → fallback to claude + warn
        env_var: env variable name for highest-priority overrides

    Returns:
        ResolvedRouting with provider, model, tier, sources, fallback info
    """
    canonical = normalize_role(role)
    project_path = Path(project_cwd).resolve() if project_cwd else None

    env_cfg, project_cfg, user_cfg = _load_layer(env_var, project_path)
    sources: list[str] = []

    # Merge roleRouting (later overrides earlier; we want env > project > user > defaults)
    merged_routing: dict[str, dict] = dict(DEFAULT_ROLE_ROUTING)
    sources.append("defaults")
    for layer_name, cfg in (("user", user_cfg), ("project", project_cfg), ("env", env_cfg)):
        section = _extract_section(cfg, "roleRouting")
        if section:
            sources.append(layer_name)
            for k, v in section.items():
                merged_routing[normalize_role(k)] = v

    # Merge tierModels
    merged_tiers = {p: dict(m) for p, m in DEFAULT_TIER_MODELS.items()}
    for cfg in (user_cfg, project_cfg, env_cfg):
        section = _extract_section(cfg, "tierModels")
        for provider, mapping in section.items():
            if provider not in merged_tiers:
                merged_tiers[provider] = {}
            merged_tiers[provider].update(mapping or {})

    # Pick spec for this role (fall back to code_generation default if unknown)
    spec = merged_routing.get(canonical) or merged_routing.get("code_generation", {})
    provider = spec.get("provider", "claude")
    model_or_tier = spec.get("model")  # may be None, tier name, or explicit id

    # Resolve model
    tier_used = "MEDIUM"
    if model_or_tier and model_or_tier.upper() in ("HIGH", "MEDIUM", "LOW"):
        tier_used = model_or_tier.upper()
        model = merged_tiers.get(provider, {}).get(tier_used, "")
    elif model_or_tier == "inherit":
        tier_used = "inherit"
        model = "inherit"
    elif model_or_tier:
        # explicit model id passed by user
        tier_used = "explicit"
        model = model_or_tier
    else:
        # No model spec → use budget tier
        tier_used = BUDGET_TIER_MAP.get(budget, "MEDIUM")
        model = merged_tiers.get(provider, {}).get(tier_used, "")

    result = ResolvedRouting(
        role=canonical,
        provider=provider,
        model=model,
        tier=tier_used,
        sources=sources,
    )

    # Loud fallback: missing CLI
    if enable_fallback and not check_cli_available(provider):
        original_provider = provider
        result.fallback = True
        result.fallback_reason = f"CLI '{original_provider}' not on PATH"
        result.provider = "claude"
        result.model = merged_tiers["claude"].get(
            tier_used if tier_used in merged_tiers["claude"] else "MEDIUM",
            "sonnet",
        )
        # Print visible warning (NEVER silent)
        print(
            f"[role-routing] FALLBACK: role='{canonical}' configured for "
            f"{original_provider} but CLI not found on PATH. "
            f"Falling back to claude/{result.model}. "
            f"Install with: npm install -g @openai/codex / @google/gemini-cli",
            file=sys.stderr,
        )

    return result


def build_snapshot(
    roles: list[str],
    budget: str = "balanced",
    project_cwd: str | Path | None = None,
    **kwargs,
) -> dict[str, ResolvedRouting]:
    """Resolve multiple roles once and return a snapshot dict.

    OMC pattern: resolved once at team creation, stable for team lifetime.
    Maestro callers should resolve once per project run, not per dispatch.
    """
    return {role: resolve_routing(role, budget, project_cwd, **kwargs) for role in roles}


# ── CLI for diagnosis ──────────────────────────────────────────────

def _cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="role-routing diagnosis")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_resolve = sub.add_parser("resolve", help="Resolve a single role")
    p_resolve.add_argument("role")
    p_resolve.add_argument("--budget", default="balanced")
    p_resolve.add_argument("--cwd", default=None)
    p_resolve.add_argument("--no-fallback", action="store_true")
    p_resolve.add_argument("--json", action="store_true")

    p_doctor = sub.add_parser("doctor", help="Check CLI availability + config sources")
    p_doctor.add_argument("--cwd", default=None)

    args = parser.parse_args()

    if args.cmd == "resolve":
        r = resolve_routing(
            args.role,
            budget=args.budget,
            project_cwd=args.cwd,
            enable_fallback=not args.no_fallback,
        )
        if args.json:
            print(json.dumps(r.as_dict(), indent=2))
        else:
            print(f"Role:     {r.role}")
            print(f"Provider: {r.provider}")
            print(f"Model:    {r.model}")
            print(f"Tier:     {r.tier}")
            print(f"Sources:  {' > '.join(r.sources)}")
            if r.fallback:
                print(f"Fallback: {r.fallback_reason}")
        return 0

    if args.cmd == "doctor":
        print("CLI availability:")
        for provider in ("claude", "codex", "gemini"):
            available = check_cli_available(provider)
            mark = "✓" if available else "✗"
            print(f"  {mark} {provider}")
        print()
        print("Config sources (highest → lowest):")
        env_cfg, project_cfg, user_cfg = _load_layer(
            "MAESTRO_ROLE_OVERRIDES",
            Path(args.cwd).resolve() if args.cwd else None,
        )
        sources = [
            ("env MAESTRO_ROLE_OVERRIDES", env_cfg),
            (f"project {args.cwd or '<cwd>'}/.claude/maestro.jsonc", project_cfg),
            (f"user {CONFIG_PATHS['user']}", user_cfg),
        ]
        for name, cfg in sources:
            mark = "✓" if cfg else "·"
            count = len(_extract_section(cfg, "roleRouting"))
            print(f"  {mark} {name}  ({count} role overrides)")
        print(f"  ✓ built-in defaults  ({len(DEFAULT_ROLE_ROUTING)} roles)")
        return 0


if __name__ == "__main__":
    sys.exit(_cli_main() or 0)
