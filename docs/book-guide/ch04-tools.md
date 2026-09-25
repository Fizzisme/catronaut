# Ch04 — Tools

**Book:** [Chương 4 — Công cụ](../ai-agent-book/ch04-tools.md) · PDF pages 144–169

## Chapter summary

1. **Five tool classes** (§4.1): perception, execution and collaboration tools, which the agent calls
   itself; user-communication and event-trigger tools, which are event-driven and covered in ch06.
2. **The form of a capability** (§4.2.1) is a spectrum from a specialised tool (structured,
   testable, hundreds of tokens each) to a general executor plus a skill (few tools, natural-language
   procedures). Default to general, except for security and permissions, platform differences, very
   high call frequency or complex parameters. Consolidate similar tools. Form (cost per capability)
   and exposure (how many at once) are independent decisions.
3. **Tool descriptions** (§4.2.2) say when to use the tool, state what it cannot do, give concrete
   parameter examples, describe the return shape, mention cost, and include 1–5 example calls —
   reported to lift call accuracy from ~72% to ~90%. When the agent picks the wrong tool, fix the
   description before blaming the model.
4. **Parameter fidelity** (§4.2.3): never silently transform inputs or inject parameters the model
   cannot see. Any normalisation is documented and reported back.
5. **Ecosystem** (§4.3): MCP standardises specialised tools; skill hubs distribute `SKILL.md` folders.
   Both are supply-chain risks — description poisoning, compromised updates, tool shadowing —
   mitigated by review, version pinning and least-privilege credentials.
6. **Too many tools** (§4.4): hierarchical grouping, on-demand loading, retrieval pre-filtering,
   active discovery and skills. Loaded schemas are appended at the tail and then pinned.
7. **Perception tools** (§4.5): structured candidate lists with pagination; reads with
   `offset`/`limit`; truncation must say how much was omitted and how to read the rest, or the agent
   believes it saw everything. Read-only tools are safe to cache and to run in parallel. Multimodal
   perception (§4.5.1) is native, extract-to-text, or a tool-based analyser such as
   `analyze_image(file, question) -> text` that keeps pixels out of the main context.
8. **Execution tools need defence in depth** (§4.6): fail-fast input validation with no "smart
   repair"; permission control; Proposer–Reviewer pre-approval for irreversible, high-impact actions
   and post-verification by switching modality (render and inspect, run in a sandbox); a sidecar
   classifier that sees only the structured call; verify-after-write that returns structured errors;
   head + tail output with the full output saved; a sandbox strength ladder; per-call observability;
   idempotency and cancellation semantics.
9. **Collaboration tools** (§4.7): `spawn`, `send`, `cancel` and `list` primitives; sub-agent
   prompts label every input source, state boundaries and fix the output format; human-in-the-loop
   needs timeouts, a default action and a feedback loop.

## Steps to apply

1. **Classify every capability** as perception, execution or collaboration, and note which ones are
   event-driven. (§4.1)
2. **Choose the form deliberately.** Default to a general executor plus skills; build a specialised
   tool for security and permissions, platform differences, very high frequency or complex
   parameters; merge near-duplicates. Decide exposure separately. (§4.2.1)
3. **Write descriptions to a template**: when to use, what it cannot do, concrete parameter examples,
   return shape, cost, 1–5 example calls. (§4.2.2)
4. **Guarantee parameter fidelity.** Tools do exactly what the visible arguments say; any
   normalisation is documented and echoed back; test it with fixtures such as curly quotes and
   non-ASCII text. (§4.2.3)
5. **Treat MCP servers and imported skills as supply chain**: review descriptions and bodies, pin
   versions, give least-privilege credentials. (§4.3)
6. **Plan for growth in tool count**: group hierarchically, load on demand (append at the tail, then
   pin), pre-filter by retrieval, or move procedures into skills. (§4.4.1–4.4.2)
7. **Design perception tools for partial views**: pagination, `offset`/`limit`, and truncation that
   states what was cut and how to read it. Mark read-only tools so they can be cached and
   parallelised. (§4.5)
8. **Pick a multimodal strategy**: native input, extraction to text, or a tool-based analyser that
   returns text. (§4.5.1)
9. **Layer the defences on execution tools**: fail-fast validation, permissions, pre-approval for
   irreversible actions, post-verification by a different modality, verify-after-write with
   structured errors, saved full output, per-call logs, idempotency keys and explicit cancellation.
   (§4.6)
10. **Standardise collaboration**: lifecycle primitives for sub-agents, labelled input sources, fixed
    output formats, and human approval with timeouts and a default. (§4.7)

## Common pitfalls

- Silent truncation, which makes the agent believe it has seen everything. (§4.5)
- "Smart repair" of invalid input instead of failing fast. (§4.6)
- Silently rewriting arguments (the curly-quote class of bug). (§4.2.3)
- Trusting third-party tool descriptions without review. (§4.3)
- One-line descriptions that leave the model guessing when to use a tool. (§4.2.2)
