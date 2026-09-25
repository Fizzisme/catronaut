# Ch03 — User memory and knowledge base

**Book:** [Chương 3 — Bộ nhớ người dùng và cơ sở kiến thức](../ai-agent-book/ch03-memory-and-knowledge-base.md) · PDF pages 104–143

## Chapter summary

1. **Two scales of persistent knowledge**: user memory (one person, across sessions) and a shared
   knowledge base (everyone). Same machinery, same failure modes: conflicts, stale facts, imprecise
   retrieval. (§3.1, §3.4)
2. **Memory hierarchy** (§3.1.2): the trajectory (an append-only record of one session), long-term
   memory (rewritten, merged, pruned) and business state (a developer-defined task phase such as
   "needs clarification / in progress / done") are different things.
3. **Four storage formats** (§3.1.3), from cheap to rich: simple notes, advanced notes, JSON cards,
   advanced JSON cards. Rich cards suit small, critical facts; simple notes suit bulk. User-as-Code
   (§3.1.4) goes further: typed state plus deterministic rule functions for counting, conflict
   detection and constraint checks.
4. **Evaluate memory before designing it** (§3.1.1): three levels — basic recall, cross-session
   retrieval, proactive service — scored on a fixed case set.
5. **RAG fundamentals** (§3.2): structure-aware chunking is the production default (start at
   256–1024 tokens with 10–20% overlap, then tune on measured retrieval quality); dense multilingual
   embeddings plus sparse BM25; hybrid retrieval → RRF fusion → cross-encoder rerank; metrics
   recall@k, MRR, nDCG.
6. **Raw case collections are not knowledge** (§3.3). Top-k over many individual cases cannot count
   them, and no single case states a policy boundary. Distil at index time into rule cards that
   state scope and exclusions.
7. **Structured indexing** (RAPTOR, GraphRAG; §3.3.1) only when queries need multi-document synthesis
   or multi-level navigation; otherwise hybrid retrieval is enough.
8. **File-system paradigm** (§3.3.2): knowledge as Markdown files in Git, with an L0 abstract (~100
   tokens), an L1 overview (~2K) and the L2 full text loaded on demand, plus explicit cross-links and
   index pages.
9. **Knowledge updates** (§3.3.3) are pull requests: a proposer drafts the minimal diff with
   evidence, an independent reviewer checks it against raw evidence, CI validates, and only the
   merged version rebuilds the derived index. Evidence, knowledge and serving are separate layers;
   superseded content is marked; permissions are filtered at retrieval; tenants are isolated.
10. **Agentic RAG** (§3.3.4): retrieval as a tool inside the loop beats one-shot retrieval on complex
    questions; one-shot stays faster and as good on simple ones. Retrieved text carries indirect
    prompt injection — tag its source and never let it trigger side effects.
11. **Contextual retrieval** (§3.3.5): prefix each chunk with an LLM-written context line before
    embedding (−49% failures with BM25, −67% with reranking).
12. **Two-layer memory** (§3.3.5, §3.4): a small structured overview always in context, plus precise
    on-demand retrieval of details.

## Steps to apply

1. **Separate the three kinds of state.** Keep the trajectory append-only, keep long-term memory
   curated, and store business state (task phase, decisions, answers already given) beside the work
   — not only in chat text. (§3.1.2)
2. **Write the memory evaluation first**: recall, cross-session retrieval and proactive service on a
   fixed case set. (§3.1.1)
3. **Choose the storage format by criticality**: rich cards for small critical facts, simple notes
   for bulk, typed state with rule functions when counting or conflicts matter. (§3.1.3–3.1.4)
4. **Start knowledge as a file system.** Markdown in Git with ~100-token abstracts, overviews, full
   text on demand, cross-links and one index page per folder, read through ordinary file tools.
   (§3.3.2)
5. **Distil, don't dump.** Turn case collections into rule cards with explicit scope and
   exclusions before they are retrievable; keep the raw cases as evidence. (§3.3)
6. **When RAG is needed, follow the pipeline**: structure-aware chunks of 256–1024 tokens with
   10–20% overlap, dense + BM25, RRF, cross-encoder rerank, measured with recall@k, MRR and nDCG on
   a fixed query set. (§3.2.1–3.2.4)
7. **Add contextual-retrieval prefixes** to chunks. (§3.3.5)
8. **Expose retrieval as a tool** for complex questions, keep one-shot retrieval for simple ones,
   and tag retrieved text as untrusted. (§3.3.4)
9. **Keep a small structured overview in context** and fetch details on demand. (§3.3.5, §3.4)
10. **Treat knowledge changes as pull requests** with evidence and an independent review; rebuild
    derived indexes only from merged content; mark superseded entries. (§3.3.3)
11. **Enforce permissions at the retrieval layer**, isolate tenants, and scrub personal data from
    logs. (§3.3.3, §3.1.8)
12. **Reach for RAPTOR or GraphRAG only** when queries genuinely need multi-document synthesis.
    (§3.3.1)

## Common pitfalls

- Indexing raw cases and expecting the retriever to count or generalise. (§3.3)
- Writing memory without checking source, time, conflicts and privacy. (§3.4)
- Keeping business state only in the chat history, so it is lost or contradicted. (§3.1.2)
- Letting retrieved text trigger side-effecting actions. (§3.3.4)
