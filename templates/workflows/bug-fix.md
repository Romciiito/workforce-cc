# Workflow: Bug Fix

A WAT-framework workflow for diagnosing and fixing a reported bug.

---

## Trigger

User reports: a crash, an unexpected behavior, a failing test, a 5xx error, a data integrity issue, or similar.

---

## Steps

### 1. Reproduce the bug

Before touching any code:

1. Read the bug report carefully. Extract:
   - What the user did (steps to reproduce)
   - What they expected
   - What actually happened (error message, stack trace, incorrect output)
2. Reproduce locally. Do not proceed to fix until you can trigger the bug yourself.
3. If the bug is intermittent or environment-specific, document the reproduction conditions.

**If you cannot reproduce:** Ask the user for more context (logs, env, steps) rather than guessing at a fix.

---

### 2. Root cause analysis — write an execution trace

Work from the symptom inward and produce a written **execution trace** before any fix discussion. This is the single highest-leverage practice for bug fixing — it forces you to find the actual cause instead of patching the first thing that looks suspicious. Pattern borrowed from `agent-dispatch`'s execution-trace methodology.

#### The trace shape

Every bug fix produces a trace with five fields:

```markdown
# Trace — <one-line bug summary>

## Entry point
<the route, CLI command, event handler, or test that triggers the bug — file:line>

## Function call chain
1. <file:line>  — <what this function does>
2. <file:line>  — <what this function does>
3. <file:line>  — <where state mutates / decision is made>
   ...

## Root cause
<one sentence — the specific thing that's wrong and why. NOT a symptom, the cause.>

## Fix site
<file:line — the single line or block that gets changed>

## Verification
<the literal command that proves the fix:  `pytest tests/<path>::test_<name> -x`>
```

If you cannot fill in any of those five fields, you have not yet found the root cause. Keep tracing.

#### How to build the trace

1. **Read the error.** Full stack trace > last line. Find the first frame in project code (skip library internals). Write that line as the bottom of the call chain.
2. **Walk up the stack.** For each frame, read the function and write a one-line summary of what it does. Continue until you reach the entry point (route / event / CLI). Now you have the chain top-to-bottom.
3. **Identify the inversion.** Somewhere in the chain a function does the wrong thing — produces wrong output for valid input, accepts invalid input, branches incorrectly, or fails to handle a case. Mark it. That's the **root cause**.
4. **Distinguish symptom from cause.** "Returns null" is a symptom. "Doesn't initialise the cache before first read" is a cause. The cause is what you fix.
5. **Identify the fix site.** Often the same line as the root cause; sometimes one frame up (e.g. caller passes wrong arg). Write the exact `file:line`.
6. **Choose the verification.** What command will prove the fix landed and the bug is gone? Usually a specific failing test name, sometimes a manual reproduction step. Write the literal command.

#### Why traces matter

- **They prevent symptom-patching.** A 5-frame trace forces you to look at the chain, not just the line where the exception was raised.
- **They produce a regression test for free.** The verification field IS the regression test command.
- **They survive context resets.** A new engineer reading the trace can jump in mid-fix without re-reading the whole codebase.
- **They make code review trivial.** The reviewer reads the trace, then the diff, and asks "does the diff change the fix site to address the root cause?"

Do not write a fix until the trace is complete.

---

### 3. Write a regression test first

The trace's `## Verification` field tells you what test name to write. Before fixing, write a test that:
- Reproduces the bug (it must fail on the current code)
- Will pass once the fix is in place
- Is as narrow as possible (unit test preferred; integration test if the bug requires I/O)
- Matches the verification command from your trace exactly

```python
# Example shape
def test_<thing>_does_not_<bad_behavior>_when_<condition>():
    # Arrange
    ...
    # Act
    result = <call that triggered the bug>
    # Assert
    assert result == <expected>, "was broken by <root cause>"
```

Commit the failing test on a separate commit (or at minimum confirm it fails) before writing the fix. This proves the test actually catches the bug.

---

### 4. Fix

1. Create a branch: `git checkout -b fix/<short-slug>`.
2. Make the minimal change that fixes the root cause. Resist the urge to refactor unrelated code in the same commit — it obscures the diff during review.
3. Confirm the regression test now passes.
4. Confirm no previously passing tests now fail: run the full test suite.
5. If the bug was a security issue (auth bypass, injection, data leak), immediately check for the same pattern in related code — bugs of a type often appear in clusters.

---

### 5. Manual verification

Run the full local stack and verify:
- [ ] The reported bug no longer occurs
- [ ] The fix does not break adjacent functionality
- [ ] Edge cases around the fix behave correctly (empty input, boundary values, concurrent requests)
- [ ] No new console errors or warnings introduced

---

### 6. Update workplan

If this bug was tracked in `workplan.md`:
- Check off the corresponding task.
- If the fix completes a phase, mark it ✅ and update the summary table.

If the bug was not in the workplan but reveals a gap (missing validation, missing test coverage), add a task to the relevant phase now.

---

### 7. Open PR

Paste the execution trace into the PR body — it's already in the right shape and saves the reviewer ten minutes of digging.

```
gh pr create \
  --title "fix: <one-line description of what was wrong>" \
  --body "$(cat <<'EOF'
## Trace
- **Entry point**: <file:line>
- **Call chain**: <file:line> → <file:line> → <file:line>
- **Root cause**: <one sentence>
- **Fix site**: <file:line>
- **Verification**: `<the literal test command>`

## Fix
<One sentence: what the change does>

## Regression test
`tests/path/to/test_<thing>.py::test_<specific_test>`

## Test plan
- [ ] Regression test passes: `pytest tests/path/to/test_<thing>.py -v`
- [ ] Full test suite passes
- [ ] Manual verification completed (see Step 5 above)
- [ ] workplan.md updated if applicable

## Risk
<low / medium / high> — <reason>
EOF
)"
```

---

## Abort conditions

- Stop and ask the user if: the root cause requires a breaking schema change, the fix would require disabling a security control, or the bug is in a third-party library with no safe workaround.
- Do not ship a fix that trades one bug for a security regression.
