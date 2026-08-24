from fastapi import FastAPI

from backend.api.ingestion import router as ingestion_router

app = FastAPI(title="ADDT Backend")
app.include_router(ingestion_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
