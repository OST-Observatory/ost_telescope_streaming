import logging
from code.config_manager import config
from code.video_capture import VideoCapture
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Video capture with ASCOM camera support")
    parser.add_argument("--camera-index", type=int, default=config['video']['camera_index'],
                       help="Camera device index")
    parser.add_argument("--camera-type", choices=['opencv', 'ascom'], 
                       default=config['video']['camera_type'],
                       help="Camera type: opencv for regular cameras, ascom for astro cameras")
    parser.add_argument("--ascom-driver", default=config['video']['ascom_driver'],
                       help="ASCOM driver ID for astro cameras")
    parser.add_argument("--width", type=int, default=config['video']['frame_width'],
                       help="Frame width")
    parser.add_argument("--height", type=int, default=config['video']['frame_height'],
                       help="Frame height")
    parser.add_argument("--fps", type=int, default=config['video']['fps'],
                       help="Frame rate")
    parser.add_argument("--exposure", type=float, default=config['video']['exposure_time']/1000.0,
                       help="Exposure time in seconds")
    parser.add_argument("--gain", type=float, default=config['video']['gain'],
                       help="Gain setting")
    parser.add_argument("--output", default="captured_frame.jpg",
                       help="Output filename")
    parser.add_argument("--action", choices=['capture', 'info', 'cooling', 'filter', 'debayer'],
                       default='capture', help="Action to perform")
    parser.add_argument("--cooling-temp", type=float, help="Target cooling temperature in °C")
    parser.add_argument("--filter-position", type=int, help="Filter wheel position")
    parser.add_argument("--bayer-pattern", default='RGGB', 
                       choices=['RGGB', 'GRBG', 'GBRG', 'BGGR'],
                       help="Bayer pattern for debayering")
    
    args = parser.parse_args()

    try:
        logger = logging.getLogger("video_capture_cli")
        logger.setLevel(logging.INFO)
        
        # Update config with command line arguments
        config['video']['camera_type'] = args.camera_type
        config['video']['ascom_driver'] = args.ascom_driver
        
        capture = VideoCapture(config=config, logger=logger)
        
        if args.action == 'info':
            # Show camera information
            if args.camera_type == 'ascom' and args.ascom_driver:
                from code.ascom_camera import ASCOMCamera
                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    print(f"Camera connected: {connect_status.message}")
                    
                    # Check cooling
                    if camera.has_cooling():
                        temp_status = camera.get_temperature()
                        if temp_status.is_success:
                            print(f"Current temperature: {temp_status.data}°C")
                        else:
                            print(f"Temperature read failed: {temp_status.message}")
                    else:
                        print("Cooling not supported")
                    
                    # Check filter wheel
                    if camera.has_filter_wheel():
                        filter_names_status = camera.get_filter_names()
                        if filter_names_status.is_success:
                            print(f"Available filters: {filter_names_status.data}")
                        else:
                            print(f"Filter names failed: {filter_names_status.message}")
                        
                        filter_pos_status = camera.get_filter_position()
                        if filter_pos_status.is_success:
                            print(f"Current filter position: {filter_pos_status.data}")
                        else:
                            print(f"Filter position failed: {filter_pos_status.message}")
                    else:
                        print("No filter wheel present")
                    
                    # Check if color camera
                    if camera.is_color_camera():
                        print("Color camera detected - debayering available")
                    else:
                        print("Mono camera detected")
                    
                    camera.disconnect()
                else:
                    print(f"Connection failed: {connect_status.message}")
                    sys.exit(1)
            else:
                print("Camera info only available for ASCOM cameras")
        
        elif args.action == 'cooling':
            if args.camera_type == 'ascom' and args.ascom_driver and args.cooling_temp is not None:
                from code.ascom_camera import ASCOMCamera
                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    cooling_status = camera.set_cooling(args.cooling_temp)
                    print(f"Cooling status: {cooling_status.level.value.upper()} - {cooling_status.message}")
                    camera.disconnect()
                else:
                    print(f"Connection failed: {connect_status.message}")
                    sys.exit(1)
            else:
                print("Cooling control requires ASCOM camera and --cooling-temp parameter")
                sys.exit(1)
        
        elif args.action == 'filter':
            if args.camera_type == 'ascom' and args.ascom_driver and args.filter_position is not None:
                from code.ascom_camera import ASCOMCamera
                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    filter_status = camera.set_filter_position(args.filter_position)
                    print(f"Filter status: {filter_status.level.value.upper()} - {filter_status.message}")
                    camera.disconnect()
                else:
                    print(f"Connection failed: {connect_status.message}")
                    sys.exit(1)
            else:
                print("Filter control requires ASCOM camera and --filter-position parameter")
                sys.exit(1)
        
        elif args.action == 'debayer':
            if args.camera_type == 'ascom' and args.ascom_driver:
                from code.ascom_camera import ASCOMCamera
                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    if camera.is_color_camera():
                        # Capture and debayer
                        expose_status = camera.expose(args.exposure, args.gain)
                        if expose_status.is_success:
                            image_status = camera.get_image()
                            if image_status.is_success:
                                debayer_status = camera.debayer(image_status.data, args.bayer_pattern)
                                if debayer_status.is_success:
                                    import cv2
                                    cv2.imwrite(args.output, debayer_status.data)
                                    print(f"Debayered image saved to: {args.output}")
                                else:
                                    print(f"Debayering failed: {debayer_status.message}")
                            else:
                                print(f"Image capture failed: {image_status.message}")
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
            status = capture.connect()
            if status.is_success:
                print(f"Camera connected: {status.message}")
                
                # For ASCOM cameras, use exposure time in seconds
                if args.camera_type == 'ascom':
                    capture_status = capture.capture_single_frame_ascom(
                        exposure_time_s=args.exposure, 
                        gain=args.gain
                    )
                else:
                    capture_status = capture.capture_single_frame()
                
                if capture_status.is_success:
                    save_status = capture.save_frame(args.output)
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
