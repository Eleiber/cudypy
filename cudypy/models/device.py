"""Device model for representing connected devices on the router."""

from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
import logging


@dataclass
class Device:
    """Represents a device connected to the router."""

    mac_address: str
    ip_address: str
    hostname: Optional[str] = None
    device_name: Optional[str] = None
    connection_type: Optional[str] = None  # 'wifi' or 'ethernet'
    connected_since: Optional[datetime] = None
    signal_strength: Optional[int] = None  # in dBm, for WiFi devices
    bandwidth_up: Optional[int] = None  # bytes/s, matching APK speed display conversion
    bandwidth_down: Optional[int] = None  # bytes/s
    is_online: Optional[bool] = None  # Legacy name: inactivity heuristic, not reachability
    has_internet: bool = True
    is_vpn: bool = False
    interface: Optional[str] = None  # Raw interface name (e.g., 'rax0', 'eth0')
    raw_iface: Optional[str] = None  # Raw iface field from API
    bytes_received: Optional[int] = None  # Legacy alias for inbytes; viewpoint unverified
    bytes_sent: Optional[int] = None  # Legacy alias for outbytes; viewpoint unverified
    inactive_time: Optional[int] = None  # Reported inactivity; unit not independently verified
    reported_online_seconds: Optional[int] = None
    reported_upbytes: Optional[int] = None
    reported_downbytes: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Device":
        """Create a Device instance from API response data.

        Args:
            data: Dictionary containing device information from the router API.
                  Expected fields include: mac, ip, hostname, interface, etc.

        Returns:
            Device object populated with data from the API response

        Raises:
            TypeError: If data is not a dictionary
            ValueError: If required fields (mac, ip) are missing
        """
        if not isinstance(data, dict):
            raise TypeError(
                f"Device data must be a dictionary, got {type(data).__name__}. "
                f"This indicates an unexpected API response format."
            )

        # Handle dict response
        try:
            # Extract numeric values safely
            def safe_int(value: Any) -> Optional[int]:
                try:
                    return int(value) if value is not None else None
                except (ValueError, TypeError, OverflowError):
                    return None

            def nonnegative_int(value: Any) -> Optional[int]:
                if isinstance(value, bool) or not isinstance(value, (int, str)):
                    return None
                result = safe_int(value)
                return result if result is not None and result >= 0 else None

            # The app formats this field as elapsed seconds.
            # The timestamp is an estimate, not a router-provided wall clock.
            online_seconds = nonnegative_int(data.get("online"))
            connected_since = None
            if online_seconds is not None:
                try:
                    connected_since = datetime.now() - timedelta(seconds=online_seconds)
                except OverflowError:
                    pass

            def safe_bool(value: Any, default: bool) -> bool:
                if value is None:
                    return default
                if isinstance(value, str):
                    return value.strip().lower() in ("1", "true", "yes", "on")
                return bool(value)

            # Determine connection type from interface
            interface = str(data.get("interface") or "").lower()
            iface = str(data.get("iface") or "").lower()

            # WiFi interfaces can be:
            # - interface: "rax0" with iface: "wlan10"
            # - interface: "ra0" with iface: "wlan00"
            # Ethernet interfaces are:
            # - interface: "eth0" with iface: "eth"

            # Check both interface and iface fields for WiFi indicators
            is_wifi = interface.startswith(("ra", "wlan", "wl", "ath")) or iface.startswith("wlan")

            # Check both interface and iface fields for Ethernet indicators
            is_ethernet = interface.startswith("eth") or iface == "eth"

            connection_type = "wifi" if is_wifi else "ethernet" if is_ethernet else None

            # Legacy activity heuristic only. Missing/invalid values are unknown,
            # not evidence of either reachability or disconnection.
            inactive_time = nonnegative_int(data.get("inactive"))
            is_online = inactive_time < 30 if inactive_time is not None else None

            # APK converts these byte rates to bit rates by multiplying by eight.
            bandwidth_up = nonnegative_int(data.get("upspeed"))
            bandwidth_down = nonnegative_int(data.get("downspeed"))
            signal = safe_int(data.get("signal"))
            if signal is None:
                rssi = safe_int(data.get("rssi"))
                signal = rssi - 100 if rssi is not None else None

            # Get total bytes transferred
            bytes_received = nonnegative_int(data.get("inbytes"))
            bytes_sent = nonnegative_int(data.get("outbytes"))

            # Validate required fields
            mac_address = str(data.get("macaddr") or data.get("mac") or "").lower() or "unknown"
            ip_address = str(data.get("ipaddr") or data.get("ip") or "") or "unknown"

            if mac_address == "unknown" and ip_address == "unknown":
                logging.warning("Device missing both MAC and IP address")

            return cls(
                mac_address=mac_address,
                ip_address=ip_address,
                hostname=str(data.get("hostname", "")) if data.get("hostname") else None,
                device_name=str(data.get("name", "")) if data.get("name") else None,
                connection_type=connection_type,
                connected_since=connected_since,
                signal_strength=signal,
                bandwidth_up=bandwidth_up,
                bandwidth_down=bandwidth_down,
                is_online=is_online,
                has_internet=safe_bool(data.get("internet"), True),
                is_vpn=safe_bool(data.get("vpn"), False),
                interface=interface if interface else None,
                raw_iface=iface if iface else None,
                bytes_received=bytes_received,
                bytes_sent=bytes_sent,
                inactive_time=inactive_time,
                reported_online_seconds=online_seconds,
                reported_upbytes=nonnegative_int(data.get("upbytes")),
                reported_downbytes=nonnegative_int(data.get("downbytes")),
                raw=dict(data),
            )
        except (TypeError, ValueError):
            raise
        except Exception as e:
            # Log the error but try to create a minimal device
            logging.error(f"Error parsing device data: {e}", exc_info=True)
            mac = str(data.get("mac", "unknown")).lower()
            ip = str(data.get("ip", "unknown"))
            raise ValueError(f"Failed to parse device data for MAC={mac}, IP={ip}: {e}") from e

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        name = self.device_name or self.hostname or self.mac_address
        return f"{name} ({self.ip_address})"

    @property
    def recently_active(self) -> Optional[bool]:
        """Whether reported inactivity is below 30; None when unknown.

        This names the legacy is_online heuristic accurately. It is not a ping
        result or evidence of Internet reachability.
        """
        return self.is_online

    @property
    def reported_inbytes(self) -> Optional[int]:
        """Native inbytes counter; direction and reset interval unverified."""
        return self.bytes_received

    @property
    def reported_outbytes(self) -> Optional[int]:
        """Native outbytes counter; direction and reset interval unverified."""
        return self.bytes_sent

    @property
    def connection_time(self) -> Optional[str]:
        """Get a human-readable connection time.

        Returns:
            Formatted string like "2d 5h 30m" or "Just connected" if recently connected,
            None if connection time is unknown
        """
        if not self.connected_since:
            return None

        delta = datetime.now() - self.connected_since
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")

        return " ".join(parts) if parts else "Just connected"

    @property
    def formatted_bandwidth_up(self) -> Optional[str]:
        """Get human-readable upload bandwidth.

        Returns:
            Formatted byte rate like "512.0 B/s" or "1.5 MiB/s", or None
        """
        if self.bandwidth_up is None:
            return None
        return self._format_rate(self.bandwidth_up)

    @property
    def formatted_bandwidth_down(self) -> Optional[str]:
        """Get human-readable download bandwidth.

        Returns:
            Formatted byte rate like "2.0 KiB/s" or "3.5 MiB/s", or None
        """
        if self.bandwidth_down is None:
            return None
        return self._format_rate(self.bandwidth_down)

    @staticmethod
    def _format_rate(value: int) -> str:
        rate = float(value)
        for unit in ("B/s", "KiB/s", "MiB/s", "GiB/s"):
            if abs(rate) < 1024 or unit == "GiB/s":
                return f"{rate:.1f} {unit}"
            rate /= 1024

    def _format_bytes(self, bytes_value: Optional[float]) -> Optional[str]:
        """Format bytes into human-readable string.

        Args:
            bytes_value: Number of bytes to format

        Returns:
            Formatted string like "1.5 MB" or "2.3 GB", None if bytes_value is None
        """
        if bytes_value is None:
            return None

        bytes_value = float(bytes_value)  # Convert to float to avoid modifying the original
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} TB"

    @property
    def formatted_bytes_received(self) -> Optional[str]:
        """Get human-readable total bytes received.

        Returns:
            Formatted string like "150.5 MB", None if not available
        """
        return self._format_bytes(self.bytes_received)

    @property
    def formatted_bytes_sent(self) -> Optional[str]:
        """Get human-readable total bytes sent.

        Returns:
            Formatted string like "45.2 MB", None if not available
        """
        return self._format_bytes(self.bytes_sent)
