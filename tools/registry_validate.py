"""
COM-AI v3 - Registry Validator  
MANDATORY tool for registry compliance per handover documentation
"""

import json
import csv
import os
from pathlib import Path
import sys

def validate_file_structure():
    """Validate that required directories and files exist"""
    print("🔍 Validating project file structure...")
    
    required_dirs = ['src', 'src/api', 'src/brain', 'src/memory', 'src/utils', 'tools', 'tests']
    required_files = [
        'src/__init__.py',
        'src/api/__init__.py', 
        'src/brain/__init__.py',
        'src/memory/__init__.py',
        'src/utils/__init__.py',
        'tools/__init__.py',
        'tests/__init__.py',
        '.env.example',
        'requirements.txt'
    ]
    
    errors = []
    
    # Check directories
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            errors.append(f"Missing required directory: {dir_path}")
        else:
            print(f"✅ Directory exists: {dir_path}")
    
    # Check files  
    for file_path in required_files:
        if not Path(file_path).exists():
            errors.append(f"Missing required file: {file_path}")
        else:
            print(f"✅ File exists: {file_path}")
    
    return errors

def validate_naming_convention():
    """Validate that files follow snake_case naming convention"""
    print("🐍 Validating snake_case naming convention...")
    
    errors = []
    
    for py_file in Path('src').rglob('*.py'):
        filename = py_file.name
        if filename != '__init__.py':
            # Check if filename is snake_case
            if '-' in filename or ' ' in filename:
                errors.append(f"File not in snake_case: {py_file}")
            elif filename.lower() != filename:
                if not (filename.startswith('__') and filename.endswith('__')):
                    errors.append(f"File not in snake_case: {py_file}")
            else:
                print(f"✅ Naming compliant: {py_file}")
    
    return errors

def validate_imports():
    """Basic validation of Python imports"""
    print("📦 Validating Python imports...")
    
    errors = []
    
    # Test import of main modules
    try:
        sys.path.insert(0, str(Path.cwd()))
        
        # Test basic imports
        import src.utils.config
        print("✅ Config module imports successfully")
        
        import src.utils.logging_config
        print("✅ Logging config imports successfully")
        
    except ImportError as e:
        errors.append(f"Import error: {e}")
    
    return errors

def validate_registry():
    """Main registry validation function"""
    print("🚀 Starting COM-AI v3 Registry Validation")
    print("=" * 50)
    
    all_errors = []
    
    # Run all validations
    all_errors.extend(validate_file_structure())
    all_errors.extend(validate_naming_convention()) 
    all_errors.extend(validate_imports())
    
    print("=" * 50)
    
    if all_errors:
        print(f"❌ Registry validation FAILED with {len(all_errors)} errors:")
        for error in all_errors:
            print(f"  • {error}")
        return False
    else:
        print("✅ Registry validation PASSED - All checks successful!")
        return True

if __name__ == '__main__':
    success = validate_registry()
    exit(0 if success else 1)