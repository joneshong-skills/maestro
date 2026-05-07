# Synthesis Protocol (CCG Adaptation)

Reference for the `synthesis` orchestration pattern in maestro. Cannibalized from
oh-my-claudecode's `ccg/SKILL.md` (Yeachan-Heo/oh-my-claudecode), adapted to
maestro's dispatcher model.

## Goal

Take ONE task. Get N independent perspectives in parallel. Produce ONE answer
that explicitly surfaces consensus, conflicts, and a final direction — instead
of asking the user to read N answers and merge them mentally.

## Phase Diagram

```
                 ┌──────────────────────────────────┐
   user task     │  Phase 1: parallel advisors      │
   ───────────► │                                  │
                 │  ├── codex   (architecture/risk) │
                 │  ├── gemini  (UX/alternatives)   │
                 │  └── ... (1-3 total)             │
                 └────────────┬─────────────────────┘
                              │
                              ▼
                 ┌──────────────────────────────────┐
                 │  Phase 2: synthesizer (claude)   │
                 │                                  │
                 │  Reconciles outputs into:        │
                 │    ## Consensus                  │
                 │    ## Conflicts                  │
                 │    ## Final Direction            │
                 │    ## Action Checklist           │
                 └──────────────────────────────────┘
                              │
                              ▼
                       ONE final answer
```

## Synthesis vs Race — Decision Table

| Question | Race | Synthesis |
|----------|------|-----------|
| What does the user want at the end? | "Pick the best of N" | "ONE merged answer" |
| Who reconciles disagreement? | The user | The synthesizer |
| Output count | N candidates | 1 final + N kept for audit |
| Cost | N × CLI | (N+1) × CLI |
| Best for | "I want options" | "I want a decision" |
| Failure mode | All N fail → no answer | All advisors fail → no synthesis (advisor results still kept) |

## Why a Separate Synthesizer

If you ask one of the advisors to also synthesize, you get an echo chamber —
the synthesizer over-weights its own contribution. The synthesizer is
**forced distinct** from the advisor list. Default split:

- Advisors: codex, gemini
- Synthesizer: claude

If the user supplies `--advisors claude,codex` with `--synthesizer claude`,
maestro removes claude from the advisor list and falls back to the default.

## Perspective Hints — Why They Matter

Without a perspective hint, both advisors will produce overlapping answers
("Here is a comprehensive review of your design..."). With perspective hints,
they produce *complementary* answers covering different facets:

- codex (architecture/backend) might surface a TOCTOU race between two
  state-mutation steps and recommend an atomic check-and-claim pattern.
- gemini (UX/content) might surface that the user-visible error string
  conflates two distinct failure modes and recommend splitting the messages.

Those two perspectives don't overlap and don't directly conflict — they cover
different failure modes. The synthesizer's job is to weave them.

## The Synthesis Prompt

```
You are synthesizing perspectives from {n} independent advisors who evaluated the same task.

Original task:
---
{task}
---

# Advisor: Codex
_Perspective: Focus on architecture, correctness, backend design, edge cases, and risks..._

{codex_output}

# Advisor: Gemini
_Perspective: Focus on UX/content clarity, alternative approaches, accessibility..._

{gemini_output}

Produce ONE unified response with these REQUIRED sections (use exact headings):

## Consensus
Points where all advisors agreed. List as bullets.

## Conflicts
Points where advisors disagreed. For each conflict:
- State the disagreement
- Each advisor's reasoning (cite which advisor)
- Which view is stronger and why

## Final Direction
Your synthesized recommendation. For each decision, cite which advisor influenced it
(or note when you departed from all of them and why).

## Action Checklist
Concrete next steps in priority order. Each step <= 1 sentence.

Rules:
- Be explicit when one advisor was clearly wrong — do not paper over disagreements.
- Be explicit when both perspectives were valid for different parts of the task.
- Do NOT just summarize each advisor in turn — integrate.
```

## Tuning the Perspectives

Defaults live in `scripts/maestro.py` as `SYNTHESIS_PERSPECTIVES`. To customize
for your project, you can either:

1. **Edit the dict directly** for global change.
2. **Wrap the task** with a perspective hint that overrides the default:
   ```bash
   $MAESTRO run --pattern synthesis \
     --advisors codex,gemini \
     "Perspective for codex: focus on Postgres-specific quirks. \
      Perspective for gemini: focus on i18n implications. \
      Task: design the user signup flow."
   ```
   The wrapper text overrides the default hint via prompt structure.

## Auto-Routing Triggers

`detect_synthesis_signal()` in `maestro.py` watches for these phrases (case-insensitive):

```
cross-validation, cross validate, cross-validate,
second opinion, multiple perspectives, multi-perspective,
reconcile, synthesize, synthesis, tri-model, ccg,
多視角, 綜合, 跨驗證, 第二意見, 整合多家
```

When auto-detected, `synthesis` wins over budget-based pattern selection. To
disable auto-routing for a specific task, pass `--pattern <other>` explicitly.

## Failure Handling

| Scenario | Maestro behavior |
|----------|-----------------|
| 1 of 2 advisors fails | Synthesize with available output, warn about missing perspective |
| Both advisors fail | Skip synthesis, return advisor failure report |
| Synthesizer fails | Keep advisor outputs, flag synthesis incomplete in report |
| Advisor times out | Treated as failure (same as launch failure) |

## Cost Profile

| Pattern | CLI calls | Tokens (rough) |
|---------|-----------|----------------|
| Solo | 1 | 1× |
| Race (3 CLIs) | 3 | 3× |
| Synthesis (2+1) | 3 | 3× advisor + ~1.5× synthesizer (because synthesizer reads all advisor outputs) |
| Pipeline (3 phases) | 3 | 3× |

Synthesizer cost is bounded — advisor outputs are truncated to 4000 chars each
in the synthesis prompt to avoid context bloat.

## Cross-References

- `SKILL.md` — Six Orchestration Patterns table + decision tree
- `scripts/maestro.py` — `execute_synthesis()`, `SYNTHESIS_PERSPECTIVES`, `SYNTHESIS_PROMPT_TEMPLATE`
- `examples/synthesis-cross-validation.sh` — runnable example
- Source: github.com/Yeachan-Heo/oh-my-claudecode `skills/ccg/SKILL.md`
