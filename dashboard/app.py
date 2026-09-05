"""
Dashboard Backend - Flask server that provides API endpoints for the Cudy Router dashboard.
Uses CudyPy to communicate with the router.
"""

import os
import sys
from flask import Flask, render_template, jsonify, request

# Add parent directory to path to import cudypy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cudypy import CudyRouter

app = Flask(__name__)

# Router configuration - these would typically come from config
ROUTER_URL = os.environ.get("ROUTER_URL", "")
ROUTER_PASSWORD = os.environ.get("ROUTER_PASSWORD", "")
ROUTER_TOKEN = os.environ.get("ROUTER_TOKEN")

# Store router instance (in production, use session management)
router_instance = None


def get_router():
    """Get or create router instance."""
    global router_instance
    if not router_instance:
        if not (ROUTER_PASSWORD or ROUTER_TOKEN):
            raise ValueError("Set ROUTER_PASSWORD or ROUTER_TOKEN")
        router_instance = CudyRouter(ROUTER_URL, ROUTER_PASSWORD, auth_token=ROUTER_TOKEN)
    return router_instance


@app.before_request
def local_requests_only():
    """The example is a loopback UI, not a remotely accessible service."""
    if request.host not in {"localhost:5000", "127.0.0.1:5000"}:
        return jsonify({"error": "Use http://127.0.0.1:5000"}), 403
    origin = request.headers.get("Origin")
    if origin and origin != request.host_url.rstrip("/"):
        return jsonify({"error": "Cross-origin requests are not accepted"}), 403


@app.route("/")
def index():
    """Render the main dashboard page."""
    return render_template("index.html")


@app.route("/api/devices")
def get_devices():
    """Get all connected devices."""
    try:
        router = get_router()
        if not router.authenticate():
            return jsonify({"error": "Authentication failed"}), 401

        devices = router.get_devices()
        return jsonify(
            {
                "devices": [
                    {
                        "mac_address": d.mac_address,
                        "ip_address": d.ip_address,
                        "hostname": d.hostname,
                        "device_name": d.device_name,
                        "connection_type": d.connection_type,
                        "is_online": d.is_online,
                        "has_internet": d.has_internet,
                        "signal_strength": d.signal_strength,
                        "bandwidth_up": d.bandwidth_up,
                        "bandwidth_down": d.bandwidth_down,
                        "bytes_sent": d.bytes_sent,
                        "bytes_received": d.bytes_received,
                        "connection_time": d.connection_time,
                        "formatted_bandwidth_up": d.formatted_bandwidth_up,
                        "formatted_bandwidth_down": d.formatted_bandwidth_down,
                        "formatted_bytes_sent": d.formatted_bytes_sent,
                        "formatted_bytes_received": d.formatted_bytes_received,
                    }
                    for d in devices
                ]
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/devices/online")
def get_online_devices():
    """Get only online devices."""
    try:
        router = get_router()
        if not router.authenticate():
            return jsonify({"error": "Authentication failed"}), 401

        devices = router.get_online_devices()
        return jsonify(
            {
                "devices": [
                    {
                        "mac_address": d.mac_address,
                        "ip_address": d.ip_address,
                        "hostname": d.hostname,
                        "device_name": d.device_name,
                        "connection_type": d.connection_type,
                        "is_online": d.is_online,
                        "signal_strength": d.signal_strength,
                    }
                    for d in devices
                ]
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/devices/wifi")
def get_wifi_devices():
    """Get WiFi-connected devices."""
    try:
        router = get_router()
        if not router.authenticate():
            return jsonify({"error": "Authentication failed"}), 401

        devices = router.get_wifi_devices()
        return jsonify(
            {
                "devices": [
                    {
                        "mac_address": d.mac_address,
                        "ip_address": d.ip_address,
                        "hostname": d.hostname,
                        "device_name": d.device_name,
                        "signal_strength": d.signal_strength,
                        "is_online": d.is_online,
                    }
                    for d in devices
                ]
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/devices/ethernet")
def get_ethernet_devices():
    """Get Ethernet-connected devices."""
    try:
        router = get_router()
        if not router.authenticate():
            return jsonify({"error": "Authentication failed"}), 401

        devices = router.get_ethernet_devices()
        return jsonify(
            {
                "devices": [
                    {
                        "mac_address": d.mac_address,
                        "ip_address": d.ip_address,
                        "hostname": d.hostname,
                        "device_name": d.device_name,
                        "is_online": d.is_online,
                    }
                    for d in devices
                ]
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/system")
def get_system_info():
    """Get router system information."""
    try:
        router = get_router()
        if not router.authenticate():
            return jsonify({"error": "Authentication failed"}), 401

        info = router.get_system_info()
        return jsonify({"system": info.raw})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/network")
def get_network_status():
    """Get network interface status."""
    try:
        router = get_router()
        if not router.authenticate():
            return jsonify({"error": "Authentication failed"}), 401

        status = router.get_network_status()
        return jsonify({"network": status.raw})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def refresh_connection():
    """Force re-authentication and refresh data."""
    try:
        global router_instance
        if router_instance:
            router_instance.close()
            router_instance = None

        router = get_router()
        if not router.authenticate():
            return jsonify({"error": "Authentication failed"}), 401
        return jsonify({"status": "refreshed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/config", methods=["GET", "POST"])
def config():
    """Get or update router configuration."""
    if request.method == "POST":
        global ROUTER_URL, ROUTER_PASSWORD, ROUTER_TOKEN, router_instance

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        # Validate the complete replacement before closing the current client.
        url = data.get("url", ROUTER_URL)
        password = data.get("password") or ROUTER_PASSWORD
        token = ROUTER_TOKEN if url == ROUTER_URL else None
        if url != ROUTER_URL and not data.get("password"):
            return jsonify({"error": "A new router requires its own credentials"}), 400
        try:
            candidate = CudyRouter(url, password, auth_token=token)
            candidate.close()
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid router URL or credentials"}), 400
        if "url" in data:
            ROUTER_URL = data["url"]
        if "password" in data:
            ROUTER_PASSWORD = password
        ROUTER_TOKEN = token

        # Reset router instance to apply new config
        if router_instance:
            router_instance.close()
            router_instance = None

        return jsonify({"status": "updated"})

    return jsonify({"url": ROUTER_URL, "password": ""})  # Don't return actual password


if __name__ == "__main__":
    print(f"Starting Cudy Dashboard on http://localhost:5000")
    print(f"Router URL: {ROUTER_URL}")
    app.run(debug=False, host="127.0.0.1", port=5000, threaded=False)
