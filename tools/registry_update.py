"""
COM-AI v3 - Registry Update Tool
"""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def update_registry():
    """Update registry after file changes"""
    print("🔄 Updating registry...")
    
    # This will integrate with generate_manifest.py
    from tools.generate_manifest import generate_manifest
    
    try:
        generate_manifest('.', write_registry=True)
        print("✅ Registry updated successfully")
        return True
    except Exception as e:
        print(f"❌ Registry update failed: {e}")
        return False

if __name__ == '__main__':
    success = update_registry()
    exit(0 if success else 1)