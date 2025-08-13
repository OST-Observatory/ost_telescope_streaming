#!/usr/bin/env python3
"""
Example script demonstrating ASCOM Camera usage.
This script shows how to use the ASCOM Camera features including:
- Basic camera control
- Cooling control
- Filter wheel control
- Debayering for color cameras
"""

import logging
from pathlib import Path
import sys

# Add the code directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from config_manager import config
from drivers.ascom.camera import ASCOMCamera


def main():
    """Main example function."""
    print("ASCOM Camera Example")
    print("=" * 30)

    # Set up logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

    # Example ASCOM driver IDs (replace with your actual drivers)
    # QHY Camera: "ASCOM.QHYCamera.Camera"
    # ZWO Camera: "ASCOM.ZWOCamera.Camera"
    driver_id = "ASCOM.QHYCamera.Camera"  # Change this to your camera driver

    try:
        # Create camera instance
        print(f"Connecting to ASCOM camera: {driver_id}")
        camera = ASCOMCamera(driver_id=driver_id, config=config, logger=logger)

        # Connect to camera
        connect_status = camera.connect()
        if not connect_status.is_success:
            print(f"Failed to connect: {connect_status.message}")
            return

        print("✓ Camera connected successfully")

        # 1. Basic Camera Information
        print("\n1. Camera Information:")
        print("-" * 20)

        # Check if camera has cooling
        if camera.has_cooling():
            print("✓ Camera supports cooling")
            temp_status = camera.get_temperature()
            if temp_status.is_success:
                print(f"  Current temperature: {temp_status.data}°C")
            else:
                print(f"  Temperature read failed: {temp_status.message}")
        else:
            print("✗ Camera does not support cooling")

        # Check if camera has filter wheel
        if camera.has_filter_wheel():
            print("✓ Camera has filter wheel")
            filter_names_status = camera.get_filter_names()
            if filter_names_status.is_success:
                print(f"  Available filters: {filter_names_status.data}")
            else:
                print(f"  Filter names failed: {filter_names_status.message}")

            filter_pos_status = camera.get_filter_position()
            if filter_pos_status.is_success:
                print(f"  Current filter position: {filter_pos_status.data}")
            else:
                print(f"  Filter position failed: {filter_pos_status.message}")
        else:
            print("✗ Camera does not have filter wheel")

        # Check if color camera
        if camera.is_color_camera():
            print("✓ Color camera detected")
        else:
            print("✓ Mono camera detected")

        # 2. Cooling Control Example
        print("\n2. Cooling Control Example:")
        print("-" * 30)

        if camera.has_cooling():
            # Set cooling to -10°C
            target_temp = -10.0
            print(f"Setting cooling to {target_temp}°C...")
            cooling_status = camera.set_cooling(target_temp)
            print(
                f"Cooling status: {cooling_status.level.value.upper()} - {cooling_status.message}"
            )

            # Wait a moment and check temperature
            import time

            time.sleep(2)
            temp_status = camera.get_temperature()
            if temp_status.is_success:
                print(f"Current temperature: {temp_status.data}°C")
        else:
            print("Skipping cooling example (not supported)")

        # 3. Filter Wheel Control Example
        print("\n3. Filter Wheel Control Example:")
        print("-" * 35)

        if camera.has_filter_wheel():
            # Get current position
            current_pos_status = camera.get_filter_position()
            if current_pos_status.is_success:
                current_pos = current_pos_status.data
                print(f"Current filter position: {current_pos}")

                # Move to position 1 (if different from current)
                if current_pos != 1:
                    print("Moving to filter position 1...")
                    filter_status = camera.set_filter_position(1)
                    print(
                        f"Filter move status: {filter_status.level.value.upper()} - "
                        f"{filter_status.message}"
                    )
                else:
                    print("Already at filter position 1")
        else:
            print("Skipping filter wheel example (not supported)")

        # 4. Image Capture Example
        print("\n4. Image Capture Example:")
        print("-" * 25)

        # Capture with 5 second exposure
        exposure_time = 5.0  # seconds
        gain = 20

        # Get binning from config
        binning = config["video"]["ascom"]["binning"]

        print(f"Capturing image with {exposure_time}s exposure, gain={gain}, binning={binning}...")
        expose_status = camera.expose(exposure_time, gain, binning)
        if not expose_status.is_success:
            print(f"Exposure failed: {expose_status.message}")
            return

        print("✓ Exposure completed")

        # Get the image
        image_status = camera.get_image()
        if not image_status.is_success:
            print(f"Image retrieval failed: {image_status.message}")
            return

        print("✓ Image retrieved")

        # 5. Debayering Example (for color cameras)
        print("\n5. Debayering Example:")
        print("-" * 20)

        if camera.is_color_camera():
            print("Processing color image...")
            debayer_status = camera.debayer(image_status.data)
            if debayer_status.is_success:
                print("✓ Debayering successful")

                # Save the debayered image
                import cv2

                output_file = "ascom_camera_example_debayered.jpg"
                cv2.imwrite(output_file, debayer_status.data)
                print(f"✓ Debayered image saved to: {output_file}")
            else:
                print(f"Debayering failed: {debayer_status.message}")

                # Save the raw image instead
                import cv2

                output_file = "ascom_camera_example_raw.jpg"
                cv2.imwrite(output_file, image_status.data)
                print(f"✓ Raw image saved to: {output_file}")
        else:
            print("Skipping debayering (mono camera)")

            # Save the mono image
            import cv2

            output_file = "ascom_camera_example_mono.jpg"
            cv2.imwrite(output_file, image_status.data)
            print(f"✓ Mono image saved to: {output_file}")

        # 6. Disconnect
        print("\n6. Disconnecting:")
        print("-" * 15)

        disconnect_status = camera.disconnect()
        print(
            f"Disconnect status: {disconnect_status.level.value.upper()} - "
            f"{disconnect_status.message}"
        )

        print("\n✓ Example completed successfully!")

    except Exception as e:
        print(f"Error in example: {e}")
        logger.exception("Example failed")


if __name__ == "__main__":
    main()
