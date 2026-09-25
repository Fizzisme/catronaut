# Ch06 — Interaction: expanding the observation and action spaces

**Book:** [Chương 6 — Tương tác: mở rộng không gian quan sát và không gian hành động](../ai-agent-book/ch06-interaction-observation-and-action-spaces.md) · PDF pages 215–253

## Chapter summary

1. **Two new axes** (§6.1): modality (text, audio, screen, sensors) and timing (the world pushes
   events; actions span turns and can be interrupted or pre-empted). Models are trained on strictly
   turn-based data; real environments do not wait.
2. **Asynchronous, event-driven agents** (§6.2):
   - every input is a structured event with source, channel, content and context, so the agent
     never confuses a user instruction with a tool result — which is also an injection defence;
   - events are consumed only at safe points (the end of a reasoning step, a tool return), with
     three strategies: queue (batch at the next safe point), cancel (create a safe point early for
     urgent events) and parallel (independent lightweight queries) (§6.2.6);
   - a cancellation point must be a place where a tool or inference can end safely; an unfinished
     tool result is an explicit placeholder, never faked as success (§6.2.6);
   - long operations get async tool semantics: `initiate_x` returns a task id immediately and
     completion arrives as an event (§6.2.7);
   - batched events are numbered so the model does not attend only to the last one.
3. **Event-trigger tools** (timers, background-task monitors, external channels; §6.2.3) and
   **user-communication tools** (the agent messages the user through channels instead of returning
   an assistant turn; §6.2.4).
4. **Voice** (§6.3): cascade vs omni (end-to-end) vs full-duplex; a fast/slow split in which the foreground
   keeps the conversation going while the background reasons.
5. **Computer use** (§6.4): perceive → think → act → re-observe; structured element indices beat raw
   coordinates (§6.4.1–6.4.2); understanding a screen is not completing a task; confirm that reality
   matches the plan after every action.
6. **Robotics** (§6.5): layered control, action chunking, world models; completion is judged by a
   fresh observation, never by the model's own claim.
7. **A common control frame** (§6.6): sense → judge state and timing → choose → act → observe →
   continue, fix, retry, stop or replan, with shared primitives: wake-up, safe point, cancel,
   pre-empt, fast/slow split.

## Steps to apply

1. **Represent every input as a structured event** with source, channel, content and context.
   (§6.2)
2. **Consume events only at safe points**, and choose queue, cancel or parallel handling per event
   type. (§6.2.6)
3. **Place cancellation points where work can end safely**, and report interrupted work as an
   explicit placeholder — never as success. (§6.2.6)
4. **Give long operations async semantics**: return a task id at once and deliver completion as an
   event; let tool names and descriptions say that the call is asynchronous. (§6.2.7)
5. **Number batched events** so each one is attended to. (§6.2)
6. **Add event-trigger and user-communication tools** only when inbound channels exist. (§6.2.3–6.2.4)
7. **Split fast and slow paths** for real-time interaction: a responsive foreground, a reasoning
   background. (§6.3)
8. **For screen agents**, act through structured element indices and re-observe after every action.
   (§6.4.1–6.4.2)
9. **Judge completion by a fresh observation**, never by the model's claim. (§6.4, §6.5)
10. **Reuse the common control frame** and its primitives across modalities. (§6.6)

## Common pitfalls

- Assuming the world waits for the model's turn. (§6.1)
- Faking success for an interrupted or timed-out tool. (§6.2.6)
- Declaring a task done because the screen was understood, not because the state changed. (§6.4)
