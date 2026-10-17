"""Compose pattern exploration with the existing extraction/backend application."""
from ai.app import create_app as create_ai_app
from .router import router


def create_app(snapshot_directory=None):
    application = create_ai_app(snapshot_directory)
    application.include_router(router)
    return application


app = create_app()
