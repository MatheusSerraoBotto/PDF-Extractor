"""
Post-processing and validation utilities (stub).

Normalize formats, run regex validation, and compute confidence scores based on
source (heuristic vs LLM) and verification checks.
"""

from typing import Dict, Any


def validate_and_normalize(fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate field formats and normalize values.
    Current stub: returns the same dictionary unchanged.
    """
    # Later:
    # - apply regex for CPF/phone
    # - uppercase normalization for categories
    # - strip and canonicalize whitespace
    return fields
