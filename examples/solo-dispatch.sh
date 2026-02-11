#!/bin/bash
# Solo pattern: dispatch a single task to the best CLI
MAESTRO="python3 $HOME/.claude/skills/maestro/scripts/maestro.py"

# Auto-select CLI (Claude for debugging tasks)
$MAESTRO run "Fix the login bug in src/auth.ts" --cwd /path/to/project

# Force budget CLI (Gemini for cheap)
$MAESTRO run --budget minimize "Explain the auth module" --cwd /path/to/project

# Dry-run to see what would happen
$MAESTRO plan "Add a new /users endpoint to the REST API"
