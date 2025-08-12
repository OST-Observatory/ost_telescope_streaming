#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean Python cache files
"""

import os
import shutil
import glob

def clean_python_cache():
    """Remove all Python cache files and directories."""
    print("Cleaning Python cache files...")
    
    # Patterns to match cache files
    cache_patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        "**/*.pyd"
    ]
    
    cleaned_count = 0
    
    for pattern in cache_patterns:
        for path in glob.glob(pattern, recursive=True):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    print(f"Removed directory: {path}")
                else:
                    os.remove(path)
                    print(f"Removed file: {path}")
                cleaned_count += 1
            except Exception as e:
                print(f"Warning: Could not remove {path}: {e}")
    
    print(f"Cleaned {cleaned_count} cache files/directories")
    print("Cache cleaning completed!")

if __name__ == "__main__":
    clean_python_cache() 