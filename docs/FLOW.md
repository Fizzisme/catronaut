# Luồng chạy của Catronaut, đi từ `app/main.py`

> Tài liệu học tập cho người mới đọc code AI-service ở mức này. Không phải doc chính thức của dự
> án (đó là `CLAUDE.md`/`README.md`/`ROADMAP.md`) — file này giải thích *tại sao* code được viết
> theo cấu trúc này, đọc song song với code thật.

## Bức tranh tổng thể trước khi đọc code

Có 2 câu hỏi cần trả lời trước khi đọc bất kỳ dòng code nào:

1. **Ai gọi service này?** → Go API gateway của bạn, không phải người dùng cuối trực tiếp. Gateway
   lo login/JWT/routing công khai, rồi forward request vào service này qua nội bộ.
2. **Service này làm gì cốt lõi?** → Nhận 1 request HTTP → chọn đúng "agent" theo domain
   (`ui_ux`, sau này `code_review`,...) → agent build prompt → gọi model qua Ollama → trả text.

Toàn bộ code trong `app/` chỉ là cách tổ chức 2 việc đó cho gọn và dễ mở rộng. Không có gì huyền
bí — không có "AI tự suy nghĩ" ở tầng framework, tầng framework chỉ là ống dẫn HTTP request tới
một lệnh gọi HTTP khác (tới Ollama).

## 2 pha của một FastAPI app: startup và request

Đây là điều quan trọng nhất cần hiểu trước, vì code được viết xoay quanh nó:

- **Pha startup**: chạy **một lần duy nhất** khi bạn gõ `uvicorn app.main:app`. Đây là lúc tạo kết
  nối tới Ollama, dựng danh sách agent. Việc này *chậm* (mở kết nối mạng, load config) nên không
  ai muốn làm lại mỗi request.
- **Pha request**: chạy **mỗi lần** có HTTP request tới. Việc này phải *nhanh* — chỉ tái sử dụng
  cái đã dựng ở pha startup, không tạo mới gì tốn kém.

Câu thần chú của toàn bộ kiến trúc: **"dựng 1 lần ở startup, dùng lại ở mọi request."** Đây là lý
do vì sao có `app.state`, `lifespan`, và tại sao agent không bao giờ tự tạo kết nối riêng.

---

## Bước 1 — `uvicorn app.main:app` chạy, Python import `app/main.py`

Mở [app/main.py](../app/main.py). Khi Python import file này, các dòng import ở đầu file chạy
**trước tiên**, theo đúng thứ tự viết:

```python
from app.api.router import api_router          # (1)
from app.core.config import settings            # (2)
from app.core.exceptions import register_exception_handlers  # (3)
from app.core.lifespan import lifespan           # (4)
```

Đây không phải 4 dòng độc lập — chúng kéo theo cả một chuỗi import khác. Đi theo từng dòng:

### (2) `app.core.config` — nạp cấu hình trước tiên

[app/core/config.py](../app/core/config.py) định nghĩa class `Settings` (kế thừa
`pydantic_settings.BaseSettings`) và tạo sẵn **một object dùng chung** tên là `settings`:

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

`Settings()` tự động đọc file `.env` (đường dẫn khai trong `model_config`) và biến môi trường,
map vào các field như `settings.model_name`, `settings.ollama_base_url`. Vì `settings` được tạo
**ngay khi module này được import lần đầu**, và Python cache module (import lần 2 trở đi không
chạy lại code), nên **mọi nơi trong codebase `from app.core.config import settings` đều nhận
đúng một object y hệt nhau** — không phải đọc `.env` lại mỗi lần. Đây là pattern "singleton" kiểu
Python: không cần class đặc biệt, chỉ cần tạo instance ở module-level rồi import nó.

### (3) `app.core.exceptions` — định nghĩa các loại lỗi

[app/core/exceptions.py](../app/core/exceptions.py) định nghĩa một cây exception:

```
CatronautError (base, status 500)
├── UnknownDomainError   (404 — domain không tồn tại, vd gọi /code-review khi chưa có)
├── ProviderError        (502 — Ollama lỗi/timeout/trả về sai định dạng)
└── DomainError          (422 — agent xử lý input không hợp lệ)
```

