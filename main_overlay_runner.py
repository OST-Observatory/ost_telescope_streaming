import logging
from code.config_manager import config
from code.overlay_runner import OverlayRunner

if __name__ == "__main__":
    print("OST Telescope Streaming - Overlay Runner")
    print("=" * 50)
    logger = logging.getLogger("overlay_runner_cli")
    runner = OverlayRunner(config=config, logger=logger)
    runner.run() 