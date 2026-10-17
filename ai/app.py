"""Compatibility entry point; the backend now includes AI routes by default."""
from api.main import app, create_app

from .router import register_ai