Ý tưởng: **code nghiệp vụ (agent, provider) không bao giờ tự trả HTTP response.** Nó chỉ
`raise ProviderError("...")`. Việc biến exception đó thành JSON response đúng status code là việc
của `register_exception_handlers(app)` — một hàm đăng ký "nếu thấy `CatronautError` bay ra, bắt
nó và trả về `{"error": {"code", "message"}}`". Nhờ vậy domain code không cần biết gì về HTTP.

### (4) `app.core.lifespan` — hàm sẽ chạy lúc startup/shutdown (nhưng CHƯA chạy lúc import)

[app/core/lifespan.py](../app/core/lifespan.py) định nghĩa hàm `lifespan`, nhưng **import chỉ
định nghĩa hàm, không gọi nó**. Hàm này thật sự chạy ở Bước 2 bên dưới. Cứ nhớ tạm: đây là nơi
"máy pha cà phê" được cắm điện và bật lên trước khi khách tới order.

### (1) `app.api.router` — kéo theo toàn bộ cây agent

[app/api/router.py](../app/api/router.py):

```python
from app.api import ui_ux
api_router = APIRouter()
api_router.include_router(ui_ux.router, prefix="/ui-ux", tags=["ui-ux"])
```

Import `app.api.ui_ux` kéo theo import `app.schemas.agent` (định nghĩa hình dạng JSON request/
response). Đây chỉ là khai báo route `/ui-ux/...` — **không có prefix `/api` hay `/v1`**, vì
service này chạy sau Go API gateway, gateway đã lo public routing/versioning rồi (xem
`CLAUDE.md` §1 nếu muốn hiểu tại sao quyết định vậy).

## Bước 2 — Tạo app FastAPI

Sau khi các import ở trên chạy xong, `main.py` tiếp tục:

```python
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,      # <-- gắn hàm lifespan vào app, CHƯA chạy nó
)

register_exception_handlers(app)   # đăng ký handler bắt CatronautError
app.include_router(api_router)     # gắn route /ui-ux/analyze vào app
```

Ba dòng này chỉ **cấu hình** object `app`. `app` chưa "sống" — nó chỉ là một object Python mô tả
"tôi có những route này, lỗi thì xử lý kiểu này, lúc bật/tắt thì chạy hàm này". `uvicorn` là cái
thực sự biến nó thành một HTTP server đang lắng nghe port.

## Bước 3 — `uvicorn` gọi `lifespan`, service thật sự "sống"

Khi `uvicorn app.main:app` khởi động server, nó gọi hàm `lifespan(app)` đã gắn ở Bước 2.
Mở [app/core/lifespan.py](../app/core/lifespan.py):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    model_provider = OllamaProvider(
        base_url=settings.ollama_base_url,
        model_name=settings.model_name,
        num_ctx=settings.model_num_ctx,
        timeout_s=settings.model_timeout_s,
        think=settings.model_think,
    )
    orchestrator = Orchestrator(model_provider, AGENT_REGISTRY)

    app.state.model_provider = model_provider
    app.state.orchestrator = orchestrator

    logger.info("started env=%s model=%s ...")

    try:
        yield              # <-- server bắt đầu nhận request TẠI ĐÂY
    finally:
        await model_provider.aclose()   # chạy khi server shutdown (Ctrl+C)
