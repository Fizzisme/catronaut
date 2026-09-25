# Qwen3.8-27B — Model Reference

Source: official Hugging Face model card (Qwen team, August 2026).

## Overview

Qwen3.8 is the newest generation in the Qwen open-model family, built on the architectural
foundation of Qwen3.5. It delivers improvements across coding, professional work, research,
and long-horizon agentic tasks. Qwen3.8-27B is a compact, deployment-friendly dense model in
this generation: a native vision-language model that understands images and video, with
flexible thinking control, designed for reliable completion of complex multi-step tasks.

**Highlights:**
- **Core capabilities**: broad improvements across coding, professional work, research, and long-horizon agentic tasks.
- **Agent execution**: stronger autonomous planning and better handling of environment feedback, for more reliable end-to-end task completion.
- **Downstream compatibility**: broader support for popular harnesses and development tools.
- **Flexible thinking control**: thinking mode on by default, can be disabled per request; reasoning depth tunable via `reasoning_effort`; reasoning context from prior messages retained via `preserve_thinking`.
- **Vision-language understanding**: native image and video understanding, from STEM diagrams and documents to hour-scale video.

## Availability

- Weights distributed in Hugging Face Transformers format, compatible with HF Transformers, vLLM, SGLang, and TokenSpeed.
- A managed hosted version ("Qwen Cloud") is announced but not yet available — planned to include 1M context by default and official built-in tools.

## Model specification

| Field | Value |
|---|---|
| Type | Causal language model with vision encoder |
| Training stage | Pre-training & post-training |
| Parameters | 27B |
| Hidden dimension | 5,120 |
| Token embedding | 248,320 (padded) |
| Layers | 64 |
| Hidden layout | 16 × (3 × (Gated DeltaNet → FFN) → 1 × (Gated Attention → FFN)) |
| Gated DeltaNet | 48 attention heads for V, 16 for QK; head dimension 128 |
| Gated Attention | 24 attention heads for Q, 4 for KV; head dimension 256; RoPE dimension 64 |
| Feed-forward network | intermediate dimension 17,408 |
| LM output | 248,320 (padded) |
| MTP (multi-token prediction) | trained with multiple steps |
| Context length | 262,144 native, extensible to 1,000,000 tokens |

## Benchmark results

### Text Performance

