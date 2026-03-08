# Ontology is always importable (no ADK dependency).
# Agent (root_agent) is imported lazily in main.py via _try_import_adk()
# so that the server starts gracefully even when google-adk is unavailable.
from .ontology import graph

__all__ = ["graph"]
