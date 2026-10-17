"""Serve the optional Angular build on the API's loopback origin.

Missing frontend assets never stop the backend or cause a fixture fallback.
The Angular hash router keeps navigation inside /ui/.
"""

from pathlib import Path
import re

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from api.review_router import require_local


DEFAULT_FRONTEND_DIRECTORY = Path(__file__).resolve().parents[1] / "web" / "dist" / "web" / "browser"


class LocalFrontend(StaticFiles):
    def __init__(self, directory):
        self.frontend_directory = Path(directory)
        super().__init__(directory=str(directory), html=True, check_dir=False, follow_symlink=False)

    async def __call__(self, scope, receive, send):
        try:
            require_local(Request(scope, receive))
        except HTTPException as error:
            return await JSONResponse({"detail": error.detail}, status_code=error.status_code)(scope, receive, send)
        try:
            index = (self.frontend_directory / "index.html").read_bytes()
            ready = re.search(rb"<base\s+href=[\"']/ui/[\"']\s*/?>", index, re.IGNORECASE) is not None
        except OSError:
            ready = False
        if not ready:
            return await JSONResponse(status_code=503, content={"detail": {
                "code": "frontend_build_unavailable",
                "message": "Construiește interfața din web/ cu npm run build:local, apoi reîncarcă /ui/.",
            }})(scope, receive, send)
        await super().__call__(scope, receive, send)


def register_frontend(application, directory=None):
    application.mount("/ui", LocalFrontend(directory or DEFAULT_FRONTEND_DIRECTORY), name="safeiasi-ui")
    return application
