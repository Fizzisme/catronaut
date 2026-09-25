# Catronaut — Roadmap (bản tiếng Việt)

> Bản dịch cho người đọc của [ROADMAP.md](../../ROADMAP.md). Bản tiếng Anh là bản chuẩn.
>
> **Phạm vi:** `ai-service` — harness của agent Catronaut. Frontend, API gateway và
> `project-service` do team khác phụ trách, chỉ xuất hiện ở đây dưới dạng contract.
> **Phiên bản:** v1 · 2026-09-25.

## 1. North star

Catronaut là nền tảng agent nhiều domain. Domain đầu tiên, `ui_ux`, biến một yêu cầu như "làm
trang web thương mại điện tử" thành một **project Next.js chạy được (chỉ frontend)**. Agent tự kiểm
tra xem đã đủ thông tin chưa, hỏi lại bằng câu hỏi có cấu trúc nếu thiếu, đề xuất art direction,
lập plan, viết code, và project chạy trực tiếp trong trình duyệt của user. Chất lượng thẩm mỹ ở mức
đoạt giải ([awwwards.com](https://www.awwwards.com/) là thước đo) là điểm khác biệt so với các công
cụ kiểu Claude Design. Domain thứ hai, `cyber` (cybersecurity), làm sau trên cùng core.

Model là **Qwen3.8-27B**, serve bằng **vLLM** ([model reference](../qwen3.8-27b-reference.md)).
Làm harness trước; fine-tune làm sau, khi đã qua gate.

## 2. Quyết định đã chốt

| # | Quyết định | Hệ quả |
|---|---|---|
| D1 | **Preview = Next.js subset + shim trên Sandpack classic bundler.** | Agent viết project Next.js App Router thật, giới hạn trong một subset chỉ-frontend. Preview runtime (shim cho `next/*`, giả lập App Router, Tailwind browser build) thuộc frontend; `ai-service` định nghĩa và enforce **preview contract**. Project export ra không chứa shim. |
| D2 | **`ai-service` dùng Python + FastAPI.** | pydantic, `openai` SDK gọi vLLM, `mcp` SDK, `httpx`, SSE. TSX được kiểm tra parse-only bằng tree-sitter; chỉ thêm Node sidecar để type-check nếu eval cho thấy parse-only để lọt quá nhiều lỗi. Playwright (Python) cho eval. |
| D3 | **Phạm vi chỉ gồm `ai-service`; file tree nằm ở `project-service`.** | Workspace là adapter bọc `project-service`. Version và revert, lock, export là các điều khoản contract với `project-service`. Dev, test và eval dùng workspace local. |
| D4 | **Docs tiếng Anh là bản chuẩn; `docs/vn/` chứa bản tiếng Việt cho người đọc.** | Agent chỉ đọc docs tiếng Anh; `CLAUDE.md` (M0.1) ghi rõ điều này. |
| D5 | **`ai-service` không bao giờ build hay chạy code được sinh ra.** Được phép parse. | Ranh giới an toàn là iframe preview cross-origin trong trình duyệt user. Các kiểm tra cần trình duyệt chỉ chạy trong pipeline eval offline. |

## 3. Dữ kiện định hình kế hoạch

| # | Dữ kiện | Tác động |
|---|---|---|
| F1 | Template `nextjs` của Sandpack chạy trên Nodebox, mà Nodebox bị ghim ở Node 16 nên Next.js ≥ 14 không chạy được ([sandpack#1104][sandpack-1104]). Các template Nodebox (`nextjs`, `vite*`, `astro`, `node`) cần license của CodeSandbox khi dùng thương mại; template classic (`react-ts`, `static`, …) là Apache-2.0 và self-host được ([Sandpack FAQ][sandpack-faq]). | Dẫn tới D1. |
| F2 | Qwen3.8-27B là model hybrid (Gated DeltaNet + Gated Attention). Docs vLLM v0.26 vẫn ghi prefix caching chưa hỗ trợ cho model hybrid; code có nhánh experimental `mamba_cache_mode="align"` ([vLLM v1 guide][vllm-hybrid]). | Không có cache hit thì mỗi bước của agent phải prefill lại toàn bộ prefix. Đo ở M0.2 trước khi chốt chiến lược context. |
| F3 | vLLM serve thế hệ trước, Qwen3.6-27B, với `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3` ([vLLM Codex integration][vllm-codex]). | Cấu hình khởi điểm cho Qwen3.8; verify ở M0.2. |
| F4 | Điểm agentic của Qwen3.8 được đo trên harness Claude Code. Model hỗ trợ vision native; thinking bật mặc định, có `reasoning_effort` và `preserve_thinking`. | Tool có shape giống Claude Code (Read, Write, Edit, Glob, Grep, TodoWrite). Chính model này review được screenshot. Reasoning phải được round-trip đúng theo chat template. |
| F5 | open-design cung cấp 19 skill và 71 design system (`DESIGN.md`) cho các coding-agent CLI, kể cả Qwen ([open-design][open-design]); impeccable là nguồn design skill còn lại. | Nguyên liệu cho skills và thư viện design system. Kiểm tra license trước khi port (M4.2). |

## 4. Giả định cần xác nhận

- **A1.** Làm lại từ đầu: không tái dùng code Catronaut cũ; tài liệu cũ chỉ để tham khảo.
- **A2.** Agent loop chạy trong `ai-service`. `project-service` là nguồn sự thật cho file; mỗi run
  làm việc trên một working copy rồi ghi ngược lại.
- **A3.** Có GPU server chạy vLLM với Qwen3.8-27B; một model nhỏ phục vụ smoke test cho dev và CI.
- **A4.** Phía trước có API gateway lo xác thực và gắn user id (thiết kế cũ dùng Go gateway).
- **A5.** Team frontend sở hữu preview runtime. `ai-service` làm spike M0.3, viết contract rồi bàn
  giao; pipeline eval dùng lại đúng runtime đó.
- **A6.** Không gắn ngày. Mỗi phase có exit criteria; ước lượng thời gian sau Phase 0.

## 5. Nguyên tắc

1. Agent = LLM + context + tools; harness chính là sản phẩm — [ch01] §1.1–1.2.
2. Ràng buộc được enforce bằng code, không phải nhờ prompt — [ch05] §5.1.4.
3. "Done" phải được kiểm chứng, không phải tự tuyên bố: run chỉ thành công khi verifiers pass —
   [ch10] §10.4.3.
4. Context thân thiện với KV cache: prefix tĩnh → history → phần động ở đuôi — [ch02] §2.3.
5. Eval trước khi tối ưu. Mỗi layer của harness có feature switch để đo được, và gỡ bỏ khi model
   không còn cần nó — [ch07] §7.10, postscript.
6. Trajectory trung lập provider được log ngay từ ngày đầu — [ch05] §5.1.5, [ch08] §8.14.
7. Tool có shape giống Claude Code để nằm trong phân phối huấn luyện của model (F4).
8. Bảo mật là vấn đề kiến trúc ngay từ dòng code đầu tiên: guardrail ở tầng context, tầng thực thi
   và tầng dữ liệu — [ch01] §1.2.5.

## 6. Kiến trúc

```
Trình duyệt (team frontend): chat · form câu hỏi · file tree · preview (Sandpack classic + Next.js shim)
   │ run requests                ▲ SSE run events               │ lỗi preview + screenshot
   ▼                             │                              ▼
API gateway: xác thực, user id, rate limit
   ├──► ai-service  ◄── phạm vi của roadmap này (Python / FastAPI)
   │      core: LLM client · agent loop · context và compaction · tools · skills · MCP client
   │            · workspace adapter · verifiers · tracing
   │      domains: ui_ux (trước) · cyber (sau)
   │        ├──► project-service: file tree, versions, locks   [team khác]
   │        ├──► vLLM: Qwen3.8-27B   [+ multi-LoRA sau này]
   │        └──► MCP servers: context7, …
   └──► project-service
```

## 7. Các phase

Guide: mỗi phase trỏ tới các guide theo chương trong [docs/vn/book-guide/](book-guide/README.md)
(bản chuẩn: [docs/book-guide/](../book-guide/README.md)), tóm tắt các bước trong sách *Hiểu sâu về
AI Agent* kèm tham chiếu mục (§) về sách.

### Phase 0 — Nền móng và spike

| ID | Milestone | Kết quả bàn giao |
|---|---|---|
| M0.1 | Khởi tạo repo | Git repo riêng; `uv`, `ruff`, `pyright`, `pytest`, CI; khung FastAPI; layout `app/core/`, `app/domains/ui_ux/`, `app/api/`, `evals/`, `docs/`; `CLAUDE.md` ghi rõ docs tiếng Anh là bản chuẩn và agent không đọc `docs/vn/`. |
| M0.2 | Spike serve model | vLLM với các flag ở F3; chọn quantization theo GPU (BF16 ≈ 54 GB weights, FP8 ≈ 27 GB); thử MTP speculative decoding. Đo tỉ lệ parse tool call đúng (~50 call mẫu), TTFT và tokens/s ở context 8K/32K/64K, **tỉ lệ prefix-cache hit** (F2), số session đồng thời; kiểm tra `enable_thinking`, `reasoning_effort` và `preserve_thinking` có đi qua vLLM không → ADR-0001. |
| M0.3 | Spike preview | Sandpack classic bundler (self-host được) với shim cho `next/link`, `next/image`, `next/font`, `next/navigation` và metadata; giả lập App Router từ `app/**/page.tsx`, `layout.tsx` lồng nhau và segment `[slug]`; Tailwind qua browser build; thử dependency (motion, gsap, lenis, three/R3F); bắt lỗi bundler và runtime; chụp screenshot iframe → ADR-0002, **preview contract** (được dùng và bị cấm: `"use server"`, `app/**/route.ts`, `next/headers`, `server-only`, API Node, …) và danh sách dependency đã kiểm chứng. |
| M0.4 | Contract giữa các service | (a) Frontend ↔ `ai-service` qua gateway: vòng đời run (start, SSE stream, `needs_input`, resume, cancel) và endpoint nhận báo cáo preview. (b) `ai-service` ↔ `project-service`: đọc file tree, ghi theo batch, một version cho mỗi run và revert, lease/lock, optimistic concurrency → ADR-0003. |
| M0.5 | Spike kiểm tra tĩnh | Parse TSX bằng tree-sitter, resolve import và kiểm luật preview contract, chạy trên starter và một tập lỗi cài sẵn; đo lỗi bị lọt rồi quyết định có cần Node type-check sidecar không → ADR-0004. |
| M0.6 | Book guides | [docs/book-guide/](../book-guide/README.md): các bước theo từng chương kèm tham chiếu về sách, và bản tiếng Việt. **Xong 2026-09-25.** |

**Exit:** tool calling ổn định trên model thật; một starter Next.js render được trong preview;
ADR-0001 đến ADR-0004 được chấp thuận.
**Guide:** [ch01]; [ch02] §2.3; [ch04] §4.6; [ch06] §6.1–6.2.

### Phase 1 — Harness core (không phụ thuộc domain)

| ID | Milestone | Kết quả bàn giao |
|---|---|---|
| M1.1 | LLM client | `AsyncOpenAI` gọi vLLM có streaming; reasoning được round-trip theo chat template; chỉ retry lỗi retryable (429, 5xx, mất kết nối) với backoff và jitter; phát hiện `finish_reason=length` và **không bao giờ execute tool call bị cắt**; message model trung lập provider. |
| M1.2 | Agent loop (ReAct) | Xử lý mọi tool call trong một turn; terminal states `done`, `needs_input`, `stopped_at_limit`, `failed`, `cancelled`; giới hạn số vòng, wall clock và token; fingerprint call lặp lại và circuit breaker khi lỗi liên tiếp; mỗi `tool_call` có kết quả đi kèm trước request tiếp theo; cancel tại safe point. |
| M1.3 | Tool framework | pydantic schema, validate fail-fast; mô tả đầy đủ (khi nào dùng, khi nào không, ví dụ, shape kết quả, chi phí); lỗi tool trả về dạng observation có cấu trúc kèm gợi ý khắc phục; cắt output head + tail có nói rõ cách đọc phần còn lại. |
| M1.4 | Workspace adapter | Interface `Workspace`. `ProjectServiceWorkspace` nạp file tree lúc bắt đầu run vào working copy, ghi ngược về `project-service` và phát `file_changed`; `LocalWorkspace` dùng cho dev, test và eval. Path guard; quota ghi mỗi run (kích thước, số file, đuôi file); lease project trong suốt run. |
| M1.5 | File tools | `Read` (có số dòng, `offset`/`limit`), `Write` (file đã tồn tại phải được Read trước), `Edit` (thay chính xác `old_string` → `new_string`: match duy nhất, nếu không thì báo lỗi rõ), `Glob`, `Grep`, `TodoWrite`. Tham số không bao giờ bị âm thầm biến đổi. |
| M1.6 | Context engineering | System prompt ghép từ các section có tên, byte-stable; thứ tự thân thiện KV cache; status bar tính bằng code (vòng n/max, bộ đếm, tóm tắt manifest); token budget; compaction nhiều tầng có handle để đọc lại, chỉ làm khi số đo cho thấy cần. |
| M1.7 | Tracing | Mỗi run một JSON trace: model call (token, thời gian, finish reason), tool call (digest tham số, trạng thái, thời gian chạy) và kết quả. |
| M1.8 | Run API và streaming | FastAPI async run với SSE (delta `thinking` và `message`, `tool_call`, `tool_result`, `file_changed`, `needs_input`, `done`), resume và cancel. Một run sinh cả site mất nhiều phút nên run phải bất đồng bộ. |
| M1.9 | Dev CLI và playground | `catronaut run "<prompt>"` trên `LocalWorkspace`, cộng một trang dev tối thiểu có preview, để thử harness khi chưa có frontend thật. |

**Exit:** trên model thật, agent tạo và sửa file qua tools, trace đầy đủ; smoke test CI trên model nhỏ
pass.
**Guide:** [ch01] §1.1.5; [ch02] §2.2–2.7; [ch04] §4.2, §4.5; [ch05] §5.1.4–5.1.8; [ch06] §6.2.

### Phase 2 — MVP `ui_ux`: từ prompt tới project Next.js chạy trong preview

| ID | Milestone | Kết quả bàn giao |
|---|---|---|
| M2.1 | Domain pack `ui_ux` | Prompt sections, tool allowlist, skills, knowledge, verifiers, bộ eval — khuôn mẫu mọi domain đều theo. |
| M2.2 | Starter và manifest | Scaffold tất định từ một starter đã kiểm chứng trong preview, ghi qua workspace adapter; `.catronaut/project.json` lưu template, câu trả lời discovery, quyết định design, và danh sách file kèm hash. |
| M2.3 | Discovery | `ask_user` trả về câu hỏi có cấu trúc `{id, text, kind: single\|multi\|text, options}`; run kết thúc ở `needs_input`; frontend hiển thị form và mọi câu trả lời quay về trong một lượt. Skill quyết định hỏi gì; harness từ chối scaffold khi còn thiếu thông tin bắt buộc. |
| M2.4 | Design brief và design system | `DESIGN.md` cùng tokens (màu, type scale, spacing, radius, motion) trong workspace, chọn từ thư viện design system hoặc suy ra từ input của user. |
| M2.5 | Plan | Sitemap và danh sách page/component qua `TodoWrite`; với yêu cầu lớn thì xác nhận plan với user trước. |
| M2.6 | Build và verify | Sau mỗi lần ghi: parse bằng tree-sitter, resolve import, luật preview contract, dependency allowlist. Run chỉ xong khi verifiers pass. |
| M2.7 | Vòng phản hồi từ preview | Trong run, tool `check_preview` chờ (có timeout) frontend báo lại sau khi render lại; nếu không thì lỗi đi kèm lượt sau. Số vòng tự sửa có giới hạn. |
| M2.8 | Sửa tiếp theo yêu cầu | "Đổi màu nút" thành một `Edit` đúng chỗ; revert dùng version của `project-service`; `reasoning_effort` cho từng bước được chọn bằng eval. |

**Exit:** tỉ lệ run không có lỗi bundler và runtime trên bộ eval đạt ngưỡng đặt ra sau baseline của
Phase 3.
**Guide:** [ch05]; [ch03] §3.1.2; [ch04] §4.6; [ch09] §9.2.2.

### Phase 3 — Evaluation harness (song song với Phase 2; phải có baseline trước Phase 4)

| ID | Milestone | Kết quả bàn giao |
|---|---|---|
| M3.1 | Task set v0 | 30–50 prompt: loại site (landing, thương mại điện tử, portfolio, SaaS, nhà hàng, …) × độ mơ hồ; template có tham số để chống contamination; trap task. |
| M3.2 | Verifiers tất định | Workspace contract, kiểm tra parse, veto item (khai báo một file không tồn tại, ghi ra ngoài workspace, …). |
| M3.3 | Kiểm tra bằng trình duyệt | Chỉ trong CI và eval: Playwright mở preview (cùng runtime với frontend) → lỗi bundler và runtime, accessibility bằng axe, performance cơ bản, screenshot ở ba breakpoint. |
| M3.4 | Điểm design | Rubric và judge có vision chấm screenshot; một mẫu gán nhãn tay để hiệu chuẩn; luật anti-pattern kiểu impeccable. |
| M3.5 | User simulator | Cho discovery: chỉ tiết lộ sở thích khi được hỏi, kiên nhẫn có hạn → số câu hỏi so với kết quả. |
| M3.6 | Báo cáo | Pass@k và Pass^k; token, latency và chi phí mỗi task; so sánh paired giữa các phiên bản harness; hồ sơ quy trách nhiệm lỗi. |

**Exit:** một lệnh chạy eval và ghi report; baseline được lưu lại.
**Guide:** [ch07]; [ch09] §9.1.

### Phase 4 — Skills, knowledge và MCP

| ID | Milestone | Kết quả bàn giao |
|---|---|---|
| M4.1 | Skill system | Định dạng Agent Skills (`SKILL.md` + frontmatter + `references/`); catalog nằm trong prefix tĩnh; `load_skill` gắn body vào đuôi context. |
| M4.2 | Design skills | Port impeccable và open-design (kiểm tra license trước; review như review code), viết lại cho Qwen3.8; A/B test bằng eval. |
| M4.3 | Knowledge base | File system trước RAG: component patterns, preview contract, accessibility, typography và màu, viết bằng Markdown có abstract ~100 token và trang index. |
| M4.4 | MCP client | context7 và các server khác; allowlist theo domain, timeout, cắt output; output MCP được gắn nhãn là dữ liệu không tin cậy; web fetch có SSRF guard. |
| M4.5 | Assets | Ảnh (API ảnh stock hoặc placeholder), icon và font, để site không trông trống trải. |

**Exit:** eval cho thấy skills nâng điểm design so với baseline.
**Guide:** [ch02] §2.4.7, §2.5; [ch03] §3.2–3.3; [ch04] §4.3–4.4.

### Phase 5 — Lớp sáng tạo chuẩn awwwards

| ID | Milestone | Kết quả bàn giao |
|---|---|---|
| M5.1 | Phân loại kỹ thuật | Các kỹ thuật thấy ở site đoạt giải: layout kiểu editorial và bất đối xứng, chữ cỡ lớn và kinetic type, kể chuyện theo scroll (GSAP ScrollTrigger, Lenis), page transition, micro-interaction và custom cursor, WebGL/3D (three.js, R3F, shader), texture (grain, noise, gradient), art direction về màu. Học **pattern**; không bao giờ copy site. |
| M5.2 | Thư viện recipe | Mỗi kỹ thuật là một recipe đã chạy được trong preview, kèm guardrail: `prefers-reduced-motion`, fallback cho mobile, perf budget, accessibility. |
| M5.3 | Creative direction | Agent đề xuất 2–3 hướng (concept, cặp font, palette, ngôn ngữ chuyển động, ý tưởng layout); user chọn một; hướng đó được ghi vào `DESIGN.md` và manifest. |
| M5.4 | Tự review bằng hình ảnh | Frontend gửi screenshot preview; Qwen3.8 (vision) review theo direction và danh sách anti-pattern, trả về các sửa đổi có cấu trúc, trong giới hạn số vòng. |
| M5.5 | Eval sáng tạo | Một subset riêng và rubric về độ khác biệt/độ tinh xảo, chấm theo cặp (người + judge) so với baseline. |

**Exit:** người chấm ưu tiên output của lớp sáng tạo hơn baseline ở ít nhất X% số cặp (X đặt cùng
baseline eval).
**Guide:** [ch05] §5.2; [ch04] §4.5.1; [ch07] §7.5; [ch10] §10.2.

### Phase 6 — Gia cố cho production (phía `ai-service`)

| ID | Milestone | Kết quả bàn giao |
|---|---|---|
| M6.1 | Scale và quota | Instance stateless; run state trong Redis hoặc database để instance nào cũng resume hay stream được; quota token và run theo user (chi phí GPU); user id lấy từ gateway. |
| M6.2 | Lưu trữ | Run và trace trong database và object storage; file và version vẫn ở `project-service`. |
| M6.3 | Observability | Dashboard cho latency, token, GPU, tỉ lệ lỗi tool và kết quả run; cảnh báo. |
| M6.4 | Bảo mật | Kiểm tra lethal trifecta cho từng tool pack, kiểm soát egress, MCP allowlist, quản lý secrets. |
| M6.5 | Độ chuẩn của bản export | CI chạy `next build` thật trên project được sinh ra (không có shim) để bảo đảm bản export chạy được; bản thân tính năng export thuộc `project-service` và frontend. |
| M6.6 | Sub-agents (có gate) | Chỉ thêm khi eval cho thấy một context thứ hai có thông tin mới giúp ích, ví dụ reviewer đọc screenshot. |

**Guide:** [ch01] §1.2.5; [ch02] §2.7.6; [ch05] §5.1.9; [ch10].

### Phase 7 — Fine-tuning (có gate)

**Gate:** đã có evaluation harness, đã thu đủ trace, và vẫn còn một loại lỗi sau khi đã thử sửa bằng
prompt, tool, ràng buộc và context.

| ID | Milestone | Kết quả bàn giao |
|---|---|---|
| M7.1 | Data pipeline | Trace → lọc bằng verifiers (rejection sampling) → tập SFT/DPO; chia train/eval theo task template; kiểm tra license Qwen3.8 cho fine-tune và phân phối adapter. |
| M7.2 | SFT LoRA | Giao thức dùng tool, hành vi discovery, design skills; eval so với base model trên boundary set và retention set. |
| M7.3 | Serving | vLLM multi-LoRA: mỗi domain một adapter (`ui_ux`, `cyber`), route theo domain. |
| M7.4 | RL (về sau) | Reward kiểm chứng được: không có lỗi preview, accessibility, điểm judge. |

**Guide:** [ch08]; [ch09].

### Phase 8 — Domain thứ hai: cybersecurity (sau Phase 2–3)

| ID | Milestone | Kết quả bàn giao |
|---|---|---|
| M8.1 | ADR của domain | Sandbox thực thi cho scanner, phạm vi được ủy quyền, luật egress, phê duyệt của con người — một mô hình an toàn khác hẳn `ui_ux`. |
| M8.2 | Domain pack `cyber` | Dùng lại core; có prompts, tools, skills, verifiers và bộ eval riêng. |

**Guide:** [ch01] §1.2.5; [ch04] §4.6; [ch05] §5.1.9.

## 8. Rủi ro và câu hỏi mở

| Rủi ro hoặc câu hỏi | Cách giảm thiểu |
|---|---|
| Prefix caching có thể không hoạt động với model hybrid trên vLLM (F2). | Đo ở M0.2. Nếu không có: compaction chặt hơn, prefix ngắn hơn, hoặc đánh giá SGLang. |
| Shim không tái hiện được mọi hành vi của Next.js. | Preview contract giới hạn agent trong subset chỉ-frontend; M6.5 kiểm tra build thật. |
| License: open-design, impeccable, Qwen3.8 (fine-tune), Sandpack bundler tự host. | Kiểm tra lần lượt trước M4.2, M7.1 và M0.3. |
| Timeout của gateway so với run SSE kéo dài. | Chốt trong contract M0.4; resume từ manifest. |
| `project-service` cung cấp được gì (version, lease, ghi theo batch). | Thống nhất ở M0.4; trong lúc chờ, `LocalWorkspace` giúp dev không bị chặn. |
| User sửa file trong lúc run đang chạy. | Lease project và optimistic concurrency (M0.4, M1.4). |

## 9. Nguồn

- [Sandpack FAQ — license cho template Nodebox][sandpack-faq]
- [codesandbox/sandpack#1104 — Nodebox bị ghim ở Node 16][sandpack-1104]
- [vLLM — Codex integration (flag serve Qwen3.6-27B)][vllm-codex]
- [vLLM v0.26 V1 guide — model hybrid và prefix caching][vllm-hybrid]
- [open-design (có nhiều fork; cần xác nhận repo gốc)][open-design]

[sandpack-faq]: https://sandpack.codesandbox.io/docs/resources/faq
[sandpack-1104]: https://github.com/codesandbox/sandpack/issues/1104
[vllm-codex]: https://docs.vllm.ai/en/stable/serving/integrations/codex
[vllm-hybrid]: https://github.com/vllm-project/vllm/blob/v0.26.0/docs/usage/v1_guide.md
[open-design]: https://github.com/ccfuncy/open-design
[ch01]: book-guide/ch01-getting-started.md
[ch02]: book-guide/ch02-context-engineering.md
[ch03]: book-guide/ch03-memory-and-knowledge-base.md
[ch04]: book-guide/ch04-tools.md
[ch05]: book-guide/ch05-coding-agents-and-code-generation.md
[ch06]: book-guide/ch06-interaction-observation-and-action-spaces.md
[ch07]: book-guide/ch07-agent-evaluation.md
[ch08]: book-guide/ch08-model-post-training.md
[ch09]: book-guide/ch09-continuous-agent-evolution.md
[ch10]: book-guide/ch10-multi-agent-collaboration.md
