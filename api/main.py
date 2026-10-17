"""Local SafeIasi API foundation, independent of datasets and AI services."""

from typing import Literal

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["safeiasi-api"] = "safeiasi-api"


app = FastAPI(
    title="SafeIași API",
    version="0.1.0",
    description=(
        "Server local în etapa de pornire. /health confirmă doar că API-ul rulează; "
        "nu verifică date, extracție AI sau alte servicii."
    ),
)


@app.get("/", include_in_schema=False)
async def index():
    return RedirectResponse(url="/docs")


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Verifică pornirea serverului local",
    description="Verificare de funcționare a procesului, independentă de date și chei API.",
)
async def health() -> HealthResponse:
    return HealthResponse()
