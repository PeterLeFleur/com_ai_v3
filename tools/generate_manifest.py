"""
COM-AI v3 - Manifest Generator
MANDATORY tool for registry compliance per handover documentation
"""

import json
import os
import csv
import argparse
from datetime import datetime
from pathlib import Path
import hashlib

# Files and patterns to exclude from manifest
EXCLUDE_PATTERNS = [
    '__pycache__',
    '*.pyc', 
    '*.pyo',
    '.pytest_cache',
    '*.egg-info',
    '.coverage',
    'coverage.xml',
    '.mypy_cache'
]

EXCLUDE_FILES = [
    '__init__.py'  # Optional: exclude empty __init__.py files
]

def should_exclude_file(filepath: Path) -> bool:
    """Check if file should be excluded from manifest"""
    # Check if it's an excluded filename
    if filepath.name in EXCLUDE_FILES and filepath.stat().st_size < 50:  # Only exclude small __init__.py files
        return True
    
    # Check exclude patterns
    for pattern in EXCLUDE_PATTERNS:
        if pattern in str(filepath):
            return True
    
    return False

def generate_file_hash(filepath: str) -> str:
    """Generate MD5 hash of file contents"""
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return "error"

def scan_project_files(repo_path: str) -> list:
    """Scan project and return list of tracked files"""
    tracked_files = []
    repo_root = Path(repo_path)
    
    # Directories to scan
    scan_dirs = ['src', 'tools', 'tests']
    
    for scan_dir in scan_dirs:
        scan_path = repo_root / scan_dir
        if scan_path.exists():
            for py_file in scan_path.rglob('*.py'):
                # Skip excluded files
                if should_exclude_file(py_file):
                    continue
                    
                rel_path = py_file.relative_to(repo_root)
                file_info = {
                    'path': str(rel_path).replace('\\', '/'),
                    'size': py_file.stat().st_size,
                    'modified': datetime.fromtimestamp(py_file.stat().st_mtime).isoformat(),
                    'hash': generate_file_hash(str(py_file)),
                    'type': 'python'
                }
                tracked_files.append(file_info)
    
    return tracked_files

def generate_manifest(repo_path: str, write_registry: bool = False):
    """Generate manifest.json and optionally FILE_REGISTRY.csv"""
    print("🔧 Generating project manifest...")
    
    tracked_files = scan_project_files(repo_path)
    
    manifest = {
        'generated_at': datetime.now().isoformat(),
        'project': 'com_ai_v3',
        'version': '3.0.0',
        'total_files': len(tracked_files),
        'files': tracked_files
    }
    
    # Write manifest.json
    manifest_path = Path(repo_path) / 'manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✅ Generated manifest.json with {len(tracked_files)} files")
    
    # Write registry if requested
    if write_registry:
        registry_path = Path(repo_path) / 'FILE_REGISTRY.csv'
        with open(registry_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['path', 'type', 'size', 'hash', 'modified'])
            for file_info in tracked_files:
                writer.writerow([
                    file_info['path'],
                    file_info['type'], 
                    file_info['size'],
                    file_info['hash'],
                    file_info['modified']
                ])
        print(f"✅ Generated FILE_REGISTRY.csv")
    
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate project manifest')
    parser.add_argument('--repo', default='.', help='Repository root path')
    parser.add_argument('--write-registry', action='store_true', help='Also generate FILE_REGISTRY.csv')
    
    args = parser.parse_args()
    
    try:
        manifest = generate_manifest(args.repo, args.write_registry)
        print("🎯 Manifest generation completed successfully")
    except Exception as e:
        print(f"❌ Manifest generation failed: {e}")
        exit(1)