# Book guide — *Hiểu sâu về AI Agent*

Per-chapter summaries of what the book recommends, turned into steps for building an agent harness,
with section (§) references into the book. The book itself (Vietnamese) is in
[docs/ai-agent-book/](../ai-agent-book/README.md). Where a guide and the book disagree, the book wins.

Each guide has three parts:

- **Chapter summary** — the chapter's argument, condensed, with § references.
- **Steps to apply** — a numbered checklist: what to do, why, and where the book covers it.
- **Common pitfalls** — what the chapter warns against.

The guides are project-agnostic. [ROADMAP.md](../../ROADMAP.md) links each milestone to the chapters
it draws on.

| Chapter | Guide | Main steps |
|---|---|---|
| 1 Getting started | [ch01](ch01-getting-started.md) | Treat the harness as the product; a ReAct loop with explicit exits; prompt → workflow → autonomy; three guardrail layers |
| 2 Context engineering | [ch02](ch02-context-engineering.md) | Stable prefix, dynamic tail; SOP-style system prompt; skills by progressive disclosure; status bar; layered compaction |
| 3 Memory and knowledge base | [ch03](ch03-memory-and-knowledge-base.md) | Separate trajectory, memory and business state; file-system knowledge before RAG; distil cases into rules; reviewed updates |
| 4 Tools | [ch04](ch04-tools.md) | Choose the form of a capability; full descriptions; parameter fidelity; explicit truncation; defence in depth for execution |
| 5 Coding agents | [ch05](ch05-coding-agents-and-code-generation.md) | Read/write/edit/glob/grep; exact-match edits; failure taxonomy and tiered recovery; start from vetted examples; render and review |
| 6 Interaction | [ch06](ch06-interaction-observation-and-action-spaces.md) | Structured events; safe points and cancellation; async tool semantics; judge completion by a fresh observation |
| 7 Evaluation | [ch07](ch07-agent-evaluation.md) | Evaluate model + harness; Pass^k and veto items; calibrated judges; failure attribution; statistics; feature switches |
| 8 Post-training | [ch08](ch08-model-post-training.md) | Rule out non-training fixes; SFT for protocol, RL for policy; verified data only; LoRA defaults; reward design |
| 9 Continuous evolution | [ch09](ch09-continuous-agent-evolution.md) | Evaluate before summarising; pick the right carrier; boundary and retention sets; offline evolution loop; protected trust roots |
| 10 Multi-agent + postscript | [ch10](ch10-multi-agent-collaboration.md) | Add agents only for new information; done is verified; structured handoffs; guard against conflicts and homogeneous failure |

## Finding a section in the book

The Markdown conversion of the book lost a few headings. Some sections appear as bold lines rather
than headings (for example §2.4.1–2.4.4, §2.3.5, §8.1.3, §9.2.2.2, §9.3.1), and §6.3 and §8.3 have
no heading line of their own. Search the chapter file for the section number. The PDF is
authoritative when the conversion looks wrong.
