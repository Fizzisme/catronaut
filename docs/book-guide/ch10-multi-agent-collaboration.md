# Ch10 — Multi-agent collaboration (and the postscript)

**Book:** [Chương 10 — Nhiều lần cộng tác Agent](../ai-agent-book/ch10-multi-agent-collaboration.md) · PDF pages 376–417 ·
[Postscript](../ai-agent-book/postscript.md) · PDF pages 418–421

## Chapter summary

1. **Two design axes** (§10.1): shared vs isolated context, and topology — peer (2–3 agents
   iterating), manager/orchestrator, decentralised handoff. Isolated agents communicate through tool
   parameters, a shared file system or a message bus.
2. **The one criterion** (§10.2): multi-agent helps only when collaboration brings information a
   single generation could not have — execution results, rendered screenshots, external
   verification. Same-model self-review and debate over the same text add nothing, or hurt, at equal
   compute. Multi-agent runs cost many times the tokens of a chat (around 15×).
3. **Role switching inside one context** (§10.3): prefer skills (static prefix unchanged, `SKILL.md`
   appended at the tail) when roles differ in knowledge or procedure; use a separate agent only when
   roles differ in permissions or side effects, and enforce the tool limit in code.
4. **A virtual file system with four zones** (§10.4.1): private scratchpad, shared workspace (with
   concurrency control), mounted external resources (mostly read-only) and built-in read-only
   resources (skills, templates). Pass paths, not content.
5. **Control plane** (§10.4.2): structured message envelopes; status through a progress file rather
   than full trajectories; stall detection by modification time; graceful then forced cancellation,
   propagated to children; budgets, per-task model choice, concurrency caps.
6. **Loop engineering and Proposer–Reviewer** (§10.4.3): the dominant failure is premature completion
   — a lazy "done", giving up after one path, false success. "Done" is a claim until a verifier
   proves it: the model may propose done but must not approve it. The reviewer reads independent
   evidence (tests, state, screenshots), returns actionable findings and may not edit tests,
   evidence collectors or release gates. Self-correction without external feedback lowers accuracy.
7. **Manager pattern** (§10.4.4): the planner is the bottleneck, so it gets the strongest model and
   prompt; the manager keeps only an index of artifacts; parallel settlement is "first verified
   success", claimed idempotently.
8. **Decentralised handoff** (§10.4.5): a handoff packet carries the goal, constraints, accepted
   facts, artifact references, remaining budget and visited agents; the runtime owns cycle detection
   and budgets.
9. **Failure modes** (§10.5): lost updates on shared files (§10.5.1), error amplification along
   chains (§10.5.2), homogeneous convergence — same model, same mistake (§10.5.3), responsibility
   shifting (§10.5.4), runaway loops (§10.5.5), and comprehension debt for the humans running the
   system (§10.5.6). Agent failures are wrong but plausible, so only deterministic external feedback
   is trustworthy.
10. **Postscript**: Agent = LLM + context + tools. The harness compensates for what the model cannot
    yet do reliably and is removed layer by layer as models internalise those constraints — but each
    new frontier needs a new layer. Keep asking: what does the agent see, what can it do, and how is
    "done correctly" verified?

## Steps to apply

1. **Stay single-agent by default.** Add an agent only when it brings new information (execution
   results, screenshots, external checks), and compare against the single agent at an equal token
   budget. (§10.2)
2. **Decide the context model and topology** — shared or isolated; peer, manager or decentralised.
   (§10.1)
3. **Switch roles with skills** when roles differ in knowledge; split into separate agents only for
   different permissions or side effects, with limits enforced in code. (§10.3)
4. **Lay out the file system in four zones** and pass paths, not content. (§10.4.1)
5. **Build the control plane**: structured envelopes, progress files, stall detection, cancellation
   that propagates to children, explicit budgets and concurrency caps. (§10.4.2)
6. **Make "done" a verified state**: the model proposes, a verifier approves; reviewers read
   independent evidence and cannot edit the gates. (§10.4.3)
7. **If you use a manager**, give it the strongest model and prompt, keep an artifact index, and
   settle parallel work on the first verified success. (§10.4.4)
8. **Standardise handoff packets**: goal, constraints, accepted facts, artifact references, budget,
   visited agents. (§10.4.5)
9. **Guard against the failure modes**: optimistic locking or isolated working copies against lost
   updates, cross-validation from raw evidence against error amplification, diversified sources
   against homogeneous convergence, explicit budgets and cancellation against runaway loops. (§10.5)
10. **Keep humans able to understand the system** — short, current documentation counters
    comprehension debt. (§10.5.6)
11. **Re-check each harness layer as models improve**; remove what the model has internalised.
    (postscript)

## Common pitfalls

- Same-model debate or self-review presented as verification. (§10.2)
- Accepting the model's "done" without independent evidence. (§10.4.3)
- Concurrent writes to a shared workspace without locking. (§10.5.1)
- Adding agents for their own sake and paying many times the tokens. (§10.2)
