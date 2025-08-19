#!/usr/bin/env python3
# Moved from code/generate_overlay.py
import logging
import platform
from typing import Optional, Tuple

# astroquery is optional; we import Simbad lazily in generate_overlay()
from astropy.coordinates import SkyCoord
import astropy.units as u
from overlay.drawing import draw_ellipse_for_object, draw_info_panel, draw_secondary_fov, draw_title
from overlay.info import camera_info, cooling_info, format_coordinates, fov_info, telescope_info
from overlay.projection import skycoord_to_pixel_with_rotation as project_skycoord
from overlay.simbad_fields import discover_simbad_dimension_fields
from PIL import Image, ImageDraw, ImageFont
from status import success_status


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
        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)
        self.overlay_config = self.config.get_overlay_config()
        self.display_config = self.config.get_display_config()
        self.advanced_config = self.config.get_advanced_config()
        self.platform_config = self.config.get_platform_config()

        # Initialize settings
        self.fov_deg = self.overlay_config.get("field_of_view", 1.5)
        self.mag_limit = self.overlay_config.get("magnitude_limit", 10.0)
        self.include_no_magnitude = self.overlay_config.get("include_no_magnitude", True)
        self.object_types = self.overlay_config.get("object_types", [])
        self.image_size = tuple(self.overlay_config.get("image_size", [800, 800]))
        self.max_name_length = self.overlay_config.get("max_name_length", 15)
        self.default_filename = self.overlay_config.get("default_filename", "overlay.png")

        # Display settings
        self.object_color = tuple(self.display_config.get("object_color", [255, 0, 0]))
        self.text_color = tuple(self.display_config.get("text_color", [255, 255, 255]))
        self.marker_size = self.display_config.get("marker_size", 5)
        self.text_offset = self.display_config.get("text_offset", [8, -8])

        # Info panel settings
        self.info_panel_config = self.overlay_config.get("info_panel", {})
        self.info_panel_enabled = self.info_panel_config.get("enabled", True)
        # Cooling info optional
        self.show_cooling_info = bool(self.info_panel_config.get("show_cooling_info", False))

        # Title settings
        self.title_config = self.overlay_config.get("title", {})
        self.title_enabled = self.title_config.get("enabled", True)

        # Secondary FOV settings
        self.secondary_fov_config = self.overlay_config.get("secondary_fov", {})
        self.secondary_fov_enabled = self.secondary_fov_config.get("enabled", False)
        # Coordinate handling options
        coords_cfg = self.overlay_config.get("coordinates", {})
        # In astronomical convention with north up, RA increases to the left; default True
        self.ra_increases_left = coords_cfg.get("ra_increases_left", True)
        # Optional fixed rotation offset to apply to overlays (degrees)
        try:
            self.rotation_offset_deg = float(coords_cfg.get("rotation_offset_deg", 0.0))
        except Exception:
            self.rotation_offset_deg = 0.0
        # Optional: use WCS-based projection instead of math-based
        self.use_wcs_projection = bool(coords_cfg.get("use_wcs_projection", False))

    def get_font(self):
        """Loads an available font for the current system."""
        font_size = self.overlay_config.get("font_size", 14)

        font_paths = []
        system = platform.system().lower()

        if system == "windows":
            font_paths = self.platform_config.get("fonts", {}).get("windows", ["arial.ttf"])
        elif system == "linux":
            font_paths = self.platform_config.get("fonts", {}).get("linux", [])
        elif system == "darwin":  # macOS
            font_paths = self.platform_config.get("fonts", {}).get("macos", [])

        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, font_size)
            except (IOError, OSError):
                continue

        # Fallback to default font
        self.logger.warning("Could not load TrueType font, using default font.")
        return ImageFont.load_default()

    def skycoord_to_pixel_with_rotation(
        self,
        obj_coord,
        center_coord,
        size_px,
        fov_width_deg,
        fov_height_deg,
        position_angle_deg=0.0,
        flip_x: bool = False,
        flip_y: bool = False,
    ):
        """Wrapper that delegates to math or WCS projection based on config."""
        obj_ra = obj_coord.ra.degree
        obj_dec = obj_coord.dec.degree
        cen_ra = center_coord.ra.degree
        cen_dec = center_coord.dec.degree

        if not self.use_wcs_projection:
            return project_skycoord(
                obj_ra,
                obj_dec,
                cen_ra,
                cen_dec,
                size_px,
                fov_width_deg,
                fov_height_deg,
                position_angle_deg,
                flip_x,
                flip_y,
                self.ra_increases_left,
            )

        # WCS branch: derive pixel scale (arcsec/pixel) from FOV and image size
        width_px, height_px = size_px
        try:
            scale_x_arcsec = float(fov_width_deg) * 3600.0 / float(width_px)
            scale_y_arcsec = float(fov_height_deg) * 3600.0 / float(height_px)
            pixel_scale_arcsec = (scale_x_arcsec + scale_y_arcsec) * 0.5
        except Exception:
            # Fallback to symmetric estimate
            pixel_scale_arcsec = float(fov_width_deg) * 3600.0 / max(1.0, float(width_px))

        from overlay.projection import skycoord_to_pixel_wcs as project_skycoord_wcs

        return project_skycoord_wcs(
            obj_ra,
            obj_dec,
            cen_ra,
            cen_dec,
            size_px,
            pixel_scale_arcsec=pixel_scale_arcsec,
            position_angle_deg=position_angle_deg,
            flip_x=flip_x,
            flip_y=flip_y,
            ra_increases_left=self.ra_increases_left,
        )

    def skycoord_to_pixel(self, obj_coord, center_coord, size_px, fov_deg):
        """Converts sky coordinates to pixel coordinates (legacy method)."""
        return self.skycoord_to_pixel_with_rotation(
            obj_coord, center_coord, size_px, fov_deg, fov_deg, 0.0
        )

    def validate_coordinates(self, ra: float, dec: float):
        """Validates RA/Dec values."""
        if not (0 <= ra <= 360):
            raise ValueError(f"RA must be between 0 and 360 degrees, not {ra}")
        if not (-90 <= dec <= 90):
            raise ValueError(f"Dec must be between -90 and 90 degrees, not {dec}")

    def _get_info_panel_font(self, size: Optional[int] = None):
        """Get font for info panel with specified size."""
        font_size: int = int(
            size if size is not None else self.info_panel_config.get("font_size", 12)
        )

        font_paths = []
        system = platform.system().lower()

        if system == "windows":
            font_paths = self.platform_config.get("fonts", {}).get("windows", ["arial.ttf"])
        elif system == "linux":
            font_paths = self.platform_config.get("fonts", {}).get("linux", [])
        elif system == "darwin":  # macOS
            font_paths = self.platform_config.get("fonts", {}).get("macos", [])

        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, font_size)
            except (IOError, OSError):
                continue

        # Fallback to default font
        return ImageFont.load_default()

    def _get_title_font(self, size: Optional[int] = None):
        """Get font for title with specified size."""
        font_size: int = int(size if size is not None else self.title_config.get("font_size", 18))

        font_paths = []
        system = platform.system().lower()

        if system == "windows":
            font_paths = self.platform_config.get("fonts", {}).get("windows", ["arial.ttf"])
        elif system == "linux":
            font_paths = self.platform_config.get("fonts", {}).get("linux", [])
        elif system == "darwin":  # macOS
            font_paths = self.platform_config.get("fonts", {}).get("macos", [])

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

        ra_angle = Angle(ra_deg, unit="deg")
        dec_angle = Angle(dec_deg, unit="deg")

        ra_str = ra_angle.to_string(unit="hourangle", sep=":", precision=2)
        dec_str = dec_angle.to_string(unit="deg", sep=":", precision=1)

        return f"RA: {ra_str} | Dec: {dec_str}"

    def _get_telescope_info(self) -> str:
        """Get telescope information from config."""
        telescope_config = self.config.get_telescope_config()
        focal_length = telescope_config.get("focal_length", "Unknown")
        aperture = telescope_config.get("aperture", "Unknown")
        focal_ratio = telescope_config.get("focal_ratio", "Unknown")
        telescope_type = telescope_config.get("type", "Unknown")

        return f"Telescope: {aperture}mm {telescope_type} (f/{focal_ratio}, {focal_length}mm FL)"

    def _get_camera_info(self) -> str:
        """Get camera information from config."""
        camera_config = self.config.get_camera_config()
        camera_type = camera_config.get("camera_type", "Unknown")
        sensor_width = camera_config.get("sensor_width", "Unknown")
        sensor_height = camera_config.get("sensor_height", "Unknown")
        pixel_size = camera_config.get("pixel_size", "Unknown")
        bit_depth = camera_config.get("bit_depth", "Unknown")

        return (
            f"Camera: {camera_type.upper()} ("
            f"{sensor_width}×{sensor_height}mm, {pixel_size}μm, {bit_depth}bit)"
        )

    def _get_fov_info(self, fov_width_deg: float, fov_height_deg: float) -> str:
        """Get field of view information."""
        fov_width_arcmin = fov_width_deg * 60
        fov_height_arcmin = fov_height_deg * 60

        return (
            f"FOV: {fov_width_deg:.2f}°×{fov_height_deg:.2f}° ("
            f"{fov_width_arcmin:.1f}'×{fov_height_arcmin:.1f}')"
        )

    # Removed local drawing wrappers; direct overlay.drawing calls are used instead

    def _should_draw_ellipse(self, object_type: str) -> bool:
        """Determine if an object should be drawn as an ellipse based on its type.

        Args:
            object_type: SIMBAD object type

        Returns:
            bool: True if object should be drawn as ellipse
        """
        # Object types that typically have measurable dimensions
        ellipse_types = [
            "G",  # Galaxy
            "GlC",  # Globular Cluster
            "OC",  # Open Cluster
            "Neb",  # Nebula
            "PN",  # Planetary Nebula
            "SNR",  # Supernova Remnant
            "HII",  # HII Region
            "Cl*",  # Cluster
            "Cld",  # Cloud
            "ISM",  # Interstellar Medium
            "MoC",  # Molecular Cloud
            "RNe",  # Reflection Nebula
            "DNe",  # Dark Nebula
            "EmO",  # Emission Object
            "Abs",  # Absorption
            "Rad",  # Radio Source
            "X",  # X-ray Source
            "gLSB",  # Low Surface Brightness Galaxy
            "AGN",  # Active Galactic Nucleus
            "QSO",  # Quasar
            "BLLac",  # BL Lacertae Object
            "Sy1",  # Seyfert 1 Galaxy
            "Sy2",  # Seyfert 2 Galaxy
            "LINER",  # LINER
            "H2G",  # HII Galaxy
            "SBG",  # Starburst Galaxy
            "LSB",  # Low Surface Brightness Galaxy
            "dSph",  # Dwarf Spheroidal Galaxy
            "dE",  # Dwarf Elliptical Galaxy
            "dI",  # Dwarf Irregular Galaxy
            "dS0",  # Dwarf S0 Galaxy
            "dS",  # Dwarf Spiral Galaxy
            "dSB",  # Dwarf Barred Spiral Galaxy
            "dE,N",  # Dwarf Elliptical Galaxy with Nucleus
            "dS0,N",  # Dwarf S0 Galaxy with Nucleus
            "dS,N",  # Dwarf Spiral Galaxy with Nucleus
            "dSB,N",  # Dwarf Barred Spiral Galaxy with Nucleus
        ]

        return object_type in ellipse_types

    # Secondary FOV helpers moved to overlay.info

    def _draw_secondary_fov(self, *args, **kwargs):
        pass

    def generate_overlay(
        self,
        ra_deg: float,
        dec_deg: float,
        output_file: Optional[str] = None,
        fov_width_deg: Optional[float] = None,
        fov_height_deg: Optional[float] = None,
        position_angle_deg: Optional[float] = None,
        image_size: Optional[Tuple[int, int]] = None,
        mag_limit: Optional[float] = None,
        flip_x: Optional[bool] = None,
        flip_y: Optional[bool] = None,
        # Legacy alias for backward compatibility
        is_flipped: Optional[bool] = None,
        status_messages: Optional[list[str]] = None,
    ) -> str:
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
            pa_deg_in = position_angle_deg if position_angle_deg is not None else 0.0
            # Apply user-configured rotation offset
            pa_deg = pa_deg_in + float(self.rotation_offset_deg)
            img_size = image_size if image_size is not None else self.image_size
            mag_limit = mag_limit if mag_limit is not None else self.mag_limit
            # Default: do not flip X; solver PA already accounts for flips
            if flip_x is None:
                flip_x = bool(is_flipped) if is_flipped is not None else False
            flip_y = flip_y if flip_y is not None else False
            output_file = output_file or self.default_filename

            # Do not adjust PA here; upstream solvers (e.g., PlateSolve2) may already apply PA+180°.
            # If a solver indicates flipping without PA correction,
            # the X-mirror in the projection handles it.

            center = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")

            # Try to import astroquery lazily
            simbad_available = True
            try:
                from astroquery.simbad import Simbad  # noqa: F401
            except Exception:
                simbad_available = False
                self.logger.warning(
                    "astroquery not available; generating overlay without catalog objects"
                )

            result = None
            if simbad_available:
                # Configure SIMBAD with robust field selection (delegated)
                custom_simbad = Simbad()
                custom_simbad.reset_votable_fields()
                custom_simbad.add_votable_fields("ra", "dec", "V", "otype", "main_id")
                picked_maj, picked_min, picked_ang, picked_dims, pa_supported = (
                    discover_simbad_dimension_fields(Simbad)
                )
                for fld in [picked_maj, picked_min, picked_ang, picked_dims]:
                    if fld:
                        try:
                            custom_simbad.add_votable_fields(fld)
                        except Exception:
                            pass

                # Radius is half-diagonal of field of view
                radius = ((fov_w**2 + fov_h**2) ** 0.5) / 2

                self.logger.info("SIMBAD query running...")
                try:
                    result = custom_simbad.query_region(center, radius=radius * u.deg)
                except Exception as e:
                    self.logger.warning(
                        f"Simbad query failed: {e}; proceeding without catalog objects"
                    )
                    result = None

            if result is None or len(result) == 0:
                if simbad_available:
                    self.logger.warning("No objects found.")
                # Create empty overlay if configured
                if self.advanced_config.get("save_empty_overlays", True):
                    img = Image.new("RGBA", img_size, (0, 0, 0, 0))
                    img.save(output_file)
                    self.logger.info(f"Empty overlay saved as {output_file}")
                _ = success_status(
                    f"Empty overlay saved as {output_file}",
                    data=output_file,
                    details={
                        "fov_width_deg": fov_w,
                        "fov_height_deg": fov_h,
                        "position_angle_deg": pa_deg,
                        "image_size": img_size,
                        "magnitude_limit": mag_limit,
                    },
                )
                # Return the path string for this method's contract
                return str(output_file)

            # Debug: Print available column names
            if self.advanced_config.get("debug_simbad", False):
                self.logger.debug("Available columns: %s", result.colnames)
                self.logger.debug("Number of objects: %d", len(result))

            # Prepare image
            img = Image.new("RGBA", img_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            font = self.get_font()

            # Draw title and info panel first (so they appear behind objects)
            draw_title(
                draw,
                img_size,
                self.title_config.get("text", "OST Telescope Streaming"),
                self.title_config.get("position", "top_center"),
                self._get_title_font(self.title_config.get("font_size", 18)),
                tuple(self.title_config.get("font_color", [255, 255, 0, 255])),
                tuple(self.title_config.get("background_color", [0, 0, 0, 180])),
                self.title_config.get("padding", 10),
                tuple(self.title_config.get("border_color", [255, 255, 255, 255])),
                self.title_config.get("border_width", 1),
            )

            if self.info_panel_enabled:
                info_font = self._get_info_panel_font(self.info_panel_config.get("font_size", 12))
                lines = []
                title_color = tuple(self.info_panel_config.get("title_color", [255, 255, 0, 255]))
                text_color = tuple(self.info_panel_config.get("text_color", [255, 255, 255, 255]))
                lines.append(("INFO PANEL", title_color))
                lines.append(("", text_color))
                # Optional status messages (e.g., slewing/parking)
                if status_messages:
                    alert_color = tuple(
                        self.info_panel_config.get("alert_color", [255, 165, 0, 255])
                    )
                    for msg in status_messages:
                        lines.append((msg, alert_color))
                    lines.append(("", text_color))
                if self.info_panel_config.get("show_timestamp", True):
                    from datetime import datetime

                    lines.append(
                        (f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", text_color)
                    )
                if self.info_panel_config.get("show_coordinates", True):
                    lines.append((format_coordinates(ra_deg, dec_deg), text_color))
                if pa_deg != 0.0:
                    lines.append((f"Position Angle: {pa_deg:.1f}°", text_color))
                if self.info_panel_config.get("show_telescope_info", True):
                    lines.append(("", text_color))
                    lines.append((telescope_info(self.config.get_telescope_config()), text_color))
                if self.info_panel_config.get("show_camera_info", True):
                    lines.append((camera_info(self.config.get_camera_config()), text_color))
                if self.info_panel_config.get("show_fov_info", True):
                    lines.append(("", text_color))
                    lines.append((fov_info(fov_w, fov_h), text_color))
                if self.show_cooling_info:
                    # Try to get cooling status if cooling service exists
                    try:
                        from services.cooling.service import CoolingService  # noqa: F401

                        cooling_status = None
                        # Heuristic: video processor may have started status monitoring
                        if (
                            hasattr(self, "video_processor")
                            and self.video_processor
                            and hasattr(self.video_processor, "cooling_service")
                        ):
                            cs = self.video_processor.cooling_service
                            if cs:
                                cooling_status = cs.get_cooling_status()
                        # Fallback: inspector in config not available here; show enabled flag only
                        enabled = bool(
                            self.config.get_camera_config()
                            .get("cooling", {})
                            .get("enable_cooling", False)
                        )
                        lines.append((cooling_info(cooling_status, enabled), text_color))
                    except Exception:
                        pass

                draw_info_panel(
                    draw,
                    img_size,
                    lines,
                    self.info_panel_config.get("position", "top_right"),
                    self.info_panel_config.get("width", 300),
                    self.info_panel_config.get("padding", 10),
                    self.info_panel_config.get("line_spacing", 5),
                    tuple(self.info_panel_config.get("background_color", [0, 0, 0, 180])),
                    tuple(self.info_panel_config.get("border_color", [255, 255, 255, 255])),
                    self.info_panel_config.get("border_width", 2),
                    info_font,
                )

            # Draw secondary FOV overlay
            draw_secondary_fov(
                draw,
                img_size,
                ra_deg,
                dec_deg,
                fov_w,
                fov_h,
                pa_deg,
                self.secondary_fov_config,
                self.ra_increases_left,
            )

            # Process objects
            objects_drawn = 0
            for row in result:
                try:
                    # Handle objects with and without V magnitude
                    has_v_magnitude = (
                        "V" in row.colnames and row["V"] is not None and row["V"] != "--"
                    )

                    # Skip objects that are too faint (if they have magnitude)
                    if has_v_magnitude and row["V"] > mag_limit:
                        continue

                    # Skip objects without magnitude if configured
                    if not has_v_magnitude and not self.include_no_magnitude:
                        continue

                    # Filter by object type if specified
                    if self.object_types and "otype" in row.colnames:
                        obj_type = row["otype"]
                        if obj_type not in self.object_types:
                            continue

                    # Try different possible column names for RA/Dec
                    ra_col = None
                    dec_col = None

                    # Check for various possible column names
                    for ra_name in ["RA", "ra", "RA_d", "ra_d"]:
                        if ra_name in row.colnames:
                            ra_col = ra_name
                            break

                    for dec_name in ["DEC", "dec", "DEC_d", "dec_d"]:
                        if dec_name in row.colnames:
                            dec_col = dec_name
                            break

                    if ra_col is None or dec_col is None:
                        self.logger.warning(
                            f"Could not find RA/Dec columns. Available: {row.colnames}"
                        )
                        continue

                    # Use found column names
                    obj_coord = SkyCoord(ra=row[ra_col], dec=row[dec_col], unit="deg")
                    x, y = self.skycoord_to_pixel_with_rotation(
                        obj_coord, center, img_size, fov_w, fov_h, pa_deg, flip_x, flip_y
                    )

                    # Check if object is within image bounds
                    if 0 <= x <= img_size[0] and 0 <= y <= img_size[1]:
                        # Check if we should draw an ellipse for this object type
                        object_type = row.get("otype", "") if "otype" in row.colnames else ""
                        should_draw_ellipse = self._should_draw_ellipse(object_type)

                        # Check if we have dimension data for ellipse
                        has_dimensions = False
                        dim_maj = None
                        dim_min = None
                        pa = None

                        if should_draw_ellipse:
                            # Prefer explicit numeric fields first
                            # (use whichever we successfully added)
                            if (
                                picked_maj
                                and picked_maj in row.colnames
                                and row[picked_maj] not in (None, "--")
                            ):
                                try:
                                    dim_maj = float(row[picked_maj])
                                except Exception:
                                    dim_maj = None
                            if (
                                picked_min
                                and picked_min in row.colnames
                                and row[picked_min] not in (None, "--")
                            ):
                                try:
                                    dim_min = float(row[picked_min])
                                except Exception:
                                    dim_min = None
                            if (
                                picked_ang
                                and picked_ang in row.colnames
                                and row[picked_ang] not in (None, "--")
                            ):
                                try:
                                    pa = float(row[picked_ang])
                                except Exception:
                                    pa = None

                            # Fallback to legacy combined string field
                            if (dim_maj is None or dim_min is None) and (
                                (picked_dims and picked_dims in row.colnames)
                                or "dimensions" in row.colnames
                            ):
                                dimensions_str = str(row["dimensions"])
                                if dimensions_str != "--" and dimensions_str.strip():
                                    try:
                                        if "x" in dimensions_str:
                                            parts = dimensions_str.split("x")
                                            if len(parts) == 2:
                                                dim_maj = dim_maj or float(parts[0].strip())
                                                dim_min = dim_min or float(parts[1].strip())
                                        else:
                                            dim_maj = dim_maj or float(dimensions_str)
                                            dim_min = dim_min or dim_maj
                                    except (ValueError, TypeError):
                                        pass

                            # Final fallback for PA via 'pa' field (if supported)
                            if (
                                pa is None
                                and picked_ang
                                and picked_ang in row.colnames
                                and row[picked_ang] is not None
                            ):
                                pa_str = str(row[picked_ang])
                                if pa_str != "--" and pa_str.strip():
                                    try:
                                        pa = float(pa_str)
                                    except (ValueError, TypeError):
                                        pa = None

                            has_dimensions = dim_maj is not None and dim_min is not None
                            pa = pa or 0.0

                        # Draw ellipse if we have dimension data
                        if (
                            should_draw_ellipse
                            and has_dimensions
                            and dim_maj is not None
                            and dim_min is not None
                        ):
                            ellipse_drawn = draw_ellipse_for_object(
                                draw,
                                x,
                                y,
                                dim_maj,
                                dim_min,
                                pa or 0.0,
                                img_size,
                                fov_w,
                                fov_h,
                                pa_deg,
                                flip_x,
                                tuple(self.object_color),
                                2,
                            )
                            if not ellipse_drawn:
                                # Fallback to marker if ellipse drawing failed
                                draw.ellipse(
                                    (
                                        x - self.marker_size,
                                        y - self.marker_size,
                                        x + self.marker_size,
                                        y + self.marker_size,
                                    ),
                                    outline=self.object_color,
                                    width=2,
                                )
                        else:
                            # Draw standard marker
                            draw.ellipse(
                                (
                                    x - self.marker_size,
                                    y - self.marker_size,
                                    x + self.marker_size,
                                    y + self.marker_size,
                                ),
                                outline=self.object_color,
                                width=2,
                            )

                        # Safe name handling - try different possible column names
                        name = None
                        name_columns = ["MAIN_ID", "main_id", "MAINID", "mainid"]

                        for name_col in name_columns:
                            if name_col in row.colnames:
                                name_value = row[name_col]
                                if name_value is not None:
                                    if isinstance(name_value, bytes):
                                        name = name_value.decode("utf-8", errors="ignore")
                                    else:
                                        name = str(name_value)
                                    break

                        # Fallback if no name found
                        if name is None:
                            name = f"Obj_{objects_drawn}"

                        # Truncate long names
                        if len(name) > self.max_name_length:
                            name = name[: self.max_name_length - 3] + "..."

                        draw.text(
                            (x + self.text_offset[0], y + self.text_offset[1]),
                            name,
                            fill=self.text_color,
                            font=font,
                        )
                        objects_drawn += 1

                except Exception as e:
                    # More detailed error information for debugging
                    if self.advanced_config.get("debug_simbad", False):
                        self.logger.warning(f"Error processing object: {e}")
                        self.logger.debug(
                            "  Available columns: %s",
                            row.colnames if hasattr(row, "colnames") else "No colnames",
                        )
                        if hasattr(row, "colnames") and "main_id" in row.colnames:
                            self.logger.debug(f"  main_id value: {row['main_id']}")
                    else:
                        self.logger.warning(f"Error processing object: {e}")
                    continue

            img.save(output_file)
            self.logger.info("Overlay with %d objects saved as %s", objects_drawn, output_file)
            # Return path string to satisfy method signature
            return str(output_file)

        except Exception as e:
            self.logger.error(f"Error: {e}")
            # Re-raise or return a fallback path; we return the default filename
            return output_file or self.default_filename


# Transitional re-exports removed; use overlay.generator directly
