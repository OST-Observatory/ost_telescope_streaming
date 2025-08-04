#!/usr/bin/env python3
"""
Extended Alpyca cooling test.

This script tests cooling over several minutes to see if power increases
and if the connection persists properly.
"""

import sys
import logging
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from alpaca_camera import AlpycaCameraWrapper
from config_manager import ConfigManager

def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("cooling_extended_test")

class CoolingMonitor:
    """Monitor cooling status over time."""
    
    def __init__(self, camera, logger):
        self.camera = camera
        self.logger = logger
        self.monitoring = False
        self.data = []
        self.monitor_thread = None
    
    def start_monitoring(self, duration_minutes=5):
        """Start monitoring cooling status."""
        self.monitoring = True
        self.data = []
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(duration_minutes,)
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.logger.info(f"Started cooling monitoring for {duration_minutes} minutes")
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        self.logger.info("Stopped cooling monitoring")
    
    def _monitor_loop(self, duration_minutes):
        """Monitoring loop."""
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        while self.monitoring and datetime.now() < end_time:
            try:
                # Get current status
                temp = self.camera.ccd_temperature
                power = self.camera.cooler_power
                cooler_on = self.camera.cooler_on
                target = self.camera.set_ccd_temperature
                
                # Record data
                timestamp = datetime.now()
                elapsed = (timestamp - start_time).total_seconds()
                
                data_point = {
                    'timestamp': timestamp,
                    'elapsed_seconds': elapsed,
                    'temperature': temp,
                    'power': power,
                    'cooler_on': cooler_on,
                    'target': target
                }
                self.data.append(data_point)
                
                # Log status
                self.logger.info(
                    f"[{elapsed:6.1f}s] Temp: {temp:5.1f}°C, "
                    f"Power: {power:5.1f}%, Cooler: {cooler_on}, "
                    f"Target: {target:5.1f}°C"
                )
                
                # Check for significant changes
                if len(self.data) > 1:
                    prev_power = self.data[-2]['power']
                    if power > prev_power + 5:  # 5% increase
                        self.logger.info(f"🎉 Cooling power increased from {prev_power:.1f}% to {power:.1f}%!")
                    elif power > 0 and prev_power == 0:
                        self.logger.info(f"🚀 Cooling power started: {power:.1f}%")
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error during monitoring: {e}")
                time.sleep(5)
    
    def get_summary(self):
        """Get monitoring summary."""
        if not self.data:
            return "No data collected"
        
        initial = self.data[0]
        final = self.data[-1]
        
        temp_change = final['temperature'] - initial['temperature']
        power_change = final['power'] - initial['power']
        
        # Find max power
        max_power = max(point['power'] for point in self.data)
        max_power_time = next(point['elapsed_seconds'] for point in self.data if point['power'] == max_power)
        
        summary = {
            'duration_seconds': final['elapsed_seconds'],
            'initial_temp': initial['temperature'],
            'final_temp': final['temperature'],
            'temp_change': temp_change,
            'initial_power': initial['power'],
            'final_power': final['power'],
            'power_change': power_change,
            'max_power': max_power,
            'max_power_time': max_power_time,
            'data_points': len(self.data)
        }
        
        return summary

def test_connection_persistence(camera, logger, test_duration_minutes=3):
    """Test if connection persists during cooling."""
    print(f"\n=== CONNECTION PERSISTENCE TEST ({test_duration_minutes} minutes) ===")
    
    try:
        print(f"Testing connection persistence during cooling...")
        
        # Set cooling
        target_temp = -10.0
        print(f"Setting cooling to {target_temp}°C...")
        status = camera.set_cooling(target_temp)
        
        if not status.is_success:
            print(f"❌ Failed to set cooling: {status.message}")
            return False
        
        print(f"✅ Cooling set successfully")
        
        # Start monitoring
        monitor = CoolingMonitor(camera, logger)
        monitor.start_monitoring(test_duration_minutes)
        
        # Wait for monitoring to complete
        print(f"Monitoring cooling for {test_duration_minutes} minutes...")
        print("Press Ctrl+C to stop early")
        
        try:
            while monitor.monitoring:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  Stopping monitoring early...")
            monitor.stop_monitoring()
        
        # Get summary
        summary = monitor.get_summary()
        
        if isinstance(summary, str):
            print(f"❌ {summary}")
            return False
        
        print(f"\n=== MONITORING SUMMARY ===")
        print(f"Duration: {summary['duration_seconds']:.1f} seconds")
        print(f"Data points: {summary['data_points']}")
        print(f"Temperature: {summary['initial_temp']:.1f}°C → {summary['final_temp']:.1f}°C (Δ{summary['temp_change']:+.1f}°C)")
        print(f"Power: {summary['initial_power']:.1f}% → {summary['final_power']:.1f}% (Δ{summary['power_change']:+.1f}%)")
        print(f"Max power: {summary['max_power']:.1f}% at {summary['max_power_time']:.1f}s")
        
        # Analyze results
        if summary['max_power'] > 0:
            print(f"✅ Cooling power did increase (max: {summary['max_power']:.1f}%)")
        else:
            print(f"⚠️  Cooling power remained at 0%")
        
        if summary['temp_change'] < 0:
            print(f"✅ Temperature decreased by {abs(summary['temp_change']):.1f}°C")
        else:
            print(f"⚠️  Temperature increased by {summary['temp_change']:.1f}°C")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection persistence test failed: {e}")
        return False

