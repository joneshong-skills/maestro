#!/bin/bash
# Pipeline pattern: Claude architects → Codex implements → Claude reviews
MAESTRO="python3 $HOME/.claude/skills/maestro/scripts/maestro.py"

# Auto-detected pipeline (sequential signals in task description)
$MAESTRO run "First design the API spec, then implement it, finally review for quality" \
  --cwd /path/to/project

# Explicit pipeline for a feature build
$MAESTRO run --pattern pipeline "Build user registration with email verification" \
  --cwd /path/to/project \
  --timeout 600 \
  --notify

# Check progress while running
$MAESTRO status maestro-20260211-143022

# View final report
$MAESTRO report maestro-20260211-143022
