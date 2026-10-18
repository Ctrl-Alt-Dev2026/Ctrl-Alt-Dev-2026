"""AI routes; approval/persistence remain the backend owner's responsibility."""
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from .service import ExtractionService


class ArticleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    article_id: StrictStr = Field(min_length=1)
    sursa: StrictStr
    url: StrictStr
    titlu: StrictStr
    text: StrictStr = Field(min_length=1, max_length=100_000)
    publicat_la: StrictStr
    colectat_la: StrictStr


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    article: ArticleInput
    pipeline: Literal["rules", "direct", "evidence", "agreement", "hybrid"] = "hybrid"
    mode: Literal["extract"] = "extract"


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["replay"]
    article_id: StrictStr = Field(min_length=1)


class PressCsvRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["press_csv"]
    pipeline: Literal["rules", "direct", "evidence", "agreement", "hybrid"] = "hybrid"
    limit: int | None = Field(default=None, gt=0, le=2000)


class GeminiCsvRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["gemini_csv"]
    limit: int | None = Field(default=None, gt=0, le=2000)
    cache_only: bool = True


class GeminiTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["gemini_test"]


@lru_cache(maxsize=1)
def get_service():
    # No provider connection, fixture read or cache directory creation at startup.
    return ExtractionService()


router = APIRouter(tags=["ai"])


def register_ai(application):
    """Compose the backend once, including when a legacy entry point is imported."""
    if not getattr(application.state, "safeiasi_ai_routes_registered", False):
        application.include_router(router)
        application.state.safeiasi_ai_routes_registered = True
        application.openapi_schema = None
    return application


@router.post("/api/v1/ai/extract", summary="Extract pending candidates; never approve events")
def extract(request: ExtractRequest | ReplayRequest | PressCsvRequest | GeminiCsvRequest | GeminiTestRequest, service: ExtractionService = Depends(get_service)):
    try:
        if isinstance(request, GeminiTestRequest):
            return service.test_gemini()
        if isinstance(request, GeminiCsvRequest):
            result = service.extract_gemini_csv(limit=request.limit, cache_only=request.cache_only)
            status_code = 409 if result.get("status") == "cache_miss" else (503 if result["errors"] else 200)
            return JSONResponse(status_code=status_code, content=result,
                                headers={"X-AI-Provider": "gemini"})
        if isinstance(request, ReplayRequest):
            return service.replay(request.article_id)
        if isinstance(request, PressCsvRequest):
            result = service.extract_clean_csv(pipeline=request.pipeline, limit=request.limit)
        else:
            result = service.extract(request.article.model_dump(), request.pipeline)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="saved synthetic replay not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="CSV-ul clean nu există în scraping/ pe server.") from exc
    return JSONResponse(status_code=503 if result["errors"] else 200, content=result)


# Compatibility with the P2 route in Planificare.md, without a second extractor.
router.add_api_route("/extract", extract, methods=["POST"], include_in_schema=False)


@router.get("/api/v1/ai/replays/{article_id}", summary="Explicitly labeled synthetic replay")
def replay(article_id: str, service: ExtractionService = Depends(get_service)):
    try:
        return service.replay(article_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="saved synthetic replay not found") from exc
