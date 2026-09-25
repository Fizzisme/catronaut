# Ch02 — Context engineering

**Book:** [Chương 2 — Context Engineering](../ai-agent-book/ch02-context-engineering.md) · PDF pages 52–103

## Chapter summary

1. **The model API is stateless; the harness rebuilds the context on every call** (§2.1–2.2). Its
   core job is managing one message list. The minimal per-call decision (§2.2.5) is
   `messages = [stable_prefix] + trajectory + [status_message]`, compressing old evidence — while
   keeping decisions, constraints, failures and citations — only when the budget is near.
2. **Three KV-cache rules** (§2.3), which the chapter treats as architectural constraints rather
   than late optimisations (§2.3.4):
   1. never change the system prompt or tool definitions once fixed — one changed byte invalidates
      everything after it (no timestamps, no per-user fields, no reordering tools by usage);
   2. append dynamic information at the end, never splice it near the front;
   3. use the standard message format — never hand-concatenate turns or put tool results in a
      `user` message.
   Measured anti-patterns: a dynamic system prompt, dynamic tool order, sliding-window history (it
   breaks the prefix and drops tool results the agent later needs, so it loops re-calling tools),
   and text-formatted transcripts.
3. **Chat templates differ in how they keep prior reasoning** (§2.3.1). Some families drop it,
   others require it back whenever tools are sent. Mislabelling a tool result as `user` makes the
   Qwen3 template treat it as a new user turn and discard in-flight reasoning.
4. **Prompt engineering** (§2.4): Markdown for hierarchy plus XML tags for machine-precise sections;
   SOP-style procedures beat flat rule lists (scrambling rule organisation dropped task success by
   more than 30%; removing tool descriptions raised tool-call errors by 45%); business rules must be
   explicit and decidable; few-shot examples only where rules cannot express the target, drawn from
   a fixed set per task type so the prefix stays stable (§2.4.5).
5. **Tool definitions** (§2.4.6) carry usage boundaries, concrete examples, performance hints and
   cross-tool relations ("read before edit"). Deferred tool loading appends schemas at the tail and
   needs a model trained for it.
6. **Prompt injection** (§2.4.7): wrap external content in source tags
   (`<external_content source="webpage">`), keep roles strict, and treat sanitisation as auxiliary.
   Skills and status bars are injection surfaces too — review third-party skill content like code.
7. **Agent Skills are progressive disclosure** (§2.5): level 1 is metadata (`name`, and a
   `description` written as a routing condition — "use when / don't use when"); level 2 is the
   `SKILL.md` body, loaded on demand and appended at the point of invocation; level 3 is referenced
   files, read selectively. A useful skill states its reader, 3–5 core principles with right and
   wrong examples, a forbidden list and references (§2.5.2).
8. **Agent status bar** (§2.6): runtime state computed in code and appended at the tail — tool-call
   counters, the TODO plan, detailed errors, environment facts. Attention retrieves well but does not
   aggregate; a precomputed status let small open models approach frontier accuracy and cut thinking
   tokens by about an order of magnitude. Detailed error messages (type, arguments, recovery hint)
   raised alternative-solution success from 60% to 95%.
9. **Compression has three motives** (§2.7.1): length and cost, reasoning quality, and context
   anxiety. Context rot degrades retrieval long before the window is full. Production compaction is
   layered (§2.7.4): tool-result budget → drop noise → API-level clearing → archived per-round
   summaries → full LLM compaction behind a circuit breaker.
10. **Sub-agent context isolation** (§2.7.6) keeps noise out of the main context in the first place.

## Steps to apply

1. **Rebuild context explicitly on every call** as stable prefix + trajectory + status message; the
   harness owns this list. (§2.2.5)
2. **Freeze the prefix.** The system prompt and tool definitions do not change within a session: no
   timestamps, no per-user fields, deterministic tool order. (§2.3.2, §2.3.4)
3. **Append dynamic content at the tail only** — retrieved text, loaded skills, status. (§2.3.2)
4. **Use the standard message format.** Tool results go in the `tool` role with their
   `tool_call_id`; never hand-build transcripts. (§2.2.3, §2.3.1)
5. **Test your model's chat template** for how prior reasoning is kept, and round-trip reasoning the
   way the template expects. (§2.3.1)
6. **Write the system prompt as an SOP.** Named sections, Markdown headings, XML-tagged blocks,
   explicit and decidable business rules; few-shot examples only where rules fall short, from a
   fixed set. (§2.4.2–2.4.5)
7. **Write complete tool definitions**: usage boundaries, examples, performance hints, relations to
   other tools. (§2.4.6)
8. **Tag external content by source and keep roles strict.** Review third-party skills like code
   before loading them. (§2.4.7)
9. **Implement skills as progressive disclosure.** Catalog (name + routing-condition description) in
   the prefix; body loaded on demand at the tail; references read selectively. (§2.5.1–2.5.4)
10. **Add a status bar computed in code** at the tail: counters, plan, errors, environment facts.
    Never delete the raw context it summarises; choose replace-each-round or append-only by the
    break-even rule. (§2.6.1–2.6.4)
11. **Make tool errors detailed**: error type, offending arguments, a one-line recovery hint. (§2.6)
12. **Compact in layers when measurements call for it.** Offload large tool output with a preview
    and a frozen replacement; batch near a threshold (e.g. 80%); keep decisions, constraints,
    failures and sources; mark compressed content so it is never compressed twice. (§2.7.4–2.7.5)
13. **Have the agent write progress to documents** so compaction cannot lose early decisions.
    (§2.7.5)
14. **Isolate noisy subtasks in a sub-agent context.** (§2.7.6)

## Common pitfalls

- A dynamic system prompt or tool order — every call misses the cache. (§2.3)
- Sliding-window history: breaks the prefix and drops tool results the agent still needs. (§2.3)
- Putting tool results in a `user` message. (§2.3.1)
- Compressing only for length and ignoring context rot. (§2.7.1)
- Flat, unordered rule lists in the system prompt. (§2.4.3)
