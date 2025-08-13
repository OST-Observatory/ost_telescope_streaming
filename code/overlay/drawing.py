from __future__ import annotations

from typing import Tuple

import numpy as np
from overlay.projection import skycoord_to_pixel_with_rotation as project_skycoord
from PIL import ImageDraw, ImageFont


def draw_title(
    draw: ImageDraw.ImageDraw,
    img_size: Tuple[int, int],
    text: str,
    position: str,
    font: ImageFont.ImageFont,
    font_color: Tuple[int, int, int, int],
    background_color: Tuple[int, int, int, int],
    padding: int,
    border_color: Tuple[int, int, int, int],
    border_width: int,
) -> None:
    text_bbox = font.getbbox(text)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    box_w = text_w + 2 * padding
    box_h = text_h + 2 * padding
    if position == "top_center":
        box_x = (img_size[0] - box_w) // 2
        box_y = padding
    elif position == "top_left":
        box_x = padding
        box_y = padding
    elif position == "top_right":
        box_x = img_size[0] - box_w - padding
        box_y = padding
    else:
        box_x = padding
        box_y = padding
    bg_rect = [box_x, box_y, box_x + box_w, box_y + box_h]
    draw.rectangle(bg_rect, fill=background_color)
    if border_width > 0:
        border_rect = [
            box_x - border_width,
            box_y - border_width,
            box_x + box_w + border_width,
            box_y + box_h + border_width,
        ]
        draw.rectangle(border_rect, outline=border_color, width=border_width)
    draw.text((box_x + padding, box_y + padding), text, fill=font_color, font=font)


def draw_info_panel(
    draw: ImageDraw.ImageDraw,
    img_size: Tuple[int, int],
    lines: list[tuple[str, Tuple[int, int, int, int]]],
    position: str,
    width: int,
    padding: int,
    line_spacing: int,
    background_color: Tuple[int, int, int, int],
    border_color: Tuple[int, int, int, int],
    border_width: int,
    font: ImageFont.ImageFont,
) -> None:
    text_bbox = font.getbbox("A")
    line_height = text_bbox[3] - text_bbox[1] + line_spacing
    panel_height = len(lines) * line_height + 2 * padding
    if position == "top_left":
        panel_x = padding
        panel_y = padding
    elif position == "top_right":
        panel_x = img_size[0] - width - padding
        panel_y = padding
    elif position == "bottom_left":
        panel_x = padding
        panel_y = img_size[1] - panel_height - padding
    elif position == "bottom_right":
        panel_x = img_size[0] - width - padding
        panel_y = img_size[1] - panel_height - padding
    else:
        panel_x = padding
        panel_y = padding
    bg_rect = [panel_x, panel_y, panel_x + width, panel_y + panel_height]
    draw.rectangle(bg_rect, fill=background_color)
    if border_width > 0:
        border_rect = [
            panel_x - border_width,
            panel_y - border_width,
            panel_x + width + border_width,
            panel_y + panel_height + border_width,
        ]
        draw.rectangle(border_rect, outline=border_color, width=border_width)
    y_off = panel_y + padding
    for text, color in lines:
        if text:
            draw.text((panel_x + padding, y_off), text, fill=color, font=font)
        y_off += line_height


def draw_ellipse_for_object(
    draw: ImageDraw.ImageDraw,
    center_x: int,
    center_y: int,
    dim_maj_arcmin: float,
    dim_min_arcmin: float,
    pa_deg: float,
    img_size: Tuple[int, int],
    fov_width_deg: float,
    fov_height_deg: float,
    position_angle_deg: float,
    is_flipped: bool,
    color: Tuple[int, int, int, int],
    line_width: int,
) -> bool:
    scale_x = (fov_width_deg * 60) / img_size[0]
    scale_y = (fov_height_deg * 60) / img_size[1]
    major_px = dim_maj_arcmin / scale_x
    minor_px = dim_min_arcmin / scale_y
    if major_px < 3 or minor_px < 3:
        return False
    total_rot = (-pa_deg if is_flipped else pa_deg) + position_angle_deg
    rot = np.deg2rad(total_rot)
    cos_r = np.cos(rot)
    sin_r = np.sin(rot)
    max_x = np.sqrt((major_px * cos_r) ** 2 + (minor_px * sin_r) ** 2)
    max_y = np.sqrt((major_px * sin_r) ** 2 + (minor_px * cos_r) ** 2)
    # Bounding box values computed but not used directly; retained for future enhancements
    _left = center_x - max_x
    _right = center_x + max_x
    _top = center_y - max_y
    _bottom = center_y + max_y
    steps = 72
    pts = []
    for i in range(steps):
        theta = 2 * np.pi * i / steps
        x = major_px * np.cos(theta)
        y = minor_px * np.sin(theta)
        xr = x * cos_r - y * sin_r
        yr = x * sin_r + y * cos_r
        pts.append((center_x + xr, center_y + yr))
    for i in range(steps - 1):
        draw.line([pts[i], pts[i + 1]], fill=color, width=line_width)
    draw.line([pts[-1], pts[0]], fill=color, width=line_width)
    return True


