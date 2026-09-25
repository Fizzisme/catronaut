# Ch01 — Getting started: Agent = Model + Harness

**Book:** [Chương 1 — AI Agent Bắt đầu](../ai-agent-book/ch01-getting-started.md) · PDF pages 20–51

## Chapter summary

1. **Agent = LLM + context + tools** — brain, eyes, hands and feet; all three are required (§1.1,
   §1.4). In production terms **Agent = Model + Harness**, and the harness is context management,
   the tool interface, constraints, verification and correction (§1.2). Most production harness code
   implements the guarantees — constraints, verification, correction — not just context and tools
   (§1.4).
2. **With the model fixed, the main lever is the observation and action space** (§1.1.1). Many
   "we need a smarter model" problems are interface problems: put the missing data in context, or
   expose the missing operation as a tool. Expand on demand, with access control and verification.
3. **Tool design rule** (§1.1.2): general-purpose capabilities for composition and exploration;
   narrow, audited tools for high-risk operations (payment, deletion, deployment). A long-running
   agent gets a controlled virtual working directory limited by path, size and file type — never the
   host filesystem.
4. **Context = static prefix + trajectory** (§1.1.4–1.1.5). The static prefix is the system prompt
   and tool definitions; the trajectory is user, assistant and tool messages. Ablations show that
   without tool results the agent retries blindly until the budget runs out, and without tool
   definitions it confidently fabricates. "Produced an answer" is not "completed the task".
5. **ReAct loop** (§1.1.5): think → act → observe. Independent calls in one turn may run in
   parallel. Exits: a final-answer tool, a response with no tool call, an unrecoverable error, or
   the iteration cap.
6. **From prompt engineering to loop engineering** (§1.2.1). Harness code that patches a model
   weakness (few-shot tricks, JSON repair, prompt rewriting) is gradually absorbed by better models
   (§1.2.4.1).
7. **Three principles** (§1.2.2): keep it simple; be transparent (plans, logs, decision trace);
   design the agent–computer interface so misuse is impossible (poka-yoke).
8. **Model selection** (§1.2.3): evaluate on your own tasks; reasoning models for multi-step work;
   output speed matters because it multiplies by the number of rounds; multimodality when the task
   needs it.
9. **Orchestration** (§1.2.4): prompt → workflow → autonomous agent, in that order of adoption, and
   mixed — deterministic nodes for compliance-critical steps, autonomy where paths are open.
10. **Guardrails in three layers, ordered by how hard they are to bypass** (§1.2.5): the context
    layer (relevance and safety classification, prompt-injection detection, source labelling), the
    execution layer (per-tool risk rating, human approval outside the model's context, output
    checks) and the data layer (enforcement that does not depend on the model). Measure false
    refusals as well as blocked attacks.
11. **Human in the loop** (§1.2.5.2): escalate when a failure threshold is crossed or before a
    high-risk operation.
12. **Five recurring design patterns** (§1.3): Proposer–Reviewer (a separate context judges the
    artifact), progressive disclosure, append-only, boundary set + retention set, minimal diff +
    reversible.

## Steps to apply

1. **Give each harness responsibility an owner.** Context, tools, constraints, verification and
   correction each get a module; verification and correction are first-class, not afterthoughts.
   (§1.2, §1.4)
2. **Diagnose the interface before blaming the model.** When the agent fails, ask whether data is
   missing (add it to context) or an operation is missing (add a tool). (§1.1.1)
3. **Give the agent a controlled workspace.** Limit it by path, file size, file count and file type;
   never expose the host filesystem. (§1.1.2)
4. **Build the ReAct loop with explicit exits.** Handle every tool call in a turn, run independent
   read-only calls in parallel, and stop on a final answer, an unrecoverable error or the iteration
   cap. (§1.1.5)
5. **Define terminal states for a run** — for example done, needs input, stopped at limit, failed —
   so a caller never mistakes "produced an answer" for "completed the task". (§1.1.4–1.1.5)
6. **Adopt autonomy in order.** Optimise the prompt first, then add workflow nodes, then autonomy;
   keep compliance-critical steps deterministic. (§1.2.4, §1.2.4.1)
7. **Label adapter-layer code.** Mark code that only patches a model weakness so it can be removed
   when the model internalises the behaviour. (§1.2.4.1)
8. **Keep it simple and transparent.** Log plans and a per-iteration decision trace; shape tools so
   that misuse is impossible rather than merely discouraged. (§1.2.2)
9. **Choose the model on your own tasks.** Measure multi-step success, output speed × rounds, and
   multimodality where required. (§1.2.3)
10. **Put guardrails in three layers.** Label and screen what enters context; rate tool risk and keep
    approval outside the model's context; enforce data rules in code that the model cannot bypass.
    Track false refusals too. (§1.2.5)
11. **Escalate to a human** after repeated failures or before a high-risk operation. (§1.2.5.2)
12. **Use the five patterns as shared vocabulary** in design documents, so later designs reference
    them instead of re-deriving them. (§1.3)

## Common pitfalls

- Treating a confident answer as task completion. (§1.1.4–1.1.5)
- Letting the same context that produced an artifact also approve it — self-review is unreliable.
  (§1.3)
- Jumping to an autonomous agent when a workflow would do. (§1.2.4)
- Bolting security on before release instead of designing it in from the first line. (§1.4)
