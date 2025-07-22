import logging
from code.config_manager import config
from code.video_capture import VideoCapture
import argparse
import time

def main():
    parser = argparse.ArgumentParser(description="Test video capture module")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--capture", action="store_true", help="Capture single frame")
    parser.add_argument("--stream", action="store_true", help="Start continuous capture")
    parser.add_argument("--info", action="store_true", help="Show camera info")
    parser.add_argument("--output", default="test_frame.jpg", help="Output filename")
    args = parser.parse_args()
    config.update_video_config({"camera_index": args.camera})
    logger = logging.getLogger("video_capture_cli")
    video_capture = VideoCapture(config=config, logger=logger)
    if args.info:
        info = video_capture.get_camera_info()
        print("Camera Information:")
        for key, value in info.items():
            print(f"  {key}: {value}")
    if args.capture:
        connect_status = video_capture.connect()
        if connect_status:
            frame_status = video_capture.capture_single_frame()
            print(f"Status: {frame_status.level.value.upper()} - {frame_status.message}")
            if frame_status.details:
                print(f"Details: {frame_status.details}")
            if frame_status.is_success and frame_status.data is not None:
                save_status = video_capture.save_frame(frame_status.data, args.output)
                print(f"Status: {save_status.level.value.upper()} - {save_status.message}")
                if save_status.details:
                    print(f"Details: {save_status.details}")
            video_capture.disconnect()
        else:
            print("Failed to connect to camera")
    if args.stream:
        start_status = video_capture.start_capture()
        print(f"Status: {start_status.level.value.upper()} - {start_status.message}")
        if start_status.details:
            print(f"Details: {start_status.details}")
        if start_status.is_success:
            try:
                print("Press Ctrl+C to stop streaming...")
                while True:
                    frame = video_capture.get_current_frame()
                    if frame is not None:
                        print(f"Frame captured: {frame.shape}")
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping stream...")
            finally:
                stop_status = video_capture.stop_capture()
                print(f"Status: {stop_status.level.value.upper()} - {stop_status.message}")
                if stop_status.details:
                    print(f"Details: {stop_status.details}")
                video_capture.disconnect()

if __name__ == "__main__":
    main()