def draw_secondary_fov(
    draw: ImageDraw.ImageDraw,
    img_size: Tuple[int, int],
    center_ra_deg: float,
    center_dec_deg: float,
    fov_width_deg: float,
    fov_height_deg: float,
    position_angle_deg: float,
    is_flipped: bool,
    secondary_fov_config: dict,
    ra_increases_left: bool,
) -> None:
    if not secondary_fov_config.get("enabled", False):
        return

    def calculate_secondary_fov_dims(cfg: dict) -> Tuple[float, float]:
        fov_type = cfg.get("type", "camera")
        telescope_config = cfg.get("telescope", {})
        focal_length = telescope_config.get("focal_length", 1000.0)
        if fov_type == "camera":
            camera_cfg = cfg.get("camera", {})
            sensor_w = float(camera_cfg.get("sensor_width", 10.0))
            sensor_h = float(camera_cfg.get("sensor_height", 10.0))
            sec_w = (sensor_w / focal_length) * (180.0 / np.pi)
            sec_h = (sensor_h / focal_length) * (180.0 / np.pi)
            return sec_w, sec_h
        elif fov_type == "eyepiece":
            eyepiece = cfg.get("eyepiece", {})
            eyepiece_fl = float(eyepiece.get("focal_length", 25.0))
            afov = float(eyepiece.get("afov", 68.0))
            barlow = float(eyepiece.get("barlow", 1.0))
            effective_fl = focal_length * barlow
            true_fov_deg = afov * (eyepiece_fl / effective_fl)
            aspect = cfg.get("eyepiece", {}).get("aspect_ratio", [1.0, 1.0])
            ar_w, ar_h = float(aspect[0]), float(aspect[1])
            norm = max(ar_w, ar_h)
            return true_fov_deg * (ar_w / norm), true_fov_deg * (ar_h / norm)
        return 0.0, 0.0

    sec_w, sec_h = calculate_secondary_fov_dims(secondary_fov_config)
    if sec_w <= 0 or sec_h <= 0:
        return

    display = secondary_fov_config.get("display", {})
    color = tuple(display.get("color", [0, 255, 255, 255]))
    line_width = int(display.get("line_width", 2))
    style = display.get("style", "dashed")
    show_label = display.get("show_label", True)
    label_color = tuple(display.get("label_color", [0, 255, 255, 255]))
    label_font_size = int(display.get("label_font_size", 10))
    label_offset = display.get("label_offset", [5, 5])

    offset_cfg = secondary_fov_config.get("position_offset", {})
    ra_offset_arcmin = float(offset_cfg.get("ra_offset_arcmin", 0.0))
    dec_offset_arcmin = float(offset_cfg.get("dec_offset_arcmin", 0.0))
    ra_offset_deg = ra_offset_arcmin / 60.0
    dec_offset_deg = dec_offset_arcmin / 60.0

    offset_center_ra = center_ra_deg + ra_offset_deg
    offset_center_dec = center_dec_deg + dec_offset_deg

    center_x, center_y = project_skycoord(
        offset_center_ra,
        offset_center_dec,
        center_ra_deg,
        center_dec_deg,
        img_size,
        fov_width_deg,
        fov_height_deg,
        position_angle_deg,
        is_flipped,
        ra_increases_left,
    )

    scale_x = (fov_width_deg * 60.0) / img_size[0]
    scale_y = (fov_height_deg * 60.0) / img_size[1]
    sec_w_px = (sec_w * 60.0) / scale_x
    sec_h_px = (sec_h * 60.0) / scale_y

    half_w = sec_w_px / 2.0
    half_h = sec_h_px / 2.0

    fov_type = secondary_fov_config.get("type", "camera")
    if fov_type == "camera":
        left = center_x - half_w
        top = center_y - half_h
        right = center_x + half_w
        bottom = center_y + half_h
        left = max(0, min(left, img_size[0]))
        top = max(0, min(top, img_size[1]))
        right = max(0, min(right, img_size[0]))
        bottom = max(0, min(bottom, img_size[1]))
        if style == "dashed":
            dash_len = 10
            # Top
            for x in range(int(left), int(right), dash_len * 2):
                end_x = min(x + dash_len, right)
                draw.line([(x, top), (end_x, top)], fill=color, width=line_width)
            # Bottom
            for x in range(int(left), int(right), dash_len * 2):
                end_x = min(x + dash_len, right)
                draw.line([(x, bottom), (end_x, bottom)], fill=color, width=line_width)
            # Left
            for y in range(int(top), int(bottom), dash_len * 2):
                end_y = min(y + dash_len, bottom)
                draw.line([(left, y), (left, end_y)], fill=color, width=line_width)
            # Right
            for y in range(int(top), int(bottom), dash_len * 2):
                end_y = min(y + dash_len, bottom)
                draw.line([(right, y), (right, end_y)], fill=color, width=line_width)
        else:
            draw.rectangle([left, top, right, bottom], outline=color, width=line_width)
    elif fov_type == "eyepiece":
        radius = min(half_w, half_h)
        left = center_x - radius
        top = center_y - radius
        right = center_x + radius
        bottom = center_y + radius
        if style == "dashed":
            segments = 32
            for i in range(segments):
                if i % 2 == 1:
                    continue
                theta1 = 2 * np.pi * i / segments
                theta2 = 2 * np.pi * (i + 1) / segments
                x1 = center_x + radius * np.cos(theta1)
                y1 = center_y + radius * np.sin(theta1)
                x2 = center_x + radius * np.cos(theta2)
                y2 = center_y + radius * np.sin(theta2)
                draw.line([(x1, y1), (x2, y2)], fill=color, width=line_width)
        else:
            draw.ellipse([left, top, right, bottom], outline=color, width=line_width)

    if show_label:
        label_text = secondary_fov_config.get("label", "Secondary FOV")
        try:
            from overlay.text import get_info_panel_font

            font = get_info_panel_font({}, label_font_size)
        except Exception:
            font = None
        label_x = max(10, min(center_x + label_offset[0], img_size[0] - 200))
        label_y = max(10, min(center_y + label_offset[1], img_size[1] - 20))
        if font is not None:
            bbox = font.getbbox(label_text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.rectangle(
                [label_x - 2, label_y - 2, label_x + tw + 2, label_y + th + 2], fill=(0, 0, 0, 180)
            )
        draw.text((label_x, label_y), label_text, fill=label_color, font=font)
