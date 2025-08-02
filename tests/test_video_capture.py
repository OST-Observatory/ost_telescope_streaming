import logging
import sys
from pathlib import Path

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from config_manager import ConfigManager
from video_capture import VideoCapture
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Video capture with ASCOM camera support")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    
    # Parse config argument first to load the right configuration
    args, remaining = parser.parse_known_args()
    
    # Load configuration
    if args.config:
        config = ConfigManager(config_path=args.config)
    else:
        config = ConfigManager()
    
    video_config = config.get_video_config()
    
    # Recreate parser with the loaded configuration defaults
    parser = argparse.ArgumentParser(description="Video capture with ASCOM camera support")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--camera-index", type=int, default=video_config['opencv']['camera_index'],
                       help="Camera device index (OpenCV)")
    parser.add_argument("--camera-type", choices=['opencv', 'ascom'], 
                       default=video_config['camera_type'],
                       help="Camera type: opencv for regular cameras, ascom for astro cameras")
    parser.add_argument("--ascom-driver", default=video_config['ascom']['ascom_driver'],
                       help="ASCOM driver ID (astro cameras)")
    parser.add_argument("--width", type=int, default=video_config['opencv']['frame_width'],
                       help="Frame width")
    parser.add_argument("--height", type=int, default=video_config['opencv']['frame_height'],
                       help="Frame height")
    parser.add_argument("--fps", type=int, default=video_config['opencv']['fps'],
                       help="Frame rate")
    parser.add_argument("--exposure", type=float, default=video_config['opencv']['exposure_time'],
                       help="Exposure time in seconds")
    parser.add_argument("--gain", type=float, default=video_config['ascom']['gain'],
                       help="Gain setting (ASCOM cameras)")
    parser.add_argument("--binning", type=int, default=video_config['ascom']['binning'],
                       help="Binning factor (1x1, 2x2, etc.)")
    parser.add_argument("--output", default="captured_frame.jpg",
                       help="Output filename")
    parser.add_argument("--action", choices=['capture', 'info', 'cooling', 'cooling-off', 'cooling-status', 'cooling-status-cache', 'cooling-background', 'filter', 'debayer'],
                       default='capture', help="Action to perform")
    parser.add_argument("--cooling-temp", type=float, help="Target cooling temperature in °C")
    parser.add_argument("--keep-cooling", action='store_true', help="Keep cooling on when disconnecting (cooling action only)")
    parser.add_argument("--filter-position", type=int, help="Filter wheel position")
    parser.add_argument("--bayer-pattern", default='RGGB', 
                       choices=['RGGB', 'GRBG', 'GBRG', 'BGGR'],
                       help="Bayer pattern for debayering")
    
    args = parser.parse_args()

    try:
        logger = logging.getLogger("video_capture_cli")
        logger.setLevel(logging.DEBUG)  # Enable debug logging
        
        # Update config with command line arguments BEFORE creating VideoCapture
        video_config['camera_type'] = args.camera_type
        video_config['opencv']['camera_index'] = args.camera_index
        video_config['ascom']['ascom_driver'] = args.ascom_driver
        
        capture = VideoCapture(config=config, logger=logger)
        
        if args.action == 'info':
            # Show camera information
            if args.camera_type == 'ascom' and args.ascom_driver:
                from ascom_camera import ASCOMCamera
                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    print(f"Camera connected: {connect_status.message}")
                    
                    # Add a small delay to ensure ASCOM driver has updated values
                    import time
                    time.sleep(0.5)
                    
                    # Check cooling
                    if camera.has_cooling():
                        print(f"Cooling supported: ✅")
                        
                        # Use force refresh for accurate readings
                        print(f"Refreshing cooling status...")
                        refresh_status = camera.force_refresh_cooling_status()
                        
                        if refresh_status.is_success:
                            info = refresh_status.data
                            print(f"Current temperature: {info['temperature']}°C")
                            print(f"Cooler power: {info['cooler_power']}%")
                            print(f"Cooler on: {info['cooler_on']}")
                            print(f"Target temperature: {info['target_temperature']}°C")
                            print(f"Can set cooler power: {info['can_set_cooler_power']}")
                            print(f"Refresh attempts: {info['refresh_attempts']}")
                            
                            # Show cooling analysis
                            if info['cooler_power'] == 0 and info['cooler_on']:
                                print(f"⚠️  Cooler is on but power is 0% - may need time to start")
                            elif info['cooler_power'] > 0:
                                print(f"✅ Cooler is active with {info['cooler_power']}% power")
                            elif not info['cooler_on']:
                                print(f"ℹ️  Cooler is off")
                        else:
                            print(f"❌ Cooling refresh failed: {refresh_status.message}")
                            
                            # Fallback to smart cooling info
                            cooling_info_status = camera.get_smart_cooling_info()
                            if cooling_info_status.is_success:
                                info = cooling_info_status.data
                                print(f"Current temperature: {info['temperature']}°C")
                                print(f"Cooler power: {info['cooler_power']}%")
                                print(f"Cooler on: {info['cooler_on']}")
                                print(f"Target temperature: {info['target_temperature']}°C")
                    else:
                        print(f"Cooling supported: ❌")
                    
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
                    
                    # Show filter wheel driver info if configured
                    if hasattr(camera, 'filter_wheel_driver_id') and camera.filter_wheel_driver_id:
                        print(f"Separate filter wheel driver: {camera.filter_wheel_driver_id}")
                    else:
                        print("No separate filter wheel driver configured")
                    
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
                from ascom_camera import ASCOMCamera
                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    print(f"✅ Connected successfully")
                    print(f"Setting target temperature to {args.cooling_temp}°C...")
                    
                    # Set cooling with improved method
                    cooling_status = camera.set_cooling(args.cooling_temp)
                    print(f"Cooling status: {cooling_status.level.value.upper()} - {cooling_status.message}")
                    
                    # Show detailed cooling information if available
                    if cooling_status.is_success and hasattr(cooling_status, 'details') and cooling_status.details:
                        details = cooling_status.details
                        print(f"  Target temperature: {details.get('target_temp')}°C")
                        print(f"  Temperature before: {details.get('current_temp')}°C")
                        print(f"  Temperature after: {details.get('new_temp')}°C")
                        print(f"  Cooler power before: {details.get('current_power')}%")
                        print(f"  Cooler power after: {details.get('new_power')}%")
                        print(f"  Cooler on before: {details.get('current_cooler_on')}")
                        print(f"  Cooler on after: {details.get('new_cooler_on')}")
                    
                    # Force refresh cooling status to get accurate power readings
                    print(f"\nForcing cooling status refresh...")
                    refresh_status = camera.force_refresh_cooling_status()
                    if refresh_status.is_success:
                        refresh_info = refresh_status.data
                        print(f"✅ Cooling status refreshed successfully!")
                        print(f"  Temperature: {refresh_info.get('temperature')}°C")
                        print(f"  Cooler power: {refresh_info.get('cooler_power')}%")
                        print(f"  Cooler on: {refresh_info.get('cooler_on')}")
                        print(f"  Target temperature: {refresh_info.get('target_temperature')}°C")
                        print(f"  Refresh attempts: {refresh_info.get('refresh_attempts')}")
                    else:
                        print(f"⚠️  Force refresh failed: {refresh_status.message}")
                    
                    # Wait for cooling to stabilize
                    print(f"\nWaiting for cooling to stabilize (timeout: 30s)...")
                    stabilization_status = camera.wait_for_cooling_stabilization(timeout=30, check_interval=2.0)
                    
                    if stabilization_status.is_success:
                        final_info = stabilization_status.data
                        print(f"✅ Cooling stabilized successfully!")
                        print(f"Final status:")
                        print(f"  Temperature: {final_info.get('temperature')}°C")
                        print(f"  Cooler power: {final_info.get('cooler_power')}%")
                        print(f"  Cooler on: {final_info.get('cooler_on')}")
                        print(f"  Target temperature: {final_info.get('target_temperature')}°C")
                    else:
                        print(f"⚠️  Cooling stabilization: {stabilization_status.message}")
                        if hasattr(stabilization_status, 'data') and stabilization_status.data:
                            final_info = stabilization_status.data
                            print(f"Final status (timeout):")
                            print(f"  Temperature: {final_info.get('temperature')}°C")
                            print(f"  Cooler power: {final_info.get('cooler_power')}%")
                            print(f"  Cooler on: {final_info.get('cooler_on')}")
                    
                    # Handle cooling when disconnecting
                    if args.keep_cooling:
                        print(f"\n⚠️  Keeping cooling on when disconnecting...")
                        print(f"   Note: Cooling will remain active after disconnect")
                        print(f"   Camera connection will be released but cooling stays on")
                        
                        # For ASCOM cameras, we need to keep the connection alive to maintain cooling
                        # Instead of disconnecting, we'll just release the Python object reference
                        # but keep the ASCOM connection active
                        print(f"   ⚠️  ASCOM limitation: Cooling will turn off when connection is lost")
                        print(f"   💡 Solution: Keep camera connected in background")
                        
                        # Don't disconnect - keep the connection alive
                        # The camera object will be garbage collected, but ASCOM connection stays
                        print(f"✅ Camera connection kept alive (cooling active)")
                        print(f"   ⚠️  IMPORTANT: Don't close this terminal or run other camera commands!")
                        print(f"   ⚠️  Use 'cooling-off' action in a NEW terminal to turn off cooling")
                        print(f"   💡 Tip: Keep this terminal open to maintain cooling")
                        
                        # Return without disconnecting
                        return
                    else:
                        print(f"\n⚠️  Disconnecting will turn off cooling...")
                        print(f"   Use --keep-cooling to maintain cooling after disconnect")
                        camera.disconnect()
                        print(f"✅ Disconnected from camera (cooling turned off)")
        
        elif args.action == 'cooling-off':
            if args.camera_type == 'ascom' and args.ascom_driver:
                from ascom_camera import ASCOMCamera
                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    print(f"✅ Connected successfully")
                    print(f"Turning off cooling...")
                    
                    # Turn off cooling explicitly
                    cooling_off_status = camera.turn_cooling_off()
                    print(f"Cooling off status: {cooling_off_status.level.value.upper()} - {cooling_off_status.message}")
                    
                    # Show detailed cooling off information if available
                    if cooling_off_status.is_success and hasattr(cooling_off_status, 'details') and cooling_off_status.details:
                        details = cooling_off_status.details
                        print(f"  Temperature before: {details.get('current_temp')}°C")
                        print(f"  Temperature after: {details.get('new_temp')}°C")
                        print(f"  Cooler power before: {details.get('current_power')}%")
                        print(f"  Cooler power after: {details.get('new_power')}%")
                        print(f"  Cooler on before: {details.get('current_cooler_on')}")
                        print(f"  Cooler on after: {details.get('new_cooler_on')}")
                    
                    # Force refresh to confirm cooling is off
                    print(f"\nConfirming cooling status...")
                    refresh_status = camera.force_refresh_cooling_status()
                    if refresh_status.is_success:
                        refresh_info = refresh_status.data
                        print(f"✅ Cooling status confirmed:")
                        print(f"  Temperature: {refresh_info.get('temperature')}°C")
                        print(f"  Cooler power: {refresh_info.get('cooler_power')}%")
                        print(f"  Cooler on: {refresh_info.get('cooler_on')}")
                    
                    # Now disconnect
                    camera.disconnect()
                    print(f"✅ Disconnected from camera (cooling turned off)")
                else:
                    print(f"❌ Connection failed: {connect_status.message}")
                    sys.exit(1)
            else:
                print("Cooling off requires ASCOM camera")
                sys.exit(1)
        
        elif args.action == 'cooling-status':
            if args.camera_type == 'ascom' and args.ascom_driver:
                from ascom_camera import ASCOMCamera
                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                
                print(f"Checking cooling status (non-intrusive)...")
                
                # Try to connect without affecting existing cooling
                connect_status = camera.connect()
                if connect_status.is_success:
                    print(f"✅ Connected successfully")
                    
                    # Use force refresh to get accurate status without changing settings
                    print(f"Reading cooling status...")
                    refresh_status = camera.force_refresh_cooling_status()
                    
                    if refresh_status.is_success:
                        info = refresh_status.data
                        print(f"Current cooling status:")
                        print(f"  Temperature: {info['temperature']}°C")
                        print(f"  Cooler power: {info['cooler_power']}%")
                        print(f"  Cooler on: {info['cooler_on']}")
                        print(f"  Target temperature: {info['target_temperature']}°C")
                        print(f"  Can set cooler power: {info['can_set_cooler_power']}")
                        
                        # Provide analysis of the status
                        if info['cooler_on'] and info['cooler_power'] > 0:
                            print(f"✅ Cooling is active and working")
                        elif info['cooler_on'] and info['cooler_power'] == 0:
                            print(f"⚠️  Cooler is on but power is 0% - may be at target temperature")
                        elif not info['cooler_on']:
                            print(f"ℹ️  Cooler is off")
                        
                        # Check if target temperature is set
                        if info['target_temperature'] is not None:
                            temp_diff = info['temperature'] - info['target_temperature']
                            print(f"  Temperature difference: {temp_diff:+.1f}°C")
                    else:
                        print(f"❌ Failed to read cooling status: {refresh_status.message}")
                        
                        # Fallback to smart cooling info
                        cooling_info_status = camera.get_smart_cooling_info()
                        if cooling_info_status.is_success:
                            info = cooling_info_status.data
                            print(f"Fallback cooling status:")
                            print(f"  Temperature: {info['temperature']}°C")
                            print(f"  Cooler power: {info['cooler_power']}%")
                            print(f"  Cooler on: {info['cooler_on']}")
                            print(f"  Target temperature: {info['target_temperature']}°C")
                        else:
                            print(f"❌ Both status methods failed")
                    
                    # Disconnect without affecting cooling
                    camera.disconnect()
                    print(f"✅ Disconnected (cooling settings preserved)")
                else:
                    print(f"❌ Connection failed: {connect_status.message}")
                    print(f"   This may indicate the camera is already in use by another application")
                    sys.exit(1)
            else:
                print("Cooling status check requires ASCOM camera")
                sys.exit(1)
        
        elif args.action == 'cooling-status-cache':
            # This action reads cooling status from the cache without connecting to the camera
            # It's useful for checking the current state of cooling without affecting settings
            print(f"Reading cooling status from cache...")
            try:
                import json
                from pathlib import Path
                
                # Construct the cache file path based on the driver ID
                driver_id = args.ascom_driver.replace('.', '_').replace(':', '_')
                cache_filename = f"cooling_cache_{driver_id}.json"
                cache_path = Path("cache") / cache_filename
                
                if not cache_path.exists():
                    print(f"❌ Cache file not found: {cache_path}")
                    print(f"   This may mean cooling has not been used yet or cache is in a different location")
                    sys.exit(1)
                
                # Load the cache file
                with open(cache_path, 'r') as f:
                    cache_data = json.load(f)
                
                print(f"✅ Cache file loaded: {cache_path}")
                
                # Extract cooling status from the cache
                if cache_data:
                    print(f"Current cooling status from cache:")
                    print(f"  Temperature: {cache_data.get('temperature')}°C")
                    print(f"  Cooler power: {cache_data.get('cooler_power')}%")
                    print(f"  Cooler on: {cache_data.get('cooler_on')}")
                    print(f"  Target temperature: {cache_data.get('target_temperature')}°C")
                    
                    # Provide analysis of the status
                    if cache_data.get('cooler_on') and cache_data.get('cooler_power', 0) > 0:
                        print(f"✅ Cooling is active and working (from cache)")
                    elif cache_data.get('cooler_on') and cache_data.get('cooler_power', 0) == 0:
                        print(f"⚠️  Cooler is on but power is 0% - may be at target temperature (from cache)")
                    elif not cache_data.get('cooler_on'):
                        print(f"ℹ️  Cooler is off (from cache)")
                        
                    # Check if target temperature is set
                    if cache_data.get('target_temperature') is not None and cache_data.get('temperature') is not None:
                        temp_diff = cache_data['temperature'] - cache_data['target_temperature']
                        print(f"  Temperature difference: {temp_diff:+.1f}°C (from cache)")
                        
                    # Show cache age if available
                    if 'timestamp' in cache_data:
                        from datetime import datetime
                        cache_time = datetime.fromtimestamp(cache_data['timestamp'])
                        age = datetime.now() - cache_time
                        print(f"  Cache age: {age.total_seconds():.1f} seconds")
                else:
                    print(f"❌ No cooling data found in cache")
                    
            except FileNotFoundError:
                print(f"❌ Cache file not found: {cache_path}")
                print(f"   This may mean cooling has not been used yet")
                sys.exit(1)
            except json.JSONDecodeError:
                print(f"❌ Error: Could not decode JSON from cache file {cache_path}")
                sys.exit(1)
            except Exception as e:
                print(f"❌ Error reading cache: {e}")
                sys.exit(1)
        
        elif args.action == 'cooling-background':
            if args.camera_type == 'ascom' and args.ascom_driver:
                from ascom_camera import ASCOMCamera
                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    print(f"✅ Connected successfully")
                    print(f"Starting cooling in background...")
                    
                    # Set cooling with improved method
                    cooling_status = camera.set_cooling(args.cooling_temp)
                    print(f"Cooling status: {cooling_status.level.value.upper()} - {cooling_status.message}")
                    
                    # Show detailed cooling information if available
                    if cooling_status.is_success and hasattr(cooling_status, 'details') and cooling_status.details:
                        details = cooling_status.details
                        print(f"  Target temperature: {details.get('target_temp')}°C")
                        print(f"  Temperature before: {details.get('current_temp')}°C")
                        print(f"  Temperature after: {details.get('new_temp')}°C")
                        print(f"  Cooler power before: {details.get('current_power')}%")
                        print(f"  Cooler power after: {details.get('new_power')}%")
                        print(f"  Cooler on before: {details.get('current_cooler_on')}")
                        print(f"  Cooler on after: {details.get('new_cooler_on')}")
                    
                    # Force refresh cooling status to get accurate power readings
                    print(f"\nForcing cooling status refresh...")
                    refresh_status = camera.force_refresh_cooling_status()
                    if refresh_status.is_success:
                        refresh_info = refresh_status.data
                        print(f"✅ Cooling status refreshed successfully!")
                        print(f"  Temperature: {refresh_info.get('temperature')}°C")
                        print(f"  Cooler power: {refresh_info.get('cooler_power')}%")
                        print(f"  Cooler on: {refresh_info.get('cooler_on')}")
                        print(f"  Target temperature: {refresh_info.get('target_temperature')}°C")
                        print(f"  Refresh attempts: {refresh_info.get('refresh_attempts')}")
                    else:
                        print(f"⚠️  Force refresh failed: {refresh_status.message}")
                    
                    # Wait for cooling to stabilize
                    print(f"\nWaiting for cooling to stabilize (timeout: 30s)...")
                    stabilization_status = camera.wait_for_cooling_stabilization(timeout=30, check_interval=2.0)
                    
                    if stabilization_status.is_success:
                        final_info = stabilization_status.data
                        print(f"✅ Cooling stabilized successfully!")
                        print(f"Final status:")
                        print(f"  Temperature: {final_info.get('temperature')}°C")
                        print(f"  Cooler power: {final_info.get('cooler_power')}%")
                        print(f"  Cooler on: {final_info.get('cooler_on')}")
                        print(f"  Target temperature: {final_info.get('target_temperature')}°C")
                    else:
                        print(f"⚠️  Cooling stabilization: {stabilization_status.message}")
                        if hasattr(stabilization_status, 'data') and stabilization_status.data:
                            final_info = stabilization_status.data
                            print(f"Final status (timeout):")
                            print(f"  Temperature: {final_info.get('temperature')}°C")
                            print(f"  Cooler power: {final_info.get('cooler_power')}%")
                            print(f"  Cooler on: {final_info.get('cooler_on')}")
                    
                    # Handle cooling when disconnecting
                    if args.keep_cooling:
                        print(f"\n⚠️  Keeping cooling on when disconnecting...")
                        print(f"   Note: Cooling will remain active after disconnect")
                        print(f"   Camera connection will be released but cooling stays on")
                        
                        # For ASCOM cameras, we need to keep the connection alive to maintain cooling
                        # Instead of disconnecting, we'll just release the Python object reference
                        # but keep the ASCOM connection active
                        print(f"   ⚠️  ASCOM limitation: Cooling will turn off when connection is lost")
                        print(f"   💡 Solution: Keep camera connected in background")
                        
                        # Don't disconnect - keep the connection alive
                        # The camera object will be garbage collected, but ASCOM connection stays
                        print(f"✅ Camera connection kept alive (cooling active)")
                        print(f"   ⚠️  IMPORTANT: Don't close this terminal or run other camera commands!")
                        print(f"   ⚠️  Use 'cooling-off' action in a NEW terminal to turn off cooling")
                        print(f"   💡 Tip: Keep this terminal open to maintain cooling")
                        
                        # Return without disconnecting
                        return
                    else:
                        print(f"\n⚠️  Disconnecting will turn off cooling...")
                        print(f"   Use --keep-cooling to maintain cooling after disconnect")
                        camera.disconnect()
                        print(f"✅ Disconnected from camera (cooling turned off)")
                else:
                    print(f"❌ Connection failed: {connect_status.message}")
                    sys.exit(1)
            else:
                print("Cooling background requires ASCOM camera")
                sys.exit(1)
        
        elif args.action == 'filter':
            if args.camera_type == 'ascom' and args.ascom_driver and args.filter_position is not None:
                from ascom_camera import ASCOMCamera
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
                from ascom_camera import ASCOMCamera
                camera = ASCOMCamera(driver_id=args.ascom_driver, config=config, logger=logger)
                connect_status = camera.connect()
                if connect_status.is_success:
                    if camera.is_color_camera():
                        # Capture and debayer
                        # Get binning from CLI argument or config
                        binning = args.binning if hasattr(args, 'binning') else video_config['ascom']['binning']
                        
                        # Start exposure
                        expose_status = camera.expose(args.exposure, args.gain, binning)
                        if expose_status.is_success:
                            image_status = camera.get_image()
                            if image_status.is_success:
                                print(f"Image captured successfully")
                                print(f"Image data: {image_status.data}")
                                debayer_status = camera.debayer(image_status.data, args.bayer_pattern)
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
            status = capture.connect()
            if status.is_success:
                print(f"Camera connected: {status.message}")
                
                # For ASCOM cameras, use exposure time in seconds
                if args.camera_type == 'ascom':
                    # Get binning from CLI argument or config
                    binning = args.binning if hasattr(args, 'binning') else video_config['ascom']['binning']
                    
                    # Capture single frame with ASCOM camera
                    capture_status = capture.capture_single_frame_ascom(
                        exposure_time_s=args.exposure,
                        gain=args.gain,
                        binning=binning
                    )
                else:
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