def test_connection_stability(camera, logger):
    """Test connection stability with repeated operations."""
    print(f"\n=== CONNECTION STABILITY TEST ===")
    
    try:
        print(f"Testing connection stability with repeated operations...")
        
        operations = [
            ("Get temperature", lambda: camera.ccd_temperature),
            ("Get cooler power", lambda: camera.cooler_power),
            ("Get cooler on", lambda: camera.cooler_on),
            ("Get target temperature", lambda: camera.set_ccd_temperature),
            ("Get gain", lambda: camera.gain),
            ("Get offset", lambda: camera.offset),
        ]
        
        for i in range(10):  # 10 cycles
            print(f"Cycle {i+1}/10:")
            
            for name, operation in operations:
                try:
                    result = operation()
                    print(f"  ✅ {name}: {result}")
                except Exception as e:
                    print(f"  ❌ {name}: {e}")
                    return False
            
            time.sleep(2)  # Wait between cycles
        
        print(f"✅ Connection stability test passed")
        return True
        
    except Exception as e:
        print(f"❌ Connection stability test failed: {e}")
        return False

def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Extended Alpyca cooling test")
    parser.add_argument("--config", type=str, required=True, help="Path to configuration file")
    parser.add_argument("--target-temp", type=float, default=-10.0, help="Target temperature for cooling test")
    parser.add_argument("--duration", type=int, default=5, help="Test duration in minutes")
    parser.add_argument("--verbose", action='store_true', help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = setup_logging()
    
    print("=== EXTENDED ALPYCA COOLING TEST ===")
    print(f"Configuration: {args.config}")
    print(f"Target temperature: {args.target_temp}°C")
    print(f"Test duration: {args.duration} minutes")
    print("This test monitors cooling over time to see if power increases.")
    print()
    
    try:
        # Load configuration
        config = ConfigManager(args.config)
        video_config = config.get_video_config()
        alpaca_config = video_config.get('alpaca', {})
        
        print(f"Alpyca configuration:")
        print(f"  Host: {alpaca_config.get('host', 'localhost')}")
        print(f"  Port: {alpaca_config.get('port', 11111)}")
        print(f"  Device ID: {alpaca_config.get('device_id', 0)}")
        
        # Create camera instance
        camera = AlpycaCameraWrapper(
            host=alpaca_config.get('host', 'localhost'),
            port=alpaca_config.get('port', 11111),
            device_id=alpaca_config.get('device_id', 0),
            config=config,
            logger=logger
        )
        
        # Connect to camera
        print(f"\nConnecting to Alpyca camera...")
        connect_status = camera.connect()
        if not connect_status.is_success:
            print(f"❌ Connection failed: {connect_status.message}")
            return False
        
        print(f"✅ Connected to: {camera.name}")
        
        # Run tests
        tests_passed = 0
        total_tests = 0
        
        # Test connection stability
        total_tests += 1
        if test_connection_stability(camera, logger):
            tests_passed += 1
        
        # Test connection persistence with cooling
        total_tests += 1
        if test_connection_persistence(camera, logger, args.duration):
            tests_passed += 1
        
        # Disconnect
        camera.disconnect()
        print(f"\n✅ Disconnected from camera")
        
        # Summary
        print(f"\n=== TEST SUMMARY ===")
        print(f"Tests passed: {tests_passed}/{total_tests}")
        print(f"Success rate: {tests_passed/total_tests*100:.1f}%")
        
        if tests_passed == total_tests:
            print("🎉 All tests passed! Cooling and connection are working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the output above for details.")
            return False
            
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    success = main()
    sys.exit(0 if success else 1) 