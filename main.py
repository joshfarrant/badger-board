import base64
import os
import serial
import time

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

# Debug settings
DEBUG_BORDERS = False  # Set to False to hide cell borders
DEBUG_FAST_REFRESH = False  # Set to True for 10-second refresh instead of per-minute

# Display settings
DISPLAY_CONFIG = {
    "width": 296,
    "height": 128,
    "cols": 2,
    "rows": 4,
    "icon_size": 24,  # Icons will be resized to this
    "fonts": {
        "text": {"path": "./fonts/Minecraftia-12.ttf", "size": 24},
    },
}

# Cell definitions: each cell has position, sensor key, icon, formatting, and thresholds
# Thresholds: [warning_threshold, danger_threshold] or None for no warnings
# icon_y_offset: fine-tune vertical icon position (positive = down, negative = up)
ICONS_DIR = "./icons/PNG/for-light-mode/24px/solid"
ICONS_DIR_DARK = "./icons/PNG/for-dark-mode/24px/solid"
GRID_CONFIG = [
    # Row 0
    {"row": 0, "col": 0, "sensor": "co2", "icon": "seedlings.png", "format": "int", "thresholds": [1000, 2000]},
    {"row": 0, "col": 1, "sensor": "co", "icon": "fire.png", "format": "1f", "thresholds": [10, 35]},
    # Row 1
    {"row": 1, "col": 0, "sensor": "pm25", "icon": "sparkles.png", "format": "1f", "thresholds": [12, 35]},
    {"row": 1, "col": 1, "sensor": "humidity", "icon": "cloud-download.png", "format": "0f", "suffix": "%", "thresholds": None},
    # Row 2
    {"row": 2, "col": 0, "sensor": "outside_temp", "icon": "sun.png", "format": "1f", "suffix": "°C", "thresholds": None},
    {"row": 2, "col": 1, "sensor": "temperature", "icon": "home.png", "format": "1f", "suffix": "°C", "thresholds": None},
    # Row 3
    {"row": 3, "col": 0, "sensor": "time", "icon": "clock.png", "format": "raw", "thresholds": None},
    {"row": 3, "col": 1, "sensor": "date", "icon": "calender.png", "format": "raw", "thresholds": None},
]

# Sensor entity mappings
SENSOR_ENTITIES = {
    "co2": os.getenv("CO2_ENTITY"),
    "co": os.getenv("CO_ENTITY"),
    "temperature": os.getenv("TEMP_ENTITY"),
    "pm25": os.getenv("PM25_ENTITY"),
    "humidity": os.getenv("HUMIDITY_ENTITY"),
}

# Weather entity (temperature fetched from attributes)
WEATHER_ENTITY = os.getenv("WEATHER_ENTITY")

# Home Assistant configuration
HA_URL = os.getenv("HA_URL")
HA_TOKEN = os.getenv("HA_TOKEN")
BADGE_PORT = os.getenv("BADGE_PORT", "/dev/tty.usbmodem1101")

# =============================================================================
# SENSOR FETCHING
# =============================================================================

headers = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json",
}


def get_sensor_value(entity_id):
    """Fetch a sensor value from Home Assistant."""
    if not entity_id:
        return "ERR"
    try:
        url = f"{HA_URL}/api/states/{entity_id}"
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data["state"]
    except Exception as e:
        print(f"Error fetching {entity_id}: {e}")
        return "ERR"


def get_weather_temperature():
    """Fetch temperature from weather entity attributes."""
    if not WEATHER_ENTITY:
        return "ERR"
    try:
        url = f"{HA_URL}/api/states/{WEATHER_ENTITY}"
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data["attributes"].get("temperature", "ERR")
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return "ERR"


