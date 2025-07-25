#!/usr/bin/env python3
"""
Test utilities for OST Telescope Streaming.
Provides flexible configuration management and common test functions.
"""

import sys
import os
import argparse
from pathlib import Path
import logging

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from config_manager import ConfigManager

def setup_logging(level=logging.INFO):
    """Setup logging for tests.
    
    Args:
        level: Logging level (default: INFO)
    
    Returns:
        Logger instance
    """
    # Configure root logger to ensure all loggers use the same configuration
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True  # Force reconfiguration
    )
    
    # Set level for all loggers to ensure consistency
    logging.getLogger().setLevel(level)
    
    # Also set level for common module loggers
    logging.getLogger('ascom_camera').setLevel(level)
    logging.getLogger('config_manager').setLevel(level)
    logging.getLogger('video_capture').setLevel(level)
    logging.getLogger('video_processor').setLevel(level)
    logging.getLogger('plate_solver').setLevel(level)
    logging.getLogger('overlay_runner').setLevel(level)
    
    return logging.getLogger("test_utils")

def get_test_config(config_path=None):
    """Get configuration for tests.
    
    Args:
        config_path: Optional path to config file. If None, uses default config.
    
    Returns:
        ConfigManager instance
    """
    if config_path:
        # Make relative paths relative to tests directory
        if not os.path.isabs(config_path):
            tests_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(tests_dir, config_path)
        
        # Use custom config file
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        return ConfigManager(config_path=config_path)
    else:
        # Use default config
        return ConfigManager()

def get_ascom_driver_from_config(config):
    """Get ASCOM driver ID from configuration.
    
    Args:
        config: ConfigManager instance
    
    Returns:
        ASCOM driver ID string
    """
    video_config = config.get_video_config()
    return video_config['ascom']['ascom_driver']

def parse_test_args(description="Test script"):
    """Parse command line arguments for tests.
    
    Args:
        description: Description for argument parser
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", "-c", 
                       help="Path to custom config file")
    parser.add_argument("--driver", "-d",
                       help="ASCOM driver ID (overrides config)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging (DEBUG level)")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging (same as --verbose)")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="Enable quiet logging (WARNING level only)")
    return parser.parse_args()

def setup_test_environment(args=None):
    """Setup test environment with configuration and logging.
    
    Args:
        args: Optional parsed arguments. If None, will parse from command line.
    
    Returns:
        Tuple of (config, logger, driver_id)
    """
    if args is None:
        args = parse_test_args()
    
    # Setup logging
    if args.debug or args.verbose:
        logger = setup_logging(logging.DEBUG)
    elif args.quiet:
        logger = setup_logging(logging.WARNING)
    else:
        logger = setup_logging(logging.INFO)  # Default: INFO level
    
    # Get configuration
    try:
        config = get_test_config(args.config)
        logger.info(f"Configuration loaded from: {config.config_path}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise
    
    # Get ASCOM driver
    if args.driver:
        driver_id = args.driver
        logger.info(f"Using ASCOM driver from command line: {driver_id}")
    else:
        driver_id = get_ascom_driver_from_config(config)
        logger.info(f"Using ASCOM driver from config: {driver_id}")
    
    return config, logger, driver_id

def print_test_header(test_name, driver_id=None, config_path=None):
    """Print a formatted test header.
    
    Args:
        test_name: Name of the test
        driver_id: Optional ASCOM driver ID to display
        config_path: Optional config file path to display
    """
    print("=" * 60)
    print(f"TEST: {test_name}")
    print("=" * 60)
    if driver_id:
        print(f"ASCOM Driver: {driver_id}")
    if config_path:
        print(f"Config File: {config_path}")
    print()

def print_test_result(success, message):
    """Print a formatted test result.
    
    Args:
        success: Boolean indicating success/failure
        message: Result message
    """
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")

def get_cache_file_path(driver_id):
    """Get cache file path for a given driver ID.
    
    Args:
        driver_id: ASCOM driver ID
    
    Returns:
        Path to cache file
    """
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'cache')
    cache_filename = f'cooling_cache_{driver_id.replace(".", "_").replace(":", "_")}.json'
    return os.path.join(cache_dir, cache_filename)

def check_cache_file(driver_id):
    """Check if cache file exists and return its content.
    
    Args:
        driver_id: ASCOM driver ID
    
    Returns:
        Tuple of (exists, content) where content is None if file doesn't exist
    """
    import json
    cache_file = get_cache_file_path(driver_id)
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                content = json.load(f)
            return True, content
        except Exception as e:
            return True, f"Error reading cache: {e}"
    else:
        return False, None 