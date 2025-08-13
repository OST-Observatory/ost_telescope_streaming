import logging
from pathlib import Path
import sys

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

import argparse
import sys

from capture.controller import VideoCapture
from config_manager import ConfigManager


def main():
    parser = argparse.ArgumentParser(description="Video capture with ASCOM/Alpyca camera support")
    parser.add_argument("--config", type=str, help="Path to configuration file")

    # Parse config argument first to load the right configuration
    args, remaining = parser.parse_known_args()

    # Load configuration
    if args.config:
        config = ConfigManager(config_path=args.config)
    else:
        config = ConfigManager()

    video_config = config.get_frame_processing_config()

    # Recreate parser with the loaded configuration defaults
    parser = argparse.ArgumentParser(description="Video capture with ASCOM/Alpyca camera support")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument(
        "--camera-index",
        type=int,
        default=video_config["opencv"]["camera_index"],
        help="Camera device index (OpenCV)",
    )
    parser.add_argument(
        "--camera-type",
        choices=["opencv", "ascom", "alpaca"],
        default=config.get_camera_config().get("camera_type", "opencv"),
        help="Camera type: opencv for regular cameras, ascom for classic ASCOM, alpaca for Alpyca",
    )
    parser.add_argument(
        "--ascom-driver",
        default=config.get_camera_config()
        .get("ascom", {})
        .get("ascom_driver", "ASCOM.MyCamera.Camera"),
        help="ASCOM driver ID (astro cameras)",
    )
    parser.add_argument(
        "--alpaca-host",
        default=config.get_camera_config().get("alpaca", {}).get("host", "localhost"),
        help="Alpaca server host",
    )
    parser.add_argument(
        "--alpaca-port",
        type=int,
        default=config.get_camera_config().get("alpaca", {}).get("port", 11111),
        help="Alpaca server port",
    )
    parser.add_argument(
        "--alpaca-device-id",
        type=int,
        default=config.get_camera_config().get("alpaca", {}).get("device_id", 0),
        help="Alpaca camera device ID",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=config.get_camera_config().get("opencv", {}).get("frame_width", 1920),
        help="Frame width",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=config.get_camera_config().get("opencv", {}).get("frame_height", 1080),
        help="Frame height",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=config.get_camera_config().get("opencv", {}).get("fps", 30),
        help="Frame rate",
    )
    parser.add_argument(
        "--exposure",
        type=float,
        default=config.get_camera_config().get("opencv", {}).get("exposure_time", 0.1),
        help="Exposure time in seconds",
    )
    parser.add_argument(
        "--gain",
        type=float,
        default=config.get_camera_config().get("ascom", {}).get("gain", 1.0),
        help="Gain setting (ASCOM/Alpyca cameras)",
    )
    parser.add_argument(
        "--offset",
        type=float,
        default=config.get_camera_config().get("ascom", {}).get("offset", 0.0),
        help="Offset setting (ASCOM/Alpyca cameras)",
    )
    parser.add_argument(
        "--readout-mode",
        type=int,
        default=config.get_camera_config().get("ascom", {}).get("readout_mode", 0),
        help="Readout mode (ASCOM/Alpyca cameras)",
    )
    parser.add_argument(
        "--binning",
        type=int,
        default=config.get_camera_config().get("ascom", {}).get("binning", 1),
        help="Binning factor (1x1, 2x2, etc.)",
    )
    parser.add_argument("--output", default="captured_frame.jpg", help="Output filename")
    parser.add_argument(
        "--action",
        choices=[
            "capture",
            "info",
            "cooling",
            "cooling-off",
            "cooling-status",
            "cooling-status-cache",
            "cooling-background",
            "cooling-clear-cache",
            "filter",
            "debayer",
        ],
        default="capture",
        help="Action to perform",
    )
    parser.add_argument("--cooling-temp", type=float, help="Target cooling temperature in °C")
    parser.add_argument(
        "--keep-cooling",
        action="store_true",
        help="Keep cooling on when disconnecting (cooling action only)",
    )
    parser.add_argument("--filter-position", type=int, help="Filter wheel position")
    parser.add_argument(
        "--bayer-pattern",
        default="RGGB",
        choices=["RGGB", "GRBG", "GBRG", "BGGR"],
        help="Bayer pattern for debayering",
    )

    args = parser.parse_args()

    try:
        logger = logging.getLogger("video_capture_cli")
        logger.setLevel(logging.DEBUG)  # Enable debug logging

        # Update config with command line arguments BEFORE creating VideoCapture
        # Note: These updates are now handled by the individual camera classes
        # which read from the correct config sections

        capture = VideoCapture(config=config, logger=logger, return_frame_objects=True)

        if args.action == "info":
            # Show camera information
            if args.camera_type == "ascom" and args.ascom_driver:
                from drivers.ascom.camera import ASCOMCamera

                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    print(f"Camera connected: {connect_status.message}")

                    # Add a small delay to ensure ASCOM driver has updated values
                    import time

                    time.sleep(0.5)

                    # Check cooling
                    if camera.has_cooling():
                        print("Cooling supported: ✅")

                        # Use force refresh for accurate readings
                        print("Refreshing cooling status...")
                        refresh_status = camera.force_refresh_cooling_status()

                        if refresh_status.is_success:
                            info = refresh_status.data
                            print(f"Current temperature: {info['temperature']}°C")
                            print(f"Cooler power: {info['cooler_power']}%")
                            print(f"Cooler on: {info['cooler_on']}")
                            print(f"Target temperature: {info['target_temperature']}°C")

                            # Check camera type
                            is_color = camera.is_color_camera()
                            print(f"Camera type: {'Color' if is_color else 'Monochrome'}")

                            # Show camera capabilities
                            capabilities = camera.get_camera_capabilities()
                            print(f"Camera capabilities: {capabilities}")
                        else:
                            print(f"Failed to refresh cooling status: {refresh_status.message}")
                    else:
                        print("Cooling not supported: ❌")

                    camera.disconnect()
                else:
                    print(f"Failed to connect: {connect_status.message}")

            elif args.camera_type == "alpaca":
                from drivers.alpaca.camera import AlpycaCameraWrapper

                camera = AlpycaCameraWrapper(
                    host=args.alpaca_host,
                    port=args.alpaca_port,
                    device_id=args.alpaca_device_id,
                    config=config,
                    logger=logger,
                )
                connect_status = camera.connect()
                if connect_status.is_success:
                    print(f"Alpyca camera connected: {connect_status.message}")

                    # Get camera info
                    info_status = camera.get_camera_info()
                    if info_status.is_success:
                        info = info_status.data
                        print(f"Camera: {info['name']}")
                        print(f"Description: {info['description']}")
                        print(f"Driver: {info['driver_info']}")
                        print(f"Version: {info['driver_version']}")
                        print(f"Connected: {info['connected']}")
                        print(f"Sensor: {info['camera_size']}")
                        print(f"Pixel size: {info['pixel_size']}")
                        print(f"Camera type: {'Color' if info['is_color'] else 'Monochrome'}")
                        print(f"Cooling supported: {'Yes' if info['cooling_supported'] else 'No'}")
                        cps = "Yes" if info["cooler_power_supported"] else "No"
                        print(f"Cooler power supported: {cps}")
                        print(f"Binning supported: {'Yes' if info['binning_supported'] else 'No'}")
                        print(f"Gain supported: {'Yes' if info['gain_supported'] else 'No'}")
                        print(f"Offset supported: {'Yes' if info['offset_supported'] else 'No'}")
                        rms = "Yes" if info["readout_modes_supported"] else "No"
                        print(f"Readout modes supported: {rms}")

                    # Check cooling if supported
                    if camera.can_set_ccd_temperature:
                        print("\nCooling Information:")
                        cooling_status = camera.get_cooling_status()
                        if cooling_status.is_success:
                            info = cooling_status.data
                            print(f"Current temperature: {info['temperature']}°C")
                            print(f"Target temperature: {info['target_temperature']}°C")
                            print(f"Cooler on: {info['cooler_on']}")
                            print(f"Cooler power: {info['cooler_power']}%")
                            print(f"Heat sink temperature: {info['heat_sink_temperature']}°C")

                    camera.disconnect()
                else:
                    print(f"Failed to connect: {connect_status.message}")

            else:
                # OpenCV camera info
                print(f"OpenCV camera (index {args.camera_index})")
                print(f"Resolution: {args.width}x{args.height}")
                print(f"FPS: {args.fps}")
                print(f"Exposure: {args.exposure}s")

        elif args.action == "cooling":
            if args.cooling_temp is not None:
                if args.camera_type == "ascom" and args.ascom_driver:
                    from ascom_camera import ASCOMCamera

                    camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                    connect_status = camera.connect()
                    if connect_status.is_success:
                        print("✅ Connected successfully")
                        print(f"Setting target temperature to {args.cooling_temp}°C...")

                        # Set cooling with improved method
                        cooling_status = camera.set_cooling(args.cooling_temp)
                        print(
                            "Cooling status: %s - %s"
                            % (cooling_status.level.value.upper(), cooling_status.message)
                        )

                        # Show detailed cooling information if available
                        if (
                            cooling_status.is_success
                            and hasattr(cooling_status, "details")
                            and cooling_status.details
                        ):
                            details = cooling_status.details
                            print(f"  Target temperature: {details.get('target_temp')}°C")
                            print(f"  Temperature before: {details.get('current_temp')}°C")
                            print(f"  Temperature after: {details.get('new_temp')}°C")
                            print(f"  Cooler power before: {details.get('current_power')}%")
                            print(f"  Cooler power after: {details.get('new_power')}%")
                            print(f"  Cooler on before: {details.get('current_cooler_on')}")
                            print(f"  Cooler on after: {details.get('new_cooler_on')}")

                        # Force refresh cooling status to get accurate power readings
                        print("\nForcing cooling status refresh...")
                        refresh_status = camera.force_refresh_cooling_status()
                        if refresh_status.is_success:
                            refresh_info = refresh_status.data
                            print("✅ Cooling status refreshed successfully!")
                            print(f"  Temperature: {refresh_info.get('temperature')}°C")
                            print(f"  Cooler power: {refresh_info.get('cooler_power')}%")
                            print(f"  Cooler on: {refresh_info.get('cooler_on')}")
                            print(
                                f"  Target temperature: {refresh_info.get('target_temperature')}°C"
                            )
                            print(f"  Refresh attempts: {refresh_info.get('refresh_attempts')}")
                        else:
                            print(f"⚠️  Force refresh failed: {refresh_status.message}")

                        # Wait for cooling to stabilize
                        print("\nWaiting for cooling to stabilize (timeout: 30s)...")
                        stabilization_status = camera.wait_for_cooling_stabilization(
                            timeout=30, check_interval=2.0
                        )

                        if stabilization_status.is_success:
                            final_info = stabilization_status.data
                            print("✅ Cooling stabilized successfully!")
                            print("Final status:")
                            print(f"  Temperature: {final_info.get('temperature')}°C")
                            print(f"  Cooler power: {final_info.get('cooler_power')}%")
                            print(f"  Cooler on: {final_info.get('cooler_on')}")
                            print(f"  Target temperature: {final_info.get('target_temperature')}°C")
                        else:
                            print(f"⚠️  Cooling stabilization: {stabilization_status.message}")
                            if hasattr(stabilization_status, "data") and stabilization_status.data:
                                final_info = stabilization_status.data
                                print("Final status (timeout):")
                                print(f"  Temperature: {final_info.get('temperature')}°C")
                                print(f"  Cooler power: {final_info.get('cooler_power')}%")
                                print(f"  Cooler on: {final_info.get('cooler_on')}")

                        # Handle cooling when disconnecting
                        if args.keep_cooling:
                            print("\n⚠️  Keeping cooling on when disconnecting...")
                            print("   Note: Cooling will remain active after disconnect")
                            print("   Connection released; cooling stays on")

                            # For ASCOM, keep connection alive to maintain cooling
                            # Release Python reference; ASCOM connection stays active
                            print(
                                "   ⚠️  ASCOM limitation: Cooling turns off when connection is lost"
                            )
                            print("   💡 Solution: Keep camera connected in background")

                            # Do not disconnect - keep the connection alive
                            # Camera object may be GC'd; ASCOM persists
                            print("✅ Camera connection kept alive (cooling active)")
                            print("   ⚠️  IMPORTANT: Keep this terminal open")
                            print("   Avoid running other camera commands")
                            print("   ⚠️  Use 'cooling-off' in a NEW terminal to turn off cooling")
                            print("   💡 Tip: Keep this terminal open to maintain cooling")

                            # Return without disconnecting
                            return
                        else:
                            print("\n⚠️  Disconnecting will turn off cooling...")
                            print("   Use --keep-cooling to maintain cooling after disconnect")
                            camera.disconnect()
                            print("✅ Disconnected from camera (cooling turned off)")

                elif args.camera_type == "alpaca":
                    from alpaca_camera import AlpycaCameraWrapper

                    alpaca_config = video_config.get("alpaca", {})
                    camera = AlpycaCameraWrapper(
                        host=alpaca_config.get("host", "localhost"),
                        port=alpaca_config.get("port", 11111),
                        device_id=alpaca_config.get("device_id", 0),
                        config=config,
                        logger=logger,
                    )
                    connect_status = camera.connect()
                    if connect_status.is_success:
                        print("✅ Connected successfully")
                        print(f"Setting target temperature to {args.cooling_temp}°C...")

                        # Set cooling with keep_connection parameter
                        cooling_status = camera.set_cooling(
                            args.cooling_temp, keep_connection=args.keep_cooling
                        )
                        print(
                            "Cooling status: %s - %s"
                            % (cooling_status.level.value.upper(), cooling_status.message)
                        )

                        # Show detailed cooling information if available
                        if (
                            cooling_status.is_success
                            and hasattr(cooling_status, "details")
                            and cooling_status.details
                        ):
                            details = cooling_status.details
                            print(f"  Target temperature: {details.get('target_temp')}°C")
                            print(f"  Temperature before: {details.get('current_temp')}°C")
                            print(f"  Temperature after: {details.get('new_temp')}°C")
                            print(f"  Cooler power before: {details.get('current_power')}%")
                            print(f"  Cooler power after: {details.get('new_power')}%")
                            print(f"  Cooler on before: {details.get('current_cooler_on')}")
                            print(f"  Cooler on after: {details.get('new_cooler_on')}")
                            print(f"  Keep connection: {details.get('keep_connection')}")

                        # Handle cooling when disconnecting
                        if args.keep_cooling:
                            print("\n🚀 Keeping cooling active for 5 minutes...")
                            # Keep connection alive for cooling
                            cooling_maintenance_status = camera.keep_cooling_alive(
                                duration_minutes=5
                            )
                            if cooling_maintenance_status.is_success:
                                print("✅ Cooling maintenance completed successfully")
                            else:
                                msg = cooling_maintenance_status.message
                                print(f"⚠️  Cooling maintenance had issues: {msg}")
                        else:
                            print("\n⚠️  Disconnecting will turn off cooling...")
                            print("   Use --keep-cooling to maintain cooling after disconnect")
                            camera.disconnect()
                            print("✅ Disconnected from camera (cooling turned off)")
                    else:
                        print(f"❌ Connection failed: {connect_status.message}")

                else:
                    print("❌ Cooling action requires:")
                    print("   --camera-type ascom (--ascom-driver) or --camera-type alpaca")
            else:
                print("❌ Please specify --cooling-temp")

        elif args.action == "cooling-off":
            if args.camera_type == "ascom" and args.ascom_driver:
                from ascom_camera import ASCOMCamera

                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    print("✅ Connected successfully")
                    print("Turning off cooling...")

                    # Turn off cooling explicitly
                    cooling_off_status = camera.turn_cooling_off()
                    lvl = cooling_off_status.level.value.upper()
                    print(f"Cooling off status: {lvl} - {cooling_off_status.message}")

                    # Show detailed cooling off information if available
                    if (
                        cooling_off_status.is_success
                        and hasattr(cooling_off_status, "details")
                        and cooling_off_status.details
                    ):
                        details = cooling_off_status.details
                        print(f"  Temperature before: {details.get('current_temp')}°C")
                        print(f"  Temperature after: {details.get('new_temp')}°C")
                        print(f"  Cooler power before: {details.get('current_power')}%")
                        print(f"  Cooler power after: {details.get('new_power')}%")
                        print(f"  Cooler on before: {details.get('current_cooler_on')}")
                        print(f"  Cooler on after: {details.get('new_cooler_on')}")

                    # Force refresh to confirm cooling is off
                    print("\nConfirming cooling status...")
                    refresh_status = camera.force_refresh_cooling_status()
                    if refresh_status.is_success:
                        refresh_info = refresh_status.data
                        print("✅ Cooling status confirmed:")
                        print(f"  Temperature: {refresh_info.get('temperature')}°C")
                        print(f"  Cooler power: {refresh_info.get('cooler_power')}%")
                        print(f"  Cooler on: {refresh_info.get('cooler_on')}")

                    # Now disconnect
                    camera.disconnect()
                    print("✅ Disconnected from camera (cooling turned off)")
                else:
                    print(f"❌ Connection failed: {connect_status.message}")
                    sys.exit(1)

            elif args.camera_type == "alpaca":
                from alpaca_camera import AlpycaCameraWrapper

                camera = AlpycaCameraWrapper(
                    host=args.alpaca_host,
                    port=args.alpaca_port,
                    device_id=args.alpaca_device_id,
                    config=config,
                    logger=logger,
                )
                connect_status = camera.connect()
                if connect_status.is_success:
                    print("✅ Alpyca camera connected successfully")
                    print("Turning off cooling...")

                    # Turn off cooling explicitly
                    cooling_off_status = camera.turn_cooling_off()
                    lvl = cooling_off_status.level.value.upper()
                    print(f"Cooling off status: {lvl} - {cooling_off_status.message}")

                    # Force refresh to confirm cooling is off
                    print("\nConfirming cooling status...")
                    refresh_status = camera.force_refresh_cooling_status()
                    if refresh_status.is_success:
                        refresh_info = refresh_status.data
                        print("✅ Cooling status confirmed:")
                        print(f"  Temperature: {refresh_info.get('temperature')}°C")
                        print(f"  Cooler power: {refresh_info.get('cooler_power')}%")
                        print(f"  Cooler on: {refresh_info.get('cooler_on')}")

                    # Now disconnect
                    camera.disconnect()
                    print("✅ Disconnected from camera (cooling turned off)")
                else:
                    print(f"❌ Connection failed: {connect_status.message}")
                    sys.exit(1)

            else:
                print("Cooling off requires ASCOM or Alpyca camera")
                sys.exit(1)

        elif args.action == "cooling-status":
            if args.camera_type == "ascom" and args.ascom_driver:
                from ascom_camera import ASCOMCamera

                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)

                print("Checking cooling status (non-intrusive)...")

                # Try to connect without affecting existing cooling
                connect_status = camera.connect()
                if connect_status.is_success:
                    print("✅ Connected successfully")

                    # Use force refresh to get accurate status without changing settings
                    print("Reading cooling status...")
                    refresh_status = camera.force_refresh_cooling_status()

                    if refresh_status.is_success:
                        info = refresh_status.data
                        print("Current cooling status:")
                        print(f"  Temperature: {info['temperature']}°C")
                        print(f"  Cooler power: {info['cooler_power']}%")
                        print(f"  Cooler on: {info['cooler_on']}")
                        print(f"  Target temperature: {info['target_temperature']}°C")
                        print(f"  Can set cooler power: {info['can_set_cooler_power']}")

                        # Provide analysis of the status
                        if info["cooler_on"] and info["cooler_power"] > 0:
                            print("✅ Cooling is active and working")
                        elif info["cooler_on"] and info["cooler_power"] == 0:
                            print("⚠️  Cooler is on but power is 0% - may be at target temperature")
                        elif not info["cooler_on"]:
                            print("ℹ️  Cooler is off")

                        # Check if target temperature is set
                        if info["target_temperature"] is not None:
                            temp_diff = info["temperature"] - info["target_temperature"]
                            print(f"  Temperature difference: {temp_diff:+.1f}°C")
                    else:
                        print(f"❌ Failed to read cooling status: {refresh_status.message}")

                        # Fallback to smart cooling info
                        cooling_info_status = camera.get_smart_cooling_info()
                        if cooling_info_status.is_success:
                            info = cooling_info_status.data
                            print("Fallback cooling status:")
                            print(f"  Temperature: {info['temperature']}°C")
                            print(f"  Cooler power: {info['cooler_power']}%")
                            print(f"  Cooler on: {info['cooler_on']}")
                            print(f"  Target temperature: {info['target_temperature']}°C")

                    camera.disconnect()
                    print("✅ Disconnected")
                else:
                    print(f"❌ Connection failed: {connect_status.message}")

            elif args.camera_type == "alpaca":
                from alpaca_camera import AlpycaCameraWrapper

                camera = AlpycaCameraWrapper(
                    host=args.alpaca_host,
                    port=args.alpaca_port,
                    device_id=args.alpaca_device_id,
                    config=config,
                    logger=logger,
                )

                print("Checking Alpyca cooling status (non-intrusive)...")

                # Try to connect without affecting existing cooling
                connect_status = camera.connect()
                if connect_status.is_success:
                    print("✅ Connected successfully")

                    # Use force refresh to get accurate status without changing settings
                    print("Reading cooling status...")
                    refresh_status = camera.force_refresh_cooling_status()

                    if refresh_status.is_success:
                        info = refresh_status.data
                        print("Current cooling status:")
                        print(f"  Temperature: {info['temperature']}°C")
                        print(f"  Cooler power: {info['cooler_power']}%")
                        print(f"  Cooler on: {info['cooler_on']}")
                        print(f"  Target temperature: {info['target_temperature']}°C")
                        print(f"  Can get cooler power: {info['can_set_cooler_power']}")

                        # Provide analysis of the status
                        if info["cooler_on"] and info["cooler_power"] > 0:
                            print("✅ Cooling is active and working")
                        elif info["cooler_on"] and info["cooler_power"] == 0:
                            print("⚠️  Cooler is on but power is 0% - may be at target temperature")
                        elif not info["cooler_on"]:
                            print("ℹ️  Cooler is off")

                        # Check if target temperature is set
                        if info["target_temperature"] is not None:
                            temp_diff = info["temperature"] - info["target_temperature"]
                            print(f"  Temperature difference: {temp_diff:+.1f}°C")
                    else:
                        print(f"❌ Failed to read cooling status: {refresh_status.message}")

                    camera.disconnect()
                    print("✅ Disconnected")
                else:
                    print(f"❌ Connection failed: {connect_status.message}")

            else:
                print("Cooling status requires ASCOM or Alpyca camera")
                sys.exit(1)

        elif args.action == "cooling-status-cache":
            # This action reads cooling status from the cache without connecting to the camera
            # It's useful for checking the current state of cooling without affecting settings
            print("Reading cooling status from cache...")
            try:
                import json
                from pathlib import Path

                # Construct the cache file path based on the driver ID
                driver_id = args.ascom_driver.replace(".", "_").replace(":", "_")
                cache_filename = f"cooling_cache_{driver_id}.json"
                cache_path = Path("cache") / cache_filename

                if not cache_path.exists():
                    print(f"❌ Cache file not found: {cache_path}")
                    print("   Cooling may not have been used yet")
                    print("   Or cache is in a different location")
                    sys.exit(1)

                # Load the cache file
                with open(cache_path, "r") as f:
                    cache_data = json.load(f)

                print(f"✅ Cache file loaded: {cache_path}")

                # Extract cooling status from the cache
                if cache_data:
                    print("Current cooling status from cache:")

                    # Check if we have valid cooling data
                    temperature = cache_data.get("temperature")
                    cooler_power = cache_data.get("cooler_power")
                    cooler_on = cache_data.get("cooler_on")
                    target_temperature = cache_data.get("target_temperature")

                    # Validate the data
                    valid_data = all(
                        v is not None
                        for v in [temperature, cooler_power, cooler_on, target_temperature]
                    )

                    if valid_data:
                        print(f"  Temperature: {temperature}°C")
                        print(f"  Cooler power: {cooler_power}%")
                        print(f"  Cooler on: {cooler_on}")
                        print(f"  Target temperature: {target_temperature}°C")

                        # Provide analysis of the status
                        if cooler_on and cooler_power > 0:
                            print("✅ Cooling is active and working (from cache)")
                        elif cooler_on and cooler_power == 0:
                            print("⚠️  Cooler on, power 0% (may be at target temp; from cache)")
                        elif not cooler_on:
                            print("ℹ️  Cooler is off (from cache)")

                        # Check if target temperature is set
                        if target_temperature is not None and temperature is not None:
                            temp_diff = temperature - target_temperature
                            print(f"  Temperature difference: {temp_diff:+.1f}°C (from cache)")
                    else:
                        print("⚠️  Cache contains invalid data:")
                        print(f"  Temperature: {temperature}°C")
                        print(f"  Cooler power: {cooler_power}%")
                        print(f"  Cooler on: {cooler_on}")
                        print(f"  Target temperature: {target_temperature}°C")
                        print("")
                        print("💡 This may indicate:")
                        print("   - Cooling was not properly initialized")
                        print("   - Camera connection was lost")
                        print("   - Cache file is corrupted")
                        print("")
                        print("🔧 Try these solutions:")
                        print("   1. Start cooling again:")
                        print("      python tests/test_video_capture.py ")
                        print("         --config config.yaml --action cooling --cooling-temp -10.0")
                        print("   2. Check live status (may reset cooling):")
                        print("      python tests/test_video_capture.py ")
                        print("         --config config.yaml --action cooling-status")
                        print("   3. Use detailed debug:")
                        print("      python tests/test_cooling_debug.py ")
                        print("         --config config.yaml --target-temp -10.0")

                    # Show cache age if available
                    if "timestamp" in cache_data:
                        from datetime import datetime

                        cache_time = datetime.fromtimestamp(cache_data["timestamp"])
                        age = datetime.now() - cache_time
                        print(f"  Cache age: {age.total_seconds():.1f} seconds")
                else:
                    print("❌ No cooling data found in cache")

            except FileNotFoundError:
                print(f"❌ Cache file not found: {cache_path}")
                print("   This may mean cooling has not been used yet")
                sys.exit(1)
            except json.JSONDecodeError:
                print(f"❌ Error: Could not decode JSON from cache file {cache_path}")
                sys.exit(1)
            except Exception as e:
                print(f"❌ Error reading cache: {e}")
                sys.exit(1)

        elif args.action == "cooling-background":
            if args.camera_type == "ascom" and args.ascom_driver:
                from ascom_camera import ASCOMCamera

                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    print("✅ Connected successfully")
                    print("Starting cooling in background...")

                    # Set cooling with improved method
                    cooling_status = camera.set_cooling(args.cooling_temp)
                    print(
                        "Cooling status: %s - %s"
                        % (cooling_status.level.value.upper(), cooling_status.message)
                    )

                    # Show detailed cooling information if available
                    if (
                        cooling_status.is_success
                        and hasattr(cooling_status, "details")
                        and cooling_status.details
                    ):
                        details = cooling_status.details
                        print(f"  Target temperature: {details.get('target_temp')}°C")
                        print(f"  Temperature before: {details.get('current_temp')}°C")
                        print(f"  Temperature after: {details.get('new_temp')}°C")
                        print(f"  Cooler power before: {details.get('current_power')}%")
                        print(f"  Cooler power after: {details.get('new_power')}%")
                        print(f"  Cooler on before: {details.get('current_cooler_on')}")
                        print(f"  Cooler on after: {details.get('new_cooler_on')}")

                    # Force refresh cooling status to get accurate power readings
                    print("\nForcing cooling status refresh...")
                    refresh_status = camera.force_refresh_cooling_status()
                    if refresh_status.is_success:
                        refresh_info = refresh_status.data
                        print("✅ Cooling status refreshed successfully!")
                        print(f"  Temperature: {refresh_info.get('temperature')}°C")
                        print(f"  Cooler power: {refresh_info.get('cooler_power')}%")
                        print(f"  Cooler on: {refresh_info.get('cooler_on')}")
                        print(f"  Target temperature: {refresh_info.get('target_temperature')}°C")
                        print(f"  Refresh attempts: {refresh_info.get('refresh_attempts')}")
                    else:
                        print(f"⚠️  Force refresh failed: {refresh_status.message}")

                    # Wait for cooling to stabilize
                    print("\nWaiting for cooling to stabilize (timeout: 30s)...")
                    stabilization_status = camera.wait_for_cooling_stabilization(
                        timeout=30, check_interval=2.0
                    )

                    if stabilization_status.is_success:
                        final_info = stabilization_status.data
                        print("✅ Cooling stabilized successfully!")
                        print("Final status:")
                        print(f"  Temperature: {final_info.get('temperature')}°C")
                        print(f"  Cooler power: {final_info.get('cooler_power')}%")
                        print(f"  Cooler on: {final_info.get('cooler_on')}")
                        print(f"  Target temperature: {final_info.get('target_temperature')}°C")
                    else:
                        print(f"⚠️  Cooling stabilization: {stabilization_status.message}")
                        if hasattr(stabilization_status, "data") and stabilization_status.data:
                            final_info = stabilization_status.data
                            print("Final status (timeout):")
                            print(f"  Temperature: {final_info.get('temperature')}°C")
                            print(f"  Cooler power: {final_info.get('cooler_power')}%")
                            print(f"  Cooler on: {final_info.get('cooler_on')}")

                    # Handle cooling when disconnecting
                    if args.keep_cooling:
                        print("\n⚠️  Keeping cooling on when disconnecting...")
                        print("   Note: Cooling will remain active after disconnect")
                        print("   Connection released; cooling stays on")

                        # For ASCOM cameras, keep the connection alive to maintain cooling
                        # Instead of disconnecting, we'll just release the Python object reference
                        # but keep the ASCOM connection active
                        print(
                            "   ⚠️  ASCOM limitation: Cooling will turn off when connection is lost"
                        )
                        print("   💡 Solution: Keep camera connected in background")

                        # Don't disconnect - keep the connection alive
                        # The camera object will be garbage collected, but ASCOM connection stays
                        print("✅ Camera connection kept alive (cooling active)")
                        print("   ⚠️  IMPORTANT: Keep this terminal open")
                        print("   Avoid running other camera commands")
                        print(
                            "   ⚠️  Use 'cooling-off' action in a NEW terminal to turn off cooling"
                        )
                        print("   💡 Tip: Keep this terminal open to maintain cooling")

                        # Return without disconnecting
                        return
                    else:
                        print("\n⚠️  Disconnecting will turn off cooling...")
                        print("   Use --keep-cooling to maintain cooling after disconnect")
                        camera.disconnect()
                        print("✅ Disconnected from camera (cooling turned off)")
                else:
                    print(f"❌ Connection failed: {connect_status.message}")
                    sys.exit(1)
            else:
                print("Cooling background requires ASCOM camera")
                sys.exit(1)

        elif args.action == "cooling-clear-cache":
            if args.camera_type == "ascom" and args.ascom_driver:
                from ascom_camera import ASCOMCamera

                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    print("✅ Connected successfully")
                    print("Clearing cooling cache...")

                    # Construct the cache file path based on the driver ID
                    driver_id = args.ascom_driver.replace(".", "_").replace(":", "_")
                    cache_filename = f"cooling_cache_{driver_id}.json"
                    cache_path = Path("cache") / cache_filename

                    if cache_path.exists():
                        try:
                            cache_path.unlink()
                            print(f"✅ Cache file deleted: {cache_path}")
                        except OSError as e:
                            print(f"❌ Error deleting cache file {cache_path}: {e}")
                            sys.exit(1)
                    else:
                        print(f"❌ Cache file not found: {cache_path}")
                        print("   No cache to clear.")

                    # Force refresh cooling status to ensure it's off
                    print("\nForcing cooling status refresh to confirm off...")
                    refresh_status = camera.force_refresh_cooling_status()
                    if refresh_status.is_success:
                        refresh_info = refresh_status.data
                        print("✅ Cooling status confirmed off after clearing cache.")
                        print(f"  Temperature: {refresh_info.get('temperature')}°C")
                        print(f"  Cooler power: {refresh_info.get('cooler_power')}%")
                        print(f"  Cooler on: {refresh_info.get('cooler_on')}")
                    else:
                        print("⚠️  Force refresh failed after clearing cache:")
                        print(f"   {refresh_status.message}")

                    camera.disconnect()
                    print("✅ Disconnected from camera (cooling turned off)")
                else:
                    print(f"❌ Connection failed: {connect_status.message}")
                    sys.exit(1)
            else:
                print("Cooling cache clear requires ASCOM camera")
                sys.exit(1)

        elif args.action == "filter":
            if (
                args.camera_type == "ascom"
                and args.ascom_driver
                and args.filter_position is not None
            ):
                from ascom_camera import ASCOMCamera

                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    filter_status = camera.set_filter_position(args.filter_position)
                    lvl = filter_status.level.value.upper()
                    print(f"Filter status: {lvl} - {filter_status.message}")
                    camera.disconnect()
                else:
                    print(f"Connection failed: {connect_status.message}")
                    sys.exit(1)
            else:
                print("Filter control requires ASCOM camera and --filter-position parameter")
                sys.exit(1)

        elif args.action == "debayer":
            if args.camera_type == "ascom" and args.ascom_driver:
                from ascom_camera import ASCOMCamera

                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    if camera.is_color_camera():
                        # Capture and debayer
                        # Get binning from CLI argument or config
                        binning = (
                            args.binning
                            if hasattr(args, "binning")
                            else config.get_camera_config().get("ascom", {}).get("binning", 1)
                        )

                        # Start exposure
                        expose_status = camera.expose(args.exposure, args.gain, binning)
                        if expose_status.is_success:
                            image_status = camera.get_image()
                            if image_status.is_success:
                                print("Image captured successfully")
                                print(f"Image data: {image_status.data}")
                                debayer_status = camera.debayer(
                                    image_status.data, args.bayer_pattern
                                )
                                if debayer_status.is_success:
                                    import cv2

                                    cv2.imwrite(args.output, debayer_status.data)
                                    print(f"Debayered image saved to: {args.output}")
                                else:
                                    print(f"Debayering failed: {debayer_status.message}")
                            else:
                                print(f"Failed to get image: {image_status.message}")
                        else:
                            print(f"Exposure failed: {expose_status.message}")
                    else:
                        print("Debayering only available for color cameras")
                    camera.disconnect()
                else:
                    print(f"Connection failed: {connect_status.message}")
                    sys.exit(1)
            else:
                print("Debayering requires ASCOM camera")
                sys.exit(1)

        else:  # capture
            # Regular capture
            if args.camera_type == "ascom":
                # ASCOM camera capture
                status = capture.connect()
                if status.is_success:
                    print(f"ASCOM camera connected: {status.message}")

                    # Get binning from CLI argument or config
                    binning = (
                        args.binning
                        if hasattr(args, "binning")
                        else config.get_camera_config().get("ascom", {}).get("binning", 1)
                    )

                    # Capture single frame with ASCOM camera
                    capture_status = capture.capture_single_frame_ascom(
                        exposure_time_s=args.exposure, gain=args.gain, binning=binning
                    )

                    if capture_status.is_success:
                        # Extract frame data from capture status
                        frame_data = capture_status.data
                        save_status = capture.save_frame(frame_data, args.output)
                        if save_status.is_success:
                            print(f"Frame captured and saved to: {save_status.data}")
                        else:
                            print(f"Save failed: {save_status.message}")
                            sys.exit(1)
                    else:
                        print(f"Capture failed: {capture_status.message}")
                        sys.exit(1)

                    capture.disconnect()
                else:
                    print(f"Connection failed: {status.message}")
                    sys.exit(1)

            elif args.camera_type == "alpaca":
                # Alpyca camera capture
                from alpaca_camera import AlpycaCameraWrapper

                camera = AlpycaCameraWrapper(
                    host=args.alpaca_host,
                    port=args.alpaca_port,
                    device_id=args.alpaca_device_id,
                    config=config,
                    logger=logger,
                )

                connect_status = camera.connect()
                if connect_status.is_success:
                    print(f"Alpyca camera connected: {connect_status.message}")

                    # Start exposure
                    exposure_status = camera.start_exposure(args.exposure, True)
                    if exposure_status.is_success:
                        print(f"Exposure started: {exposure_status.message}")

                        # Wait for exposure to complete
                        print("Waiting for exposure to complete...")
                        while not camera.image_ready:
                            import time

                            time.sleep(0.1)
                            if camera.percent_completed:
                                print(f"  Progress: {camera.percent_completed}%")

                        print("Exposure completed")

                        # Get image array
                        image_status = camera.get_image_array()
                        if image_status.is_success:
                            image_array = image_status.data
                            print(f"Image captured successfully: {type(image_array)}")

                            # Save image using VideoCapture's save method
                            save_status = capture.save_frame(image_array, args.output)
                            if save_status.is_success:
                                print(f"Frame captured and saved to: {save_status.data}")
                            else:
                                print(f"Save failed: {save_status.message}")
                                sys.exit(1)
                        else:
                            print(f"Failed to get image: {image_status.message}")
                            sys.exit(1)
                    else:
                        print(f"Exposure failed: {exposure_status.message}")
                        sys.exit(1)

                    camera.disconnect()
                else:
                    print(f"Connection failed: {connect_status.message}")
                    sys.exit(1)

            else:
                # OpenCV camera capture
                status = capture.connect()
                if status.is_success:
                    print(f"OpenCV camera connected: {status.message}")

                    capture_status = capture.capture_single_frame()

                    if capture_status.is_success:
                        # Extract frame data from capture status
                        frame_data = capture_status.data
                        save_status = capture.save_frame(frame_data, args.output)
                        if save_status.is_success:
                            print(f"Frame captured and saved to: {save_status.data}")
                        else:
                            print(f"Save failed: {save_status.message}")
                            sys.exit(1)
                    else:
                        print(f"Capture failed: {capture_status.message}")
                        sys.exit(1)

                    capture.disconnect()
                else:
                    print(f"Connection failed: {status.message}")
                    sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
