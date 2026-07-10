from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, conversations, documents, settings, webhook
from app.worker.queue import close_arq_pool

app = FastAPI(title="WhatsApp AI Receptionist")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(settings.router)
app.include_router(conversations.router)
app.include_router(webhook.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_arq_pool()
