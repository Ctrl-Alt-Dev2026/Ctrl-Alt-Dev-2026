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
def extract(request: ExtractRequest | ReplayRequest, service: ExtractionService = Depends(get_service)):
    try:
        if isinstance(request, ReplayRequest):
            return service.replay(request.article_id)
        result = service.extract(request.article.model_dump(), request.pipeline)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="saved synthetic replay not found") from exc
    return JSONResponse(status_code=503 if result["errors"] else 200, content=result)


# Compatibility with the P2 route in Planificare.md, without a second extractor.
router.add_api_route("/extract", extract, methods=["POST"], include_in_schema=False)


@router.get("/api/v1/ai/replays/{article_id}", summary="Explicitly labeled synthetic replay")
def replay(article_id: str, service: ExtractionService = Depends(get_service)):
    try:
        return service.replay(article_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="saved synthetic replay not found") from exc
