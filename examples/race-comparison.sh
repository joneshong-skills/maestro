#!/bin/bash
# Race pattern: 3 CLIs compete on the same task in parallel

# Security review with all 3 CLIs
maestro run --pattern race "Review src/auth.ts for security vulnerabilities" \
  --cwd /path/to/project \
  --timeout 120 \
  --notify

# Swarm with 3:1:1 ratio (3 Claude, 1 Codex, 1 Gemini)
maestro run --pattern swarm --ratio 3:1:1 \
  "Refactor the entire user management system" \
  --cwd /path/to/project

# Escalation: start cheap, upgrade if needed
maestro run --budget minimize "Summarize the project README" \
  --cwd /path/to/project

# View JSON report for programmatic use
maestro report maestro-20260211-143022 --json | jq '.results[]'
