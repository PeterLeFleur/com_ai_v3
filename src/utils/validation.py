"""
COM-AI v3 - Input Validation Utilities
"""

from typing import Any, Dict
import re

def validate_task_id(task_id: str) -> bool:
    """Validate task ID format (e.g., API-001, BRAIN-002)"""
    pattern = r'^[A-Z]+-\d{3}$'
    return bool(re.match(pattern, task_id))

def validate_provider_name(name: str) -> bool:
    """Validate provider name format"""
    return bool(re.match(r'^[a-z_]+$', name))

def sanitize_input(text: str) -> str:
    """Sanitize user input"""
    # Basic sanitization - expand as needed
    return text.strip()