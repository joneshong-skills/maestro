# Lessons — maestro

## 2026-05-08 — Cannibalize OMC roleRouting into declarative config layer
- **Friction**: maestro had `CLI_ROUTING` hardcoded in Python; users could not override per-project without editing the script.
- **Fix**: Cannibalized OMC `team.roleRouting` pattern. Added `scripts/role_routing.py` with three-layer config (env > project > user > defaults), JSONC parser, tier abstraction (HIGH/MEDIUM/LOW), role aliases (`reviewer→code_review` etc.), and **loud fallback** (missing CLI → claude + stderr warning, never silent).
- **Rule**:
  1. `route_to_cli()` is the only place that maps category→CLI. Keep it the single hook.
  2. Loud-fallback over silent-fallback — silent fallback masks misconfig.
  3. Tier abstraction (`HIGH/MEDIUM/LOW`) decouples role config from model id changes (when Anthropic ships Sonnet 4.7, only `tierModels` updates).
  4. JSONC over JSON — config files need comments to be self-documenting.
  5. Project root for config lookup must be passed explicitly through call chain (`route_to_cli(category, budget, cwd=...)`); avoid `os.getcwd()` deep in the stack.
