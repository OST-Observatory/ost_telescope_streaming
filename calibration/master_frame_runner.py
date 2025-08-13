#!/usr/bin/env python3
"""
Master Frame Runner

This script provides a command-line interface for creating master dark and master flat frames
from captured calibration data with proper dark subtraction and normalization.

Usage:
    python master_frame_runner.py --config config_master_frames.yaml
    python master_frame_runner.py --config config_master_frames.yaml --darks-only
    python master_frame_runner.py --config config_master_frames.yaml --flats-only
"""

import argparse
from datetime import datetime
import logging
import os
from pathlib import Path
import sys

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import ConfigManager

from calibration.master_frame_builder import MasterFrameCreator


def setup_logging(level=logging.INFO):
    """Set up logging configuration."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                f'master_frames_{datetime.now().strftime("%Y%m%d")}.log', encoding="utf-8"
            ),
        ],
    )


def main():
    """Main function for master frame runner."""
    parser = argparse.ArgumentParser(
        description="Master Frame Creation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create all master frames (darks and flats)
  python master_frame_runner.py --config config_master_frames.yaml

  # Create only master darks
  python master_frame_runner.py --config config_master_frames.yaml --darks-only

  # Create only master flats
  python master_frame_runner.py --config config_master_frames.yaml --flats-only

  # Custom rejection method
  python master_frame_runner.py --config config_master_frames.yaml --rejection-method minmax

  # Debug mode
  python master_frame_runner.py --config config_master_frames.yaml --debug
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config_master_frames.yaml",
        help="Configuration file path (default: config_master_frames.yaml)",
    )

    parser.add_argument("--darks-only", action="store_true", help="Create only master darks")

    parser.add_argument("--flats-only", action="store_true", help="Create only master flats")

    parser.add_argument(
        "--rejection-method",
        type=str,
        choices=["sigma_clip", "minmax"],
        help="Frame rejection method (overrides config)",
    )

    parser.add_argument(
        "--sigma-threshold", type=float, help="Sigma threshold for rejection (overrides config)"
    )

    parser.add_argument(
        "--normalization-method",
        type=str,
        choices=["mean", "median", "max"],
        help="Normalization method for master flats (overrides config)",
    )

    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = getattr(logging, args.log_level.upper())
    if args.debug:
        log_level = logging.DEBUG

    setup_logging(log_level)
    logger = logging.getLogger("master_frame_runner")

    try:
        # Load configuration
        if not os.path.exists(args.config):
            logger.error(f"Configuration file not found: {args.config}")
            sys.exit(1)

        config = ConfigManager(args.config)
        logger.info(f"Configuration loaded from: {args.config}")

        # Override config settings with command line arguments
        master_config = config.get_master_config()

        if args.rejection_method:
            master_config["rejection_method"] = args.rejection_method
            logger.info(f"Rejection method set to: {args.rejection_method}")

        if args.sigma_threshold:
            master_config["sigma_threshold"] = args.sigma_threshold
            logger.info(f"Sigma threshold set to: {args.sigma_threshold}")

        if args.normalization_method:
            master_config["normalization_method"] = args.normalization_method
            logger.info(f"Normalization method set to: {args.normalization_method}")

        # Initialize master frame creator
        logger.info("Initializing master frame creator...")
        master_creator = MasterFrameCreator(config=config, logger=logger)

        # Display settings
        logger.info("Master Frame Creation Settings:")
        logger.info(f"  Output directory: {master_config['output_dir']}")
        logger.info(f"  Rejection method: {master_config['rejection_method']}")
        logger.info(f"  Sigma threshold: {master_config['sigma_threshold']}")
        logger.info(f"  Normalization method: {master_config['normalization_method']}")
        logger.info(f"  Quality control: {master_config['quality_control']}")

        # Determine creation mode
        if args.darks_only:
            logger.info("Mode: Master darks only")
            creation_mode = "darks"
        elif args.flats_only:
            logger.info("Mode: Master flats only")
            creation_mode = "flats"
        else:
            logger.info("Mode: All master frames (darks and flats)")
            creation_mode = "all"

        # Start master frame creation
        logger.info("Starting master frame creation process...")
        logger.info("This will process existing dark and flat frames")
        logger.info("Press Enter to continue or Ctrl+C to cancel...")

        try:
            input()
        except KeyboardInterrupt:
            logger.info("Master frame creation cancelled by user")
            sys.exit(0)

        # Create master frames based on mode
        if creation_mode == "darks":
            result = master_creator.create_master_darks()
        elif creation_mode == "flats":
            result = master_creator.create_master_flats()
        else:
            result = master_creator.create_all_master_frames()

        if result.is_success:
            logger.info("✅ Master frame creation completed successfully!")

            if creation_mode == "all":
                dark_count = result.details.get("dark_count", 0)
                flat_count = result.details.get("flat_count", 0)
                logger.info(f"Master darks created: {dark_count}")
                logger.info(f"Master flats created: {flat_count}")

                if result.data and "master_darks" in result.data:
                    logger.info("Master darks:")
                    for dark_file in result.data["master_darks"]:
                        logger.info(f"  - {dark_file}")

                if result.data and "master_flats" in result.data:
                    logger.info("Master flats:")
                    for flat_file in result.data["master_flats"]:
                        logger.info(f"  - {flat_file}")

            elif creation_mode == "darks":
                created_files = result.data
                logger.info(f"Master darks created: {len(created_files)}")
                for dark_file in created_files:
                    logger.info(f"  - {dark_file}")

            elif creation_mode == "flats":
                created_files = result.data
                logger.info(f"Master flats created: {len(created_files)}")
                for flat_file in created_files:
                    logger.info(f"  - {flat_file}")

            logger.info(f"Output directory: {master_config['output_dir']}")

            if result.details:
                logger.info("Details:")
                for key, value in result.details.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.error(f"❌ Master frame creation failed: {result.message}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nMaster frame creation interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
