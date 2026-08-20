"""Exposing our system through an API"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from RAG_pipeline import RAGPipeline

pipeline: RAGPipeline | None = (
    None  # this pipeline will get replaced by a real RAGPipeline instance once the server starts
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    pipeline = RAGPipeline()
    yield  # everything above yield will be executed only once at server startup. We avoid creating a new instance every time we start the server.
    pipeline.close()  # everything below yield will be closed once the server is shut down


app = FastAPI(
    title="RAG API", lifespan=lifespan
)  # lifespan is what actually exucutes everything below/above yield at startup/shutdown of the server

# browser blocks request that come from different ports. To overcome this issue, I use  CORS so that my
# fronted (running on port 5173) does not crash becuase my FastAPI application comes from port 8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # vite dev server
        "http://127.0.0.1.5173",
        "http://localhost:8000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Pydantic models
class Query(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=50)


class Source(BaseModel):
    citation: int
    id: int | None = None
    source: str
    page_numbers: list[int] = []
    headings: list[str] = []


class Chunk(BaseModel):
    id: int
    content: str
    metadata: dict[str, Any]
    rank: int
    rrf_score: float


class Answer(BaseModel):
    answer: str
    sources: list[Source]
    model: str
    chunks: list[Chunk] = []


# End point to check the health of the app. It return the number of chunks
@app.get("/health")
def health() -> dict[str, Any]:
    try:
        return {"status": "ok", "chunks": pipeline.vector_store.count()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"database unreachable: {e}")


# End point to search and generate the answer
@app.post("/search")
def search(request: Query) -> list[dict[str, Any]]:
    return pipeline.search(request.query, request.top_k)


# End point to generate answer based on top most relevant chunks
@app.post("/answer", response_model=Answer)
def answer(request: Query) -> dict[str, Any]:
    try:
        return pipeline.ask(request.query, top_k=request.top_k)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"generation failed: {e}")
