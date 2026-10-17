"""Person 2 extraction interface; importing this package needs no AI service."""
from .service import ExtractionConfig, ExtractionService, ExtractionUnavailable, extract_article

__all__ = ["ExtractionConfig", "ExtractionService", "ExtractionUnavailable", "extract_article"]
