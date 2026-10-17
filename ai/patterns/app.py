"""Compatibility entry point; the standard backend includes pattern routes."""
from api.main import app, create_app
from .router import register_patterns
