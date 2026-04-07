#!/bin/bash
# Solo pattern: dispatch a single task to the best CLI

# Auto-select CLI (Claude for debugging tasks)
maestro run "Fix the login bug in src/auth.ts" --cwd /path/to/project

# Force budget CLI (Gemini for cheap)
maestro run --budget minimize "Explain the auth module" --cwd /path/to/project

# Dry-run to see what would happen
maestro plan "Add a new /users endpoint to the REST API"
