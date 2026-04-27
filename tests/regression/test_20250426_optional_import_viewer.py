"""
REGRESSION TEST: Missing Optional import in viewer.py
======================================================

Date: 2025-04-26
File: backend/routes/viewer.py
Symptom: Module fails to load due to NameError: name 'Optional' is not defined
Root Cause: viewer.py uses Optional[str] in function signature but doesn't import Optional from typing
Fix: Added 'from typing import Optional' at top of file
Verify: App should import without errors, tests should pass
"""

import pytest


def test_viewer_module_imports_without_error():
    """
    Test that viewer.py can be imported without NameError.
    
    This was failing with:
        NameError: name 'Optional' is not defined
    
    At line 119: def _extract_job_source(data: dict) -> Optional[str]:
    """
    # This should not raise any exceptions
    try:
        from backend.routes import viewer
    except NameError as e:
        pytest.fail(f"viewer.py failed to import: {e}")


def test_main_app_imports_without_error():
    """
    Test that the main FastAPI app can be imported.
    
    This imports viewer indirectly through the route imports.
    """
    try:
        from backend.main import app
    except NameError as e:
        pytest.fail(f"main.py failed to import: {e}")
