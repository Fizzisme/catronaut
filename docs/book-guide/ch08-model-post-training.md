# Ch08 — Model post-training

**Book:** [Chương 8 — Post-training mô hình](../ai-agent-book/ch08-model-post-training.md) · PDF pages 300–354

## Chapter summary

1. **Four stages, four different gaps** (§8.1, §8.7): pre-training and mid-training supply knowledge
   and base capability; SFT fixes protocol (format, tool-call schema, style, procedure) with high
   sample efficiency; RL shifts probability mass toward strategies the model already produces
   occasionally. "SFT memorises, RL generalises" is a tendency seen in controlled experiments, not a
   law (§8.16).
2. **Decide before training** (§8.7):
   1. first rule out fixes that need no weight change — prompt, tools, code constraints, context
      management; use RAG for facts that change;
   2. measure pass@1 and pass@k on held-out target tasks — if pass@k ≈ 0, RL has nothing to amplify
      (mid-train or SFT first);
   3. SFT builds protocol, not knowledge bases;
   4. RL only when rollouts are scorable, occasionally successful, and the reward is faithful.
3. **LoRA defaults** (§8.1, LoRA box): apply LoRA to all major weight matrices, MLP included;
   learning rate ≈ 10× full fine-tuning; SFT rank 64–256, RL rank 8–32; one inference server can host
   many adapters.
4. **SFT data** (§8.5–8.6): human seeds define the format → a teacher model scales → rejection
   sampling keeps only verified trajectories. Pipeline: production data → task blueprint → synthetic
   tasks (personal data regenerated) → multiple candidate trajectories → task and trajectory
   verification → SFT set. Failed trajectories are never positive demonstrations; they become
   preference pairs or coverage probes.
5. **Environments and isolation** (§8.10): environment fidelity matters more than the RL algorithm;
   train and evaluation may share generators and verifiers but never task instances; hidden tests
   and reference answers stay with the verifier. Model-simulated environments are possible, but
   their bias becomes the policy's ceiling.
6. **Multi-turn RL** (§8.11): credit assignment across turns; tool calls bring the environment inside
   the agent.
7. **Reward design** (§8.12): verifiable rewards first; outcome before process; beware reward
   hacking and reward seeking; RLVP — reward the outcome and penalise verifiable path violations
   (e.g. editing tests, bypassing checks).
8. **Distillation** (§8.13): on-policy distillation turns one rollout into dense per-token
   supervision; self-distillation works without a stronger teacher.
9. **From bad case to training** (§8.14): end-to-end regression tasks → RL/RFT pools;
   trajectory-prefix tasks → DPO pairs and SFT boundary demonstrations; failure attribution records
   → process-reward labels and RLVP rules; rubrics → reward vectors. Worked cases: premature
   completion, scope-sensitive quote conversion, exact `old_string` copying (§8.14.1–8.14.3).
10. **Pitfalls** (§8.15): training to memorise facts, RL before the format is stable, bad reward
    functions, low-fidelity simulation, overtraining, underestimating RL compute (10–100× SFT), dirty
    data. Validate assumptions small before spending big.

## Steps to apply

1. **Exhaust non-training fixes first**: prompt, tools, code constraints, context; RAG for changing
   facts. Write down what was tried. (§8.7)
2. **Measure pass@1 and pass@k on held-out tasks** and let them pick the stage: mid-training when
   pass@k ≈ 0, SFT when the format is unstable, RL when rollouts are scorable and sometimes succeed.
   (§8.7, §8.16)
3. **Use SFT for protocol**, not for knowledge. (§8.5)
4. **Start from the LoRA defaults**: all major matrices including MLP, LR ≈ 10× full fine-tuning,
   rank 64–256 for SFT and 8–32 for RL, early stopping on a held-out set. (§8.1)
5. **Build SFT data from verified trajectories only**: seeds → teacher → rejection sampling through
   the same verifiers the evaluation uses; failures become preference pairs, never positives.
   (§8.5–8.6)
6. **Split train and evaluation by task template**; never share instances; keep hidden tests with the
   verifier. (§8.10.3)
7. **Invest in environment fidelity** before tuning algorithms. (§8.10.1–8.10.2)
8. **Design rewards carefully**: verifiable, outcome first, with path-violation penalties (RLVP).
   (§8.12)
9. **Map evaluation assets to training uses**: regressions, prefix tasks, attribution records and
   rubrics each have a training role. (§8.14)
10. **Attribute layer by layer before calling it a model problem**: tool output → harness
    serialisation → tokenizer → model output. (§8.14.3)
11. **Evaluate every trained model on boundary and retention sets**, plus a general-capability
    check. (§8.14.1)
12. **Consider distillation** to improve sample efficiency. (§8.13)
13. **Validate small before spending big.** (§8.15)

## Common pitfalls

- Training to memorise facts that belong in retrieval. (§8.15)
- Running RL before the output format is stable. (§8.7, §8.15)
- Treating failed trajectories as positive examples. (§8.6)
- Letting train and evaluation share task instances. (§8.10.3)
- Underestimating RL compute. (§8.15)
