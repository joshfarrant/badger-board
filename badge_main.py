"""
Badge display receiver - copy this to your Badger2040 as main.py

This receives pre-rendered images from your Mac over serial,
so you can update the display design without reflashing the badge.
"""
import badger2040
import sys
import select
import binascii

# Display setup
display = badger2040.Badger2040()
display.set_update_speed(badger2040.UPDATE_FAST)

WIDTH = 296
HEIGHT = 128

# Full refresh counter to prevent ghosting
FULL_REFRESH_INTERVAL = 60
update_count = 0


def show_waiting_screen():
    """Show a waiting message on startup."""
    display.set_pen(15)  # White
    display.clear()
    display.set_pen(0)  # Black
    display.set_font("bitmap8")
    display.text("Waiting for data...", 10, 55, scale=2)
    display.update()


def display_image(img_bytes):
    """Display raw 1-bit image data on the screen."""
    global update_count

    display.set_pen(15)
    display.clear()
    display.set_pen(0)

    byte_idx = 0
    for y in range(HEIGHT):
        for x in range(0, WIDTH, 8):
            if byte_idx < len(img_bytes):
                byte = img_bytes[byte_idx]
                for bit in range(8):
                    px = x + bit
                    if px < WIDTH:
                        # Check if pixel is black (bit is 0)
                        if not (byte & (1 << (7 - bit))):
                            display.set_pen(0)
                            display.pixel(px, y)
                byte_idx += 1

    # Full refresh periodically to prevent ghosting
    update_count += 1
    if update_count >= FULL_REFRESH_INTERVAL:
        display.set_update_speed(badger2040.UPDATE_NORMAL)
        display.update()
        display.set_update_speed(badger2040.UPDATE_FAST)
        update_count = 0
    else:
        display.update()


# Show initial screen
show_waiting_screen()

# Buffer for incoming data
buffer = ""

print("Badge ready - listening for images...")

while True:
    if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
        char = sys.stdin.read(1)
        if char == "\n":
            line = buffer.strip()
            buffer = ""

            if line.startswith("IMG:"):
                try:
                    # Decode base64 image data
                    encoded_data = line[4:]
                    img_bytes = binascii.a2b_base64(encoded_data)
                    display_image(img_bytes)
                    print("Image displayed")
                except Exception as e:
                    print(f"Error: {e}")

            # Keep backward compatibility with text-only mode
            elif line.startswith("CO2:"):
                co2_level = line.split(":")[1]
                display.set_pen(15)
                display.clear()
                display.set_pen(0)
                display.set_font("bitmap8")
                display.text("Room CO2 Level", 10, 10, scale=2)
                display.text(co2_level, 30, 50, scale=4)
                display.text("ppm", 30, 90, scale=2)
                display.update()
        else:
            buffer += char
