from fastapi import FastAPI

app = FastAPI(title="Catronaut ai-service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
