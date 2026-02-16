"""
Module 3: The Studio
Refactored for Unified Content Engine — output goes to temp/ folder.
"""

import os
import random
import textwrap
import json
from moviepy import (
    VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip,
    vfx, afx
)
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Configuration — paths resolve relative to THIS file
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "temp")
VIDEO_DURATION = 15

os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_random_file(directory, extensions):
    """Picks a random file with specific extension from a folder."""
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")
    files = [f for f in os.listdir(directory) if f.lower().endswith(extensions)]
    if not files:
        raise FileNotFoundError(f"No files with {extensions} found in {directory}")
    return os.path.join(directory, random.choice(files))


def load_template_config():
    """Loads the JSON configuration for video templates."""
    config_path = os.path.join(ASSETS_DIR, "templates", "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


# Map font_weight names to filename suffixes
FONT_WEIGHT_MAP = {
    "regular": "Regular",
    "bold": "Bold",
    "semibold": "SemiBold",
    "light": "Light",
    "medium": "Medium",
    "extrabold": "ExtraBold",
}


def _resolve_font_name(config):
    """Resolve font filename considering font_weight."""
    if not config:
        return None
    font_name = config.get("font")
    if not font_name:
        return None

    font_weight = config.get("font_weight", "regular").lower()
    if font_weight and font_weight != "regular":
        base = font_name.rsplit("-", 1)[0] if "-" in font_name else font_name.rsplit(".", 1)[0]
        ext = font_name.rsplit(".", 1)[-1] if "." in font_name else "ttf"
        weight_suffix = FONT_WEIGHT_MAP.get(font_weight, font_weight.capitalize())
        variant_name = f"{base}-{weight_suffix}.{ext}"
        fonts_dir = os.path.join(ASSETS_DIR, "fonts")
        if os.path.exists(os.path.join(fonts_dir, variant_name)):
            return variant_name
        else:
            print(f"   ⚠️  Weight variant '{variant_name}' not found, using '{font_name}'")
    return font_name


def _load_font(config, font_size):
    """Load font based on config, with clear fallback warnings."""
    fonts_dir = os.path.join(ASSETS_DIR, "fonts")

    font_name = _resolve_font_name(config)
    if font_name:
        try:
            font_path = os.path.join(fonts_dir, font_name)
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, font_size)
            else:
                print(f"   ⚠️  Font '{font_name}' not found at {font_path}")
        except Exception as e:
            print(f"   ⚠️  Error loading config font: {e}")

    try:
        font_path = get_random_file(fonts_dir, (".ttf", ".otf"))
        return ImageFont.truetype(font_path, font_size)
    except FileNotFoundError:
        print("   ⚠️  No fonts in assets/fonts/. Using system default font.")
    except Exception as e:
        print(f"   ⚠️  Font loading error: {e}")

    try:
        return ImageFont.load_default(size=font_size)
    except TypeError:
        print(f"   ⚠️  Pillow too old for sized default font. Text may be very small.")
        return ImageFont.load_default()


