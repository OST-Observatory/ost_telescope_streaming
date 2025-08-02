#!/usr/bin/env python3
"""
Test script for Alpyca camera integration.

This script tests the AlpycaCameraWrapper class and all its features.
"""

import sys
import logging
import time
from pathlib import Path

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from alpaca_camera import AlpycaCameraWrapper
from config_manager import ConfigManager

def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("alpaca_test")

def test_connection():
    """Test basic camera connection."""
    print("\n=== CONNECTION TEST ===")
    
    try:
        # Load configuration if provided
        config = None
        host = "localhost"
        port = 11111
        device_id = 0
        
        if len(sys.argv) > 2 and sys.argv[1] == '--config':
            config_file = sys.argv[2]
            print(f"Loading configuration from: {config_file}")
            try:
                config = ConfigManager(config_file)
                video_config = config.get_video_config()
                alpaca_config = video_config.get('alpaca', {})
                
                host = alpaca_config.get('host', 'localhost')
                port = alpaca_config.get('port', 11111)
                device_id = alpaca_config.get('device_id', 0)
                
                print(f"Using config: host={host}, port={port}, device_id={device_id}")
            except Exception as e:
                print(f"⚠️  Failed to load configuration: {e}")
                print("Using default configuration")
        else:
            print("Using default configuration")
        
        # Create camera instance
        camera = AlpycaCameraWrapper(
            host=host,
            port=port,
            device_id=device_id,
            config=config,
            logger=setup_logging()
        )
        
        # Test connection
        print("Testing Alpyca camera connection...")
        status = camera.connect()
        
        if not status.is_success:
            print(f"❌ Connection failed: {status.message}")
            print("💡 Make sure Alpaca server is running on localhost:11111")
            return False
        
        print(f"✅ Connected to: {camera.name}")
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def test_camera_properties(camera):
    """Test camera properties."""
    print("\n=== CAMERA PROPERTIES TEST ===")
    
    try:
        # Core properties
        print(f"Name: {camera.name}")
        print(f"Description: {camera.description}")
        print(f"Driver: {camera.driver_info}")
        print(f"Version: {camera.driver_version}")
        print(f"Interface: {camera.interface_version}")
        print(f"Connected: {camera.connected}")
        
        # Sensor properties
        print(f"\nSensor Information:")
        print(f"  Sensor: {camera.sensor_name}")
        print(f"  Type: {camera.sensor_type}")
        print(f"  Size: {camera.camera_x_size}x{camera.camera_y_size}")
        print(f"  Pixel size: {camera.pixel_size_x}x{camera.pixel_size_y} μm")
        print(f"  Max ADU: {camera.max_adu}")
        print(f"  Electrons per ADU: {camera.electrons_per_adu}")
        print(f"  Full well capacity: {camera.full_well_capacity}")
        
        # Camera type detection
        print(f"\nCamera Type Detection:")
        is_color = camera.is_color_camera()
        print(f"  Is color camera: {is_color}")
        
        return True
        
    except Exception as e:
        print(f"❌ Properties test failed: {e}")
        return False

def test_exposure_properties(camera):
    """Test exposure-related properties."""
    print("\n=== EXPOSURE PROPERTIES TEST ===")
    
    try:
        print(f"Exposure limits:")
        print(f"  Min: {camera.exposure_min} s")
        print(f"  Max: {camera.exposure_max} s")
        print(f"  Resolution: {camera.exposure_resolution} s")
        
        print(f"\nLast exposure:")
        print(f"  Duration: {camera.last_exposure_duration} s")
        print(f"  Start time: {camera.last_exposure_start_time}")
        
        print(f"\nCurrent state:")
        print(f"  Camera state: {camera.camera_state}")
        print(f"  Image ready: {camera.image_ready}")
        print(f"  Percent completed: {camera.percent_completed}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Exposure properties test failed: {e}")
        return False

def test_binning_properties(camera):
    """Test binning properties."""
    print("\n=== BINNING PROPERTIES TEST ===")
    
    try:
        print(f"Current binning: {camera.bin_x}x{camera.bin_y}")
        print(f"Max binning: {camera.max_bin_x}x{camera.max_bin_y}")
        print(f"Can asymmetric bin: {camera.can_asymmetric_bin}")
        
        # Test setting binning
        if camera.max_bin_x and camera.max_bin_x > 1:
            print(f"\nTesting binning change...")
            original_bin_x = camera.bin_x
            original_bin_y = camera.bin_y
            
            # Set to 2x2 if supported
            if camera.max_bin_x >= 2 and camera.max_bin_y >= 2:
                camera.bin_x = 2
                camera.bin_y = 2
                print(f"  Set binning to: {camera.bin_x}x{camera.bin_y}")
                
                # Restore original
                camera.bin_x = original_bin_x
                camera.bin_y = original_bin_y
                print(f"  Restored binning to: {camera.bin_x}x{camera.bin_y}")
            else:
                print("  Skipping binning test (max binning < 2)")
        
        return True
        
    except Exception as e:
        print(f"❌ Binning properties test failed: {e}")
        return False

