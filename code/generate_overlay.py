# generate_overlay.py
import argparse
import sys
import platform
import numpy as np
from astroquery.simbad import Simbad
from astropy.coordinates import SkyCoord
import astropy.units as u
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, Tuple, List, Dict, Any
import logging


from exceptions import OverlayError, FileError
from status import OverlayStatus, success_status, error_status, warning_status
from overlay.projection import skycoord_to_pixel_with_rotation as project_skycoord
from overlay.simbad_fields import discover_simbad_dimension_fields

class OverlayGenerator:
    """Class for generating astronomical overlays based on RA/Dec coordinates."""

    def __init__(self, config=None, logger=None):
        """Initialize the overlay generator with configuration."""
        from config_manager import ConfigManager
        # Only create default config if no config is provided
        # This prevents loading config.yaml when config is passed from tests
        if config is None:
            default_config = ConfigManager()
        else:
            default_config = None
        import logging
        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)
        self.overlay_config = self.config.get_overlay_config()
        self.display_config = self.config.get_display_config()
        self.advanced_config = self.config.get_advanced_config()
        self.platform_config = self.config.get_platform_config()

        # Initialize settings
        self.fov_deg = self.overlay_config.get('field_of_view', 1.5)
        self.mag_limit = self.overlay_config.get('magnitude_limit', 10.0)
        self.include_no_magnitude = self.overlay_config.get('include_no_magnitude', True)
        self.object_types = self.overlay_config.get('object_types', [])
        self.image_size = tuple(self.overlay_config.get('image_size', [800, 800]))
        self.max_name_length = self.overlay_config.get('max_name_length', 15)
        self.default_filename = self.overlay_config.get('default_filename', 'overlay.png')

        # Display settings
        self.object_color = tuple(self.display_config.get('object_color', [255, 0, 0]))
        self.text_color = tuple(self.display_config.get('text_color', [255, 255, 255]))
        self.marker_size = self.display_config.get('marker_size', 5)
        self.text_offset = self.display_config.get('text_offset', [8, -8])
        
        # Info panel settings
        self.info_panel_config = self.overlay_config.get('info_panel', {})
        self.info_panel_enabled = self.info_panel_config.get('enabled', True)
        
        # Title settings
        self.title_config = self.overlay_config.get('title', {})
        self.title_enabled = self.title_config.get('enabled', True)
        
        # Secondary FOV settings
        self.secondary_fov_config = self.overlay_config.get('secondary_fov', {})
        self.secondary_fov_enabled = self.secondary_fov_config.get('enabled', False)
        # Coordinate handling options
        coords_cfg = self.overlay_config.get('coordinates', {})
        # In astronomical convention with north up, RA increases to the left; default True
        self.ra_increases_left = coords_cfg.get('ra_increases_left', True)

    def get_font(self):
        """Loads an available font for the current system."""
        font_size = self.overlay_config.get('font_size', 14)

        font_paths = []
        system = platform.system().lower()

        if system == "windows":
            font_paths = self.platform_config.get('fonts', {}).get('windows', ['arial.ttf'])
        elif system == "linux":
            font_paths = self.platform_config.get('fonts', {}).get('linux', [])
        elif system == "darwin":  # macOS
            font_paths = self.platform_config.get('fonts', {}).get('macos', [])

        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, font_size)
            except (IOError, OSError):
                continue

        # Fallback to default font
        self.logger.warning("Could not load TrueType font, using default font.")
        return ImageFont.load_default()

    def skycoord_to_pixel_with_rotation(self, obj_coord, center_coord, size_px, fov_width_deg, fov_height_deg, position_angle_deg=0.0, is_flipped=False):
        """Thin wrapper that delegates projection to overlay.projection."""
        return project_skycoord(
            obj_coord.ra.degree,
            obj_coord.dec.degree,
            center_coord.ra.degree,
            center_coord.dec.degree,
            size_px,
            fov_width_deg,
            fov_height_deg,
            position_angle_deg,
            is_flipped,
            self.ra_increases_left,
        )

    def skycoord_to_pixel(self, obj_coord, center_coord, size_px, fov_deg):
        """Converts sky coordinates to pixel coordinates (legacy method for backward compatibility)."""
        return self.skycoord_to_pixel_with_rotation(obj_coord, center_coord, size_px, fov_deg, fov_deg, 0.0)

    def validate_coordinates(self, ra: float, dec: float):
        """Validates RA/Dec values."""
        if not (0 <= ra <= 360):
            raise ValueError(f"RA must be between 0 and 360 degrees, not {ra}")
        if not (-90 <= dec <= 90):
            raise ValueError(f"Dec must be between -90 and 90 degrees, not {dec}")
    
    def _get_info_panel_font(self, size: int = None):
        """Get font for info panel with specified size."""
        font_size = size or self.info_panel_config.get('font_size', 12)
        
        font_paths = []
        system = platform.system().lower()

        if system == "windows":
            font_paths = self.platform_config.get('fonts', {}).get('windows', ['arial.ttf'])
        elif system == "linux":
            font_paths = self.platform_config.get('fonts', {}).get('linux', [])
        elif system == "darwin":  # macOS
            font_paths = self.platform_config.get('fonts', {}).get('macos', [])

        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, font_size)
            except (IOError, OSError):
                continue

        # Fallback to default font
        return ImageFont.load_default()
    
    def _get_title_font(self, size: int = None):
        """Get font for title with specified size."""
        font_size = size or self.title_config.get('font_size', 18)
        
        font_paths = []
        system = platform.system().lower()

        if system == "windows":
            font_paths = self.platform_config.get('fonts', {}).get('windows', ['arial.ttf'])
        elif system == "linux":
            font_paths = self.platform_config.get('fonts', {}).get('linux', [])
        elif system == "darwin":  # macOS
            font_paths = self.platform_config.get('fonts', {}).get('macos', [])

        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, font_size)
            except (IOError, OSError):
                continue

        # Fallback to default font
        return ImageFont.load_default()
    
    def _format_coordinates(self, ra_deg: float, dec_deg: float) -> str:
        """Format coordinates in HH:MM:SS.SS +DD:MM:SS.S format."""
        from astropy.coordinates import Angle
        
        ra_angle = Angle(ra_deg, unit='deg')
        dec_angle = Angle(dec_deg, unit='deg')
        
        ra_str = ra_angle.to_string(unit='hourangle', sep=':', precision=2)
        dec_str = dec_angle.to_string(unit='deg', sep=':', precision=1)
        
        return f"RA: {ra_str} | Dec: {dec_str}"
    
    def _get_telescope_info(self) -> str:
        """Get telescope information from config."""
        telescope_config = self.config.get_telescope_config()
        focal_length = telescope_config.get('focal_length', 'Unknown')
        aperture = telescope_config.get('aperture', 'Unknown')
        focal_ratio = telescope_config.get('focal_ratio', 'Unknown')
        telescope_type = telescope_config.get('type', 'Unknown')
        
        return f"Telescope: {aperture}mm {telescope_type} (f/{focal_ratio}, {focal_length}mm FL)"
    
    def _get_camera_info(self) -> str:
        """Get camera information from config."""
        camera_config = self.config.get_camera_config()
        camera_type = camera_config.get('camera_type', 'Unknown')
        sensor_width = camera_config.get('sensor_width', 'Unknown')
        sensor_height = camera_config.get('sensor_height', 'Unknown')
        pixel_size = camera_config.get('pixel_size', 'Unknown')
        bit_depth = camera_config.get('bit_depth', 'Unknown')
        
        return f"Camera: {camera_type.upper()} ({sensor_width}×{sensor_height}mm, {pixel_size}μm, {bit_depth}bit)"
    
    def _get_fov_info(self, fov_width_deg: float, fov_height_deg: float) -> str:
        """Get field of view information."""
        fov_width_arcmin = fov_width_deg * 60
        fov_height_arcmin = fov_height_deg * 60
        
        return f"FOV: {fov_width_deg:.2f}°×{fov_height_deg:.2f}° ({fov_width_arcmin:.1f}'×{fov_height_arcmin:.1f}')"
    
    def _draw_info_panel(self, draw, img_size: Tuple[int, int], ra_deg: float, dec_deg: float, 
                        fov_width_deg: float, fov_height_deg: float, position_angle_deg: float = 0.0):
        """Draw information panel on the overlay."""
        if not self.info_panel_enabled:
            return
        
        # Get panel configuration
        position = self.info_panel_config.get('position', 'top_right')
        width = self.info_panel_config.get('width', 300)
        padding = self.info_panel_config.get('padding', 10)
        line_spacing = self.info_panel_config.get('line_spacing', 5)
        background_color = tuple(self.info_panel_config.get('background_color', [0, 0, 0, 180]))
        border_color = tuple(self.info_panel_config.get('border_color', [255, 255, 255, 255]))
        border_width = self.info_panel_config.get('border_width', 2)
        text_color = tuple(self.info_panel_config.get('text_color', [255, 255, 255, 255]))
        title_color = tuple(self.info_panel_config.get('title_color', [255, 255, 0, 255]))
        
        # Get fonts
        info_font = self._get_info_panel_font()
        
        # Prepare text lines
        lines = []
        
        # Title
        lines.append(("INFO PANEL", title_color))
        lines.append(("", text_color))  # Empty line
        
        # Timestamp
        if self.info_panel_config.get('show_timestamp', True):
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            lines.append((f"Time: {timestamp}", text_color))
        
        # Coordinates
        if self.info_panel_config.get('show_coordinates', True):
            coord_str = self._format_coordinates(ra_deg, dec_deg)
            lines.append((coord_str, text_color))
        
        # Position angle
        if position_angle_deg != 0.0:
            lines.append((f"Position Angle: {position_angle_deg:.1f}°", text_color))
        
        # Telescope info
        if self.info_panel_config.get('show_telescope_info', True):
            lines.append(("", text_color))  # Empty line
            lines.append((self._get_telescope_info(), text_color))
        
        # Camera info
        if self.info_panel_config.get('show_camera_info', True):
            lines.append((self._get_camera_info(), text_color))
        
        # FOV info
        if self.info_panel_config.get('show_fov_info', True):
            lines.append(("", text_color))  # Empty line
            lines.append((self._get_fov_info(fov_width_deg, fov_height_deg), text_color))
        
        # Calculate panel height
        text_bbox = info_font.getbbox("A")
        line_height = text_bbox[3] - text_bbox[1] + line_spacing
        panel_height = len(lines) * line_height + 2 * padding
        
        # Calculate panel position
        if position == 'top_left':
            panel_x = padding
            panel_y = padding
        elif position == 'top_right':
            panel_x = img_size[0] - width - padding
            panel_y = padding
        elif position == 'bottom_left':
            panel_x = padding
            panel_y = img_size[1] - panel_height - padding
        elif position == 'bottom_right':
            panel_x = img_size[0] - width - padding
            panel_y = img_size[1] - panel_height - padding
        else:
            panel_x = padding
            panel_y = padding
        
        # Draw background rectangle
        background_rect = [panel_x, panel_y, panel_x + width, panel_y + panel_height]
        draw.rectangle(background_rect, fill=background_color)
        
        # Draw border
        if border_width > 0:
            border_rect = [panel_x - border_width, panel_y - border_width, 
                          panel_x + width + border_width, panel_y + panel_height + border_width]
            draw.rectangle(border_rect, outline=border_color, width=border_width)
        
        # Draw text lines
        y_offset = panel_y + padding
        for line_text, color in lines:
            if line_text:  # Skip empty lines
                draw.text((panel_x + padding, y_offset), line_text, fill=color, font=info_font)
            y_offset += line_height
    
    def _draw_title(self, draw, img_size: Tuple[int, int]):
        """Draw title/header on the overlay."""
        if not self.title_enabled:
            return
        
        # Get title configuration
        title_text = self.title_config.get('text', 'OST Telescope Streaming')
        position = self.title_config.get('position', 'top_center')
        font_size = self.title_config.get('font_size', 18)
        font_color = tuple(self.title_config.get('font_color', [255, 255, 0, 255]))
        background_color = tuple(self.title_config.get('background_color', [0, 0, 0, 180]))
        padding = self.title_config.get('padding', 10)
        border_color = tuple(self.title_config.get('border_color', [255, 255, 255, 255]))
        border_width = self.title_config.get('border_width', 1)
        
        # Get font
        title_font = self._get_title_font(font_size)
        
        # Get text size
        text_bbox = title_font.getbbox(title_text)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        # Calculate title box dimensions
        box_width = text_width + 2 * padding
        box_height = text_height + 2 * padding
        
        # Calculate position
        if position == 'top_center':
            box_x = (img_size[0] - box_width) // 2
            box_y = padding
        elif position == 'top_left':
            box_x = padding
            box_y = padding
        elif position == 'top_right':
            box_x = img_size[0] - box_width - padding
            box_y = padding
        else:
            box_x = padding
            box_y = padding
        
        # Draw background rectangle
        background_rect = [box_x, box_y, box_x + box_width, box_y + box_height]
        draw.rectangle(background_rect, fill=background_color)
        
        # Draw border
        if border_width > 0:
            border_rect = [box_x - border_width, box_y - border_width, 
                          box_x + box_width + border_width, box_y + box_height + border_width]
            draw.rectangle(border_rect, outline=border_color, width=border_width)
        
        # Draw text
        text_x = box_x + padding
        text_y = box_y + padding
        draw.text((text_x, text_y), title_text, fill=font_color, font=title_font)
    
    def _draw_ellipse_for_object(self, draw, center_x: int, center_y: int, 
                                dim_maj_arcmin: float, dim_min_arcmin: float, 
                                pa_deg: float, img_size: Tuple[int, int], 
                                fov_width_deg: float, fov_height_deg: float,
                                position_angle_deg: float = 0.0, is_flipped: bool = False,
                                color: Tuple[int, int, int, int] = None, 
                                line_width: int = 2):
        """Draw an ellipse for a deep-sky object based on its dimensions.
        
        Args:
            draw: PIL ImageDraw object
            center_x, center_y: Center coordinates in pixels
            dim_maj_arcmin: Major axis in arcminutes
            dim_min_arcmin: Minor axis in arcminutes
            pa_deg: Position angle in degrees (from SIMBAD)
            img_size: Image size in pixels
            fov_width_deg, fov_height_deg: Field of view in degrees
            position_angle_deg: Image rotation angle
            is_flipped: Whether image is flipped
            color: Ellipse color (RGBA)
            line_width: Line width
        """
        if color is None:
            color = tuple(self.object_color)
        
        # Calculate pixel scale
        scale_x = (fov_width_deg * 60) / img_size[0]   # arcmin per pixel in X
        scale_y = (fov_height_deg * 60) / img_size[1]  # arcmin per pixel in Y
        
        # Convert arcminutes to pixels
        major_axis_px = dim_maj_arcmin / scale_x
        minor_axis_px = dim_min_arcmin / scale_y
        
        # Skip if ellipse is too small to be visible
        if major_axis_px < 3 or minor_axis_px < 3:
            return False
        
        # Calculate total rotation (object PA + image rotation)
        total_rotation_deg = pa_deg + position_angle_deg
        
        # Apply flip correction if needed
        if is_flipped:
            total_rotation_deg = -total_rotation_deg
        
        # Convert to radians
        rotation_rad = np.radians(total_rotation_deg)
        
        # Calculate bounding box for the ellipse
        # We need to find the extreme points of the rotated ellipse
        cos_rot = np.cos(rotation_rad)
        sin_rot = np.sin(rotation_rad)
        
        # Calculate the maximum extent in x and y directions
        max_x_extent = np.sqrt((major_axis_px * cos_rot)**2 + (minor_axis_px * sin_rot)**2)
        max_y_extent = np.sqrt((major_axis_px * sin_rot)**2 + (minor_axis_px * cos_rot)**2)
        
        # Calculate bounding box
        left = center_x - max_x_extent
        top = center_y - max_y_extent
        right = center_x + max_x_extent
        bottom = center_y + max_y_extent
        
        # Check if ellipse is within image bounds
        if (left > img_size[0] or right < 0 or top > img_size[1] or bottom < 0):
            return False
        
        # Clip to image bounds
        left = max(0, min(left, img_size[0]))
        top = max(0, min(top, img_size[1]))
        right = max(0, min(right, img_size[0]))
        bottom = max(0, min(bottom, img_size[1]))
        
        # For PIL, we need to draw the ellipse as a polygon approximation
        # since PIL doesn't support rotated ellipses directly
        num_points = 32
        points = []
        
        for i in range(num_points):
            angle = 2 * np.pi * i / num_points
            
            # Parametric equation of ellipse
            x = major_axis_px * np.cos(angle)
            y = minor_axis_px * np.sin(angle)
            
            # Apply rotation
            x_rot = x * cos_rot - y * sin_rot
            y_rot = x * sin_rot + y * cos_rot
            
            # Translate to center
            px = center_x + x_rot
            py = center_y + y_rot
            
            # Clip to image bounds
            px = max(0, min(px, img_size[0] - 1))
            py = max(0, min(py, img_size[1] - 1))
            
            points.append((px, py))
        
        # Draw the ellipse as a polygon
        if len(points) >= 3:
            draw.polygon(points, outline=color, width=line_width)
            return True
        
        return False
    
    def _should_draw_ellipse(self, object_type: str) -> bool:
        """Determine if an object should be drawn as an ellipse based on its type.
        
        Args:
            object_type: SIMBAD object type
            
        Returns:
            bool: True if object should be drawn as ellipse
        """
        # Object types that typically have measurable dimensions
        ellipse_types = [
            'G',      # Galaxy
            'GlC',    # Globular Cluster
            'OC',     # Open Cluster
            'Neb',    # Nebula
            'PN',     # Planetary Nebula
            'SNR',    # Supernova Remnant
            'HII',    # HII Region
            'Cl*',    # Cluster
            'Cld',    # Cloud
            'ISM',    # Interstellar Medium
            'MoC',    # Molecular Cloud
            'RNe',    # Reflection Nebula
            'DNe',    # Dark Nebula
            'EmO',    # Emission Object
            'Abs',    # Absorption
            'Rad',    # Radio Source
            'X',      # X-ray Source
            'gLSB',   # Low Surface Brightness Galaxy
            'AGN',    # Active Galactic Nucleus
            'QSO',    # Quasar
            'BLLac',  # BL Lacertae Object
            'Sy1',    # Seyfert 1 Galaxy
            'Sy2',    # Seyfert 2 Galaxy
            'LINER',  # LINER
            'H2G',    # HII Galaxy
            'SBG',    # Starburst Galaxy
            'LSB',    # Low Surface Brightness Galaxy
            'dSph',   # Dwarf Spheroidal Galaxy
            'dE',     # Dwarf Elliptical Galaxy
            'dI',     # Dwarf Irregular Galaxy
            'dS0',    # Dwarf S0 Galaxy
            'dS',     # Dwarf Spiral Galaxy
            'dSB',    # Dwarf Barred Spiral Galaxy
            'dE,N',   # Dwarf Elliptical Galaxy with Nucleus
            'dS0,N',  # Dwarf S0 Galaxy with Nucleus
            'dS,N',   # Dwarf Spiral Galaxy with Nucleus
            'dSB,N',  # Dwarf Barred Spiral Galaxy with Nucleus
        ]
        
        return object_type in ellipse_types
    
    def _calculate_secondary_fov(self) -> Tuple[float, float]:
        """Calculate secondary telescope field of view in degrees."""
        if not self.secondary_fov_enabled:
            return 0.0, 0.0
        
        fov_type = self.secondary_fov_config.get('type', 'camera')
        telescope_config = self.secondary_fov_config.get('telescope', {})
        focal_length = telescope_config.get('focal_length', 1000)
        
        if fov_type == 'camera':
            # Camera-based FOV calculation
            camera_config = self.secondary_fov_config.get('camera', {})
            sensor_width = camera_config.get('sensor_width', 10.0)
            sensor_height = camera_config.get('sensor_height', 10.0)
            
            # Calculate FOV in degrees
            fov_width_deg = (sensor_width / focal_length) * 57.2958  # Convert radians to degrees
            fov_height_deg = (sensor_height / focal_length) * 57.2958
            
            return fov_width_deg, fov_height_deg
            
        elif fov_type == 'eyepiece':
            # Eyepiece-based FOV calculation
            eyepiece_config = self.secondary_fov_config.get('eyepiece', {})
            eyepiece_fl = eyepiece_config.get('focal_length', 25)
            afov = eyepiece_config.get('afov', 68)
            
            # Calculate magnification
            magnification = focal_length / eyepiece_fl
            
            # Calculate true field of view
            tfov = afov / magnification
            
            # For eyepiece, assume circular FOV
            return tfov, tfov
        
        return 0.0, 0.0
    
    def _get_secondary_fov_label(self) -> str:
        """Get label text for secondary FOV."""
        if not self.secondary_fov_enabled:
            return ""
        
        fov_type = self.secondary_fov_config.get('type', 'camera')
        telescope_config = self.secondary_fov_config.get('telescope', {})
        focal_length = telescope_config.get('focal_length', 1000)
        aperture = telescope_config.get('aperture', 200)
        telescope_type = telescope_config.get('type', 'reflector')
        
        if fov_type == 'camera':
            camera_config = self.secondary_fov_config.get('camera', {})
            sensor_width = camera_config.get('sensor_width', 10.0)
            sensor_height = camera_config.get('sensor_height', 10.0)
            pixel_size = camera_config.get('pixel_size', 5.0)
            
            return f"Secondary: {aperture}mm {telescope_type} + {sensor_width}×{sensor_height}mm sensor"
            
        elif fov_type == 'eyepiece':
            eyepiece_config = self.secondary_fov_config.get('eyepiece', {})
            eyepiece_fl = eyepiece_config.get('focal_length', 25)
            afov = eyepiece_config.get('afov', 68)
            
            return f"Secondary: {aperture}mm {telescope_type} + {eyepiece_fl}mm ({afov}° AFOV)"
        
        return "Secondary FOV"
    
    def _draw_secondary_fov(self, draw, img_size: Tuple[int, int], center_ra_deg: float, 
                           center_dec_deg: float, fov_width_deg: float, fov_height_deg: float,
                           position_angle_deg: float = 0.0, is_flipped: bool = False):
        """Draw secondary telescope field of view overlay."""
        if not self.secondary_fov_enabled:
            return
        
        # Get secondary FOV dimensions
        secondary_fov_w, secondary_fov_h = self._calculate_secondary_fov()
        if secondary_fov_w <= 0 or secondary_fov_h <= 0:
            return
        
        # Get display settings
        display_config = self.secondary_fov_config.get('display', {})
        color = tuple(display_config.get('color', [0, 255, 255, 255]))
        line_width = display_config.get('line_width', 2)
        style = display_config.get('style', 'dashed')
        show_label = display_config.get('show_label', True)
        label_color = tuple(display_config.get('label_color', [0, 255, 255, 255]))
        label_font_size = display_config.get('label_font_size', 10)
        label_offset = display_config.get('label_offset', [5, 5])
        
        # Get position offset
        offset_config = self.secondary_fov_config.get('position_offset', {})
        ra_offset_arcmin = offset_config.get('ra_offset_arcmin', 0.0)
        dec_offset_arcmin = offset_config.get('dec_offset_arcmin', 0.0)
        
        # Calculate offset in degrees
        ra_offset_deg = ra_offset_arcmin / 60.0
        dec_offset_deg = dec_offset_arcmin / 60.0
        
        # Apply offset to center coordinates
        offset_center_ra = center_ra_deg + ra_offset_deg
        offset_center_dec = center_dec_deg + dec_offset_deg
        
        # Use projection helper to compute pixel center of secondary FOV
        center_x, center_y = project_skycoord(
            offset_center_ra, offset_center_dec,
            center_ra_deg, center_dec_deg,
            img_size, fov_width_deg, fov_height_deg,
            position_angle_deg, is_flipped, self.ra_increases_left,
        )
        
        # Compute secondary FOV size in pixels using main scale
        scale_x = (fov_width_deg * 60) / img_size[0]
        scale_y = (fov_height_deg * 60) / img_size[1]
        secondary_fov_w_px = (secondary_fov_w * 60) / scale_x
        secondary_fov_h_px = (secondary_fov_h * 60) / scale_y
        
        # Apply flip correction if needed
        if is_flipped:
            center_x = img_size[0] - center_x
        
        # Check if secondary FOV is within image bounds
        half_width = secondary_fov_w_px / 2
        half_height = secondary_fov_h_px / 2
        
        if (center_x - half_width > img_size[0] or center_x + half_width < 0 or
            center_y - half_height > img_size[1] or center_y + half_height < 0):
            # Secondary FOV is completely outside image bounds
            return
        
        # Draw secondary FOV
        fov_type = self.secondary_fov_config.get('type', 'camera')
        
        if fov_type == 'camera':
            # Draw rectangular FOV for camera
            left = center_x - half_width
            top = center_y - half_height
            right = center_x + half_width
            bottom = center_y + half_height
            
            # Clip to image bounds
            left = max(0, min(left, img_size[0]))
            top = max(0, min(top, img_size[1]))
            right = max(0, min(right, img_size[0]))
            bottom = max(0, min(bottom, img_size[1]))
            
            # Draw rectangle
            if style == 'dashed':
                # Draw dashed rectangle
                dash_length = 10
                # Top line
                for x in range(int(left), int(right), dash_length * 2):
                    end_x = min(x + dash_length, right)
                    draw.line([(x, top), (end_x, top)], fill=color, width=line_width)
                # Bottom line
                for x in range(int(left), int(right), dash_length * 2):
                    end_x = min(x + dash_length, right)
                    draw.line([(x, bottom), (end_x, bottom)], fill=color, width=line_width)
                # Left line
                for y in range(int(top), int(bottom), dash_length * 2):
                    end_y = min(y + dash_length, bottom)
                    draw.line([(left, y), (left, end_y)], fill=color, width=line_width)
                # Right line
                for y in range(int(top), int(bottom), dash_length * 2):
                    end_y = min(y + dash_length, bottom)
                    draw.line([(right, y), (right, end_y)], fill=color, width=line_width)
            else:
                # Draw solid rectangle
                draw.rectangle([left, top, right, bottom], outline=color, width=line_width)
        
        elif fov_type == 'eyepiece':
            # Draw circular FOV for eyepiece
            radius = min(half_width, half_height)
            
            # Clip to image bounds
            left = center_x - radius
            top = center_y - radius
            right = center_x + radius
            bottom = center_y + radius
            
            if (left < img_size[0] and right > 0 and top < img_size[1] and bottom > 0):
                # Draw circle
                if style == 'dashed':
                    # Draw dashed circle (approximation with arcs)
                    import math
                    segments = 32
                    for i in range(segments):
                        angle1 = i * 2 * math.pi / segments
                        angle2 = (i + 1) * 2 * math.pi / segments
                        
                        # Only draw every other segment for dashed effect
                        if i % 2 == 0:
                            x1 = center_x + radius * math.cos(angle1)
                            y1 = center_y + radius * math.sin(angle1)
                            x2 = center_x + radius * math.cos(angle2)
                            y2 = center_y + radius * math.sin(angle2)
                            
                            # Clip to image bounds
                            if (0 <= x1 <= img_size[0] and 0 <= y1 <= img_size[1] and
                                0 <= x2 <= img_size[0] and 0 <= y2 <= img_size[1]):
                                draw.line([(x1, y1), (x2, y2)], fill=color, width=line_width)
                else:
                    # Draw solid circle
                    draw.ellipse([left, top, right, bottom], outline=color, width=line_width)
        
        # Draw label if enabled
        if show_label:
            label_text = self._get_secondary_fov_label()
            if label_text:
                # Get label font
                label_font = self._get_info_panel_font(label_font_size)
                
                # Calculate label position
                label_x = center_x + label_offset[0]
                label_y = center_y + label_offset[1]
                
                # Ensure label is within image bounds
                label_x = max(10, min(label_x, img_size[0] - 200))
                label_y = max(10, min(label_y, img_size[1] - 20))
                
                # Draw label background for better readability
                text_bbox = label_font.getbbox(label_text)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                bg_left = label_x - 2
                bg_top = label_y - 2
                bg_right = label_x + text_width + 2
                bg_bottom = label_y + text_height + 2
                
                # Draw background
                draw.rectangle([bg_left, bg_top, bg_right, bg_bottom], 
                             fill=(0, 0, 0, 180))
                
                # Draw text
                draw.text((label_x, label_y), label_text, fill=label_color, font=label_font)

    def generate_overlay(self, ra_deg: float, dec_deg: float, output_file: Optional[str] = None,
                        fov_width_deg: Optional[float] = None, fov_height_deg: Optional[float] = None,
                        position_angle_deg: Optional[float] = None, image_size: Optional[Tuple[int, int]] = None,
                        mag_limit: Optional[float] = None, is_flipped: Optional[bool] = None) -> str:
        """Generate an overlay image for the given coordinates.

        Creates a comprehensive astronomical overlay showing stars, deep sky objects,
        and other celestial features for the specified coordinates and field of view.

        Args:
            ra_deg: Right Ascension in degrees
            dec_deg: Declination in degrees
            output_file: Optional output filename
            fov_width_deg: Field of view width in degrees
            fov_height_deg: Field of view height in degrees
            position_angle_deg: Position angle in degrees
            image_size: Image size as (width, height) in pixels
            mag_limit: Magnitude limit for objects to include
            is_flipped: Whether the image is flipped (from PlateSolve2)

        Returns:
            str: Path to the generated overlay file

        Note:
            This method integrates multiple data sources to create a comprehensive
            astronomical overlay suitable for telescope streaming and observation.
        """
        try:
            # Validate input values
            self.validate_coordinates(ra_deg, dec_deg)

            # Use provided values or defaults
            fov_w = fov_width_deg if fov_width_deg is not None else self.fov_deg
            fov_h = fov_height_deg if fov_height_deg is not None else self.fov_deg
            pa_deg = position_angle_deg if position_angle_deg is not None else 0.0
            img_size = image_size if image_size is not None else self.image_size
            mag_limit = mag_limit if mag_limit is not None else self.mag_limit
            is_flipped = is_flipped if is_flipped is not None else False
            output_file = output_file or self.default_filename

            # Do not adjust PA here; upstream solvers (e.g., PlateSolve2) may already apply PA+180°.
            # If a solver indicates flipping without PA correction, the X-mirror in the projection handles it.

            center = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame='icrs')

            # Configure SIMBAD with robust field selection (delegated)
            custom_simbad = Simbad()
            custom_simbad.reset_votable_fields()
            custom_simbad.add_votable_fields('ra', 'dec', 'V', 'otype', 'main_id')
            picked_maj, picked_min, picked_ang, picked_dims, pa_supported = discover_simbad_dimension_fields(Simbad)
            for fld in [picked_maj, picked_min, picked_ang, picked_dims]:
                if fld:
                    try:
                        custom_simbad.add_votable_fields(fld)
                    except Exception:
                        pass

            # Radius is half-diagonal of field of view
            radius = ((fov_w**2 + fov_h**2)**0.5) / 2

            self.logger.info("SIMBAD query running...")
            result = custom_simbad.query_region(center, radius=radius * u.deg)

            if result is None or len(result) == 0:
                self.logger.warning("No objects found.")
                # Create empty overlay if configured
                if self.advanced_config.get('save_empty_overlays', True):
                    img = Image.new("RGBA", img_size, (0, 0, 0, 0))
                    img.save(output_file)
                    self.logger.info(f"Empty overlay saved as {output_file}")
                return success_status(
                    f"Empty overlay saved as {output_file}",
                    data=output_file,
                    details={'fov_width_deg': fov_w, 'fov_height_deg': fov_h, 'position_angle_deg': pa_deg, 'image_size': img_size, 'magnitude_limit': mag_limit}
                )

            # Debug: Print available column names
            if self.advanced_config.get('debug_simbad', False):
                self.logger.debug(f"Available columns: {result.colnames}")
                self.logger.debug(f"Number of objects: {len(result)}")

            # Prepare image
            img = Image.new("RGBA", img_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            font = self.get_font()
            
            # Draw title and info panel first (so they appear behind objects)
            self._draw_title(draw, img_size)
            self._draw_info_panel(draw, img_size, ra_deg, dec_deg, fov_w, fov_h, pa_deg)
            
            # Draw secondary FOV overlay
            self._draw_secondary_fov(draw, img_size, ra_deg, dec_deg, fov_w, fov_h, pa_deg, is_flipped)

            # Process objects
            objects_drawn = 0
            for row in result:
                try:
                    # Handle objects with and without V magnitude
                    has_v_magnitude = 'V' in row.colnames and row['V'] is not None and row['V'] != '--'

                    # Skip objects that are too faint (if they have magnitude)
                    if has_v_magnitude and row['V'] > mag_limit:
                        continue

                    # Skip objects without magnitude if configured
                    if not has_v_magnitude and not self.include_no_magnitude:
                        continue

                    # Filter by object type if specified
                    if self.object_types and 'otype' in row.colnames:
                        obj_type = row['otype']
                        if obj_type not in self.object_types:
                            continue

                    # Try different possible column names for RA/Dec
                    ra_col = None
                    dec_col = None

                    # Check for various possible column names
                    for ra_name in ['RA', 'ra', 'RA_d', 'ra_d']:
                        if ra_name in row.colnames:
                            ra_col = ra_name
                            break

                    for dec_name in ['DEC', 'dec', 'DEC_d', 'dec_d']:
                        if dec_name in row.colnames:
                            dec_col = dec_name
                            break

                    if ra_col is None or dec_col is None:
                        self.logger.warning(f"Could not find RA/Dec columns. Available: {row.colnames}")
                        continue

                    # Use found column names
                    obj_coord = SkyCoord(ra=row[ra_col], dec=row[dec_col], unit="deg")
                    x, y = self.skycoord_to_pixel_with_rotation(obj_coord, center, img_size, fov_w, fov_h, pa_deg, is_flipped)

                    # Check if object is within image bounds
                    if 0 <= x <= img_size[0] and 0 <= y <= img_size[1]:
                        # Check if we should draw an ellipse for this object type
                        object_type = row.get('otype', '') if 'otype' in row.colnames else ''
                        should_draw_ellipse = self._should_draw_ellipse(object_type)
                        
                        # Check if we have dimension data for ellipse
                        has_dimensions = False
                        dim_maj = None
                        dim_min = None
                        pa = None
                        
                        if should_draw_ellipse:
                            # Prefer explicit numeric fields first (use whichever we successfully added)
                            if picked_maj and picked_maj in row.colnames and row[picked_maj] not in (None, '--'):
                                try:
                                    dim_maj = float(row[picked_maj])
                                except Exception:
                                    dim_maj = None
                            if picked_min and picked_min in row.colnames and row[picked_min] not in (None, '--'):
                                try:
                                    dim_min = float(row[picked_min])
                                except Exception:
                                    dim_min = None
                            if picked_ang and picked_ang in row.colnames and row[picked_ang] not in (None, '--'):
                                try:
                                    pa = float(row[picked_ang])
                                except Exception:
                                    pa = None

                            # Fallback to legacy combined string field
                            if (dim_maj is None or dim_min is None) and ((picked_dims and picked_dims in row.colnames) or 'dimensions' in row.colnames):
                                dimensions_str = str(row['dimensions'])
                                if dimensions_str != '--' and dimensions_str.strip():
                                    try:
                                        if 'x' in dimensions_str:
                                            parts = dimensions_str.split('x')
                                            if len(parts) == 2:
                                                dim_maj = dim_maj or float(parts[0].strip())
                                                dim_min = dim_min or float(parts[1].strip())
                                        else:
                                            dim_maj = dim_maj or float(dimensions_str)
                                            dim_min = dim_min or dim_maj
                                    except (ValueError, TypeError):
                                        pass

                            # Final fallback for PA via 'pa' field (if supported)
                            if pa is None and picked_ang and picked_ang in row.colnames and row[picked_ang] is not None:
                                pa_str = str(row[picked_ang])
                                if pa_str != '--' and pa_str.strip():
                                    try:
                                        pa = float(pa_str)
                                    except (ValueError, TypeError):
                                        pa = None

                            has_dimensions = (dim_maj is not None and dim_min is not None)
                            pa = pa or 0.0
                        
                        # Draw ellipse if we have dimension data
                        if should_draw_ellipse and has_dimensions and dim_maj is not None and dim_min is not None:
                            ellipse_drawn = self._draw_ellipse_for_object(
                                draw, x, y, dim_maj, dim_min, pa or 0.0,
                                img_size, fov_w, fov_h, pa_deg, is_flipped
                            )
                            if not ellipse_drawn:
                                # Fallback to marker if ellipse drawing failed
                                draw.ellipse((x - self.marker_size, y - self.marker_size,
                                            x + self.marker_size, y + self.marker_size),
                                           outline=self.object_color, width=2)
                        else:
                            # Draw standard marker
                            draw.ellipse((x - self.marker_size, y - self.marker_size,
                                        x + self.marker_size, y + self.marker_size),
                                       outline=self.object_color, width=2)

                        # Safe name handling - try different possible column names
                        name = None
                        name_columns = ['MAIN_ID', 'main_id', 'MAINID', 'mainid']

                        for name_col in name_columns:
                            if name_col in row.colnames:
                                name_value = row[name_col]
                                if name_value is not None:
                                    if isinstance(name_value, bytes):
                                        name = name_value.decode("utf-8", errors='ignore')
                                    else:
                                        name = str(name_value)
                                    break

                        # Fallback if no name found
                        if name is None:
                            name = f"Obj_{objects_drawn}"

                        # Truncate long names
                        if len(name) > self.max_name_length:
                            name = name[:self.max_name_length-3] + "..."

                        draw.text((x + self.text_offset[0], y + self.text_offset[1]),
                                name, fill=self.text_color, font=font)
                        objects_drawn += 1

                except Exception as e:
                    # More detailed error information for debugging
                    if self.advanced_config.get('debug_simbad', False):
                        self.logger.warning(f"Error processing object: {e}")
                        self.logger.debug(f"  Available columns: {row.colnames if hasattr(row, 'colnames') else 'No colnames'}")
                        if hasattr(row, 'colnames') and 'main_id' in row.colnames:
                            self.logger.debug(f"  main_id value: {row['main_id']}")
                    else:
                        self.logger.warning(f"Error processing object: {e}")
                    continue

            img.save(output_file)
            self.logger.info(f"Overlay with {objects_drawn} objects saved as {output_file}")
            return success_status(
                f"Overlay with {objects_drawn} objects saved as {output_file}",
                data=output_file,
                details={'objects_drawn': objects_drawn, 'fov_width_deg': fov_w, 'fov_height_deg': fov_h, 'position_angle_deg': pa_deg, 'image_size': img_size, 'magnitude_limit': mag_limit}
            )

        except Exception as e:
            self.logger.error(f"Error: {e}")
            return error_status(f"Error generating overlay: {e}")
