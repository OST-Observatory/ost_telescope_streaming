from __future__ import annotations

import platform
from typing import Tuple
from PIL import ImageFont


def get_info_panel_font(platform_config: dict, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_paths = []
    system = platform.system().lower()
    if system == "windows":
        font_paths = platform_config.get('fonts', {}).get('windows', ['arial.ttf'])
    elif system == "linux":
        font_paths = platform_config.get('fonts', {}).get('linux', [])
    elif system == "darwin":
        font_paths = platform_config.get('fonts', {}).get('macos', [])
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def get_title_font(platform_config: dict, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return get_info_panel_font(platform_config, size)


