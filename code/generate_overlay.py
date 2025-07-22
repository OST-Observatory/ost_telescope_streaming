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

# Import configuration
from config_manager import config
from exceptions import OverlayError, FileError
from status import OverlayStatus, success_status, error_status, warning_status

class OverlayGenerator:
    """Class for generating astronomical overlays based on RA/Dec coordinates."""
    
    def __init__(self, config=None, logger=None):
        """Initialize the overlay generator with configuration."""
        from config_manager import config as default_config
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
    
    def skycoord_to_pixel(self, obj_coord, center_coord, size_px, fov_deg):
        """Converts sky coordinates to pixel coordinates."""
        try:
            delta_ra = (obj_coord.ra.degree - center_coord.ra.degree) * \
                u.deg.to(u.arcmin) * np.cos(center_coord.dec.radian)
            delta_dec = (obj_coord.dec.degree - center_coord.dec.degree) * u.deg.to(u.arcmin)

            scale = size_px[0] / (fov_deg * 60)  # arcmin -> pixels

            x = size_px[0] / 2 + delta_ra * scale
            y = size_px[1] / 2 - delta_dec * scale  # Invert Y-axis (Dec up)

            return int(x), int(y)
        except Exception as e:
            raise ValueError(f"Error in coordinate conversion: {e}")
    
    def validate_coordinates(self, ra: float, dec: float):
        """Validates RA/Dec values."""
        if not (0 <= ra <= 360):
            raise ValueError(f"RA must be between 0 and 360 degrees, not {ra}")
        if not (-90 <= dec <= 90):
            raise ValueError(f"Dec must be between -90 and 90 degrees, not {dec}")
    
    def generate_overlay(self, ra_deg: float, dec_deg: float, output_file: Optional[str] = None, fov_deg: Optional[float] = None, mag_limit: Optional[float] = None) -> OverlayStatus:
        """Generiert ein Overlay-Bild für die gegebenen Koordinaten.
        Returns:
            OverlayStatus: Status-Objekt mit Ergebnis oder Fehler.
        """
        try:
            # Validate input values
            self.validate_coordinates(ra_deg, dec_deg)
            
            # Use provided values or defaults
            fov = fov_deg if fov_deg is not None else self.fov_deg
            mag_limit = mag_limit if mag_limit is not None else self.mag_limit
            output_file = output_file or self.default_filename
            
            center = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame='icrs')

            # Configure SIMBAD with updated field names
            custom_simbad = Simbad()
            custom_simbad.reset_votable_fields()
            # Use new field names to avoid deprecation warnings
            custom_simbad.add_votable_fields('ra', 'dec', 'V', 'otype', 'main_id')

            # Radius is half-diagonal of field of view
            radius = ((fov**2 + fov**2)**0.5) / 2

            self.logger.info("SIMBAD query running...")
            result = custom_simbad.query_region(center, radius=radius * u.deg)

            if result is None or len(result) == 0:
                self.logger.warning("No objects found.")
                # Create empty overlay if configured
                if self.advanced_config.get('save_empty_overlays', True):
                    img = Image.new("RGBA", self.image_size, (0, 0, 0, 0))
                    img.save(output_file)
                    self.logger.info(f"Empty overlay saved as {output_file}")
                return success_status(
                    f"Empty overlay saved as {output_file}",
                    data=output_file,
                    details={'fov_deg': fov_deg, 'magnitude_limit': mag_limit}
                )

            # Debug: Print available column names
            if self.advanced_config.get('debug_simbad', False):
                self.logger.debug(f"Available columns: {result.colnames}")
                self.logger.debug(f"Number of objects: {len(result)}")

            # Prepare image
            img = Image.new("RGBA", self.image_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            font = self.get_font()

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
                    x, y = self.skycoord_to_pixel(obj_coord, center, self.image_size, fov)

                    # Check if object is within image bounds
                    if 0 <= x <= self.image_size[0] and 0 <= y <= self.image_size[1]:
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
                details={'objects_drawn': objects_drawn, 'fov_deg': fov_deg, 'magnitude_limit': mag_limit}
            )

        except Exception as e:
            self.logger.error(f"Error: {e}")
            return error_status(f"Error generating overlay: {e}")