```

Đây chính là nơi "dựng 1 lần" xảy ra:

- **`OllamaProvider(...)`** ([app/core/model_provider/ollama_provider.py](../app/core/model_provider/ollama_provider.py))
  tạo **một** `httpx.AsyncClient` — nghĩ nó như một "đường dây điện thoại" luôn mở sẵn tới Ollama.
  Không tạo `httpx.AsyncClient` mới cho mỗi request — tốn tài nguyên và chậm.
- **`Orchestrator(model_provider, AGENT_REGISTRY)`**
  ([app/core/orchestrator.py](../app/core/orchestrator.py)) build sẵn **mọi agent** (hiện tại chỉ
  có `UIUXAgent`), mỗi agent giữ tham chiếu tới **cùng một** `model_provider` ở trên. Nếu sau này
  có domain `code_review`, nó cũng dùng chung provider này — không load model 2 lần.
  `AGENT_REGISTRY` đến từ [app/domains/registry.py](../app/domains/registry.py) — dict đơn giản
  `{"ui_ux": UIUXAgent}`, là nơi *duy nhất* khai báo "domain nào tồn tại".
- **`app.state.model_provider = ...`** và **`app.state.orchestrator = ...`**: đây là cách FastAPI
  cho phép "cất" một object ở cấp application để mọi request sau này lấy lại được, thông qua
  `request.app.state`. Coi `app.state` như một cái tủ chung — bỏ đồ vào 1 lần lúc mở tiệm, khách
  nào tới cũng lấy được từ tủ đó, không cần đúc lại đồ mỗi lần khách vào.
- **`yield`**: đây là điểm bàn giao. Code trước `yield` là "lúc mở tiệm", code sau `yield` (trong
  `finally`) là "lúc đóng tiệm". Giữa hai mốc đó, server chạy bình thường và xử lý request.

## Bước 4 — Một request HTTP thật sự tới: `GET /health`

Quay lại [app/main.py](../app/main.py):

```python
@app.get("/health")
async def health_check(request: Request) -> dict:
    provider = request.app.state.model_provider   # lấy lại đồ đã "cất tủ" ở Bước 3
    backend_ok = await provider.health()            # hỏi thẳng Ollama "còn sống không?"
    return {
        "status": "ok" if backend_ok else "degraded",
        ...
        "domains": request.app.state.orchestrator.domains,
    }
```

`request.app` chính là object `app` đã tạo ở Bước 2, `request.app.state` chính là cái tủ đã bỏ đồ
vào ở Bước 3. Route handler không tạo gì mới — chỉ lấy lại và dùng. `provider.health()` gọi
`GET /api/version` sang Ollama thật để biết Ollama có đang chạy không (không phải chỉ kiểm tra
Python process của chính mình còn sống).

## Bước 5 — Request thật sự: `POST /ui-ux/analyze`

Đây là luồng chính, đi qua 4 lớp. Theo dõi bằng một ví dụ cụ thể: client gửi
`{"prompt": "Review my login form"}`.

```
Client (Go gateway)
  │  POST /ui-ux/analyze  {"prompt": "..."}
  ▼
[Lớp 1] app/api/ui_ux.py           — route, KHÔNG có business logic
  │
  ▼
[Lớp 2] app/core/orchestrator.py   — chọn đúng agent theo domain
  │
  ▼
[Lớp 3] app/domains/ui_ux/agent.py — build prompt, gọi model, xử lý kết quả
  │
  ▼
[Lớp 4] app/core/model_provider/ollama_provider.py — nói chuyện HTTP với Ollama
  │
  ▼
Ollama (đang chạy model qwen3:4b)
```

### Lớp 1 — Route ([app/api/ui_ux.py](../app/api/ui_ux.py))

```python
@router.post("/analyze", response_model=AgentOutput)
async def analyze(payload: AgentInput, request: Request) -> AgentOutput:
    agent = request.app.state.orchestrator.get_agent("ui_ux")
    return await agent.handle(payload)
```

Hai điều xảy ra tự động mà bạn không viết code cho nó:

- **`payload: AgentInput`** — FastAPI đọc JSON body, validate theo
  [app/schemas/agent.py](../app/schemas/agent.py) (`AgentInput` yêu cầu `prompt` không rỗng). Nếu
  client gửi thiếu `prompt` hoặc gửi `prompt: ""`, FastAPI tự trả lỗi 422 **trước khi** dòng code
  nào trong hàm `analyze` chạy. Đây là lý do dùng Pydantic model thay vì `dict` thô.
- **`response_model=AgentOutput`** — khi hàm trả về, FastAPI tự serialize object đó thành đúng
  JSON theo schema `AgentOutput`.

Route chỉ làm **đúng 2 việc**: lấy agent, gọi `handle()`. Không có prompt, không có xử lý lỗi
riêng — tất cả các thứ đó cố tình nằm ở lớp khác, để route mãi mãi "mỏng" và dễ đọc.

### Lớp 2 — Orchestrator ([app/core/orchestrator.py](../app/core/orchestrator.py))

```python
def get_agent(self, domain: str) -> Agent:
    agent = self._agents.get(domain)
    if agent is None:
        raise UnknownDomainError(f"Unknown domain '{domain}'...")
    return agent
