from __future__ import annotations

from typing import Tuple
import numpy as np
from PIL import ImageDraw, ImageFont


def draw_title(draw: ImageDraw.ImageDraw, img_size: Tuple[int, int], text: str, position: str,
               font: ImageFont.ImageFont, font_color: Tuple[int, int, int, int],
               background_color: Tuple[int, int, int, int], padding: int,
               border_color: Tuple[int, int, int, int], border_width: int) -> None:
    text_bbox = font.getbbox(text)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    box_w = text_w + 2 * padding
    box_h = text_h + 2 * padding
    if position == 'top_center':
        box_x = (img_size[0] - box_w) // 2
        box_y = padding
    elif position == 'top_left':
        box_x = padding
        box_y = padding
    elif position == 'top_right':
        box_x = img_size[0] - box_w - padding
        box_y = padding
    else:
        box_x = padding
        box_y = padding
    bg_rect = [box_x, box_y, box_x + box_w, box_y + box_h]
    draw.rectangle(bg_rect, fill=background_color)
    if border_width > 0:
        border_rect = [box_x - border_width, box_y - border_width,
                       box_x + box_w + border_width, box_y + box_h + border_width]
        draw.rectangle(border_rect, outline=border_color, width=border_width)
    draw.text((box_x + padding, box_y + padding), text, fill=font_color, font=font)


def draw_info_panel(draw: ImageDraw.ImageDraw, img_size: Tuple[int, int],
                    lines: list[tuple[str, Tuple[int, int, int, int]]],
                    position: str, width: int, padding: int, line_spacing: int,
                    background_color: Tuple[int, int, int, int],
                    border_color: Tuple[int, int, int, int], border_width: int,
                    font: ImageFont.ImageFont) -> None:
    text_bbox = font.getbbox("A")
    line_height = text_bbox[3] - text_bbox[1] + line_spacing
    panel_height = len(lines) * line_height + 2 * padding
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
    bg_rect = [panel_x, panel_y, panel_x + width, panel_y + panel_height]
    draw.rectangle(bg_rect, fill=background_color)
    if border_width > 0:
        border_rect = [panel_x - border_width, panel_y - border_width,
                       panel_x + width + border_width, panel_y + panel_height + border_width]
        draw.rectangle(border_rect, outline=border_color, width=border_width)
    y_off = panel_y + padding
    for text, color in lines:
        if text:
            draw.text((panel_x + padding, y_off), text, fill=color, font=font)
        y_off += line_height


def draw_ellipse_for_object(draw: ImageDraw.ImageDraw, center_x: int, center_y: int,
                            dim_maj_arcmin: float, dim_min_arcmin: float, pa_deg: float,
                            img_size: Tuple[int, int], fov_width_deg: float, fov_height_deg: float,
                            position_angle_deg: float, is_flipped: bool,
                            color: Tuple[int, int, int, int], line_width: int) -> bool:
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
    left = center_x - max_x
    right = center_x + max_x
    top = center_y - max_y
    bottom = center_y + max_y
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


