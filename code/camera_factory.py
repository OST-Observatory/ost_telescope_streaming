"""
Camera Factory - Factory pattern for creating camera instances.

This module provides a factory for creating camera instances based on configuration,
supporting Alpyca, classic ASCOM, and OpenCV camera types.
"""

import logging
from status import success_status, error_status

class CameraFactory:
    """Factory for creating camera instances."""
    
    @staticmethod
    def create_camera(config, logger=None):
        """Create camera instance based on configuration.
        
        Args:
            config: Configuration object
            logger: Logger instance
            
        Returns:
            Camera instance or error status
        """
        try:
            camera_type = config.get_camera_config().get('camera_type', 'opencv')
            
            logger = logger or logging.getLogger(__name__)
            logger.info(f"Creating camera of type: {camera_type}")
            
            if camera_type == 'alpaca':
                from alpaca_camera import AlpycaCameraWrapper
                alpaca_config = config.get_camera_config().get('alpaca', {})
                camera = AlpycaCameraWrapper(
                    host=alpaca_config.get('host', 'localhost'),
                    port=alpaca_config.get('port', 11111),
                    device_id=alpaca_config.get('device_id', 0),
                    config=config,
                    logger=logger
                )
                logger.info(f"Created Alpyca camera: {camera.host}:{camera.port}, device {camera.device_id}")
                return success_status("Alpyca camera created", data=camera)
                
            elif camera_type == 'ascom':
                from ascom_camera import ASCOMCamera
                ascom_config = config.get_camera_config().get('ascom', {})
                camera = ASCOMCamera(
                    driver_id=ascom_config.get('ascom_driver', 'ASCOM.ASICamera2.Camera'),
                    config=config,
                    logger=logger
                )
                logger.info(f"Created ASCOM camera: {camera.driver_id}")
                return success_status("ASCOM camera created", data=camera)
                
            elif camera_type == 'opencv':
                from opencv_camera import OpenCVCamera
                camera = OpenCVCamera(config, logger)
                logger.info("Created OpenCV camera")
                return success_status("OpenCV camera created", data=camera)
                
            else:
                error_msg = f"Unknown camera type: {camera_type}"
                logger.error(error_msg)
                return error_status(error_msg)
                
        except ImportError as e:
            error_msg = f"Failed to import camera module: {e}"
            logger.error(error_msg)
            return error_status(error_msg)
        except Exception as e:
            error_msg = f"Failed to create camera: {e}"
            logger.error(error_msg)
            return error_status(error_msg)
    
    @staticmethod
    def get_available_camera_types():
        """Get list of available camera types.
        
        Returns:
            list: Available camera types
        """
        return ['alpaca', 'ascom', 'opencv']
    
    @staticmethod
    def get_camera_type_description(camera_type):
        """Get description for camera type.
        
        Args:
            camera_type: Camera type string
            
        Returns:
            str: Description of camera type
        """
        descriptions = {
            'alpaca': 'Python-native ASCOM API (recommended)',
            'ascom': 'Classic Windows ASCOM (legacy)',
            'opencv': 'Standard webcam support'
        }
        return descriptions.get(camera_type, 'Unknown camera type')
    
    @staticmethod
    def validate_camera_config(config):
        """Validate camera configuration.
        
        Args:
            config: Configuration object
            
        Returns:
            Status: Success or error status with validation details
        """
        try:
            video_config = config.get_frame_processing_config()
            camera_type = config.get_camera_config().get('camera_type', 'opencv')
            
            validation_results = {
                'camera_type': camera_type,
                'valid': True,
                'issues': []
            }
            
            if camera_type == 'alpaca':
                alpaca_config = video_config.get('alpaca', {})
                required_fields = ['host', 'port', 'device_id']
                
                for field in required_fields:
                    if field not in alpaca_config:
                        validation_results['issues'].append(f"Missing required field: alpaca.{field}")
                        validation_results['valid'] = False
                
                # Validate port range
                port = alpaca_config.get('port', 11111)
                if not (1024 <= port <= 65535):
                    validation_results['issues'].append(f"Invalid port: {port} (must be 1024-65535)")
                    validation_results['valid'] = False
                
                # Validate device_id
                device_id = alpaca_config.get('device_id', 0)
                if device_id < 0:
                    validation_results['issues'].append(f"Invalid device_id: {device_id} (must be >= 0)")
                    validation_results['valid'] = False
                    
            elif camera_type == 'ascom':
                ascom_config = video_config.get('ascom', {})
                if 'ascom_driver' not in ascom_config:
                    validation_results['issues'].append("Missing required field: ascom.ascom_driver")
                    validation_results['valid'] = False
                    
            elif camera_type == 'opencv':
                opencv_config = video_config.get('opencv', {})
                required_fields = ['camera_index', 'frame_width', 'frame_height', 'fps']
                
                for field in required_fields:
                    if field not in opencv_config:
                        validation_results['issues'].append(f"Missing required field: opencv.{field}")
                        validation_results['valid'] = False
                        
            else:
                validation_results['issues'].append(f"Unknown camera type: {camera_type}")
                validation_results['valid'] = False
            
            if validation_results['valid']:
                return success_status("Configuration validation passed", data=validation_results)
            else:
                return error_status("Configuration validation failed", data=validation_results)
                
        except Exception as e:
            return error_status(f"Configuration validation error: {e}") 