```

`self._agents` là dict đã build sẵn ở Bước 3 (`{"ui_ux": <UIUXAgent instance>}`). Đây chỉ là một
bước tra cứu (lookup) — không có gì "AI" ở đây, chỉ là "domain string" → "đúng object agent".
Nếu domain không tồn tại, raise `UnknownDomainError` — và nhờ Bước 1.(3), exception này tự động
biến thành HTTP 404 mà route/agent không cần biết gì về việc đó.

### Lớp 3 — Agent ([app/domains/ui_ux/agent.py](../app/domains/ui_ux/agent.py))

Đây là nơi "trí thông minh nghiệp vụ" thật sự nằm — cách build prompt cho domain UI/UX:

```python
async def handle(self, input: AgentInput) -> AgentOutput:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    user_message = {"role": "user", "content": input.prompt}
    if input.image_base64:
        user_message["images"] = [input.image_base64]
    messages.append(user_message)

    raw = await self.model_provider.chat(messages=messages)
    content = self.model_provider.extract_content(raw)

    return self._build_output(raw, content)
```

- `SYSTEM_PROMPT` ([app/domains/ui_ux/prompts.py](../app/domains/ui_ux/prompts.py)) là câu lệnh
  cố định "bạn là chuyên gia UI/UX, hãy nhận xét về...". Đây chính là chỗ bạn sẽ sửa nếu muốn agent
  hành xử khác đi — không phải sửa framework.
  chat 1 lần, không có tool, không có lặp lại nhiều bước ("loop") — xem `ROADMAP.md` để biết dự
  định thêm những thứ đó sau.
- `self.model_provider.chat(...)` — gọi sang Lớp 4. `self.model_provider` chính là object
  `OllamaProvider` **duy nhất** đã tạo ở Bước 3, được `Orchestrator` gán cho agent này lúc khởi
  tạo — không phải agent tự tạo provider mới.
- `extract_content(raw)` — quan trọng: agent **không tự bóc** JSON trả về từ Ollama
  (`raw["message"]["content"]`). Nó nhờ provider làm việc đó, vì provider mới biết rõ hình dạng
  response của Ollama và các quirk của nó (xem hộp bên dưới). Nếu mai sau đổi sang backend khác
  (không phải Ollama), chỉ cần viết provider mới — agent không đổi một dòng nào.
- `self._build_output(raw, content)` — hàm dùng chung trong `Agent` base class
  ([app/core/agent_base.py](../app/core/agent_base.py)), gói `content` thành `AgentOutput`, và chỉ
  đính kèm `raw` (toàn bộ payload thô từ Ollama) nếu đang chạy ở môi trường `dev` — tránh lộ dữ
  liệu nội bộ khi lên production.

### Lớp 4 — Provider ([app/core/model_provider/ollama_provider.py](../app/core/model_provider/ollama_provider.py))

```python
async def chat(self, messages, *, tools=None, think=None, **options):
    payload = {
        "model": self.model_name,
        "messages": messages,
        "stream": False,
        "think": self._think if think is None else think,
        "options": {"num_ctx": self._num_ctx, **options},
    }
    response = await self._client.post("/api/chat", json=payload)
    ...
    return response.json()
```

`self._client` chính là `httpx.AsyncClient` đã mở **một lần** ở Bước 3. Hàm này chỉ đơn giản là
gửi HTTP POST tới `http://localhost:11434/api/chat` (API của Ollama) và trả JSON thô về. Mọi lỗi
mạng/timeout/status code xấu được bắt và bọc lại thành `ProviderError` — để tầng trên (agent,
route) không phải tự viết `try/except httpx.TimeoutException` lặp đi lặp lại ở mọi nơi.

