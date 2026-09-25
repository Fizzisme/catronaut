# Ch09 — Continuous agent evolution

**Book:** [Chương 9 — Sự tiến hóa liên tục của Agent](../ai-agent-book/ch09-continuous-agent-evolution.md) · PDF pages 355–375

## Chapter summary

1. **Storing experience is not learning from it** (chapter introduction). Learning happens only after
   the system evaluates, compares across trajectories, generalises and verifies. Production feedback
   is not a clean signal: satisfaction is not compliance. Today's practical path is a verifiable
   learning system built around the model (§9.4).
2. **Evaluate before summarising** (§9.1): three verifier layers — outcome (tests, database state),
   process (rules, permissions, action chain) and quality (a rubric with evidence and stated
   uncertainty). The lower the layer, the more it should rely on code and ground truth.
3. **Four carriers for an update**, chosen by how the capability is best represented (§9.2):
   - **knowledge documents** — facts, rules of thumb, exceptions, sources: raw trajectory →
     per-run analysis → cross-trajectory generalisation; a rule needs at least two supporting,
     non-failed trajectories and must transfer to disjoint tasks (§9.2.1);
   - **prompts and skills** — verbalisable judgement, updated as a minimal diff with provenance and
     tested on the boundary set that failed and the retention set that worked (§9.2.2);
   - **programs and harness** — deterministic procedures and hard constraints with pre-action,
     post-action and final-state checks; a `candidate → validated → invalid` lifecycle; every change
     a falsifiable change contract (§9.2.3);
   - **parameters** — perception, style, implicit strategy (§9.2.4, see ch08).
   One capability often spans several carriers.
4. **Worked example — a requirement-clarification skill** (§9.2.2.2) must balance under-asking
   (rework) against over-asking (interrogation). Compare "execute directly", "ask then execute" and
   "ask, confirm a short spec, then execute", stratified by risk and ambiguity. Metrics: requirement
   drift, post-delivery rework, clarification rounds, time to first useful output, abandonment, spec
   edit rate. The skill owns asking and explaining; the harness owns vetoing high-risk writes without
   confirmation.
5. **Two loops** (§9.3): online execution only records evidence; offline evolution aggregates,
   diagnoses, proposes candidates and releases after verification. Separate harness updating (was a
   good change proposed?) from harness benefit (did the agent load and follow it?).
6. **Limits of the verifiable loop** (§9.3.1): in open-ended work, keep negative results, separate
   claims from evidence, preserve search diversity, and keep humans on problem definition and
   evaluation criteria.
7. **Safety boundaries** (§9.3.2): untrusted evidence is never written straight into instructions;
   candidates never serve real traffic before verification; an agent must not modify its own
   verifiers, tests, release thresholds, audit logs or the stable copy that approves it.
8. **Offline consolidation — "sleep learning"** (§9.3.3): trigger, orient, gather and merge, verify,
   prune and re-index; expire rules contradicted by new evidence; keep the global prompt small by
   moving local rules into domain skills.

## Steps to apply

1. **Verify runs before learning from them**, in three layers: outcome, process, quality. (§9.1)
2. **Pick the carrier by the nature of the capability** — knowledge, prompt/skill, program/harness
   or parameters — and expect some changes to span several. (§9.2)
3. **Promote a rule to knowledge only with evidence**: at least two supporting non-failed
   trajectories, and it must transfer to disjoint tasks. (§9.2.1)
4. **Change prompts and skills as minimal diffs with provenance**, tested on the boundary set that
   failed and the retention set that worked. (§9.2.2)
5. **Evaluate the clarification policy explicitly**: compare direct execution, ask-then-execute and
   ask-confirm-execute by ambiguity and risk, with drift, rework and round-count metrics; let the
   skill ask and the harness veto. (§9.2.2.2)
6. **Write a falsifiable change contract for every harness change**: evidence, suspected root cause,
   component, predicted effect, possible regressions, tests for both. (§9.2.3)
7. **Separate the online loop from the offline loop**, and measure both whether good changes are
   proposed and whether they are loaded and followed (activation and compliance). (§9.3)
8. **Protect the trust roots**: nothing automated may edit verifiers, tests, thresholds, audit logs
   or the approving copy; candidates stay off real traffic until verified. (§9.3.2)
9. **Consolidate periodically**: merge, verify, prune, re-index, expire contradicted rules, move local
   rules into domain skills. (§9.3.3)
10. **Keep humans on problem definition and evaluation criteria** for open-ended tasks. (§9.3.1)

## Common pitfalls

- Treating user satisfaction or approval as a clean learning signal. (chapter introduction, §9.1)
- Turning one success into a rule. (§9.2.1)
- Writing untrusted evidence straight into instructions. (§9.3.2)
- Letting the system that is being improved edit its own verifiers. (§9.3.2)
