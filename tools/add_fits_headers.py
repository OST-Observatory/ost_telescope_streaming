#!/usr/bin/env python3
"""
FITS Header Editor - Helper Script

This script allows you to add, modify, or remove header information
from all FITS files in a configurable directory.

Usage:
    python add_fits_headers.py --directory darks --add "TELESCOP=MyTelescope" "OBSERVER=JohnDoe"
    python add_fits_headers.py --directory flats --add "FILTER=Clear" --remove "OLD_HEADER"
    python add_fits_headers.py --directory . --add "INSTRUMENT=ASI2600MC" --backup
    python add_fits_headers.py --directory darks --list-headers
"""

import argparse
from datetime import datetime
import logging
from pathlib import Path
import shutil
import sys
from typing import Any, List, Optional, Tuple

# Try to import astropy
try:
    import astropy.io.fits as fits

    ASTROPY_AVAILABLE = True
except ImportError:
    ASTROPY_AVAILABLE = False
    print("Warning: Astropy not available. Install with: pip install astropy")


def setup_logging(level: int = logging.INFO):
    """Set up logging configuration."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("fits_header_editor")


def parse_header_string(header_string: str) -> Tuple[str, Any, Optional[str]]:
    """Parse a header string in format 'KEYWORD=value' or 'KEYWORD=value,comment'.

    Args:
        header_string: Header string to parse

    Returns:
        tuple: (keyword, value, comment)
    """
    if "=" not in header_string:
        raise ValueError(
            "Invalid header format: "
            f"{header_string}. Use 'KEYWORD=value' or 'KEYWORD=value,comment'"
        )

    parts = header_string.split("=", 1)
    keyword = parts[0].strip().upper()
    value_part = parts[1].strip()

    # Check if there's a comment
    if "," in value_part:
        value_str, comment = value_part.split(",", 1)
        value_str = value_str.strip()
        comment = comment.strip()
    else:
        value_str = value_part
        comment = None

    # Try to convert value to appropriate type without mutating type of value_str
    parsed_value: Any
    try:
        lower_val = value_str.lower()
        if lower_val in {"true", "false"}:
            parsed_value = lower_val == "true"
        elif "." in value_str:
            parsed_value = float(value_str)
        else:
            parsed_value = int(value_str)
    except Exception:
        # Keep as string
        parsed_value = value_str

    return keyword, parsed_value, comment


def get_fits_files(directory: str) -> List[Path]:
    """Get all FITS files in the specified directory.

    Args:
        directory: Directory to search

    Returns:
        List of Path objects for FITS files
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    fits_files = []
    for file_path in dir_path.rglob("*.fits"):
        if file_path.is_file():
            fits_files.append(file_path)

    return fits_files


