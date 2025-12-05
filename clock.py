
# Python 3.12
# Generates a 44-second MP4 video of a binary clock showing 4:44 using BCD columns: [0, 4, 4, 4].
# Layout: Each digit column has 4 LEDs for bits [8,4,2,1] from top to bottom.

import math
import os
import requests  # pip install requests
from typing import List, Tuple

import imageio.v2 as imageio    # pip install imageio imageio-ffmpeg
import numpy as np              # pip install numpy
from PIL import Image, ImageDraw, ImageFont  # pip install pillow

# ----------------------------
# Configuration
# ----------------------------
DURATION_SEC = 44
FPS = 30
WIDTH, HEIGHT = 1920, 1080
BACKGROUND = (20, 24, 32)            # dark bluish
LED_ON = (40, 200, 255)              # cyan-ish
LED_OFF = (60, 70, 80)               # dim gray-blue
GRID_COLS = 4                        # digits: 0,4,4,4
GRID_ROWS = 4                        # bits: 8,4,2,1 (top->bottom)
COLUMN_SPACING = 280                 # pixels between digit columns
ROW_SPACING = 160                    # pixels between leds
LED_RADIUS = 50
# Positioning the grid center
GRID_CENTER = (WIDTH // 2, HEIGHT // 2 - 40)

# Gentle pulsing animation
PULSE_ENABLED = True
PULSE_FREQ = 0.25      # Hz (cycles per second)
PULSE_DEPTH = 0.25     # 0..1 fraction to modulate brightness

# Blinking colon
COLON_ENABLED = True
COLON_BLINK_FREQ = 1.0  # Hz (blinks per second)
COLON_COLOR = (40, 200, 255)   # light blue
COLON_RADIUS = 25
COLON_SPACING = 120      # vertical spacing between colon dots

# Code overlay
CODE_OVERLAY_ENABLED = True
CODE_OVERLAY_OPACITY = 0.4  # 0.0-1.0 transparency
CODE_FONT_SIZE = 28
CODE_LINE_HEIGHT = 32
CODE_COLOR = (150, 255, 150)  # Code color (light green)

OUTPUT_MP4 = "binary_clock_4_44.mp4"


# ----------------------------
# Binary Clock Logic (BCD)
# ----------------------------
def bcd_bits(d: int) -> List[int]:
    """Return 4-bit BCD bits [8,4,2,1] for digit d, top to bottom."""
    assert 0 <= d <= 9
    return [(d >> shift) & 1 for shift in (3, 2, 1, 0)]  # 8,4,2,1 (top->bottom)


def digits_for_time(h: int, m: int) -> List[int]:
    """Return the 4 digits in BCD order: H tens, H ones, M tens, M ones."""
    # Interpret hour as 12-hour or 24-hour as needed; here we keep '04' explicitly.
    ht = h // 10
    ho = h % 10
    mt = m // 10
    mo = m % 10
    return [ht, ho, mt, mo]


def get_time_for_elapsed(t: float) -> Tuple[int, int]:
    """Return (hour, minute) based on elapsed time t in seconds."""
    if t < 22.0:  # First 22 seconds: 4:43
        return (4, 43)
    else:  # Last 22 seconds: 4:44
        return (4, 44)


def lerp_color(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """Linear blend between c1 and c2 with t in [0,1]."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# ----------------------------
# Rendering Helpers
# ----------------------------
def draw_led(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: Tuple[int, int, int]):
    """Draw a circular LED."""
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, fill=color)


def compute_grid_positions() -> List[List[Tuple[int, int]]]:
    """Compute (x,y) positions for a 4x4 grid centered around GRID_CENTER."""
    cx, cy = GRID_CENTER
    total_w = COLUMN_SPACING * (GRID_COLS - 1)
    total_h = ROW_SPACING * (GRID_ROWS - 1)
    left = cx - total_w // 2
    top = cy - total_h // 2

    positions = []
    for col in range(GRID_COLS):
        col_x = left + col * COLUMN_SPACING
        column_positions = []
        for row in range(GRID_ROWS):
            row_y = top + row * ROW_SPACING
            column_positions.append((col_x, row_y))
        positions.append(column_positions)
    return positions


def pulse_factor(t: float) -> float:
    """Return brightness multiplier in [1-PULSE_DEPTH, 1+PULSE_DEPTH] over time."""
    if not PULSE_ENABLED:
        return 1.0
    # sine wave centered at 1.0, amplitude PULSE_DEPTH
    return 1.0 + PULSE_DEPTH * math.sin(2 * math.pi * PULSE_FREQ * t)


def modulate_brightness(color: Tuple[int, int, int], k: float) -> Tuple[int, int, int]:
    """Scale color brightness by k (clamped)."""
    k = max(0.0, min(2.0, k))
    return tuple(int(max(0, min(255, ch * k))) for ch in color)


def colon_visible(t: float) -> bool:
    """Return True if colon should be visible at time t (blinking every second)."""
    if not COLON_ENABLED:
        return False
    # Blink on/off every second
    cycle_time = 1.0 / COLON_BLINK_FREQ
    return (t % cycle_time) < (cycle_time / 2)


def download_font():
    """Download a monospace font if not already present."""
    font_path = "DejaVuSansMono.ttf"
    if os.path.exists(font_path):
        return font_path
    try:
        print("Downloading font...")
        # Use a reliable source - DejaVu fonts from SourceForge mirror
        url = "https://netcologne.dl.sourceforge.net/project/dejavu/dejavu/2.37/dejavu-fonts-ttf-2.37.zip"
        import zipfile, io
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extract("dejavu-fonts-ttf-2.37/ttf/DejaVuSansMono.ttf", ".")
            os.rename("dejavu-fonts-ttf-2.37/ttf/DejaVuSansMono.ttf", font_path)
            os.rmdir("dejavu-fonts-ttf-2.37/ttf")
            os.rmdir("dejavu-fonts-ttf-2.37")
        print("Font downloaded successfully")
        return font_path
    except Exception as e:
        print(f"Font download failed: {e}")
        return None


def load_source_code() -> List[str]:
    """Load the source code as individual lines."""
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            return [line.rstrip() for line in f.readlines()]
    except:
        return ["# Code overlay unavailable"]


def draw_code_overlay(draw: ImageDraw.ImageDraw, source_lines: List[str], t: float):
    """Draw scrolling code overlay."""
    if not CODE_OVERLAY_ENABLED or not source_lines:
        return
    
    # Calculate scroll speed to get through entire script in 44 seconds
    lines_per_screen = 25  # Show about 25 lines at once
    total_scrollable_lines = max(1, len(source_lines) - lines_per_screen + 1)
    lines_per_second = total_scrollable_lines / DURATION_SEC  # Get through all lines in 44 seconds
    
    # Calculate current starting line
    start_line = int(t * lines_per_second) % total_scrollable_lines
    end_line = min(start_line + lines_per_screen, len(source_lines))
    
    # Position over clock area
    start_y = 100
    start_x = 400
    
    # Try to load a monospace font with the specified size
    font = None
    try:
        font_path = download_font()
        if font_path:
            font = ImageFont.truetype(font_path, CODE_FONT_SIZE)
    except:
        pass
    
    if not font:
        try:
            font = ImageFont.truetype("consolas.ttf", CODE_FONT_SIZE)
        except:
            font = ImageFont.load_default()
    
    # Apply color with opacity
    color = tuple(int(c * CODE_OVERLAY_OPACITY) for c in CODE_COLOR)
    
    for i, line_idx in enumerate(range(start_line, end_line)):
        if line_idx < len(source_lines):
            line = source_lines[line_idx]
            # Trim long lines
            display_line = line[:120] if len(line) > 120 else line
            y = start_y + i * CODE_LINE_HEIGHT
            
            try:
                draw.text((start_x, y), display_line, fill=color, font=font)
            except:
                # Fallback if text rendering fails
                draw.text((start_x, y), "[code]", fill=color)


def render_frame(t: float, positions: List[List[Tuple[int, int]]], source_lines: List[str]) -> Image.Image:
    """Render one frame at time t (seconds)."""
    # Get current time based on elapsed seconds
    hour, minute = get_time_for_elapsed(t)
    digits = digits_for_time(hour, minute)
    
    img = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(img)

    # Draw scrolling code overlay first (background layer)
    draw_code_overlay(draw, source_lines, t)

    # Compute pulsing factor
    k = pulse_factor(t)

    # For each digit column
    for col_idx, d in enumerate(digits):
        bits = bcd_bits(d)  # [8,4,2,1] top->bottom
        for row_idx, bit in enumerate(bits):
            cx, cy = positions[col_idx][row_idx]
            # Choose base color based on bit
            base_color = LED_ON if bit else LED_OFF
            color = modulate_brightness(base_color, k if bit else 1.0)  # pulse only lit LEDs
            draw_led(draw, cx, cy, LED_RADIUS, color)

    # Draw blinking colon between hour and minute columns (col 1 and 2)
    if colon_visible(t):
        # Position colon between columns 1 and 2
        colon_x = (positions[1][0][0] + positions[2][0][0]) // 2
        colon_y_center = GRID_CENTER[1]
        # Draw two dots vertically spaced
        colon_y1 = colon_y_center - COLON_SPACING // 2
        colon_y2 = colon_y_center + COLON_SPACING // 2
        draw_led(draw, colon_x, colon_y1, COLON_RADIUS, COLON_COLOR)
        draw_led(draw, colon_x, colon_y2, COLON_RADIUS, COLON_COLOR)

    return img


# ----------------------------
# Main: Write MP4
# ----------------------------
def main_mp4():
    positions = compute_grid_positions()
    source_lines = load_source_code()

    total_frames = DURATION_SEC * FPS
    writer = imageio.get_writer(OUTPUT_MP4, fps=FPS, codec="libx264", quality=8)

    try:
        for i in range(total_frames):
            t = i / FPS
            frame_img = render_frame(t, positions, source_lines)
            # Convert PIL Image to numpy array
            frame_arr = np.array(frame_img)
            writer.append_data(frame_arr)
    finally:
        writer.close()

    print(f"Saved: {OUTPUT_MP4}")


if __name__ == "__main__":
    main_mp4()
