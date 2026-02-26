"""
app.services.classifier — query intent classification.

Public API:
  - QueryClassifier, get_query_classifier
  - QueryClassification (dataclass)
"""
from app.services.classifier.engine import (
    QueryClassifier,
    QueryClassification,
    get_query_classifier,
)

__all__ = [
    "QueryClassifier",
    "QueryClassification",
    "get_query_classifier",
]
