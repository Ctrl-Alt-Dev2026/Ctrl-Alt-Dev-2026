"""Optional entry point preserving the backend app, factory and snapshot lifespan."""
from api.main import app as backend_app, create_app as create_backend_app

from .router import router

def register_ai(application):
    if not getattr(application.state, "safeiasi_ai_routes_registered", False):
        application.include_router(router)
        application.state.safeiasi_ai_routes_registered = True
        application.openapi_schema = None
    return application


def create_app(snapshot_directory=None):
    """Same snapshot_directory seam as api.main.create_app, with AI routes added."""
    return register_ai(create_backend_app(snapshot_directory))


app = register_ai(backend_app)