def fetch_all_sensors():
    """Fetch all configured sensor values."""
    from datetime import datetime

    sensor_data = {}
    for key, entity in SENSOR_ENTITIES.items():
        sensor_data[key] = get_sensor_value(entity)

    # Fetch outside temperature from weather entity
    sensor_data["outside_temp"] = get_weather_temperature()

    # Add local time and date
    now = datetime.now()
    sensor_data["time"] = now.strftime("%H:%M")
    sensor_data["date"] = now.strftime("%d/%m")

    return sensor_data


# =============================================================================
# DISPLAY RENDERING
# =============================================================================

# Icon cache to avoid reloading
_icon_cache = {}


def load_icon(icon_name, size, invert=False):
    """Load and resize an icon, using dark mode icons when inverted."""
    cache_key = (icon_name, size, invert)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    # Use dark mode icons for inverted (danger) state
    icons_dir = ICONS_DIR_DARK if invert else ICONS_DIR
    icon_path = os.path.join(icons_dir, icon_name)
    try:
        icon = Image.open(icon_path).convert("RGBA")

        # Resize preserving aspect ratio to fit within size x size (scales up or down)
        orig_w, orig_h = icon.size
        scale = min(size / orig_w, size / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        icon = icon.resize((new_w, new_h), Image.Resampling.NEAREST)

        # Convert to 1-bit with transparency handling
        # Create a black background for inverted, white for normal
        bg_color = 0 if invert else 255
        bg = Image.new("L", icon.size, bg_color)

        # Get alpha channel and image data
        alpha = icon.split()[3]
        gray = icon.convert("L")

        # Composite onto background using alpha
        bg.paste(gray, mask=alpha)

        # Convert to 1-bit
        result = bg.point(lambda x: 0 if x < 128 else 255, mode="1")

        _icon_cache[cache_key] = result
        return result
    except Exception as e:
        print(f"Error loading icon {icon_name}: {e}")
        return None


def get_warning_level(value, thresholds):
    """Return warning level: 0=none, 1=warning, 2=danger."""
    if not thresholds:
        return 0
    try:
        val = float(value)
        if val >= thresholds[1]:
            return 2  # danger
        elif val >= thresholds[0]:
            return 1  # warning
    except (ValueError, TypeError):
        pass
    return 0


def format_value(value, fmt, suffix=""):
    """Format a sensor value for display."""
    if fmt == "raw":
        return f"{value}{suffix}"
    try:
        val = float(value)
        if fmt == "int":
            return f"{int(val)}{suffix}"
        elif fmt == "0f":
            return f"{val:.0f}{suffix}"
        elif fmt == "1f":
            return f"{val:.1f}{suffix}"
        else:
            return f"{val}{suffix}"
    except (ValueError, TypeError):
        return f"{value}{suffix}"


def draw_cell(draw, img, cell_config, sensor_data, cell_width, cell_height, text_font, debug_borders=False):
    """Draw a single cell in the grid."""
    col = cell_config["col"]
    row = cell_config["row"]

    # Calculate cell position - cells fill their full space with no gaps
    x = col * cell_width
    y = row * cell_height
    w = cell_width
    h = cell_height

    # Draw debug border if enabled
    if debug_borders:
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=0, width=1)

    if not cell_config.get("sensor"):
        return  # blank cell

    # Get sensor value and warning level
    sensor_key = cell_config["sensor"]
    value = sensor_data.get(sensor_key, "---")
    thresholds = cell_config.get("thresholds")
    warning_level = get_warning_level(value, thresholds)

    # Determine colors based on warning level
    # 0 = normal (black on white), 1 = warning (border), 2 = danger (inverted)
    invert = warning_level == 2
    if invert:
        fg_color = 1  # white foreground
        # Fill cell with black
        draw.rectangle([x, y, x + w, y + h], fill=0)
    else:
        fg_color = 0  # black foreground

    # Draw border for warning level
    if warning_level == 1:
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=0, width=2)

    # Format the value
    suffix = cell_config.get("suffix", "")
    formatted_value = format_value(value, cell_config.get("format", "1f"), suffix)

    # Load and draw icon
    icon_name = cell_config.get("icon", "")
    icon_size = DISPLAY_CONFIG["icon_size"]
    icon_y_offset = cell_config.get("icon_y_offset", 0)

    if icon_name:
        icon = load_icon(icon_name, icon_size, invert=invert)
        if icon:
            icon_x = x + 4
            icon_y = y + (h - icon_size) // 2 + icon_y_offset
            img.paste(icon, (icon_x, icon_y))

    # Draw text
    text_x = x + icon_size + 12
    text_y = y

    draw.text((text_x, text_y), formatted_value, font=text_font, fill=fg_color)


