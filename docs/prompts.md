# Prompts

The four specialist prompts live as plain Markdown files under [`prompts/`](../prompts/). They're rendered with Jinja at runtime (`prompts.py:render_prompt`) — variables go in `{{ var }}` placeholders, no logic in templates.

This is deliberate: prompts are the most-iterated part of the system, and a flat Markdown file is the easiest thing to diff in PR review. Versioning happens via git, not inside an agent class.

## Why prompts are here, not inline

[`agents/quality.py`](../src/pr_review_agent/agents/quality.py) is five lines:

```python
def build_quality_agent(llm, model_id):
    return SpecialistAgent(
        agent_name="quality",
        llm=llm,
        prompt_name="quality",
        model_id=model_id,
    )
```

Everything that defines what a quality reviewer looks for lives in [`prompts/quality.md`](../prompts/quality.md). Two consequences:

- Prompt iteration is a one-file PR — no Python changes needed.
- The cache key includes a hash of the prompt template (`prompts.prompt_version`), so editing a prompt invalidates the relevant cache entries automatically. No manual bumping.

## Variables

Every prompt is rendered with the same context:

| variable | type | source |
|---|---|---|
| `pr_title` | str | `PRMetadata.title` |
| `pr_author` | str (`"unknown"` if null) | `PRMetadata.author` |
| `diff` | str (full unified diff) | `ReviewState.diff` |
| `files_changed` | list[str] (paths) | `[fc.path for fc in files_changed]` |

Jinja runs in `StrictUndefined` mode so a typo in a `{{ variable }}` raises at render time rather than silently rendering an empty string.

## Output schema

Every agent prompt ends with the same JSON envelope:

```json
{
  "findings": [
    {
      "severity": "critical | high | medium | low | info",
      "file": "path/from/repo/root.py",
      "line": 42,
      "end_line": 50,
      "title": "short, lowercase title (max 80 chars)",
      "explanation": "one or two sentences explaining what is wrong and why",
      "suggestion": "concrete code or rephrasing, or null if not actionable"
    }
  ]
}
```

`end_line` and `suggestion` are optional. `file` and `line` reference the **post-PR** file (the `+` side of the diff) — the composer needs that to render `path:line` anchors that match what the reviewer sees on GitHub.

The parser in [`agents/base.py`](../src/pr_review_agent/agents/base.py):

1. Pulls a fenced JSON block out of the response (or the whole content if it's a bare object).
2. Validates each entry against `_RawFinding` — missing required fields drop the entry, not the whole response.
3. Lifts `severity` / `file` / `line` / `end_line` into a `Finding` with a `FileLocation`.

A response that returns `{"findings": []}` is the documented "no issues" path. A response that's not parseable returns zero findings — we never raise on a malformed LLM response.

## Severity guidance

Each prompt includes per-agent severity calibration. The general shape:

- **critical**: must-fix-before-merge; security agent uses this for unauthenticated RCE / SQLi
- **high**: a reviewer would block on this; security uses for auth bypass, perf for confirmed N+1 with hot-path impact
- **medium**: a reviewer would flag but not block; quality smells, untested behaviour
- **low**: minor; mention only when confident
- **info**: rarely appropriate; quality and tests prompts explicitly say "almost never"

`info` and `low` get filtered by `severity_threshold` for most users. Calibrating each agent's severity ladder tightly is what keeps the comment short.

## Iterating a prompt

The recipe:

1. Find a real PR where the agent under-fires or over-fires.
2. Save the diff and the agent's actual response (use `--cache-dir` so the call is recorded).
3. Edit `prompts/<agent>.md` — usually tightening "skip" rules or adding a concrete bad example.
4. Re-run with the same diff (cache key changes because prompt hash changed → fresh call).
5. Diff the before/after responses. Did the spurious finding go away? Did the missed one appear?

Keep the cycle short and measurable. The prompts you ship aren't the ones you wrote on day one.

## Tone

Two principles, baked into every prompt:

- **Be conservative.** A noisy reviewer trains people to ignore the bot. Borderline → drop.
- **Be specific.** A finding that says "consider improving error handling" is worse than no finding at all. The prompts demand `explanation` quote the *specific* code and `suggestion` provide *concrete* replacement text.

Both rules are restated near the bottom of each prompt because LLMs are recency-biased — putting calibration last has measurably better follow-through than putting it first.