> **Vì sao có `extract_content` với regex `_LEAKED_THINK`?**
> Model dev (`qwen3:4b`) là model "biết suy luận" (reasoning model). Ngay cả khi mình bảo nó
> `think: false`, nó vẫn suy nghĩ — chỉ là Ollama không tách phần suy nghĩ đó ra field riêng nữa,
> mà nhét thẳng vào `message.content`, kết thúc bằng thẻ `</think>` (không có thẻ mở). Nếu không
> xử lý, client sẽ nhận được cả đống văn bản "để tôi nghĩ xem..." lẫn với câu trả lời thật.
> `extract_content` cắt bỏ phần đó, chỉ giữ lại câu trả lời thật sau thẻ `</think>`. Đây là ví dụ
> thực tế cho việc "kiến thức về hình dạng response của 1 model cụ thể nên nằm ở provider, không
> lan ra agent" — nếu để agent tự làm việc này, mỗi domain agent sẽ phải copy-paste cùng 1 đoạn xử
> lý.

### Đường về: kết quả chạy ngược từ Lớp 4 → Lớp 1

`await` ở mỗi lớp có nghĩa "đợi kết quả rồi mới đi tiếp" — không phải hàng đợi phức tạp gì, chỉ là
một chuỗi gọi hàm bất đồng bộ (`async`/`await`) đi xuống rồi trả kết quả đi lên, y hệt gọi hàm
bình thường, chỉ khác là trong lúc chờ Ollama trả lời (có thể vài chục giây tới vài phút trên
CPU), server vẫn rảnh tay xử lý request khác — đây là lý do toàn bộ chuỗi này dùng `async def` chứ
không dùng hàm đồng bộ thường.

Kết quả cuối: route trả `AgentOutput`, FastAPI serialize thành JSON, HTTP response bay ngược về
Go gateway rồi tới client.

## Nếu lỗi xảy ra ở đâu đó giữa chừng?

Ví dụ Ollama đang tắt hoặc timeout: `OllamaProvider.chat` raise `ProviderError`. Exception này
**không được bắt (catch)** ở agent hay route — nó cứ bay thẳng lên. Handler đã đăng ký ở Bước 1.(3)
(`register_exception_handlers`) chặn nó lại ở tầng FastAPI và trả về:

```json
{"error": {"code": "provider_error", "message": "Model request timed out: ..."}}
```

kèm HTTP status 502. Đây chính là lý do không thấy `try/except` rải rác khắp route/agent — có
đúng **một chỗ** xử lý việc biến lỗi nghiệp vụ thành HTTP response.

## Tóm tắt bằng một câu cho mỗi file

| File | Trả lời câu hỏi |
|---|---|
| `app/main.py` | App có gì, chạy handler nào khi lỗi, khi start/stop? |
| `app/core/config.py` | Giá trị cấu hình (URL Ollama, tên model,...) lấy từ đâu? |
| `app/core/lifespan.py` | Cái gì được dựng 1 lần lúc mở server? |
| `app/core/exceptions.py` | Lỗi nghiệp vụ biến thành HTTP status nào? |
| `app/core/orchestrator.py` | Request domain "ui_ux" thì lấy đúng agent nào? |
| `app/core/agent_base.py` | Mọi agent có chung khuôn gì? |
| `app/core/model_provider/*` | Nói chuyện với Ollama bằng cách nào, xử lý quirk gì? |
| `app/domains/registry.py` | Hệ thống hiện có những domain nào? |
| `app/domains/ui_ux/agent.py` | Domain UI/UX build prompt và xử lý kết quả ra sao? |
| `app/domains/ui_ux/prompts.py` | Model được dặn dò gì trước khi trả lời? |
| `app/schemas/agent.py` | Request/response JSON có hình dạng gì? |
| `app/api/router.py`, `app/api/ui_ux.py` | URL nào map tới domain nào? |

## Đọc tiếp

- Muốn hiểu quyết định kiến trúc (tại sao không có `/api/v1`, tại sao có `ModelProvider` interface
  thay vì gọi Ollama trực tiếp,...) → đọc [`CLAUDE.md`](../CLAUDE.md).
- Muốn biết cái gì sắp được thêm (tools, RAG, agent loop,...) và vì sao 27B/4B lại được thiết kế
  khác nhau → đọc [`ROADMAP.md`](../ROADMAP.md).
