# Badger Board

A Home Assistant sensor dashboard for the [Pimoroni Badger 2040](https://shop.pimoroni.com/products/badger-2040) e-ink display.

![A GitHub Universe 2024 badge showing a grid of numbers each identified with an icon](./image.jpeg)

## Overview

Badger Board fetches sensor data from Home Assistant and displays it on a Badger 2040 badge. The display shows:

- **CO₂ levels** - with warning/danger thresholds
- **Carbon monoxide** - with warning/danger thresholds
- **PM2.5 air quality** - with warning/danger thresholds
- **Indoor temperature**
- **Outdoor temperature** (from weather entity)
- **Humidity**
- **Current time and date**

The display updates every minute and uses visual indicators for sensor warnings:
- **Border** - warning threshold exceeded
- **Inverted colors** - danger threshold exceeded

## Requirements

- Python 3.x
- Pimoroni Badger 2040
- Home Assistant instance with sensor entities

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/joshfarrant/badger-board.git
   cd badger-board
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install requests python-dotenv pillow pyserial
   ```

4. Copy the example environment file and configure:
   ```bash
   cp .env.example .env
   ```

5. Edit `.env` with your Home Assistant details and sensor entity IDs.

## Setup

### Badge Setup

Copy `badge_main.py` to your Badger 2040 as `main.py`. This acts as the receiver that displays images sent over serial.

### Host Setup

Run the sensor monitor on your computer:
```bash
python main.py
```

The script will:
1. Connect to the badge over serial
2. Fetch sensor data from Home Assistant
3. Generate and send a display image every minute

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `HA_URL` | Home Assistant URL (e.g., `http://192.168.1.100:8123`) |
| `HA_TOKEN` | Home Assistant long-lived access token |
| `CO2_ENTITY` | Entity ID for CO₂ sensor |
| `CO_ENTITY` | Entity ID for carbon monoxide sensor |
| `TEMP_ENTITY` | Entity ID for indoor temperature sensor |
| `PM25_ENTITY` | Entity ID for PM2.5 sensor |
| `HUMIDITY_ENTITY` | Entity ID for humidity sensor |
| `WEATHER_ENTITY` | Entity ID for weather (outdoor temp) |
| `BADGE_PORT` | Serial port for badge (default: `/dev/tty.usbmodem1101`) |

### Warning Thresholds

Default thresholds can be modified in `main.py`:

| Sensor | Warning | Danger |
|--------|---------|--------|
| CO₂ | 1000 ppm | 2000 ppm |
| CO | 10 ppm | 35 ppm |
| PM2.5 | 12 µg/m³ | 35 µg/m³ |

## License

MIT