def test_cooling_properties(camera):
    """Test cooling properties."""
    print("\n=== COOLING PROPERTIES TEST ===")
    
    try:
        print(f"Cooling support:")
        print(f"  Can set CCD temperature: {camera.can_set_ccd_temperature}")
        print(f"  Can get cooler power: {camera.can_get_cooler_power}")
        
        if camera.can_set_ccd_temperature:
            print(f"\nCurrent cooling status:")
            print(f"  CCD temperature: {camera.ccd_temperature}°C")
            print(f"  Target temperature: {camera.set_ccd_temperature}°C")
            print(f"  Cooler on: {camera.cooler_on}")
            print(f"  Cooler power: {camera.cooler_power}%")
            print(f"  Heat sink temperature: {camera.heat_sink_temperature}°C")
        else:
            print("  Cooling not supported by this camera")
        
        return True
        
    except Exception as e:
        print(f"❌ Cooling properties test failed: {e}")
        return False

def test_gain_offset_properties(camera):
    """Test gain and offset properties."""
    print("\n=== GAIN/OFFSET PROPERTIES TEST ===")
    
    try:
        print(f"Gain settings:")
        print(f"  Current gain: {camera.gain}")
        print(f"  Min gain: {camera.gain_min}")
        print(f"  Max gain: {camera.gain_max}")
        print(f"  Available gains: {camera.gains}")
        
        print(f"\nOffset settings:")
        print(f"  Current offset: {camera.offset}")
        print(f"  Min offset: {camera.offset_min}")
        print(f"  Max offset: {camera.offset_max}")
        print(f"  Available offsets: {camera.offsets}")
        
        # Test setting gain/offset if supported
        if camera.gain is not None:
            print(f"\nTesting gain/offset change...")
            original_gain = camera.gain
            original_offset = camera.offset
            
            # Try to set different values
            if camera.gain_max and camera.gain_max > camera.gain_min:
                test_gain = min(camera.gain_max, camera.gain + 10)
                camera.gain = test_gain
                print(f"  Set gain to: {camera.gain}")
                
                # Restore original
                camera.gain = original_gain
                print(f"  Restored gain to: {camera.gain}")
            
            if camera.offset_max and camera.offset_max > camera.offset_min:
                test_offset = min(camera.offset_max, camera.offset + 5)
                camera.offset = test_offset
                print(f"  Set offset to: {camera.offset}")
                
                # Restore original
                camera.offset = original_offset
                print(f"  Restored offset to: {camera.offset}")
        
        return True
        
    except Exception as e:
        print(f"❌ Gain/offset properties test failed: {e}")
        return False

def test_readout_properties(camera):
    """Test readout mode properties."""
    print("\n=== READOUT PROPERTIES TEST ===")
    
    try:
        print(f"Readout modes:")
        print(f"  Current mode: {camera.readout_mode}")
        print(f"  Available modes: {camera.readout_modes}")
        print(f"  Can fast readout: {camera.can_fast_readout}")
        print(f"  Fast readout: {camera.fast_readout}")
        
        # Test setting readout mode if supported
        if camera.readout_modes and len(camera.readout_modes) > 1:
            print(f"\nTesting readout mode change...")
            original_mode = camera.readout_mode
            
            # Try next mode
            next_mode = (original_mode + 1) % len(camera.readout_modes)
            camera.readout_mode = next_mode
            print(f"  Set readout mode to: {camera.readout_mode}")
            
            # Restore original
            camera.readout_mode = original_mode
            print(f"  Restored readout mode to: {camera.readout_mode}")
        
        return True
        
    except Exception as e:
        print(f"❌ Readout properties test failed: {e}")
        return False

def test_cooling_methods(camera):
    """Test cooling methods."""
    print("\n=== COOLING METHODS TEST ===")
    
    try:
        if not camera.can_set_ccd_temperature:
            print("  Cooling not supported by this camera")
            return True
        
        print("Testing cooling methods...")
        
        # Get current status
        status = camera.get_cooling_status()
        if status.is_success:
            info = status.data
            print(f"  Current temperature: {info['temperature']}°C")
            print(f"  Target temperature: {info['target_temperature']}°C")
            print(f"  Cooler on: {info['cooler_on']}")
            print(f"  Cooler power: {info['cooler_power']}%")
        
        # Test force refresh
        print(f"\nTesting force refresh...")
        refresh_status = camera.force_refresh_cooling_status()
        if refresh_status.is_success:
            info = refresh_status.data
            print(f"  Refreshed temperature: {info['temperature']}°C")
            print(f"  Refreshed cooler power: {info['cooler_power']}%")
            print(f"  Refresh attempts: {info['refresh_attempts']}")
        
        # Test setting cooling (if not already at target)
        current_temp = camera.ccd_temperature
        target_temp = camera.set_ccd_temperature
        
        if current_temp and target_temp and abs(current_temp - target_temp) > 5:
            print(f"\nTesting cooling set...")
            new_target = target_temp - 5  # 5°C cooler
            cooling_status = camera.set_cooling(new_target)
            print(f"  Cooling set result: {cooling_status.message}")
            
            # Wait a moment and check status
            time.sleep(2)
            status = camera.get_cooling_status()
            if status.is_success:
                info = status.data
                print(f"  New target: {info['target_temperature']}°C")
                print(f"  Current: {info['temperature']}°C")
                print(f"  Cooler on: {info['cooler_on']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Cooling methods test failed: {e}")
        return False

