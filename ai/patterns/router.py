"""Pattern exploration routes; never mutate the snapshot or approved records."""
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .service import PatternService

router = APIRouter(tags=['AI pattern exploration'])
service = PatternService()
DEMO_PATH = Path(__file__).parent / 'static' / 'index.html'


def register_patterns(application):
    """Register once across current and compatibility application entry points."""
    if not getattr(application.state, 'safeiasi_pattern_routes_registered', False):
        application.include_router(router)
        application.state.safeiasi_pattern_routes_registered = True
        application.openapi_schema = None
    return application


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    excluded: list[str] = Field(default_factory=list, max_length=100)
    threshold: float = Field(default=.35, ge=.10, le=.95)
    scope: Literal['fixtures', 'sources'] = 'fixtures'


@router.get('/patterns', include_in_schema=False)
def demo():
    try:
        service.validate_demo(DEMO_PATH)
        return FileResponse(DEMO_PATH)
    except (ValueError, OSError, KeyError) as exc:
        raise HTTPException(503, detail={'code': 'patterns_unprepared', 'message': str(exc)}) from exc


@router.get('/api/v1/ai/patterns/corpus')
def corpus():
    try:
        return service.load()
    except (ValueError, OSError, KeyError) as exc:
        raise HTTPException(503, detail={'code': 'patterns_unprepared', 'message': str(exc)}) from exc


@router.post('/api/v1/ai/patterns/discover')
def patterns(request: DiscoveryRequest):
    try:
        return service.discover(**request.model_dump())
    except ValueError as exc:
        if str(exc).startswith(('scope ', 'Unknown excluded')):
            raise HTTPException(422, detail=str(exc)) from exc
        raise HTTPException(503, detail={'code': 'patterns_unprepared', 'message': str(exc)}) from exc
    except (OSError, KeyError) as exc:
        raise HTTPException(503, detail={'code': 'patterns_unprepared', 'message': str(exc)}) from exc
