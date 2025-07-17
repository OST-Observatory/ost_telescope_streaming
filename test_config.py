#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for configuration system
"""

import sys
import os

# Add the code directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

try:
    from config_manager import config
    
    print("Testing configuration system...")
    print("=" * 40)
    
    # Test basic configuration loading
    print(f"Config path: {config.config_path}")
    print(f"Config loaded: {config.config is not None}")
    
    # Test some configuration values
    fov = config.get('overlay.field_of_view', 1.5)
    print(f"Field of view: {fov}")
    
    update_interval = config.get('streaming.update_interval', 30)
    print(f"Update interval: {update_interval}")
    
    # Test mount configuration
    mount_config = config.get_mount_config()
    print(f"Mount driver: {mount_config.get('driver_id', 'Not set')}")
    
    print("Configuration test completed successfully!")
    
except Exception as e:
    print(f"Error during configuration test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 