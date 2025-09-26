"""
COM-AI v3 - Environment Setup Helper
"""

import subprocess
import sys
from pathlib import Path

def setup_environment():
    """Set up development environment"""
    print("🔧 Setting up COM-AI v3 development environment...")
    
    # Create virtual environment
    print("📦 Creating virtual environment...")
    subprocess.run([sys.executable, '-m', 'venv', '.venv'])
    
    # Install dependencies
    print("⬇️ Installing dependencies...")
    venv_python = Path('.venv/Scripts/python.exe') if sys.platform == 'win32' else Path('.venv/bin/python')
    
    subprocess.run([str(venv_python), '-m', 'pip', 'install', '-r', 'requirements.txt'])
    subprocess.run([str(venv_python), '-m', 'pip', 'install', '-r', 'requirements-dev.txt'])
    
    print("✅ Environment setup complete!")

if __name__ == '__main__':
    setup_environment()