def _wrap_and_measure(draw, text, font, font_size, area_w):
    """Wrap text using pixel-accurate measurement. Returns (lines, line_heights, total_height)."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip() if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_w = bbox[2] - bbox[0]

        if line_w <= area_w:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    line_spacing = max(int(font_size * 0.3), 8)
    total_text_height = 0
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        h = bbox[3] - bbox[1]
        line_heights.append(h + line_spacing)
        total_text_height += h + line_spacing

    return lines, line_heights, total_text_height


def create_text_image(text, width=1080, height=1920, config=None):
    """
    Creates a transparent image with text using Pillow.
    Uses config for placement if provided, otherwise defaults to center.
    Auto-scales font size down if text overflows the configured text area.
    """
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_size = 70
    alignment = "center"
    text_color = "white"
    shadow_color = "black"
    padding = 0

    area_x = 0
    area_y = 0
    area_w = width
    area_h = height

    if config:
        if "text_area" in config:
            area_x = config["text_area"].get("x", 0)
            area_y = config["text_area"].get("y", 0)
            area_w = config["text_area"].get("width", width)
            area_h = config["text_area"].get("height", height)

        font_size = config.get("font_size", 70)
        alignment = config.get("alignment", "center")
        text_color = config.get("color", "white")
        shadow_color = config.get("shadow", "black")
        padding = config.get("padding", 0)

    area_x += padding
    area_y += padding
    area_w -= padding * 2
    area_h -= padding * 2

    MIN_FONT_SIZE = 16
    original_font_size = font_size

    font = _load_font(config, font_size)
    lines, line_heights, total_text_height = _wrap_and_measure(
        draw, text, font, font_size, area_w
    )

    while total_text_height > area_h and font_size > MIN_FONT_SIZE:
        font_size = max(font_size - 4, MIN_FONT_SIZE)
        font = _load_font(config, font_size)
        lines, line_heights, total_text_height = _wrap_and_measure(
            draw, text, font, font_size, area_w
        )

    if font_size != original_font_size:
        print(f"   📐 Auto-scaled font from {original_font_size}px → {font_size}px to fit text area")

    if config and "text_area" in config:
        start_y = area_y + (area_h - total_text_height) // 2
    else:
        start_y = (height - total_text_height) // 2
        box_padding = 50
        box_top = start_y - box_padding
        box_bottom = start_y + total_text_height + box_padding
        draw.rectangle(
            [(80, box_top), (width - 80, box_bottom)],
            fill=(0, 0, 0, 200)
        )

    current_y = start_y

    for line, h in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]

        if alignment == "center":
            if config:
                x = area_x + (area_w - text_w) // 2
            else:
                x = (width - text_w) // 2
        elif alignment == "left":
            x = area_x
        elif alignment == "right":
            x = area_x + area_w - text_w
        else:
            x = (width - text_w) // 2

        if shadow_color:
            draw.text((x + 3, current_y + 3), line, font=font, fill=shadow_color)
        draw.text((x, current_y), line, font=font, fill=text_color)

        current_y += h

    return np.array(img)


def generate_reel(joke_text, output_filename="daily_reel.mp4", duration=None,
                 video_path=None, audio_path=None):
    """
    Generate an Instagram Reel.
    Supports explicit video/audio paths and config-based styling.
    """
    duration = duration or VIDEO_DURATION

    if not video_path:
        video_path = get_random_file(os.path.join(ASSETS_DIR, "templates"), (".mp4", ".mov"))

    if not audio_path:
        audio_path = get_random_file(os.path.join(ASSETS_DIR, "music"), (".mp3", ".wav", ".m4a"))

    video_filename = os.path.basename(video_path)

    print(f"🎬 Creating Reel...")
    print(f"   Text: {joke_text[:50]}...")
    print(f"   📹 Video: {video_filename}")
    print(f"   🎵 Audio: {os.path.basename(audio_path)}")

    template_config = load_template_config()
    video_config = template_config.get(video_filename)

    if video_config:
        print(f"   ⚙️  Loaded config for {video_filename}")

    video = VideoFileClip(video_path)

    if video.duration < duration:
        video = video.with_effects([vfx.Loop(duration=duration)])
    else:
        video = video.subclipped(0, duration)

    target_ratio = 1080 / 1920
    current_ratio = video.w / video.h

    if abs(current_ratio - target_ratio) > 0.1:
        video = video.resized(height=1920)
        if video.w > 1080:
            x_center = video.w // 2
            video = video.cropped(x1=x_center - 540, x2=x_center + 540)
    else:
        video = video.resized(width=1080)

    txt_img_array = create_text_image(joke_text, config=video_config)
    txt_clip = ImageClip(txt_img_array).with_duration(duration)

    audio = AudioFileClip(audio_path)
    if audio.duration < duration:
        audio = audio.with_effects([afx.AudioLoop(duration=duration)])
    else:
        audio = audio.subclipped(0, duration)

    final = CompositeVideoClip([video, txt_clip])
    final = final.with_audio(audio)

    output_path = os.path.join(OUTPUT_DIR, output_filename)
    temp_audio_path = os.path.join(OUTPUT_DIR, f"temp_{output_filename}_audio.m4a")

    final.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=temp_audio_path,
        remove_temp=True,
        logger=None
    )

    video.close()
    audio.close()
    final.close()

    print(f"✅ Saved to: {output_path}")
    return output_path
