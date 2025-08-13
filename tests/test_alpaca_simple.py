#!/usr/bin/env python3
"""
Simple Alpyca connection test.

This script tests basic Alpyca camera connectivity.
"""

import sys
from pathlib import Path

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

def test_simple_connection():
    """Test simple Alpyca connection."""
    try:
        from alpaca.camera import Camera
        
        print("=== SIMPLE ALPYCA TEST ===")
        print("Testing basic Alpyca connection...")
        
        # Test direct Alpyca connection
        camera = Camera('localhost:11111', 0)
        print(f"Camera: {camera.Name}")
        print(f"Connected: {camera.Connected}")
        
        if camera.Connected:
            print("✅ Direct Alpyca connection successful!")
            return True
        else:
            print("❌ Direct Alpyca connection failed!")
            return False
            
    except Exception as e:
        print(f"❌ Direct Alpyca test failed: {e}")
        return False

def test_wrapper_connection():
    """Test AlpycaCameraWrapper connection."""
    try:
        from drivers.alpaca.camera import AlpycaCameraWrapper
        
        print("\n=== WRAPPER TEST ===")
        print("Testing AlpycaCameraWrapper connection...")
        
        # Test wrapper connection
        camera = AlpycaCameraWrapper(
            host="localhost",
            port=11111,
            device_id=0
        )
        
        status = camera.connect()
        if status.is_success:
            print(f"✅ Wrapper connection successful: {camera.name}")
            camera.disconnect()
            return True
        else:
            print(f"❌ Wrapper connection failed: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Wrapper test failed: {e}")
        return False

def main():
    """Main test function."""
    print("Testing Alpyca camera integration...")
    print("Make sure Alpaca server is running on localhost:11111")
    print()
    
    # Test direct connection
    direct_success = test_simple_connection()
    
    # Test wrapper connection
    wrapper_success = test_wrapper_connection()
    
    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"Direct Alpyca: {'✅ PASS' if direct_success else '❌ FAIL'}")
    print(f"Wrapper: {'✅ PASS' if wrapper_success else '❌ FAIL'}")
    
    if direct_success and wrapper_success:
        print("🎉 All tests passed!")
        return True
    else:
        print("⚠️  Some tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 