def add_headers_to_fits(
    file_path: Path,
    headers_to_add: List[tuple],
    headers_to_remove: List[str],
    backup: bool = False,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """Add or remove headers from a FITS file.

    Args:
        file_path: Path to the FITS file
        headers_to_add: List of (keyword, value, comment) tuples
        headers_to_remove: List of header keywords to remove
        backup: Whether to create a backup before modifying
        logger: Logger instance

    Returns:
        bool: True if successful, False otherwise
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        # Create backup if requested
        if backup:
            backup_path = file_path.with_suffix(".fits.backup")
            shutil.copy2(file_path, backup_path)
            logger.debug(f"Created backup: {backup_path}")

        # Open the FITS file
        with fits.open(file_path, mode="update") as hdul:
            header = hdul[0].header

            # Remove headers if specified
            for keyword in headers_to_remove:
                if keyword in header:
                    del header[keyword]
                    logger.debug(f"Removed header '{keyword}' from {file_path.name}")
                else:
                    logger.debug(f"Header '{keyword}' not found in {file_path.name}")

            # Add new headers
            for keyword, value, comment in headers_to_add:
                header[keyword] = (value, comment) if comment else value
                logger.debug(f"Added header '{keyword}={value}' to {file_path.name}")

            # Add modification timestamp
            header["HISTORY"] = f"Modified by fits_header_editor on {datetime.now().isoformat()}"

            # Flush changes
            hdul.flush()

        logger.info(f"Successfully updated {file_path.name}")
        return True

    except Exception as e:
        logger.error(f"Error updating {file_path.name}: {e}")
        return False


def list_headers(fits_files: List[Path], logger: Optional[logging.Logger] = None) -> None:
    """List all headers from FITS files.

    Args:
        fits_files: List of FITS file paths
        logger: Logger instance
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if not fits_files:
        logger.info("No FITS files found")
        return

    logger.info(f"Found {len(fits_files)} FITS files")

    for file_path in fits_files:
        try:
            with fits.open(file_path) as hdul:
                header = hdul[0].header

                logger.info(f"\n=== {file_path.name} ===")
                logger.info(f"File size: {file_path.stat().st_size} bytes")

                # Show important headers
                important_headers = [
                    "EXPTIME",
                    "GAIN",
                    "XBINNING",
                    "YBINNING",
                    "CCD-TEMP",
                    "DATE-OBS",
                    "CAMERA",
                    "COLORTYP",
                    "BAYERPAT",
                ]

                for keyword in important_headers:
                    if keyword in header:
                        value = header[keyword]
                        comment = header.comments[keyword] if keyword in header.comments else ""
                        logger.info(f"  {keyword}: {value} {comment}")

                # Show total number of headers
                logger.info(f"  Total headers: {len(header)}")

        except Exception as e:
            logger.error(f"Error reading {file_path.name}: {e}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Add, modify, or remove FITS headers from all FITS files in a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            """
Examples:
  # Add telescope and observer information
  python add_fits_headers.py --directory darks --add "TELESCOP=MyTelescope" "OBSERVER=JohnDoe"

  # Add filter information to flats
  python add_fits_headers.py --directory flats --add "FILTER=Clear,Clear filter used"

  # Add instrument information with backup
  python add_fits_headers.py --directory . --add "INSTRUMENT=ASI2600MC" --backup

  # Remove old headers
  python add_fits_headers.py --directory darks --remove "OLD_HEADER" "DEPRECATED_KEY"

  # List all headers
  python add_fits_headers.py --directory darks --list-headers

  # Add multiple headers at once
  python add_fits_headers.py \
    --directory . \
    --add "TELESCOP=80mm APO" "INSTRUMENT=ASI2600MC" "OBSERVER=Astronomer"
        """
        ),
    )

    parser.add_argument(
        "--directory",
        "-d",
        type=str,
        required=True,
        help="Directory containing FITS files (supports subdirectories)",
    )

    parser.add_argument(
        "--add",
        "-a",
        type=str,
        nargs="+",
        help='Headers to add in format "KEYWORD=value" or "KEYWORD=value,comment"',
    )

    parser.add_argument("--remove", "-r", type=str, nargs="+", help="Header keywords to remove")

    parser.add_argument(
        "--list-headers",
        "-l",
        action="store_true",
        help="List all headers from FITS files (no modifications)",
    )

    parser.add_argument(
        "--backup", "-b", action="store_true", help="Create backup files before modifying"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually modifying files",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Check if astropy is available
    if not ASTROPY_AVAILABLE:
        print("Error: Astropy is required but not available.")
        print("Install it with: pip install astropy")
        sys.exit(1)

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(log_level)

    try:
        # Get FITS files
        fits_files = get_fits_files(args.directory)
        logger.info(f"Found {len(fits_files)} FITS files in {args.directory}")

        if not fits_files:
            logger.warning("No FITS files found in the specified directory")
            return

        # Parse headers to add
        headers_to_add = []
        if args.add:
            for header_string in args.add:
                try:
                    keyword, value, comment = parse_header_string(header_string)
                    headers_to_add.append((keyword, value, comment))
                    logger.info(
                        f"Will add: {keyword}={value}" + (f" ({comment})" if comment else "")
                    )
                except ValueError as e:
                    logger.error(f"Invalid header format: {header_string} - {e}")
                    sys.exit(1)

        # Parse headers to remove
        headers_to_remove = []
        if args.remove:
            headers_to_remove = [h.upper() for h in args.remove]
            for header in headers_to_remove:
                logger.info(f"Will remove: {header}")

        # List headers if requested
        if args.list_headers:
            list_headers(fits_files, logger)
            return

        # Check if we have any modifications to make
        if not headers_to_add and not headers_to_remove:
            logger.warning("No headers to add or remove. Use --add or --remove options.")
            return

        # Process files
        success_count = 0
        error_count = 0

        for file_path in fits_files:
            if args.dry_run:
                logger.info(f"[DRY RUN] Would process: {file_path}")
                success_count += 1
            else:
                success = add_headers_to_fits(
                    file_path, headers_to_add, headers_to_remove, args.backup, logger
                )
                if success:
                    success_count += 1
                else:
                    error_count += 1

        # Summary
        logger.info("\n=== Summary ===")
        logger.info(f"Files processed: {len(fits_files)}")
        logger.info(f"Successful: {success_count}")
        logger.info(f"Errors: {error_count}")

        if args.backup and not args.dry_run:
            logger.info("Backup files created with .backup extension")

        if args.dry_run:
            logger.info("DRY RUN - No files were actually modified")

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
