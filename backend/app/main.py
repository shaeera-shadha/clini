"""HTTP API. `POST /generate` streams stage events as SSE when the client accepts
`text/event-stream`, otherwise it returns the final JSON result. `POST /baseline` returns the
plain-summary comparison; `GET /eval` serves the latest saved evaluation report."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.baseline import run_baseline
from app.cache import BaselineCache, NoteCache
from app.clients import get_baseline_cache, get_client, get_result_cache
from app.config import DATA_DIR, Settings, get_settings
from app.errors import PipelineError
from app.evaluation import EvalReport
from app.llm import LLMClient, MockLLM
from app.pipeline import ResultEvent, StageEvent, generate, run_pipeline
from app.samples import get_sample, list_samples
from app.schemas import (
    BaselineResult,
    GenerateRequest,
    GenerateResult,
    HealthResponse,
    Sample,
    SampleSummary,
    TextResponse,
)
from app.transcribe import transcribe_audio
from app.upload import extract_text_from_file

log = logging.getLogger("clinnote")

SettingsDep = Annotated[Settings, Depends(get_settings)]
ClientDep = Annotated[LLMClient, Depends(get_client)]
CacheDep = Annotated[NoteCache | None, Depends(get_result_cache)]
BaselineCacheDep = Annotated[BaselineCache | None, Depends(get_baseline_cache)]

EVAL_REPORT = DATA_DIR / "eval" / "latest.json"

app = FastAPI(title="ClinNote API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(PipelineError)
async def _pipeline_error(_: Request, exc: PipelineError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message})


@app.get("/health")
def health(settings: SettingsDep, client: ClientDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        mode=settings.llm_mode,
        models={"extractor": settings.extractor_model, "verifier": settings.verifier_model},
        fixtures="; ".join(sorted(client.sources)) if isinstance(client, MockLLM) else None,
    )


@app.get("/samples")
def samples() -> list[SampleSummary]:
    return list_samples()


@app.get("/samples/{sample_id}")
def sample(sample_id: str) -> Sample:
    return get_sample(sample_id)


def _resolve_transcript(body: GenerateRequest) -> str:
    if body.sample_id:
        return get_sample(body.sample_id).transcript
    if body.transcript is not None:
        return body.transcript
    raise PipelineError("empty_transcript", "Send a transcript or choose a sample.")


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream(
    transcript: str, client: LLMClient, settings: Settings, cache: NoteCache | None
) -> AsyncIterator[str]:
    try:
        async for event in run_pipeline(transcript, client, settings, cache):
            if isinstance(event, StageEvent):
                yield _sse("stage", {"stage": event.stage, "state": event.state, "ms": event.ms})
            elif isinstance(event, ResultEvent):
                yield _sse("result", event.result.model_dump(mode="json"))
    except PipelineError as exc:
        yield _sse("error", {"code": exc.code, "message": exc.message})
    except Exception:
        log.exception("Unexpected pipeline failure")
        yield _sse(
            "error",
            {"code": "internal", "message": "Something went wrong while generating the note."},
        )


@app.post("/generate", response_model=None)
async def generate_note(
    body: GenerateRequest,
    request: Request,
    settings: SettingsDep,
    client: ClientDep,
    cache: CacheDep,
) -> StreamingResponse | GenerateResult:
    transcript = _resolve_transcript(body)
    if "text/event-stream" in request.headers.get("accept", ""):
        return StreamingResponse(
            _stream(transcript, client, settings, cache),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return await generate(transcript, client, settings, cache)


@app.post("/baseline")
async def baseline(
    body: GenerateRequest, settings: SettingsDep, client: ClientDep, cache: BaselineCacheDep
) -> BaselineResult:
    return await run_baseline(_resolve_transcript(body), client, settings, cache)


@app.post("/extract-text")
async def extract_text(file: UploadFile) -> TextResponse:
    text = await extract_text_from_file(file)
    return TextResponse(text=text)


@app.post("/transcribe")
async def transcribe(file: UploadFile, settings: SettingsDep) -> TextResponse:
    text = await transcribe_audio(file, settings)
    return TextResponse(text=text)


@app.get("/eval")
def evaluation() -> EvalReport:
    if not EVAL_REPORT.exists():
        raise PipelineError(
            "eval_missing",
            "No evaluation has been run yet. From backend/, run: python -m eval.run_eval",
            404,
        )
    return EvalReport.model_validate_json(EVAL_REPORT.read_text(encoding="utf-8"))
