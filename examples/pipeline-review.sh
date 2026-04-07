#!/bin/bash
# Pipeline pattern: Claude architects → Codex implements → Claude reviews

# Auto-detected pipeline (sequential signals in task description)
maestro run "First design the API spec, then implement it, finally review for quality" \
  --cwd /path/to/project

# Explicit pipeline for a feature build
maestro run --pattern pipeline "Build user registration with email verification" \
  --cwd /path/to/project \
  --timeout 600 \
  --notify

# Check progress while running
maestro status maestro-20260211-143022

# View final report
maestro report maestro-20260211-143022
