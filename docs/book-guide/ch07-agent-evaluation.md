# Ch07 — Agent evaluation

**Book:** [Chương 7 — Đánh giá Agent](../ai-agent-book/ch07-agent-evaluation.md) · PDF pages 254–299

## Chapter summary

1. **The thing under evaluation is model + harness** (§7.1). A model-swap test (same harness, a
   stronger or weaker model) separates harness bottlenecks from model bottlenecks; an ablation (same
   model, one harness component switched off) measures what a component is worth. An evaluation suite
   is what lets a team adopt a new model in hours instead of by intuition.
2. **Metrics** (§7.2):
   - Pass@k (at least one of k succeeds) measures the capability ceiling; Pass^k (all k succeed, no
     veto) measures business reliability — at p = 0.6, Pass@5 ≈ 99% but Pass^5 ≈ 7.8% (§7.2.1–7.2.2);
   - process metrics: legal-action rate, tool-call accuracy, path efficiency, retrieval coverage,
     cost and latency (§7.2.3);
   - safety and compliance as veto items, robustness, and coverage of both trajectory and outcome —
     "the agent said it booked" is not "the booking exists" (§7.2.4);
   - human spot checks and judge calibration on a gold set (e.g. Cohen's κ > 0.7) before trusting an
     LLM judge at scale; adversarial cases (§7.2.5).
3. **The evaluation environment** (§7.3) is dataset + resettable environment state + atomic tools +
   rubric + execution protocol. Tool-type environments verify by execution and state; human
   interaction environments use a user simulator with progressive disclosure and finite patience.
4. **Dataset design** (§7.4): clarity vs openness, realism vs control, diversity with capability
   tags, cost vs coverage, contamination defence (parameterised templates, canaries, freshness);
   precise task descriptions with machine-checkable success conditions; difficulty tiers; trap
   tasks; FAIL_TO_PASS + PASS_TO_PASS double verification; heavy quality control.
5. **LLM-as-a-judge** (§7.5.1) with rubrics that are expert-grounded, comprehensive, weighted
   (essential / important / optional / veto) and independently checkable. Guard against length bias,
   position bias and reward hacking; prefer judges from several model families; multimodal judges
   extend to UI screenshots.
6. **Failure attribution** (§7.5.2): for every failed trajectory, record the first unacceptable step,
   error class, root cause vs consequences, recoverability and confidence. A starter taxonomy for
   coding agents includes requirement misunderstanding, missing process, tool-call error,
   verification hacking, incomplete change, misreporting to the user, non-functional regression,
   abnormal termination and premature stop. Rule-based pre-filters first, LLM localisation second.
7. **Regression tasks** (§7.5.3): end-to-end tasks guard whole flows; trajectory-prefix tasks freeze
   the state just before a known first error and accept a set of acceptable next actions (and a set
   of forbidden ones). Pairwise comparison ranks systems (§7.5.4).
8. **Model selection** (§7.6): TTFT vs decode speed, thinking latency, p95 tail, cost per task, Pass
   metrics and budget–capability curves; measure the model's default action threshold (read more vs
   edit early); measure cost levers in combination — savings do not add up.
9. **Statistics** (§7.7): SE ≈ √(p(1−p)/n) — at n = 100, 70% ± 9 points; paired analysis (McNemar,
   paired bootstrap), multiple seeds, correction for multiple comparisons.
10. **Observability** (§7.8): traces as span trees; production failures, anonymised, flow back into
    the evaluation set.
11. **From report to improvement** (§7.9): when scores move, check the evaluation system first;
    change one variable per round; a win on a small subset only earns a larger run.
12. **Internal evaluation infrastructure** (§7.10): every major feature independently switchable for
    ablation; A/B tests that separate mechanism metrics from goal metrics and keep guardrail
    metrics; the rendered system prompt snapshotted per version, with the suite re-run on every
    prompt change.
13. **Simulation environments** (§7.11) bridge evaluation and training: verifiers become reward
    functions, but training adds reset semantics and throughput requirements.

## Steps to apply

1. **Evaluate model and harness together**, and run model-swap tests and ablations to locate
   bottlenecks. (§7.1, §7.10.1)
2. **Report Pass@k for the ceiling and Pass^k for reliability**, with process metrics, cost and
   latency; make safety violations veto items; verify the outcome state, not only the trajectory.
   (§7.2.1–7.2.4)
3. **Calibrate every LLM judge** against human labels before relying on it; add adversarial cases.
   (§7.2.5, §7.5.1)
4. **Build a resettable environment**: dataset, state, atomic tools, rubric, execution protocol; add
   a user simulator for tasks that involve asking the user. (§7.3.1–7.3.3)
5. **Design the dataset**: machine-checkable success conditions, difficulty tiers, trap tasks,
   contamination defences, FAIL_TO_PASS and PASS_TO_PASS checks. (§7.4)
6. **Write weighted rubrics with veto items**, and guard against length and position bias; use
   multimodal judges for visual output. (§7.5.1)
7. **Record a failure attribution for every failed run**: first bad step, class, root cause,
   evidence. (§7.5.2)
8. **Turn failures into regression tasks**, both end-to-end and trajectory-prefix. (§7.5.3)
9. **Choose models by cost per task and budget–capability curves**, not a single score; measure cost
   levers together. (§7.6)
10. **State n, seeds and confidence intervals**, and use paired tests. (§7.7)
11. **Trace runs as span trees** and feed production failures back into the suite. (§7.8)
12. **When a score changes, check the evaluation system first**, then change one variable at a time.
    (§7.9)
13. **Make every major harness feature switchable**, snapshot the rendered system prompt per version,
    and re-run the suite on every prompt change. (§7.10)
14. **Treat verifiers as future reward functions** when designing environments. (§7.11)

## Common pitfalls

- Claims from single runs (n = 1) presented as facts. (§7.7)
- Summing cost savings from separate levers. (§7.6)
- Trusting an uncalibrated judge. (§7.2.5)
- Accepting "the agent said it did it" without checking the resulting state. (§7.2.4)
- A benchmark drop blamed on the agent when the evaluation system changed. (§7.9)
