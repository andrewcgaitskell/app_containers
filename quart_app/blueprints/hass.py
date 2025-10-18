import os
import json
import logging
from typing import Tuple, Any
import aiohttp
from quart import Blueprint, current_app, jsonify, request, Response

hass_bp = Blueprint("hass", __name__)

# Read defaults from environment; blueprint will use current_app.http_session for requests.
HASS_URL = os.environ.get("HASS_URL", "http://homeassistant.local:8123")
HASS_TOKEN = os.environ.get("HASS_TOKEN")  # required at runtime

def _hass_headers() -> dict:
    if not HASS_TOKEN:
        # Raise a RuntimeError so the route returns a 500 with a clear message
        raise RuntimeError("HASS_TOKEN environment variable is not set")
    return {
        "Authorization": f"Bearer {HASS_TOKEN}",
        "Content-Type": "application/json",
    }

async def call_hass_service(domain: str, service: str, service_data: dict) -> Tuple[int, Any]:
    """Call Home Assistant service (async) using the application's shared aiohttp session."""
    url = f"{HASS_URL.rstrip('/')}/api/services/{domain}/{service}"
    headers = _hass_headers()
    logging.info("Calling HA service %s.%s with data %s", domain, service, service_data)
    session: aiohttp.ClientSession = current_app.http_session
    async with session.post(url, headers=headers, json=service_data) as resp:
        text = await resp.text()
        # try to parse JSON for nicer responses when possible
        try:
            return resp.status, json.loads(text) if text else {}
        except Exception:
            return resp.status, text

async def get_entity_state(entity_id: str) -> Tuple[int, Any]:
    """Get entity state from Home Assistant."""
    url = f"{HASS_URL.rstrip('/')}/api/states/{entity_id}"
    headers = _hass_headers()
    session: aiohttp.ClientSession = current_app.http_session
    async with session.get(url, headers=headers) as resp:
        text = await resp.text()
        if resp.status == 200:
            try:
                return 200, json.loads(text)
            except Exception:
                return 200, text
        return resp.status, text

# -----------------------------
# Routes: light control endpoints
# -----------------------------
@hass_bp.route("/api/light/<path:entity_id>/set", methods=["POST"])
async def set_light(entity_id):
    """
    Set a light state. JSON payload: {"state": "on"} or {"state": "off"}
    Optionally include brightness (0-255), rgb_color, color_temp, transition, etc.
    """
    try:
        data = await request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid json"}), 400

    if not data or "state" not in data:
        return jsonify({"error": "missing 'state' in payload"}), 400

    state = data.get("state").lower()
    service_data = {"entity_id": entity_id}

    # Include optional service data (brightness, rgb_color, etc.)
    for optional in ("brightness", "rgb_color", "color_temp", "transition"):
        if optional in data:
            service_data[optional] = data[optional]

    try:
        if state == "on":
            status, result = await call_hass_service("light", "turn_on", service_data)
        elif state == "off":
            status, result = await call_hass_service("light", "turn_off", service_data)
        else:
            return jsonify({"error": "state must be 'on' or 'off'"}), 400
    except RuntimeError as e:
        # HASS_TOKEN missing
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.exception("Error calling Home Assistant")
        return jsonify({"error": "failed to call Home Assistant", "details": str(e)}), 500

    return jsonify(result), status

@hass_bp.route("/api/light/<path:entity_id>/toggle", methods=["POST"])
async def toggle_light(entity_id):
    """Toggle the light"""
    try:
        status, result = await call_hass_service("light", "toggle", {"entity_id": entity_id})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.exception("Error toggling light")
        return jsonify({"error": "failed to call Home Assistant", "details": str(e)}), 500
    return jsonify(result), status

@hass_bp.route("/api/light/<path:entity_id>/get_state", methods=["GET"])
async def api_get_state(entity_id):
    try:
        status, result = await get_entity_state(entity_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.exception("Error fetching state")
        return jsonify({"error": "failed to call Home Assistant", "details": str(e)}), 500

    if status == 200:
        return jsonify(result)
    return Response(result if isinstance(result, str) else json.dumps(result), status=status, content_type="application/json")

@hass_bp.route("/ui/light/<path:entity_id>")
async def light_ui(entity_id):
    """
    Simple HTML UI with a checkbox switch to turn the entity on/off.
    This is intentionally minimal and uses fetch to call our endpoints above.
    """
    html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8"/>
        <title>Light Switch - {entity_id}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 2rem; }}
          .switch {{ display:flex; align-items:center; gap:1rem; }}
        </style>
      </head>
      <body>
        <h1>Light: {entity_id}</h1>
        <div class="switch">
          <label>
            <input id="toggle" type="checkbox"/>
            <span id="label">Loading...</span>
          </label>
        </div>
        <script>
          const entity = "{entity_id}";
          async function fetchState() {{
            const resp = await fetch(`/api/light/${{encodeURIComponent(entity)}}/get_state`);
            if (!resp.ok) return null;
            return await resp.json();
          }}
          async function setState(state) {{
            const resp = await fetch(`/api/light/${{encodeURIComponent(entity)}}/set`, {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: JSON.stringify({{ state }})
            }});
            return resp.ok;
          }}
          document.getElementById('toggle').addEventListener('change', async function(e) {{
            const want = e.target.checked ? "on" : "off";
            const ok = await setState(want);
            if (!ok) {{
              alert("Failed to set state");
              // revert checkbox
              e.target.checked = !e.target.checked;
            }} else {{
              document.getElementById('label').textContent = want.toUpperCase();
            }}
          }});
          // initialize
          (async () => {{
            try {{
              const st = await fetchState();
              if (st && st.state) {{
                document.getElementById('toggle').checked = (st.state === "on");
                document.getElementById('label').textContent = st.state.toUpperCase();
              }} else {{
                document.getElementById('label').textContent = "unknown";
              }}
            }} catch (err) {{
              document.getElementById('label').textContent = "error";
            }}
          }})();
        </script>
      </body>
    </html>
    """
    return Response(html, content_type="text/html")