def generate_display_image(sensor_data):
    """Generate a 1-bit image for the Badger2040 display."""
    width = DISPLAY_CONFIG["width"]
    height = DISPLAY_CONFIG["height"]
    cols = DISPLAY_CONFIG["cols"]
    rows = DISPLAY_CONFIG["rows"]

    # Create white background image
    img = Image.new("1", (width, height), 1)
    draw = ImageDraw.Draw(img)

    # Load font
    font_cfg = DISPLAY_CONFIG["fonts"]
    try:
        text_font = ImageFont.truetype(font_cfg["text"]["path"], font_cfg["text"]["size"])
    except OSError:
        text_font = ImageFont.load_default()

    # Calculate cell dimensions
    cell_width = width // cols
    cell_height = height // rows

    # Draw each cell
    for cell_config in GRID_CONFIG:
        draw_cell(draw, img, cell_config, sensor_data, cell_width, cell_height, text_font, debug_borders=DEBUG_BORDERS)

    return img


# =============================================================================
# BADGE COMMUNICATION
# =============================================================================

def image_to_badge_bytes(img):
    """Convert PIL image to packed bytes for Badger2040."""
    img = img.convert("1")
    pixels = list(img.get_flattened_data())
    byte_data = bytearray()
    width = DISPLAY_CONFIG["width"]
    height = DISPLAY_CONFIG["height"]

    for y in range(height):
        for x in range(0, width, 8):
            byte = 0
            for bit in range(8):
                px = x + bit
                if px < width:
                    if pixels[y * width + px]:
                        byte |= 1 << (7 - bit)
            byte_data.append(byte)

    return bytes(byte_data)


def send_image_to_badge(ser, img):
    """Send image to badge over serial."""
    img_bytes = image_to_badge_bytes(img)
    encoded = base64.b64encode(img_bytes).decode("ascii")
    ser.write(b"IMG:")
    ser.write(encoded.encode("ascii"))
    ser.write(b"\n")
    ser.flush()


# =============================================================================
# MAIN
# =============================================================================

# Connect to badge
try:
    ser = serial.Serial(BADGE_PORT, 115200, timeout=1)
    time.sleep(2)
except Exception as e:
    print(f"Error connecting to badge: {e}")
    print("Make sure Thonny is closed and badge is connected!")
    exit(1)

print("Sensor Monitor started. Press Ctrl+C to stop.")

def wait_for_next_minute():
    """Sleep until the start of the next minute."""
    now = time.time()
    seconds_until_next_minute = 60 - (now % 60)
    time.sleep(seconds_until_next_minute)

try:
    while True:
        sensor_data = fetch_all_sensors()
        print(f"[{sensor_data['time']}] CO2: {sensor_data['co2']}, CO: {sensor_data['co']}, PM2.5: {sensor_data['pm25']}, "
              f"Temp: {sensor_data['temperature']}°C, Humidity: {sensor_data['humidity']}%, Outside: {sensor_data['outside_temp']}°C")

        img = generate_display_image(sensor_data)
        send_image_to_badge(ser, img)

        if DEBUG_FAST_REFRESH:
            time.sleep(10)
        else:
            wait_for_next_minute()

except KeyboardInterrupt:
    print("\nStopping sensor monitor...")
    ser.close()
