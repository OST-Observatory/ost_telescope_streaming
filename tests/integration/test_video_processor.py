import logging
from pathlib import Path
import sys

import pytest

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

import argparse
import time

from config_manager import ConfigManager
from processing.processor import VideoProcessor

pytestmark = pytest.mark.integration


def main():
    parser = argparse.ArgumentParser(description="Test video processor")
    parser.add_argument("--config", type=str, help="Path to configuration file")

    # Parse config argument first to load the right configuration
    args, remaining = parser.parse_known_args()

    # Load configuration
    if args.config:
        config = ConfigManager(config_path=args.config)
    else:
        config = ConfigManager()

    # Recreate parser with the loaded configuration defaults
    parser = argparse.ArgumentParser(description="Test video processor")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument(
        "--interval", type=int, default=10, help="Plate-solving interval in seconds"
    )
    parser.add_argument("--solve", action="store_true", help="Enable plate-solving")
    args = parser.parse_args()

    def on_solve_result(result):
        print(f"Plate-solving result: {result}")

    def on_capture_frame(frame, filename):
        print(f"Frame captured: {filename}")

    def on_error(error):
        print(f"Error: {error}")

    # Override config for testing
    config["video"]["video_enabled"] = True
    config["plate_solve"]["auto_solve"] = True
    config["plate_solve"]["min_solve_interval"] = args.interval

    logger = logging.getLogger("video_processor_cli")
    processor = VideoProcessor(config=config, logger=logger)
    processor.set_callbacks(on_solve_result, on_capture_frame, on_error)
    print(f"Starting video processor test for {args.duration} seconds...")
    status = processor.start()
    print(f"Status: {status.level.value.upper()} - {status.message}")
    if status.details:
        print(f"Details: {status.details}")
    if status.is_success:
        try:
            time.sleep(args.duration)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            stop_status = processor.stop()
            print(f"Status: {stop_status.level.value.upper()} - {stop_status.message}")
            if stop_status.details:
                print(f"Details: {stop_status.details}")
            stats = processor.get_statistics()
            print("\nStatistics:")
            if stats.data:
                for key, value in stats.data.items():
                    print(f"  {key}: {value}")
    else:
        print("Failed to start video processor")


# __main__ runner removed; use pytest to execute tests.