def test_exposure_methods(camera):
    """Test exposure methods."""
    print("\n=== EXPOSURE METHODS TEST ===")
    
    try:
        print("Testing exposure methods...")
        
        # Test short exposure
        exposure_time = 0.1  # 100ms
        print(f"Starting {exposure_time}s exposure...")
        
        start_status = camera.start_exposure(exposure_time, True)
        if not start_status.is_success:
            print(f"  ❌ Failed to start exposure: {start_status.message}")
            return False
        
        print(f"  ✅ Exposure started: {start_status.message}")
        
        # Wait for exposure to complete
        print("  Waiting for exposure to complete...")
        while not camera.image_ready:
            time.sleep(0.1)
            if camera.percent_completed:
                print(f"    Progress: {camera.percent_completed}%")
        
        print("  ✅ Exposure completed")
        
        # Get image array
        print("  Getting image array...")
        image_status = camera.get_image_array()
        if image_status.is_success:
            image_array = image_status.data
            print(f"  ✅ Image retrieved: {type(image_array)}")
            if hasattr(image_array, 'shape'):
                print(f"    Shape: {image_array.shape}")
        else:
            print(f"  ❌ Failed to get image: {image_status.message}")
        
        return True
        
    except Exception as e:
        print(f"❌ Exposure methods test failed: {e}")
        return False

def test_camera_info(camera):
    """Test comprehensive camera info."""
    print("\n=== CAMERA INFO TEST ===")
    
    try:
        info_status = camera.get_camera_info()
        if info_status.is_success:
            info = info_status.data
            print("Comprehensive camera information:")
            for key, value in info.items():
                print(f"  {key}: {value}")
        else:
            print(f"❌ Failed to get camera info: {info_status.message}")
        
        return True
        
    except Exception as e:
        print(f"❌ Camera info test failed: {e}")
        return False

def main():
    """Main test function."""
    print("=== ALPYCA CAMERA TEST ===")
    print("This test validates the Alpyca camera integration.")
    print("Make sure an Alpaca server is running on localhost:11111")
    print()
    
    # Load configuration if provided
    config = None
    host = "localhost"
    port = 11111
    device_id = 0
    
    if len(sys.argv) > 2 and sys.argv[1] == '--config':
        config_file = sys.argv[2]
        print(f"Loading configuration from: {config_file}")
        try:
            config = ConfigManager(config_file)
            video_config = config.get_video_config()
            alpaca_config = video_config.get('alpaca', {})
            
            host = alpaca_config.get('host', 'localhost')
            port = alpaca_config.get('port', 11111)
            device_id = alpaca_config.get('device_id', 0)
            
            print(f"Configuration loaded: host={host}, port={port}, device_id={device_id}")
        except Exception as e:
            print(f"⚠️  Failed to load configuration: {e}")
            print("Using default configuration")
    
    # Test connection first
    if not test_connection():
        print("\n❌ Connection test failed. Cannot proceed with other tests.")
        print("💡 Please ensure:")
        print("   1. Alpaca server is running on localhost:11111")
        print("   2. A camera is connected to the Alpaca server")
        print("   3. The camera is not in use by another application")
        return False
    
    # Create camera instance for other tests
    camera = AlpycaCameraWrapper(
        host=host,
        port=port,
        device_id=device_id,
        config=config,
        logger=setup_logging()
    )
    
    # Connect
    status = camera.connect()
    if not status.is_success:
        print(f"❌ Failed to connect: {status.message}")
        return False
    
    # Run all tests
    tests = [
        ("Camera Properties", test_camera_properties, camera),
        ("Exposure Properties", test_exposure_properties, camera),
        ("Binning Properties", test_binning_properties, camera),
        ("Cooling Properties", test_cooling_properties, camera),
        ("Gain/Offset Properties", test_gain_offset_properties, camera),
        ("Readout Properties", test_readout_properties, camera),
        ("Cooling Methods", test_cooling_methods, camera),
        ("Exposure Methods", test_exposure_methods, camera),
        ("Camera Info", test_camera_info, camera),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func, *args in tests:
        try:
            if test_func(*args):
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    # Disconnect
    camera.disconnect()
    
    # Summary
    print(f"\n=== TEST SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 All tests passed! Alpyca integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 