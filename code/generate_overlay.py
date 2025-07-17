# generate_overlay.py
import argparse
import sys
import platform
from astroquery.simbad import Simbad
from astropy.coordinates import SkyCoord
import astropy.units as u
from PIL import Image, ImageDraw, ImageFont

# Import configuration
from config_manager import config

def get_font():
    """Loads an available font for the current system."""
    overlay_config = config.get_overlay_config()
    platform_config = config.get_platform_config()
    font_size = overlay_config.get('font_size', 14)
    
    font_paths = []
    system = platform.system().lower()
    
    if system == "windows":
        font_paths = platform_config.get('fonts', {}).get('windows', ['arial.ttf'])
    elif system == "linux":
        font_paths = platform_config.get('fonts', {}).get('linux', [])
    elif system == "darwin":  # macOS
        font_paths = platform_config.get('fonts', {}).get('macos', [])
    
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, font_size)
        except (IOError, OSError):
            continue
    
    # Fallback to default font
    print("⚠️  Could not load TrueType font, using default font.")
    return ImageFont.load_default()

def skycoord_to_pixel(obj_coord, center_coord, size_px, fov_deg):
    """Converts sky coordinates to pixel coordinates."""
    try:
        delta_ra = (obj_coord.ra.degree - center_coord.ra.degree) * \
            u.deg.to(u.arcmin) * u.cos(center_coord.dec.radian)
        delta_dec = (obj_coord.dec.degree - center_coord.dec.degree) * u.deg.to(u.arcmin)

        scale = size_px[0] / (fov_deg * 60)  # arcmin -> pixels

        x = size_px[0] / 2 + delta_ra * scale
        y = size_px[1] / 2 - delta_dec * scale  # Invert Y-axis (Dec up)

        return int(x), int(y)
    except Exception as e:
        raise ValueError(f"Error in coordinate conversion: {e}")

def validate_coordinates(ra, dec):
    """Validates RA/Dec values."""
    if not (0 <= ra <= 360):
        raise ValueError(f"RA must be between 0 and 360 degrees, not {ra}")
    if not (-90 <= dec <= 90):
        raise ValueError(f"Dec must be between -90 and 90 degrees, not {dec}")

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Generates an overlay based on RA/Dec.")
    parser.add_argument("--ra", type=float, required=True, help="Right Ascension in degrees")
    parser.add_argument("--dec", type=float, required=True, help="Declination in degrees")
    parser.add_argument("--output", type=str, help="Output file (default: from config)")
    args = parser.parse_args()

    try:
        # Get configuration
        overlay_config = config.get_overlay_config()
        display_config = config.get_display_config()
        advanced_config = config.get_advanced_config()
        
        # Validate input values
        validate_coordinates(args.ra, args.dec)
        
        # Get configuration values
        fov_deg = overlay_config.get('field_of_view', 1.5)
        mag_limit = overlay_config.get('magnitude_limit', 10.0)
        image_size = tuple(overlay_config.get('image_size', [800, 800]))
        simbad_timeout = overlay_config.get('simbad_timeout', 30)
        max_name_length = overlay_config.get('max_name_length', 15)
        default_filename = overlay_config.get('default_filename', 'overlay.png')
        
        # Output file
        output_file = args.output or default_filename
        
        center = SkyCoord(ra=args.ra * u.deg, dec=args.dec * u.deg, frame='icrs')

        # Configure SIMBAD
        custom_simbad = Simbad()
        custom_simbad.reset_votable_fields()
        custom_simbad.add_votable_fields('ra(d)', 'dec(d)', 'V', 'otype', 'main_id')

        # Radius is half-diagonal of field of view
        radius = ((fov_deg**2 + fov_deg**2)**0.5) / 2

        print("🔭 SIMBAD query running...")
        result = custom_simbad.query_region(center, radius=radius * u.deg, timeout=simbad_timeout)

        if result is None or len(result) == 0:
            print("❌ No objects found.")
            # Create empty overlay if configured
            if advanced_config.get('save_empty_overlays', True):
                img = Image.new("RGBA", image_size, (0, 0, 0, 0))
                img.save(output_file)
                print(f"✅ Empty overlay saved as {output_file}")
            return

        # Prepare image
        img = Image.new("RGBA", image_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = get_font()

        # Get display settings
        object_color = tuple(display_config.get('object_color', [255, 0, 0]))
        text_color = tuple(display_config.get('text_color', [255, 255, 255]))
        marker_size = display_config.get('marker_size', 5)
        text_offset = display_config.get('text_offset', [8, -8])

        # Process objects
        objects_drawn = 0
        for row in result:
            try:
                if 'V' not in row.colnames or row['V'] is None:
                    continue
                if row['V'] > mag_limit:
                    continue

                obj_coord = SkyCoord(ra=row['RA_d'], dec=row['DEC_d'], unit="deg")
                x, y = skycoord_to_pixel(obj_coord, center, image_size, fov_deg)

                # Check if object is within image bounds
                if 0 <= x <= image_size[0] and 0 <= y <= image_size[1]:
                    draw.ellipse((x - marker_size, y - marker_size, x + marker_size, y + marker_size), 
                               outline=object_color, width=2)
                    
                    # Safe name handling
                    name = row['MAIN_ID']
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", errors='ignore')
                    else:
                        name = str(name)
                    
                    # Truncate long names
                    if len(name) > max_name_length:
                        name = name[:max_name_length-3] + "..."
                    
                    draw.text((x + text_offset[0], y + text_offset[1]), name, fill=text_color, font=font)
                    objects_drawn += 1
                    
            except Exception as e:
                print(f"⚠️  Error processing object: {e}")
                continue

        img.save(output_file)
        print(f"✅ Overlay with {objects_drawn} objects saved as {output_file}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