| Category | Benchmark | Qwen3.8-27B | Qwen3.6-27B | Qwen3.7-Plus | Muse Glimmer-30B | Opus4.6 Max |
|---|---|---|---|---|---|---|
| Coding | Agentic terminal coding (Terminal Bench 2.1, Terminus) | 73.0 | 63.4 | 64.0 | 51.7 | 78.2 |
| Coding | Agentic coding (SWE-bench Pro) | 61.7 | 53.5 | 57.6 | 51.2 | 53.4 |
| Coding | Repo-level code generation (NL2Repo-Bench) | 42.3 | 36.2 | 41.1 | -- | 47.6 |
| Coding | Agentic coding (DeepSWE 1.1) | 42.2 | 13.3 | 14.2 | -- | -- |
| Coding | Software engineering (QwenSWEBench) | 79.0 | 49.3 | 59.2 | -- | 63.8 |
| Agent | Long-horizon office work (CoWorkBench) | 70.7 | 61.0 | 65.1 | -- | 68.2 |
| Agent | Professional job tasks (JobBench) | 33.4 | 21.8 | 27.6 | -- | -- |
| Agent | Frontier agentic tasks (Agents' Last Exam) — Pass@1 / Score | 20.4 / 42.9 | 10.6 / 27.3 | 13.2 / 33.6 | -- | -- |
| General | Instruction following (IFBench) | 79.5 | 69.1 | 79.1 | 77.0 | 62.5 |
| General | Scientific reasoning (GPQA Diamond) | 89.2 | 87.8 | 90.3 | 83.5 | 91.3 |
| General | Multidisciplinary reasoning (HLE) | 30.8 | 24.0 | 34.7 | 22.0 | 40.0 |
| General | Competitive coding (LiveCodeBench v6) | 90.3 | 83.9 | 89.6 | -- | 88.8 |

**Evaluation notes:**
- SWE-bench Pro: except for Opus4.6 Max (officially reported score), all models evaluated with the Claude Code harness at temp=1.0, top_p=0.95, 256K context window. Problematic tasks were corrected and all baselines re-evaluated on the refined benchmark.
- NL2Repo-Bench: evaluated with the Claude Code harness; Bash commands that would access the specific repository (pip download, pip install, git clone) are disabled to prevent reward hacking.
- DeepSWE 1.1: evaluated with the Claude Code harness at temp=1.0, top_p=0.95, 256K context window.
- QwenSWEBench: in-house benchmark for software engineering capability, evaluated with the Claude Code harness, reporting avg@3 with an 8-hour timeout, max_tokens=32,768, temperature=1.0, 256K context window.
- CoWorkBench: in-house benchmark for long-horizon tasks across computer science, finance, law, medical, and other productivity domains.
- HLE judged by GPT-4o.
- Best result in each row is bolded in the original table. Empty cells (`--`) mean results are not yet available or not applicable.

### VL Performance

| Category | Benchmark | Qwen3.8-27B | Qwen3.6-27B | Qwen3.7-Plus | Muse Glimmer-30B | Opus4.6 Max |
|---|---|---|---|---|---|---|
| Agentic Multimodal | Computer use (OSWorld-Verified) | 84.3 | 63.9 | 73.3 | 65.9 | 72.7 |
| Agentic Multimodal | Browser use (WebArena-Verified) | 64.8 | 48.8 | 55.3 | -- | -- |
| Agentic Multimodal | Mobile use (AndroidWorld) | 81.9 | 70.3 | 81.0 | -- | 62.0 |
| Agentic Multimodal | Application recreation (RecreationBench) | 47.1 | 29.8 | 30.2 | -- | -- |
| Agentic Multimodal | Multimodal tool use (ClawEval-MM) — Pass@3 / Average | 57.4 / 56.9 | 42.6 / 50.4 | 57.4 / 60.1 | -- | 52.5 / 54.7 |
| Agentic Multimodal | Multimodal software engineering (SWE-MM) | 38.6 | 25.7 | 30.0 | -- | 27.1 |
| Agentic Multimodal | Visual web development (Vision2Web) | 62.9 | 45.0 | 42.1 | -- | -- |
| General Multimodal | Visual math (MathVision) — Without CI / With CI | 90.0 / 94.6 | 85.1 / -- | 90.3 / -- | -- | 65.5 / -- |
| General Multimodal | General visual reasoning (BabyVision) — Without CI / With CI | 65.7 / 85.6 | 28.9 / -- | 64.7 / 70.4 | -- | 12.6 / -- |
| General Multimodal | Scientific chart analysis (CharXiv RQ) — Without CI / With CI | 83.7 / 90.2 | 85.8 / -- | 78.4 / 85.9 | 78.8 | 66.0 / -- |
| General Multimodal | Document intelligence (OmniDocBench 1.5) | 91.1 | 89.4 | 91.4 | 75.8 | 86.6 |
| General Multimodal | Real-world perception (RealWorldQA) | 85.9 | 84.1 | 86.9 | -- | 73.9 |
| General Multimodal | Embodied intelligence (ERQA) | 65.5 | 62.5 | 69.8 | -- | 40.8 |

**Evaluation notes:**
- Where both "Without CI" and "With CI" settings are available, both are reported; otherwise only the available setting is shown. A small number of incorrect ground-truth annotations in MathVision and CharXiv (RQ) were corrected after manual verification; reported scores use the corrected annotations.
- MathVision: Qwen3.8-27B evaluated with the fixed prompt "Please reason step by step, and put your final answer within \boxed{}." For other models, the higher score of two prompt variants (with/without the `\boxed{}` requirement) is reported.
- WebArena-Verified: scored with the official WebArena-Verified grader under the OSWorld scaffold.
- RecreationBench: in-house, long-horizon application-recreation benchmark evaluating hybrid-agent capability across five platforms — desktop (Ubuntu, macOS, Windows), mobile (Android), and web.
- ClawEval-MM: reported as Pass@3 / average score. Pass@3 is the percentage of tasks passed in at least one of three trials; average score is the mean across the three trials.
- Vision2Web: scores averaged across frontend, webpage, and website categories; evaluated with the Claude Code harness, judged by gpt-5.4-2026-03-05.
- SWE-MM: evaluated on the Claude Code harness using the public dev split of SWE-bench Multimodal, with modifications described in Appendix 8.3 of the Claude Opus 4.7 system card.
- Empty cells (`--`) mean results are not yet available or not applicable.

## Quickstart

Streamlined integration is recommended via APIs. For production or high-throughput workloads,
dedicated serving engines are recommended: SGLang, vLLM, or TokenSpeed.

## API usage

Qwen3.8 operates in thinking mode by default, generating thinking content marked by
`<think>\n...\n</think>\n\n` before the final response.

**Recommended sampling parameters:**

| Mode | temperature | top_p | top_k | min_p | presence_penalty | repetition_penalty |
|---|---|---|---|---|---|---|
| Thinking mode | 1.0 | 0.95 | 20 | 0.0 | 0.0 | 1.0 |
| Instruct (non-thinking) mode | 0.7 | 0.80 | 20 | 0.0 | 1.5 | 1.0 |

Support for sampling parameters varies by inference framework.

**`reasoning_effort`** (official support) adjusts reasoning depth and cost:
- `xhigh` (default): for complex tasks demanding thorough analysis
- `medium`: balances accuracy and speed
- `low`: efficient reasoning, optimized for speed and cost

Note: in multi-turn agentic tasks, lower reasoning effort does not always reduce overall
task completion time. It may produce faster per-turn responses but can also lead to
insufficient analysis, more failures, and repeated retries — which can increase total
latency and token consumption.

**`preserve_thinking`** is enabled by default for all workloads, retaining thinking blocks
from all historical messages for full context continuity across a conversation — beneficial
for agent scenarios where decision consistency and reduced redundant reasoning matter, and
improves KV cache utilization in both thinking and non-thinking modes. Can be disabled to
retain only the latest message's thinking block.

Example request shapes (Chat Completions API, OpenAI-compatible): text-only input, image
input (via `image_url` content blocks), video input (via `video_url` content blocks, with
`fps`/frame-sampling configurable in vLLM), and non-thinking mode (setting
`enable_thinking: False` via `chat_template_kwargs`, or directly for Qwen Cloud).

## Best practices

**Adequate output length**: for agentic tasks, allocate sufficient output length for
detailed, comprehensive responses. For frameworks supporting separate reasoning/final-output
limits, within the 1M context length:
- Reasoning content: up to 262,144 tokens
- Final response: up to 131,072 tokens

**Processing ultra-long texts**: native support up to 262,144 tokens. For total length
(input + output) beyond that, RoPE scaling (YaRN) is recommended. YaRN is supported by
vLLM, SGLang, and TokenSpeed via either a config-file change (`rope_parameters` in
`config.json`) or command-line arguments at server launch. All current open-source
frameworks implement *static* YaRN — the scaling factor stays constant regardless of input
length, which can affect performance on shorter texts. The `rope_parameters` config is
recommended only when long-context processing is actually required, and the `factor` value
should be set to match the application's typical context length (e.g. `factor=2.0` for a
~524,288-token typical length rather than the default tuned for 1M).

**Long video understanding**: the default `video_preprocessor_config.json` size parameter is
conservatively configured for text/image efficiency. Setting `longest_edge` to 469,762,048
(≈224K video tokens) enables higher frame-rate sampling for hour-scale video and better
performance; this can also be overridden via engine startup parameters.

## Citation

```bibtex
@misc{qwen38,
    title = {{Qwen3.8-Max}: A New Bar for Coding and Cowork},
    url = {https://qwen.ai/blog?id=qwen3.8},
    author = {{Qwen Team}},
    month = {August},
    year = {2026}
}
```