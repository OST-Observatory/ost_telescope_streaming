import logging
from pathlib import Path
import sys

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

import argparse
import time

from config_manager import ConfigManager
from drivers.ascom.mount import ASCOMMount


def main():
    parser = argparse.ArgumentParser(description="ASCOM mount control")
    parser.add_argument("--config", type=str, help="Path to configuration file")

    # Parse config argument first to load the right configuration
    args, remaining = parser.parse_known_args()

    # Load configuration
    if args.config:
        config = ConfigManager(config_path=args.config)
    else:
        config = ConfigManager()
    logger = logging.getLogger("ascom_mount_cli")
    try:
        with ASCOMMount(config=config, logger=logger) as mount:
            while True:
                status = mount.get_coordinates()
                print(f"Status: {status.level.value.upper()} - {status.message}")
                if status.details:
                    print(f"Details: {status.details}")
                if status.is_success and status.data:
                    ra, dec = status.data
                    print(f"RA: {ra:.4f}°, Dec: {dec:.4f}°")
                else:
                    sys.exit(1)
                time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
