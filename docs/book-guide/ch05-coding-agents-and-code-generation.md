# Ch05 — Coding agents and code generation

**Book:** [Chương 5 — Coding Agent và tạo mã](../ai-agent-book/ch05-coding-agents-and-code-generation.md) · PDF pages 170–214

## Chapter summary

1. **A general agent is a coding agent plus a file system** (§5.1.1–5.1.2). A minimal coding agent
   needs seven tools: code interpreter, shell, read, write, edit, glob, grep. The file system is the
   agent's backbone: memory, artifacts and experience live in files.
2. **Project instruction files** (`CLAUDE.md`, `AGENTS.md`) are the cheapest, most cache-stable
   project-level context (§5.1.3).
3. **Recommended workflow** (§5.1.3): understand the project → clarify requirements → write a short
   design and get it approved for non-trivial work → implement → verify (tests pass, not "code
   written") → self-review → keep docs in sync. Simple tasks may shortcut it.
4. **The coding harness** (§5.1.4) has four parts: an acceptance baseline, execution boundaries,
   feedback signals and recovery means. Principles: constraints over instructions, automated
   verification, fast structured feedback, reliable recovery (version control, snapshots). Constrain
   the process too — forbid destructive shortcuts such as overwriting a file that was never read.
   Coding agents are mature because decades of test suites, type systems and version control already
   form a strong harness (§5.3).
5. **Failure and recovery** (§5.1.5):
   - four layers of failure — API (429, overload, timeout, truncated output), tool (hallucinated
     tool, bad arguments, the same error repeated), context (overflow, failed compaction, unpaired
     tool call/result), control flow (dead loops, death spirals);
   - classify before counting: retryable vs non-retryable; fingerprint tool + arguments for
     repetition; per-path consecutive-failure counters;
   - a liveness watchdog on streams; repair trajectory integrity (pair every call with a result)
     before sending;
   - tiered recovery: silent retry with backoff and jitter → degrade and continue (raise the output
     limit, a continuation instruction, a fallback model) → surface to the user only when all else
     failed;
   - tool errors become structured model input, never a crashed session;
   - provider-neutral trajectory storage — reasoning text is portable, provider signatures and call
     ids are regenerated per provider;
   - every recovery path has a circuit breaker; error paths never call the model again.
6. **Implementation techniques** (§5.1.6): execute a tool call as soon as its arguments validate;
   parallel calls behind a per-tool concurrency flag; reads by line range with line numbers; head +
   tail truncation with the full output saved; environment state appended at the tail; a syntax
   check immediately after every write.
7. **Search** (§5.1.7): grep and glob in place, without an embedding index.
8. **Five edit schemes compared** (§5.1.8): diff + apply model; old string → new string (exact,
   unique match or fail — the most predictable); line numbers (fragile); Vim commands; head + tail
   anchors. Editing is the core operation of iteration and maintenance.
9. **Security** (§5.1.9): the lethal trifecta — private data + untrusted content + external
   communication — with persistent memory as an amplifier; network egress control; semantic command
   analysis; principal loyalty.
10. **Code as a meta-capability** (§5.2): code as a thinking tool (§5.2.1); business rules as code
    with server-side checks (§5.2.2); generated media through a Proposer–Reviewer loop that renders
    the artifact and reviews it visually, stopping at "quality met" or a round cap (§5.2.3); code as
    a system adapter (§5.2.4); generated UI such as forms that clarify intent in one round instead of
    many (§5.2.5); agents that build agents (§5.2.6). Generating from a high-quality example and
    modifying it beats generating from scratch (§5.2).

## Steps to apply

1. **Give the agent a file system and the core tools**: read, write, edit, glob, grep — plus a code
   interpreter and shell only where executing code is allowed. (§5.1.1–5.1.2)
2. **Keep a project instruction file** as stable, cache-friendly project context. (§5.1.3)
3. **Encode the workflow**: understand → clarify → short design (approved when non-trivial) →
   implement → verify → self-review → sync docs. (§5.1.3)
4. **Build the four harness parts**: an acceptance baseline, execution boundaries, feedback signals
   and recovery (snapshots or version control). Enforce constraints in code, including process
   constraints such as "no overwrite without a prior read". (§5.1.4)
5. **Classify failures** by layer (API, tool, context, control flow) and by retryability;
   fingerprint repeated calls; count consecutive failures per path. (§5.1.5)
6. **Recover in tiers**: retry retryable errors with backoff and jitter, then degrade and continue,
   then surface to the user. Return tool errors as structured observations. Put a circuit breaker on
   every recovery path and never call the model from an error path. (§5.1.5)
7. **Protect the trajectory**: pair every tool call with a result before sending, detect truncated
   output and never execute a truncated call, store trajectories provider-neutrally. (§5.1.5)
8. **Apply the implementation techniques**: validate-then-execute, a concurrency flag per tool,
   line-numbered range reads, head + tail truncation with the full output saved, environment state at
   the tail, a syntax check after every write. (§5.1.6)
9. **Search in place with grep and glob.** (§5.1.7)
10. **Edit with exact old → new string replacement** that fails loudly on zero or multiple matches;
    keep whole-file writes for new files. (§5.1.8)
11. **Run the lethal-trifecta check on every tool set**; control network egress. (§5.1.9)
12. **Use code as leverage**: rules as code, render-and-review for visual artifacts with a round cap,
    generated forms for clarification, and start from vetted examples instead of from scratch.
    (§5.2.2–5.2.5, §5.2)

## Common pitfalls

- Declaring done when code is written but not verified. (§5.1.3)
- Whole-file rewrites that lose unseen content and multiply output tokens; fragile line-number
  edits. (§5.1.8)
- Retrying non-retryable errors, or letting error handlers call the model into a death spiral.
  (§5.1.5)
- Unpaired tool calls that the provider rejects. (§5.1.5)
- Constraints that live only in the prompt. (§5.1.4)
