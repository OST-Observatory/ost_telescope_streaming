import logging
import sys
from pathlib import Path

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import config
from overlay_runner import OverlayRunner
import argparse

if __name__ == "__main__":
    print("OST Telescope Streaming - Overlay Runner")
    print("=" * 50)
    logger = logging.getLogger("overlay_runner_cli")
    runner = OverlayRunner(config=config, logger=logger)
    runner.run() 