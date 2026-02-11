# Decision Tree — Full Reference

## Input Signals

| Signal | Values | How to detect |
|--------|--------|--------------|
| **Complexity** | simple / moderate / complex | Word count, multi-signal keywords ("and", "then", "also") |
| **Decomposability** | atomic / sequential / parallel | Sequential: "first...then...finally"; Parallel: multiple "and" |
| **Quality** | standard / high | User says "important", "production", "critical", "security" |
| **Budget** | minimize / balanced / maximize_quality | `--budget` flag |
| **User override** | any pattern | `--pattern` flag |

## Decision Flow

```
1. User specified --pattern?
   └── YES → Use that pattern. Done.

2. Budget == minimize?
   └── YES → Escalation (always start cheap).

3. Decomposability == sequential?
   └── YES → Pipeline.
       └── Assign phases from PIPELINE_TEMPLATES.

4. Decomposability == parallel AND complexity >= moderate?
   └── YES → Swarm.
       └── If --ratio given, use ratio distribution.
       └── Else, distribute by task category.

5. Complexity == simple OR moderate?
   └── YES → Solo (route to primary CLI for top category).

6. Complexity == complex AND decomposability == atomic?
   └── Race (same task to 2-3 CLIs for comparison).

7. Default fallback:
   └── Solo with Claude Code (safest).
```

## Worked Examples

### Example 1: "Fix the typo in README.md"
- Complexity: simple (5 words)
- Decomposability: atomic
- Category: debugging
- → **Solo** → Budget CLI: Gemini (cheapest), Primary: Claude
- Result: Solo dispatch to Claude

### Example 2: "Build user registration, then add email verification, finally deploy"
- Complexity: complex (10+ words, 2 multi-signals)
- Decomposability: sequential ("then", "finally")
- Categories: code_generation, backend
- → **Pipeline**: Claude(plan) → Codex(implement) → Claude(review)

### Example 3: "Review this PR for XSS vulnerabilities" with --budget maximize_quality
- Complexity: simple
- Categories: code_review, security
- Budget: maximize_quality → but still Solo unless --pattern race
- → **Solo** → Power CLI: Claude

### Example 4: "Refactor auth module" with --budget minimize
- Budget == minimize → **Escalation**
- Chain: Gemini → Codex → Claude (stops when quality is sufficient)

### Example 5: "Analyze the entire 500K line codebase and build a dependency graph"
- Complexity: moderate
- Categories: long_doc_analysis, research
- → **Solo** → Primary CLI: Gemini (1M context advantage)

### Example 6: Same task with --pattern race
- Override → **Race**: Claude + Codex + Gemini all analyze in parallel
- Compare outputs, pick the most comprehensive

### Example 7: "Build auth, user profiles, and notification system" with --pattern swarm --ratio 3:1:1
- Override → **Swarm** with ratio
- Claude: 3 subtasks, Codex: 1 subtask, Gemini: 1 subtask
