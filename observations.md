# Observations — maestro

## Pending

### 2026-02-11 — Parallel detection threshold too strict
- **Category**: flow
- **Evidence**: "Build auth, profiles, and notifications" (1 "and", 3 items) detected as atomic → Solo instead of Swarm
- **Research**: Pragmatist assessment: wait for real usage data before adding comma-pattern detection
- **Confidence**: Medium
- **Trigger**: If user reports a task that should be parallel but was dispatched as Solo

### 2026-02-11 — Quality signal not implemented
- **Category**: enhance
- **Evidence**: Decision tree doc references "quality" as input signal (standard/high) but code never detects it. "important production PR" stays Solo instead of Race.
- **Research**: Skeptic: undefined requirements, scope creep. Pragmatist: needs user testing to define "quality"
- **Confidence**: Low
- **Trigger**: If user explicitly requests "high quality" dispatch and gets wrong pattern

### 2026-02-11 — Pipeline template mismatch for custom sequential tasks
- **Category**: enhance
- **Evidence**: "Analyze codebase then build graph then document" uses generic code_generation template instead of matching the actual steps described
- **Research**: All 3 agents agree: scope creep risk, NLP-level parsing needed. Current templates are reasonable for v0.1.x
- **Confidence**: Low
- **Trigger**: When user frequently uses Pipeline and complains about phase mismatch

## Resolved

(none yet)
