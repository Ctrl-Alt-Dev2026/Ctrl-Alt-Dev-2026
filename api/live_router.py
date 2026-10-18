"""Public read-only access to the collected dataset (isu/), refreshed by a background scheduler.

GET  /api/v1/live/status   cheap: when the data was built, when the next collection runs, last run outcome
GET  /api/v1/live/dataset  the newest dataset, with cached street analysis and precise-only H3
POST /api/v1/live/refresh  local only: start a collection now

The scheduler runs only with SAFEIASI_LIVE=1 (the run scripts and docker-compose set it), so tests and other
tools that create the app never touch the network. Without it the newest stored dataset is still served.
"""
from __future__ import annotations

import os
from contextlib import closing

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.review_router import require_local
from isu import store
from isu.live import REFRESH_MIN, Scheduler
from risk.streets import REVISION, enrich_payload

router = APIRouter(prefix="/api/v1/live", tags=["live"])


def start_live(application) -> Scheduler | None:
    """Called from the app lifespan; returns the running scheduler, or None when collection is off."""
    application.state.live_scheduler = None
    if os.environ.get("SAFEIASI_LIVE", "0") != "1":
        return None
    scheduler = Scheduler()
    scheduler.start()
    application.state.live_scheduler = scheduler
    return scheduler


def _scheduler(request: Request) -> Scheduler | None:
    return getattr(request.app.state, "live_scheduler", None)


@router.get("/status", summary="Starea colectării automate")
def status(request: Request):
    scheduler = _scheduler(request)
    with closing(store.connect()) as db:
        latest = store.latest_dataset(db)
        runs = store.last_runs(db, 1)
    return {
        "colectare_automata": scheduler is not None,
        "interval_minute": REFRESH_MIN,
        "construit_la": latest["built_at"] if latest else None,
        "ruleaza": bool(scheduler and scheduler.running),
        "urmatoarea_rulare": scheduler.next_run_at.isoformat() if scheduler and scheduler.next_run_at else None,
        "ultima_rulare": runs[0] if runs else None,
    }


@router.get("/dataset", summary="Setul de date cel mai recent", responses={503: {"description": "Nicio colectare încheiată încă."}})
def dataset():
    with closing(store.connect()) as db:
        latest = store.latest_dataset(db)
    if latest is None:
        raise HTTPException(status_code=503, detail={
            "code": "dataset_not_ready",
            "message": "Prima colectare nu s-a încheiat încă. Datele apar automat după ea.",
        })
    # Cached by payload: old SQLite snapshots receive the same contract as new collections.
    return Response(content=enrich_payload(latest["payload"]), media_type="application/json",
                    headers={"Cache-Control": "no-cache", "ETag": f'"{latest["id"]}-{REVISION}"'})


@router.post("/refresh", status_code=202, dependencies=[Depends(require_local)], summary="Pornește o colectare acum (local)")
def refresh(request: Request):
    scheduler = _scheduler(request)
    if scheduler is None:
        raise HTTPException(status_code=409, detail="Colectarea automată este oprită (SAFEIASI_LIVE≠1). Rulează: python -m isu")
    scheduler.trigger()
    return {"ruleaza": scheduler.running, "pornita": True}


def register_live(application):
    application.include_router(router)
    return application
