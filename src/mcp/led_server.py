"""MCP server that exposes LED strip control as tools for the LLM."""

import httpx
from mcp.server.fastmcp import FastMCP

LED_API_BASE = "http://localhost:8000"

# Note: this LED strip renders red weak, so colors are compensated
# with extra red to match the intended appearance.
MOODS: dict[str, dict] = {
    "cinema": {
        "description": "Dim warm light for watching movies",
        "color": {"r": 60, "g": 15, "b": 0},
        "brightness": 15,
    },
    "romantic": {
        "description": "Soft warm red ambient light",
        "color": {"r": 255, "g": 20, "b": 10},
        "brightness": 25,
    },
    "relax": {
        "description": "Calm soft blue-white light",
        "color": {"r": 100, "g": 90, "b": 160},
        "brightness": 30,
    },
    "party": {
        "description": "Colorful cycling party effect",
        "effect": 10,
        "brightness": 90,
    },
    "boca_juniors": {
        "description": "Dale Boca! Blue and gold celebration effect",
        "effect": 52,
        "brightness": 100,
    },
    "reading": {
        "description": "Bright neutral white for reading",
        "color": {"r": 255, "g": 220, "b": 200},
        "brightness": 80,
    },
    "night": {
        "description": "Very dim warm light as a nightlight",
        "color": {"r": 60, "g": 8, "b": 0},
        "brightness": 5,
    },
    "energetic": {
        "description": "Bright cool white to boost energy",
        "color": {"r": 220, "g": 210, "b": 255},
        "brightness": 95,
    },
    "music": {
        "description": "Audio-reactive mode — LEDs dance to the music",
        "audio": True,
    },
}

mcp = FastMCP("led-control")


def _api(method: str, endpoint: str, **kwargs: dict) -> str:
    """Make an HTTP request to the LED API."""
    try:
        resp = httpx.request(method, f"{LED_API_BASE}{endpoint}", **kwargs)
        resp.raise_for_status()
        return resp.text
    except httpx.ConnectError:
        return "Error: LED API is not reachable. Is the server running?"
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code} - {e.response.text}"


@mcp.tool()
def set_room_mood(mood: str) -> str:
    """Set the room lighting to a predefined mood.

    Use this to match the room ambiance to the conversation vibe.
    Available moods: cinema, romantic, relax, party, boca_juniors, reading, night, energetic, music.

    - cinema: dim warm light for watching movies
    - romantic: soft warm red ambient light
    - relax: calm soft blue-white light
    - party: colorful cycling party effect
    - boca_juniors: Dale Boca! Blue and gold celebration (effect 52)
    - reading: bright neutral white for reading
    - night: very dim warm nightlight
    - energetic: bright cool white to boost energy
    - music: audio-reactive mode, LEDs dance to whatever is playing
    """
    mood = mood.lower().strip()
    if mood not in MOODS:
        available = ", ".join(MOODS.keys())
        return f"Unknown mood '{mood}'. Available: {available}"

    cfg = MOODS[mood]
    results = []

    # Stop audio-reactive mode when switching to a non-audio mood
    if not cfg.get("audio"):
        _api("POST", "/audio/stop")

    _api("POST", "/on")

    if cfg.get("audio"):
        results.append(_api("POST", "/audio/start"))
    else:
        if "brightness" in cfg:
            results.append(_api("POST", "/brightness", json={"percent": cfg["brightness"]}))
        if "effect" in cfg:
            results.append(_api("POST", "/effect", json={"index": cfg["effect"]}))
        elif "color" in cfg:
            results.append(_api("POST", "/color", json=cfg["color"]))

    if any("Error" in r for r in results):
        return f"Mood '{mood}' partially applied. Issues: {'; '.join(results)}"
    return f"Room mood set to '{mood}': {cfg['description']}"


@mcp.tool()
def set_led_color(r: int, g: int, b: int, brightness: int = 80) -> str:
    """Set the LED strip to a specific RGB color.

    Use this for custom colors that don't match a predefined mood.
    IMPORTANT: This LED strip renders red weaker than expected. Boost the
    red channel significantly to compensate. For example, orange should be
    around (255, 80, 0) not (255, 165, 0), and warm white needs R=255.

    Args:
        r: Red channel (0-255) — push higher than usual to compensate
        g: Green channel (0-255)
        b: Blue channel (0-255)
        brightness: Brightness percentage (0-100), defaults to 80
    """
    _api("POST", "/audio/stop")
    _api("POST", "/on")
    _api("POST", "/brightness", json={"percent": brightness})
    result = _api("POST", "/color", json={"r": r, "g": g, "b": b})
    if "Error" in result:
        return result
    return f"LED color set to RGB({r}, {g}, {b}) at {brightness}% brightness"


@mcp.tool()
def turn_off_lights() -> str:
    """Turn off the LED strip."""
    result = _api("POST", "/off")
    if "Error" in result:
        return result
    return "Lights turned off"


if __name__ == "__main__":
    mcp.run()
