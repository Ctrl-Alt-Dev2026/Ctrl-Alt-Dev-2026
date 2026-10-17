"""Opt-in routes; never mutate the snapshot or approved records."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .service import PatternService

router = APIRouter(tags=['AI pattern exploration'])
service = PatternService()


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    excluded: list[str] = Field(default_factory=list, max_length=100)
    threshold: float = Field(default=.35, ge=.10, le=.95)
    scope: str = 'fixtures'


@router.get('/patterns', include_in_schema=False)
def demo():
    return FileResponse(Path(__file__).parent / 'static' / 'index.html')


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
