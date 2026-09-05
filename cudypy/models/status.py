"""Status/configuration models that preserve firmware-specific source fields."""

from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple


def _integer(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Expected an integer")
    result = int(value)
    if result < 0:
        raise ValueError("Expected a nonnegative integer")
    return result


def _boolean(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.lower() in ("0", "1", "true", "false"):
        return value.lower() in ("1", "true")
    raise ValueError("Expected a boolean")


def _text(value: Any) -> Optional[str]:
    if value is not None and not isinstance(value, str):
        raise ValueError("Expected text")
    return value


@dataclass
class ResourceUsage:
    """Reported resource counters in native firmware units, without conversion.

    Memory, swap and filesystem counters need not use the same unit.
    Missing counters are not calculated from the other fields.
    """

    total: Optional[int] = None
    used: Optional[int] = None
    free: Optional[int] = None
    available: Optional[int] = None
    shared: Optional[int] = None
    cached: Optional[int] = None
    buffered: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "ResourceUsage":
        if not isinstance(data, dict):
            raise ValueError("Resource usage must be an object")
        return cls(
            total=_integer(data.get("total")),
            used=_integer(data.get("used")),
            free=_integer(data.get("free")),
            available=_integer(data.get("available", data.get("avail"))),
            shared=_integer(data.get("shared")),
            cached=_integer(data.get("cached")),
            buffered=_integer(data.get("buffered")),
            raw=deepcopy(data),
        )


@dataclass
class SystemStatus:
    """Selected system observations; missing model names are not inferred."""

    model: Optional[str]
    firmware: Optional[str]
    board_name: Optional[str]
    uptime_seconds: Optional[int]
    raw: Dict[str, Any] = field(repr=False, compare=False)
    memory: Optional[ResourceUsage] = None
    swap: Optional[ResourceUsage] = None
    root: Optional[ResourceUsage] = None
    tmp: Optional[ResourceUsage] = None
    cpu_usage: Optional[int] = None
    load: Optional[Tuple[int, ...]] = None
    processor: Optional[str] = None
    revision: Optional[str] = None
    rom: Optional[str] = None
    country: Optional[str] = None
    device_type: Optional[str] = None
    serial_number: Optional[str] = field(default=None, repr=False)
    mac_address: Optional[str] = field(default=None, repr=False)
    lan_ip: Optional[str] = field(default=None, repr=False)
    timestamp: Optional[int] = None
    localtime: Optional[int] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "SystemStatus":
        if not isinstance(data, dict):
            raise ValueError("System status must be an object")
        resources = {
            key: ResourceUsage.from_api_response(data[key]) if data.get(key) is not None else None
            for key in ("memory", "swap", "root", "tmp")
        }
        load = data.get("load")
        if load is not None:
            if not isinstance(load, list) or any(value is None for value in load):
                raise ValueError("System load must be an array of nonnegative integers")
            load = tuple(_integer(value) for value in load)
        return cls(
            _text(data.get("model")),
            _text(data.get("firmware")),
            _text(data.get("board_name")),
            _integer(data.get("uptime")),
            deepcopy(data),
            **resources,
            cpu_usage=_integer(data.get("cpu_usage")),
            load=load,
            processor=_text(data.get("processor")),
            revision=_text(data.get("revision")),
            rom=_text(data.get("rom")),
            country=_text(data.get("country")),
            device_type=_text(data.get("type")),
            serial_number=_text(data.get("sn")),
            mac_address=_text(data.get("macaddr")),
            lan_ip=_text(data.get("lan_ip")),
            timestamp=_integer(data.get("timestamp")),
            localtime=_integer(data.get("localtime")),
        )


@dataclass
class InterfaceStatus:
    """Runtime interface observations, distinct from configured LAN values."""

    is_up: Optional[bool]
    protocol: Optional[str]
    interface: Optional[str]
    ip_address: Optional[str]
    gateway: Optional[str]
    uptime_seconds: Optional[int]
    rx_bytes: Optional[int]
    tx_bytes: Optional[int]
    raw: Dict[str, Any] = field(repr=False, compare=False)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "InterfaceStatus":
        if not isinstance(data, dict):
            raise ValueError("Interface status must be an object")
        return cls(
            _boolean(data.get("is_up")),
            _text(data.get("proto")),
            _text(data.get("ifname")),
            _text(data.get("ipaddr")),
            _text(data.get("gwaddr")),
            _integer(data.get("uptime")),
            _integer(data.get("rx_bytes")),
            _integer(data.get("tx_bytes")),
            dict(data),
        )


@dataclass
class EthernetPort:
    """One port; byte counters are from the router port's perspective."""

    port: Optional[int]
    label: Optional[str]
    link_up: Optional[bool]
    speed_mbps: Optional[int]
    full_duplex: Optional[bool]
    auto_negotiation: Optional[bool]
    tx_bytes: Optional[int]
    rx_bytes: Optional[int]
    raw: Dict[str, Any] = field(repr=False, compare=False)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "EthernetPort":
        if not isinstance(data, dict):
            raise ValueError("Ethernet port must be an object")
        label = data.get("label")
        if label is not None and not isinstance(label, str):
            raise ValueError("Port label must be a string")
        return cls(
            port=_integer(data.get("port")),
            label=label,
            link_up=_boolean(data.get("link")),
            speed_mbps=_integer(data.get("speed")),
            full_duplex=_boolean(data.get("duplex")),
            auto_negotiation=_boolean(data.get("autoneg", data.get("auto"))),
            tx_bytes=_integer(data.get("txbyte")),
            rx_bytes=_integer(data.get("rxbyte")),
            raw=dict(data),
        )


@dataclass
class WirelessInterface:
    """A caller-selected wireless section. Credentials remain only in raw data.

    This is configuration, not evidence that a radio is currently transmitting.
    """

    section: str
    ssid: Optional[str]
    encryption: Optional[str]
    disabled: Optional[bool]
    hidden: Optional[bool]
    device: Optional[str]
    mode: Optional[str]
    raw: Dict[str, Any] = field(repr=False, compare=False)

    @classmethod
    def from_api_response(cls, section: str, data: Dict[str, Any]) -> "WirelessInterface":
        if not isinstance(section, str) or not section.strip():
            raise ValueError("Wireless section must be nonempty text")
        if not isinstance(data, dict):
            raise ValueError("Wireless interface must be an object")
        values = {}
        for key in ("ssid", "encryption", "device", "mode"):
            value = data.get(key)
            if value is not None and not isinstance(value, str):
                raise ValueError("Wireless text fields must be strings")
            values[key] = value
        return cls(
            section=section,
            disabled=_boolean(data.get("disabled")),
            hidden=_boolean(data.get("hidden")),
            raw=dict(data),
            **values,
        )


@dataclass
class LanConfig:
    """Configured LAN fields, not runtime link status. Missing fields stay unknown."""

    protocol: Optional[str]
    ip_address: Optional[str]
    netmask: Optional[str]
    gateway: Optional[str]
    interface: Optional[str]
    raw: Dict[str, Any] = field(repr=False, compare=False)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "LanConfig":
        if not isinstance(data, dict):
            raise ValueError("LAN configuration must be an object")
        values = []
        for key in ("proto", "ipaddr", "netmask", "gateway", "ifname"):
            value = data.get(key)
            if value is not None and not isinstance(value, str):
                raise ValueError("LAN configuration fields must be strings")
            values.append(value)
        return cls(values[0], values[1], values[2], values[3], values[4], raw=dict(data))


@dataclass
class RateLimit:
    """Configured per-client limits in Mbps, as displayed by the Cudy app."""

    download_mbps: Optional[Decimal]
    upload_mbps: Optional[Decimal]
    raw: Dict[str, Any] = field(repr=False, compare=False)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "RateLimit":
        if not isinstance(data, dict):
            raise ValueError("Rate limit must be an object")

        def rate(value):
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
                raise ValueError("Invalid rate limit")
            try:
                result = Decimal(str(value))
            except InvalidOperation:
                raise ValueError("Invalid rate limit") from None
            if not result.is_finite() or result < 0:
                raise ValueError("Invalid rate limit")
            return result

        return cls(rate(data.get("ddrate")), rate(data.get("uurate")), dict(data))
