"""Compatibility wrapper for the profiles streaming endpoint.

The real implementation lives in backend.endpoints.profiles.stream.
This module exists so older imports keep working.
"""

from backend.endpoints.profiles.stream import router, process_profile as process_profile_endpoint

__all__ = ["router", "process_profile_endpoint"]